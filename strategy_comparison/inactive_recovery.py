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


def window(last, now):
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
    if len(days) > MAX_SESSIONS:
        raise ValueError("Outage exceeds bounded recovery; explicit review required")
    return closed[-1], future[0], days


def identity_check(identity):
    for key in ("snapshot_sha256", "effective_sha256"):
        value = identity.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Recovery requires immutable common quote identity")


def reconcile_classic(state, loader, *, now, reviews=None):
    from classic_sp500.corporate_actions import inactive_mark, required_claim_quotes
    updated = copy.deepcopy(state)
    names = []
    for name, original in state["books"].items():
        if not original.get("paused_missing_quotes"):
            continue
        last = original["equity"][-1]["date"]
        latest, first, days = window(last, now)
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


def recover(engine, *, root=ROOT, write=False, now=None):
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
        updated, names = reconcile_classic(original, loader, now=now,
            reviews=json.loads((root / "market_data/corporate_action_reviews.json").read_text()))
        validate_state(updated, config)
        books = "books"
    else:
        sys.path.insert(0, str(ROOT / "weekly_ml"))
        from weekly_ml.daily import _check_config
        config = json.loads((root / "weekly_ml/config.json").read_text())
        _check_config(original, config)
        updated, names = reconcile_weekly(original, loader, now=now)
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
    args = parser.parse_args()
    try:
        print(json.dumps(recover(args.engine, write=args.phase == "recover"), ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("Inactive recovery error: " + repr(exc))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
