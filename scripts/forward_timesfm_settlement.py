"""Prospective TimesFM EUR execution for four MIDAS slots and two original books.

Each opening consumes a hash-locked previous-session FX reference captured
before opening; exits use contemporary USD equity and EURUSD=X observations.
No broker fills, no after-the-fact OHLC cash flows, no EUR ledger mirror.
"""
from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from operational_clock import _quote_valid, digest, timestamp, verify_lock
from native_forward_settlement import _source_at
from timesfm_strategy import run as weekly_engine
from timesfm_strategy import daily_run as daily_engine
from timesfm_strategy.forward_execution import observed_open, observed_exit

ROOT = Path(__file__).resolve().parents[1]
FX_TICKER = "EURUSD=X"
OPEN_WINDOW = timedelta(minutes=30)
EXIT_WINDOW = timedelta(minutes=5)
COHORTS = {
    "weekly": ("timesfm_state/ledger.json", "timesfm_strategy/config.json",
               {"IL-040": "timesfm", "IL-041": "benchmark_spy"}),
    "daily": ("timesfm_daily_state/ledger.json", "timesfm_strategy/config-daily.json",
              {"IL-042": "timesfm_daily", "IL-043": "benchmark_spy"}),
}


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def event_key(slot, day, action):
    return f"{slot}:{day}:{action}:timesfm_eur_forward_v1"


