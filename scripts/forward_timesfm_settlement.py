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


def _valid_quotes(quotes, symbols, now, market, mode):
    found = {t: quotes[t] for t in symbols
             if t in quotes and _quote_valid(quotes[t], now, market)}
    missing = sorted(set(symbols) - set(found))
    if missing:
        return None, missing
    cutoff = market["open"] + OPEN_WINDOW if mode == "open" else market["close"]
    left = market["open"] if mode == "open" else market["close"] - EXIT_WINDOW
    if any(not (left <= _date_time(q["quote_at_utc"]) <= cutoff)
           for q in found.values()):
        return None, ["outside_" + mode + "_window"]
    return found, []


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
                    quotes, expected, now, market, "open")
                if missing:
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
                    fx_entry, proof, book_name=name)
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
                if book != before and not same_day_open:
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
                    quotes, expected | {FX_TICKER}, now, market, "exit")
                if missing:
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
                proof = _proof(lock, key, actual)
                operations = observed_exit(
                    book, config["execution"], family, market["session"],
                    {t:row["price"] for t,row in actual.items()},
                    fx_exit, proof)
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
            updated.setdefault("forward_executions", {})[key] = marker
            changed = True
            evidence[slot] = {
                "status": "settled_native_paper", "fills": len(operations),
                "marker": marker, "operations": operations,
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
            key = event_key(slot, marker["session"], marker["mode"])
            if ledger.get("forward_executions", {}).get(key) != marker:
                raise ValueError("TimesFM canonical paper execution not persisted")
            verified.append(slot)
    return verified
