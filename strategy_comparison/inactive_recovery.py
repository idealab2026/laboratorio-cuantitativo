"""Restore missed paper marks without trades, preserving the existing campaign.

Only exact, closed XNYS sessions (at most four) may be appended. Orders that
missed their open expire; a partial current day cannot become a retroactive fill.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_SESSIONS = 4
GENETIC_NINE_SESSION_BOUND = 9  # Reviewed IL-012 outage 05–17 Nov 2026, never a general limit.
REVIEWED_PAUSED_WEEKLY = ("arima_return", "lgbm_ranker", "mlp_return")


def window(last, now, *, max_sessions=MAX_SESSIONS, reviewed_genetic_nine=False):
    import pandas_market_calendars as calendars
    if now.tzinfo is None:
        raise ValueError("Recovery clock must be timezone-aware")
    schedule = calendars.get_calendar("XNYS").schedule(
        start_date=last, end_date=(now + timedelta(days=12)).date())
    closed = [str(day.date()) for day, row in schedule.iterrows()
              if row["market_close"].to_pydatetime() + timedelta(minutes=90) <= now]
    future = [str(day.date()) for day, row in schedule.iterrows()
              if row["market_open"].to_pydatetime() > now]
    if not closed or closed[0] != last or not future:
        raise ValueError("Missing closed-session or future-opening boundary")
    days = closed[1:]
    if not (type(max_sessions) is int and
            (MAX_SESSIONS <= max_sessions <= 8 or
             reviewed_genetic_nine is True and max_sessions == GENETIC_NINE_SESSION_BOUND)):
        raise ValueError("Reviewed recovery window must be an integer from four to eight, "
                         "except the explicit genetic nine-session review")
    if len(days) > max_sessions:
        raise ValueError("Outage exceeds bounded recovery; explicit review required")
    return closed[-1], future[0], days


def identity_check(identity):
    for key in ("snapshot_sha256", "effective_sha256"):
        value = identity.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Recovery requires immutable common quote identity")


def reconcile_classic(state, loader, *, now, reviews=None, only_book=None,
                      reviewed_genetic_nine=False):
    """Optional exact-book scope prevents an unrelated claim from being mutated."""
    if only_book is not None and (not isinstance(only_book, str) or
                                 only_book not in state["books"]):
        raise ValueError("Unknown classic recovery book")

    if reviewed_genetic_nine and only_book != "genetic_frozen":
        raise ValueError("Nine-session recovery is authorized for genetic_frozen alone")
    from classic_sp500.corporate_actions import inactive_mark, required_claim_quotes
    updated = copy.deepcopy(state)
    names = []
    for name, original in state["books"].items():
        if only_book is not None and name != only_book:
            continue
        if not original.get("paused_missing_quotes"):
            continue
        last = original["equity"][-1]["date"]
        latest, first, days = window(last, now, max_sessions=(
            GENETIC_NINE_SESSION_BOUND if reviewed_genetic_nine else MAX_SESSIONS),
            reviewed_genetic_nine=reviewed_genetic_nine)
        if reviewed_genetic_nine and days != [
                "2026-11-05", "2026-11-06", "2026-11-09", "2026-11-10",
                "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16",
                "2026-11-17"]:
            raise ValueError("Reviewed genetic outage no longer matches 9 dated sessions")
        if latest != state["last_session"] or not days:
            raise ValueError("Classic recovery must reach the current global session")
        book = updated["books"][name]
        for day in days:
            bars, identity = loader(day, set(book["positions"]) | required_claim_quotes(book))
            identity_check(identity)
            inactive_mark(book, day, bars, recorded_at=now.isoformat(timespec="seconds"),
                          identity=identity, reviews=reviews)
        del book["paused_missing_quotes"]
        book["outage_control"] = {"first_trading_session": first,
                                  "registered_at_utc": now.isoformat(timespec="seconds")}
        names.append(name)
    return updated, names


def weekly_mark(book, day, bars, *, stamp, identity):
    from market_data.snapshot import normalize_bar
    marks = {}
    for ticker in book["positions"]:
        raw = bars.get(ticker)
        if not isinstance(raw, dict):
            raise ValueError("Missing exact weekly held quote: " + ticker)
        if raw.get("price_scope") == "passive_close_only":
            proof = (identity.get("passive_close_provenance") or {}).get(ticker)
            if (identity.get("closing_mark_scope") != "passive_nav_only"
                    or not isinstance(proof, dict) or raw.get("date") != day
                    or proof.get("session") != day or
                    proof.get("close") != raw.get("close")
                    or not isinstance(proof.get("document_sha256"), str)
                    or len(proof["document_sha256"]) != 64
                    or any(ch not in "0123456789abcdef" for ch in proof["document_sha256"])):
                raise ValueError("Unverified weekly passive close receipt")
            quote_stamp = datetime.fromisoformat(proof["captured_at_utc"])
            write_stamp = datetime.fromisoformat(stamp)
            if (quote_stamp.tzinfo is None or write_stamp.tzinfo is None or
                    quote_stamp.utcoffset() != timedelta(0) or quote_stamp > write_stamp):
                raise ValueError("Weekly passive mark is future-dated")
            if raw.get("split", 0) or raw.get("dividend", 0):
                raise ValueError("Weekly inactive corporate action needs separate review")
            close = float(raw["close"])
            if not math.isfinite(close) or close <= 0:
                raise ValueError("Invalid weekly passive closing price")
            marks[ticker] = close
        else:
            row = normalize_bar({**raw, "date": raw.get("date", day)}, day, ticker)
            # The weekly engine has no corporate-action entitlement accounting.
            if row["dividend"] or row["split"]:
                raise ValueError("Weekly inactive corporate action needs separate review")
            marks[ticker] = row["close"]
    nav = float(book["cash"]) + sum(float(pos["shares"]) * marks[t]
                                     for t, pos in book["positions"].items())
    if not math.isfinite(nav) or nav < 0:
        raise ValueError("Invalid inactive weekly NAV")
    expired = copy.deepcopy(book["pending"])
    book["pending"] = []
    book["nav"] = nav
    book["equity"].append({"date": day, "nav": nav, "decision_recorded": False,
        "inactive_no_fills": True, "recorded_at_utc": stamp, "quote_identity": identity})
    book["events"].append({"date": day, "type": "inactive_mark_no_trades",
        "expired_unfilled_orders": expired, "recorded_at_utc": stamp})


def reconcile_weekly(state, loader, *, now):
    if any(book["equity"][-1]["date"] != state["last_session"]
           for book in state["strategies"].values()):
        raise ValueError("Weekly ML has independently paused books; review each book before recovery")
    latest, first, days = window(state["last_session"], now)
    if not days:
        return copy.deepcopy(state), []
    result = copy.deepcopy(state)
    for day in days:
        required = {t for b in result["strategies"].values() for t in b["positions"]}
        bars, identity = loader(day, required)
        identity_check(identity)
        for book in result["strategies"].values():
            weekly_mark(book, day, bars, stamp=now.isoformat(timespec="seconds"), identity=identity)
    result["last_session"] = latest
    result["outage_control"] = {"first_trading_session": first,
                                "registered_at_utc": now.isoformat(timespec="seconds")}
    result["gap_sessions"] = sorted(set(result.get("gap_sessions", [])) | set(days))
    return result, sorted(result["strategies"])


def reconcile_weekly_paused(state, loader, *, now):
    """Recover only three audited stale ML portfolios as PAUSED mark-only books.

    Missed Fridays can hide compulsory sells. Those holdings must not
    participate in new forward opens merely because their NAV is current.
    """
    from tfg_ahp.data import is_week_end_session
    result = copy.deepcopy(state)
    updated = []
    for name in REVIEWED_PAUSED_WEEKLY:
        if name not in state["strategies"]:
            raise ValueError("Missing reviewed frozen weekly strategy")
        old = state["strategies"][name]
        pause = old.get("paused_missing_quotes", {})
        if pause.get("reason") == "unobserved_weekly_exit":
            continue
        if pause.get("reason") != "unreconciled_session":
            raise ValueError("Weekly selective recovery requires unreconciled pause")
        last = old["equity"][-1]["date"]
        latest, first, days = window(last, now, max_sessions=8)
        if latest != state["last_session"] or not days:
            raise ValueError("Weekly selective recovery must reach frozen global close")
        book = result["strategies"][name]
        missing_exit_sessions = []
        for day in days:
            bars, identity = loader(day, set(book["positions"]))
            identity_check(identity)
            weekly_mark(book, day, bars,
                        stamp=now.isoformat(timespec="seconds"), identity=identity)
            if is_week_end_session(day) and book["positions"]:
                missing_exit_sessions.append(day)
                book["events"].append({
                    "date": day, "type": "weekly_exit_unobserved_during_outage",
                    "held_tickers": sorted(book["positions"]),
                    "recorded_at_utc": now.isoformat(timespec="seconds")})
        if not missing_exit_sessions:
            raise ValueError("Reviewed weekly outage lacks omitted weekly exit")
        book["paused_missing_quotes"] = {
            "date": latest, "reason": "unobserved_weekly_exit",
            "missing_tickers": [],
            "missed_exit_sessions": missing_exit_sessions}
        book["outage_control"] = {
            "first_trading_session": first,
            "held_exits_require_future_observed_quote": True,
            "historical_fills_created": 0}
        updated.append(name)
    return result, updated


def recover(engine, *, root=ROOT, write=False, now=None, only_book=None,
            only_paused_weekly=False, reviewed_genetic_nine=False):
    if engine != "classic" and only_book is not None:
        raise ValueError("Selective recovery is only supported for classic books")
    if engine != "weekly" and only_paused_weekly:
        raise ValueError("Reviewed paused weekly recovery requires weekly engine")
    if reviewed_genetic_nine and not (engine == "classic" and only_book == "genetic_frozen"):
        raise ValueError("Nine-session outage recovery requires the exact IL-012 book")

    from market_data.revisions import load_effective
    from timesfm_strategy.run import atomic_write
    root, now = Path(root), now or datetime.now(timezone.utc)
    relative = "classic_sp500_state/ledger.json" if engine == "classic" else "weekly_ml_daily_state/ledger.json"
    path = root / relative
    original = json.loads(path.read_text())
    evidence = {}
    def loader(day, required):
        effective = load_effective(root / "market_data/snapshots", day)
        if datetime.fromisoformat(effective["last_captured_at_utc"]) > now:
            raise ValueError("Common capture is from the future")
        bars = copy.deepcopy(effective["bars"])
        identity = {"snapshot_sha256": effective["base"]["sha256"],
                    "effective_sha256": effective["effective_sha256"]}
        if engine == "classic" or only_paused_weekly:
            # Additional close-only observations are never merged into canonical
            # OHLC and never authorize an intraday stop or a missed opening.
            from market_data.close_marks import load_marks, directory
            passive, hashes, _ = load_marks(root / "market_data/snapshots", day)
            proven = {}
            for doc_hash in hashes:
                doc = json.loads((directory(root / "market_data/snapshots", day) /
                                  (doc_hash + ".json")).read_text())
                captured = datetime.fromisoformat(doc["captured_at_utc"])
                if captured.tzinfo is None or captured > now:
                    raise ValueError("Passive mark capture is future-dated")
                for ticker, row in doc["marks"].items():
                    if ticker in required and ticker not in bars:
                        proven[ticker] = {
                            "document_sha256": doc_hash, "session": day,
                            "close": row["close"], "captured_at_utc": doc["captured_at_utc"]}
                        bars[ticker] = row
            if proven:
                identity["closing_mark_scope"] = "passive_nav_only"
                identity["passive_close_provenance"] = proven
        independent = set(required) - set(effective["base"]["requested_symbols"])
        if independent:
            if engine != "weekly" or independent != {"RSP"}:
                raise ValueError("Unreviewed independent product")
            from market_data.collect import collect
            found, _failures = collect(day, ["RSP"], include_benchmark=False)
            if set(found) != {"RSP"}:
                raise ValueError("Missing exact independent RSP quote")
            # Preserve the exact independent observation and capture time in the
            # new NAV provenance, rather than pretending it was in common OHLC.
            identity["independent_observations"] = found
            identity["independent_captured_at_utc"] = now.isoformat(timespec="seconds")
            identity["independent_sha256"] = hashlib.sha256(json.dumps(
                found, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            bars.update(found)
        if not set(required) <= set(bars):
            raise ValueError("Missing genuine held quotes: " + ",".join(sorted(set(required) - set(bars))))
        evidence[day] = identity
        return bars, identity
    if engine == "classic":
        from classic_sp500.run import validate_state, verify_config
        config = json.loads((root / "classic_sp500/config.json").read_text())
        verify_config(config)
        validate_state(original, config)
        updated, names = reconcile_classic(original, loader, now=now, only_book=only_book,
            reviewed_genetic_nine=reviewed_genetic_nine,
            reviews=json.loads((root / "market_data/corporate_action_reviews.json").read_text()))
        validate_state(updated, config)
        books = "books"
    else:
        sys.path.insert(0, str(ROOT / "weekly_ml"))
        from weekly_ml.daily import _check_config
        config = json.loads((root / "weekly_ml/config.json").read_text())
        _check_config(original, config)
        updated, names = (reconcile_weekly_paused(original, loader, now=now)
                          if only_paused_weekly else
                          reconcile_weekly(original, loader, now=now))
        _check_config(updated, config)
        books = "strategies"
    for name, old in original[books].items():
        new = updated[books][name]
        if (new["trades"] != old["trades"] or
                new["equity"][:len(old["equity"])] != old["equity"] or
                set(new["positions"]) != set(old["positions"])):
            raise ValueError("Recovery changed prior fills, NAV or holding identities")
        for ticker, position in old["positions"].items():
            if position["shares"] != new["positions"][ticker]["shares"]:
                raise ValueError("Recovery changed held quantities")
        if engine == "weekly" and (new["cash"] != old["cash"] or new["positions"] != old["positions"]):
            raise ValueError("Recovery changed weekly cash or cost basis")
        if name not in names and new != old:
            raise ValueError("Recovery changed an unaffected portfolio")
    if write and names:
        atomic_write(path, updated)
    return {"status": "inactive_marks_reconciled" if names else "already_reconciled",
            "engine": engine, "recovered_books": names, "written": bool(write and names),
            "last_session": updated["last_session"], "trades_unchanged": True,
            "quote_sources": evidence,
            "first_trading_session": min((updated[books][n].get("outage_control", updated.get("outage_control", {}))["first_trading_session"] for n in names), default=None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("classic", "weekly"), required=True)
    parser.add_argument("--phase", choices=("check", "recover"), default="check")
    parser.add_argument("--only-classic-book", default=None,
                        help="Recover exactly one paused classic book; untouched peers are invariant")
    parser.add_argument("--only-paused-weekly", action="store_true",
                        help="Audit only three reviewed stale ML books; preserve missed weekly exits")
    parser.add_argument("--reviewed-genetic-nine", action="store_true",
                        help="Audit the exact IL-012 05–17 November 2026 outage; NAV only, no fills")
    args = parser.parse_args()
    try:
        print(json.dumps(recover(args.engine, write=args.phase == "recover",
                                 only_book=args.only_classic_book,
                                 only_paused_weekly=args.only_paused_weekly,
                                 reviewed_genetic_nine=args.reviewed_genetic_nine),
                         ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("Inactive recovery error: " + repr(exc))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