def _date_time(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _past_fx(lock, previous):
    fx = lock.get("fx_reference")
    if not isinstance(fx, dict):
        return None
    if (fx.get("pair") != FX_TICKER or
            fx.get("source") != "yfinance_unadjusted_daily_close" or
            fx.get("source_session") != previous or
            fx.get("purpose") != "paper_previous_XNYS_session_FX_proxy" or
            _date_time(fx["captured_at_utc"]) >= _date_time(lock["open_at_utc"])):
        return None
    value = fx.get("rate_usd_per_eur")
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        return None
    return float(value)


def _preclose(now, market):
    return market["close"] - EXIT_WINDOW <= now <= market["close"]


def _weekly_last_day(day):
    from tfg_ahp.data import is_week_end_session
    return is_week_end_session(day)


def _valid_quotes(quotes, symbols, now, market, mode, *, partial=False):
    found = {t: quotes[t] for t in symbols
             if t in quotes and _quote_valid(quotes[t], now, market)}
    missing = sorted(set(symbols) - set(found))
    if missing and (not partial or not found):
        return None, missing
    cutoff = market["open"] + OPEN_WINDOW if mode == "open" else market["close"]
    left = market["open"] if mode == "open" else market["close"] - EXIT_WINDOW
    if any(not (left <= _date_time(q["quote_at_utc"]) <= cutoff)
           for q in found.values()):
        return None, ["outside_" + mode + "_window"]
    return found, missing


def _proof(lock, key, found, *, fx_reference=None):
    return {t: {
        "source_commit": lock["source_commit"],
        "lock_sha256": lock["lock_sha256"],
        "observed_at_utc": row["observed_at_utc"],
        "quote_at_utc": row["quote_at_utc"],
        "idempotency_key": key + ":" + t,
        **({"fx_entry_reference_sha256": digest(fx_reference)}
           if fx_reference is not None else {}),
    } for t, row in found.items()}


def verified_weekly_exit_fills(lock, market, original, current, policy):
    """Reconcile *all* independently observed IL-040 sales against the frozen book.

    A later same-session poll may sell another ticker, but cannot change
    historical holdings, reinterpret its cost, replay fills or alter NAV.
    Return canonical session fills only when every received sell has a
    per-ticker immutable marker and its original position has disappeared.
    """
    slot = "IL-040"
    before = original["books"]["timesfm"]
    book = current["books"]["timesfm"]
    if book == before:
        return []
    if (original["last_session"] != current["last_session"] or
            original.get("equity") != current.get("equity") or
            not isinstance(book.get("positions"), dict) or
            not isinstance(before.get("positions"), dict)):
        raise ValueError("TimesFM weekly partial exit origin or portfolio changed")
    permitted_changes = {"cash", "positions", "trades", "events"}
    if any(before.get(k) != book.get(k)
           for k in set(before) | set(book) if k not in permitted_changes):
        raise ValueError("TimesFM weekly partial exit changed independent accounting")
    for key in ("trades", "events"):
        old = before.get(key, [])
        new = book.get(key, [])
        if not isinstance(old, list) or not isinstance(new, list) or new[:len(old)] != old:
            raise ValueError("TimesFM weekly partial exit rewrote the historical book")
    previous_positions = before["positions"]
    remaining_positions = book["positions"]
    if (not set(remaining_positions) <= set(previous_positions) or
            any(remaining_positions[t] != previous_positions[t]
                for t in remaining_positions)):
        raise ValueError("TimesFM weekly partial exit changed held shares")
    closed = set(previous_positions) - set(remaining_positions)
    new_trades = book["trades"][len(before["trades"]):]
    new_events = book["events"][len(before["events"]):]
    if not closed or len(new_trades) != len(closed) or len(new_events) != len(closed):
        raise ValueError("TimesFM weekly exit has unaccounted cash or trades")
    trade_by = {row.get("ticker"): row for row in new_trades}
    event_by = {row.get("ticker"): row for row in new_events}
    if (set(trade_by) != closed or set(event_by) != closed or
            len(trade_by) != len(new_trades) or len(event_by) != len(new_events)):
        raise ValueError("TimesFM weekly partial sale identity mismatch")
    base = event_key(slot, market["session"], "exit_symbol") + ":"
    marks = current.get("forward_executions", {})
    old_marks = original.get("forward_executions", {})
    if any(marks.get(k) != value for k, value in old_marks.items()):
        raise ValueError("TimesFM original execution marker overwritten")
    commission = float(policy["commission"])
    if not 0 <= commission < 1 or not math.isfinite(commission):
        raise ValueError("TimesFM invalid commission")
    cash = float(before["cash"])
    fills = []
    for ticker in sorted(closed):
        row, event, position = trade_by[ticker], event_by[ticker], previous_positions[ticker]
        marker = marks.get(base + ticker)
        if (not isinstance(marker, dict) or
                marker.get("mode") != "exit_symbol" or marker.get("ticker") != ticker or
                marker.get("family") != "weekly" or
                marker.get("session") != market["session"] or
                marker.get("source_commit") != lock["source_commit"] or
                marker.get("lock_sha256") != lock["lock_sha256"] or
                marker.get("fill_tickers") != [ticker] or marker.get("fills_count") != 1 or
                event.get("date") != market["session"] or
                event.get("event") != "sell" or
                event.get("execution") != "forward_observed_preclose" or
                event.get("idempotency_key") != base + ticker or
                event.get("source_commit") != lock["source_commit"] or
                event.get("lock_sha256") != lock["lock_sha256"] or
                row.get("execution") != "forward_observed_preclose" or
                row.get("exit_date") != market["session"] or
                row.get("entry_date") != position["entry_date"] or
                row.get("signal_date") != position["signal_date"]):
            raise ValueError("TimesFM weekly sale does not match locked evidence")
        try:
            when, received = _date_time(event["quote_at_utc"]), _date_time(event["observed_at_utc"])
            fx_when = _date_time(marker["exit_fx_quote_at_utc"])
            fx = float(marker["exit_fx_usd_per_eur"])
            price, shares = float(event["price_eur"]), float(position["shares"])
            proceeds = shares * price * (1 - commission)
            if (not (market["close"] - EXIT_WINDOW <= when <= received <= market["close"])
                    or not (market["close"] - EXIT_WINDOW <= fx_when <= received)
                    or not all(math.isfinite(v) and v > 0 for v in (fx, price, shares))
                    or not math.isclose(float(row["shares_at_exit"]), shares, rel_tol=1e-12)
                    or not math.isclose(float(row["sell_proceeds_eur"]), proceeds, rel_tol=1e-10, abs_tol=1e-6)
                    or not math.isclose(float(row["buy_cost_eur"]), float(position["cost_eur"]), rel_tol=1e-12)
                    or not math.isclose(float(row["dividends_eur"]), float(position["dividends_eur"]), rel_tol=1e-12)
                    or not math.isclose(float(row["net_pnl_eur"]), proceeds +
                                        float(position["dividends_eur"]) - float(position["cost_eur"]),
                                        rel_tol=1e-10, abs_tol=1e-6)
                    or not math.isclose(float(row["fx_usd_per_eur"]), fx, rel_tol=1e-12)):
                raise ValueError("TimesFM weekly sale economic or timestamp mismatch")
            cash += proceeds
            fills.append({"ticker": ticker, "side": "sell", "quantity": shares,
                          "price": price, "fee": shares * price * commission,
                          "currency": "EUR", "fx_usd_per_eur": fx,
                          "observed_at_utc": event["observed_at_utc"]})
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("TimesFM invalid weekly sale evidence") from exc
    if not math.isclose(float(book["cash"]), cash, rel_tol=1e-10, abs_tol=1e-6):
        raise ValueError("TimesFM weekly partial exit cash mismatch")
    finished = marks.get(event_key(slot, market["session"], "exit"))
    if finished is not None:
        if (remaining_positions or finished.get("mode") != "exit" or
                finished.get("lock_sha256") != lock["lock_sha256"] or
                finished.get("source_commit") != lock["source_commit"] or
                finished.get("fills_count") != len(closed) or
                finished.get("fill_tickers") != sorted(closed)):
            raise ValueError("TimesFM full exit marker without completed settlement")
    return sorted(fills, key=lambda row: (row["observed_at_utc"], row["ticker"]))


def settle_timesfm(lock, now, market, quotes, *, reader=read, frozen=_source_at):
    verify_lock(lock, market, now)
    results, evidence = {}, {}
    is_exit_time = _preclose(now, market)
    for family, (state_path, config_path, slots) in COHORTS.items():
        current = reader(state_path)
        source = frozen(lock["source_commit"], state_path)
        config = reader(config_path)
        if family == "weekly":
            weekly_engine._check(current, config)
            weekly_engine._check(source, config)
        else:
            daily_engine.check(current, config)
            daily_engine.check(source, config)
        if (source["last_session"] != market["previous"] or
                current["last_session"] != market["previous"]):
            evidence.update({slot: {"status": "source_session_changed", "fills": 0}
                             for slot in slots})
            continue
        updated = copy.deepcopy(current)
        changed = False
        for slot, name in slots.items():
            lane = lock["slots"][slot]
            book = updated["books"][name]
            before = source["books"][name]
            marker_map = updated.get("forward_executions", {})
            if (not lane["execution_ready"] or
                    lane["source_session"] != market["previous"]):
                evidence[slot] = {"status": "not_ready", "fills": 0}
                continue
            if (book["equity"][-1]["date"] != market["previous"] or
                    before["equity"][-1]["date"] != market["previous"]):
                evidence[slot] = {"status": "book_stale", "fills": 0}
                continue
            # An exit previously observed in this closing window must always
            # retain precedence over the day's earlier buy marker.
            exit_done = marker_map.get(event_key(slot, market["session"], "exit"))
            if is_exit_time and exit_done is not None:
                if exit_done["lock_sha256"] != lock["lock_sha256"]:
                    raise ValueError(f"{slot}: conflicting settled exit lock")
                evidence[slot] = {"status": "already_settled",
                                  "fills": exit_done["fills_count"],
                                  "marker": exit_done}
                continue
            if name == "benchmark_spy":
                mode = "open" if lane["orders"] else None
            elif is_exit_time and book["positions"] and (
                    family == "daily" or _weekly_last_day(market["session"])):
                mode = "exit"
            else:
                mode = "open" if lane["orders"] else None

            if mode is None:
                evidence[slot] = {"status": "no_execution_due", "fills": 0}
                continue
            key = event_key(slot, market["session"], mode)
            past_marker = marker_map.get(key)
            if past_marker:
                if past_marker.get("lock_sha256") != lock["lock_sha256"]:
                    raise ValueError(f"{slot}: conflicting same-session paper evidence")
                evidence[slot] = {
                    "status": "already_settled", "fills": past_marker["fills_count"],
                    "marker": past_marker,
                }
                continue
            if mode == "open":
                if now > market["open"] + OPEN_WINDOW:
                    evidence[slot] = {"status": "opening_window_missed", "fills": 0}
                    continue
                if book != before:
                    evidence[slot] = {"status": "source_changed", "fills": 0}
                    continue
                pending = book.get("pending")
                expected = {x["ticker"] for x in pending or []}
                planned = {x["ticker"] for x in lane["orders"]}
                if (not pending or len(expected) != len(pending)
                        or expected != planned or
                        any(x["signal_date"] != market["previous"] for x in pending) or
                        any(x["action"] != "buy" or
                            x["signal_session"] != market["previous"] or
                            x["target_session"] != market["session"] or
                            x.get("limit_price") is not None
                            for x in lane["orders"])):
                    evidence[slot] = {"status": "frozen_orders_mismatch", "fills": 0}
                    continue
                fx_entry = _past_fx(lock, market["previous"])
                if fx_entry is None:
                    evidence[slot] = {"status": "preopen_fx_missing", "fills": 0}
                    continue
                found, missing = _valid_quotes(
                    quotes, expected, now, market, "open", partial=True)
                if found is None:
                    evidence[slot] = {
                        "status": "awaiting_fresh_open_quotes", "fills": 0,
                        "missing": missing,
                    }
                    continue
                proof = _proof(lock, key, found,
                               fx_reference=lock["fx_reference"])
                operations = observed_open(
                    book, config["execution"], family, market["session"],
                    market["previous"], {t: row["price"] for t, row in found.items()},
                    fx_entry, proof, book_name=name,
                    allow_missing_observed=bool(missing))
                verified = found
                fx_note = {"entry_fx_usd_per_eur": fx_entry,
                           "fx_reference_sha256": digest(lock["fx_reference"])}
            else:
                if not is_exit_time or name == "benchmark_spy":
                    evidence[slot] = {"status": "outside_exit_window", "fills": 0}
                    continue
                # Source book may have changed through a recorded same-day
                # opening, but no unverified or stale mutation is accepted.
                same_day_open = marker_map.get(event_key(slot, market["session"], "open"))
                # A prior same-session IL-040 partial sale is legitimate only
                # if every removed share, cash change, receipt and immutable
                # per-symbol marker reconcile exactly to the frozen source.
                verified_prior = []
                if family == "weekly" and book != before:
                    try:
                        verified_prior = verified_weekly_exit_fills(
                            lock, market, source, current, config["execution"])
                    except ValueError:
                        evidence[slot] = {"status": "source_changed", "fills": 0}
                        continue
                if book != before and not same_day_open and not verified_prior:
                    evidence[slot] = {"status": "source_changed", "fills": 0}
                    continue
                if (same_day_open is not None and
                        same_day_open.get("lock_sha256") != lock["lock_sha256"]):
                    raise ValueError(f"{slot}: exit has conflicting opening lock")
                expected = set(book["positions"])
                if book["pending"] or not expected:
                    evidence[slot] = {"status": "open_book_missing_or_pending", "fills": 0}
                    continue
                found, missing = _valid_quotes(
                    quotes, expected | {FX_TICKER}, now, market, "exit",
                    partial=family == "weekly")
                if (found is None or FX_TICKER not in found or
                        not (set(found) - {FX_TICKER})):
                    evidence[slot] = {
                        "status": "awaiting_contemporaneous_exit_fx_and_quotes",
                        "fills": 0, "missing": missing,
                    }
                    continue
                fx_exit = float(found[FX_TICKER]["price"])
                if not math.isfinite(fx_exit) or fx_exit <= 0:
                    evidence[slot] = {"status": "invalid_exit_fx", "fills": 0}
                    continue
                actual = {t: row for t,row in found.items() if t != FX_TICKER}
                proof = _proof(
                    lock, event_key(slot, market["session"], "exit_symbol")
                    if family == "weekly" else key, actual)
                operations = observed_exit(
                    book, config["execution"], family, market["session"],
                    {t:row["price"] for t,row in actual.items()},
                    fx_exit, proof, allow_partial_observed=family == "weekly")
                verified = found
                fx_note = {
                    "exit_fx_usd_per_eur": fx_exit,
                    "exit_fx_quote_at_utc": found[FX_TICKER]["quote_at_utc"],
                }
            marker = {
                "session": market["session"], "mode": mode, "family": family,
                "lock_sha256": lock["lock_sha256"],
                "source_commit": lock["source_commit"],
                "recorded_at_utc": timestamp(now),
                "quotes_sha256": digest(verified),
                "fills_count": len(operations),
                "fill_tickers": sorted(x["ticker"] for x in operations),
                **fx_note,
            }
            markers = updated.setdefault("forward_executions", {})
            weekly_progress = None
            if mode == "exit" and family == "weekly":
                # One stable marker per symbol ensures a second observation
                # cannot overwrite or sell any previously liquidated shares.
                parent = event_key(slot, market["session"], "exit_symbol")
                for row in operations:
                    ticker = row["ticker"]
                    symbol_key = parent + ":" + ticker
                    if symbol_key in markers:
                        raise ValueError("Duplicate TimesFM weekly exit marker")
                    markers[symbol_key] = {
                        **marker, "mode": "exit_symbol", "ticker": ticker,
                        "fills_count": 1, "fill_tickers": [ticker],
                        "quotes_sha256": digest({
                            ticker: verified[ticker], FX_TICKER: verified[FX_TICKER]}),
                        "exit_fx_observed_at_utc": verified[FX_TICKER]["observed_at_utc"],
                    }
                session_fills = verified_weekly_exit_fills(
                    lock, market, source, updated, config["execution"])
                weekly_progress = {
                    "closed_tickers": sorted(x["ticker"] for x in session_fills),
                    "remaining_tickers": sorted(book["positions"]),
                    "complete": not bool(book["positions"]),
                    "source": "observed_preclose_eur_symbol_isolated"}
                if book["positions"]:
                    marker = markers[parent + ":" + operations[-1]["ticker"]]
                else:
                    marker = {**marker,
                        "fills_count": len(session_fills),
                        "fill_tickers": sorted(x["ticker"] for x in session_fills),
                        "observed_sale_evidence_sha256": digest([
                            x for x in book["events"]
                            if x.get("date") == market["session"] and
                            x.get("execution") == "forward_observed_preclose" and
                            x.get("idempotency_key", "").startswith(parent + ":")])}
                    markers[key] = marker
            else:
                markers[key] = marker
            changed = True
            evidence[slot] = {
                "status": "settled_native_paper", "fills": len(operations),
                "marker": marker, "operations": operations,
                **({"unfilled_open_quotes": missing, "sizing_reference": "frozen_order_budget"}
                   if mode == "open" and missing else {}),
                **({"weekly_exit_progress": weekly_progress} if weekly_progress else {}),
            }
        if changed:
            results[state_path] = updated
    return results, evidence


def verify_published(path=ROOT / "data/operational-clock.json", *, remote=_source_at):
    doc = json.loads(Path(path).read_text(encoding="utf8"))
    slots = doc.get("slots", {})
    verified = []
    for family,(state_path,_config,mapping) in COHORTS.items():
        expected = {slot: slots.get(slot,{}) for slot in mapping
                    if slots.get(slot,{}).get("status") == "native_forward_settled"}
        if not expected:
            continue
        ledger = remote("origin/main", state_path)
        for slot,lane in expected.items():
            marker = lane.get("native_marker")
            if not isinstance(marker, dict):
                raise ValueError("TimesFM public settlement has no marker")
            key = (event_key(slot, marker["session"], "exit_symbol") + ":" + marker["ticker"]
                   if marker.get("mode") == "exit_symbol" else
                   event_key(slot, marker["session"], marker["mode"]))
            if ledger.get("forward_executions", {}).get(key) != marker:
                raise ValueError("TimesFM canonical paper execution not persisted")
            verified.append(slot)
    return verified
