"""Live-causal paper operator for IL-037; AHP native USD cash and positions.

No retroactive opening fills. A source-locked Friday decision opens the
following eligible XNYS session. A portfolio stop uses a prior exact-session
verified close and sells at the next observed open. Week-end sells require an
observed 15:55-16:00 ET quote and are marked "observed_preclose", not an
official closing auction price.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from operational_clock import _quote_valid, digest, timestamp, verify_lock
from native_forward_settlement import _source_at

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tfg_ahp"))
from tfg_ahp.forward import FIRST_SIGNAL, open_week, close_week
from tfg_ahp.data import is_week_end_session

SLOT = "IL-037"
LEDGER = "tfg_state/ledger.json"
CONFIG = "tfg_ahp/config.json"
OPEN_WINDOW = timedelta(minutes=30)
PRECLOSE_WINDOW = timedelta(minutes=5)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def marker_key(session, mode):
    return f"{SLOT}:{session}:{mode}:tfg_ahp_forward_v1"


def _fresh(quotes, symbols, now, market):
    valid = {t: quotes[t] for t in symbols
             if t in quotes and _quote_valid(quotes[t], now, market)}
    return valid, sorted(set(symbols) - set(valid))


def _evidence(lock, key, fresh):
    return {t: {"source_commit": lock["source_commit"],
                "lock_sha256": lock["lock_sha256"],
                "quote_at_utc": q["quote_at_utc"],
                "observed_at_utc": q["observed_at_utc"],
                "idempotency_key": key + ":" + t}
            for t, q in fresh.items()}


def settle_ahp(lock, now, market, quotes, *, reader=read, frozen=_source_at):
    verify_lock(lock, market, now)
    lane = lock["slots"][SLOT]
    if not lane["execution_ready"] or lane["source_session"] != market["previous"]:
        return {}, {SLOT: {"status": "not_ready", "fills": 0}}
    current = reader(LEDGER)
    source = frozen(lock["source_commit"], LEDGER)
    config = reader(CONFIG)
    if current.get("config_hash") != digest(config) or source.get("config_hash") != digest(config):
        raise ValueError("AHP wrong canonical config or origin")
    marker_map = current.get("forward_executions", {})
    book = current.get("forward_book")
    last_open = marker_map.get(marker_key(market["session"], "open"))
    last_stop = marker_map.get(marker_key(market["session"], "stop"))
    last_week_end = marker_map.get(marker_key(market["session"], "week_end"))
    marker = last_stop or last_week_end or last_open
    if marker:
        if marker.get("lock_sha256") != lock["lock_sha256"]:
            raise ValueError("AHP conflicting source lock")
        return {}, {SLOT: {"status": "already_settled", "fills": marker["fills_count"],
                           "marker": marker}}
    if now < market["open"] or now > market["close"]:
        return {}, {SLOT: {"status": "outside_session", "fills": 0}}
    in_open = now <= market["open"] + OPEN_WINDOW
    is_preclose = market["close"] - PRECLOSE_WINDOW <= now <= market["close"]
    mode = None
    if book is None:
        if not lane["orders"]:
            return {}, {SLOT: {"status": "no_orders", "fills": 0}}
        if not in_open:
            return {}, {SLOT: {"status": "opening_window_missed", "fills": 0}}
        if any(current.get(k) != source.get(k) for k in
               ("nav", "last_signal_session", "signal_hash", "pending_signal",
                "forward_book", "trades", "equity")):
            return {}, {SLOT: {"status": "source_changed", "fills": 0}}
        signal = current.get("pending_signal") or {}
        selected = signal.get("selections", [])
        signal_day = signal.get("asof")
        if (signal_day != market["previous"] or signal_day < FIRST_SIGNAL or
                current.get("last_signal_session") != signal_day or
                {x.get("ticker") for x in selected} != {o["ticker"] for o in lane["orders"]} or
                len(selected) != len(lane["orders"]) or
                any(o["action"] != "buy" or o["target_session"] != market["session"] or
                    o["signal_session"] != signal_day or o["limit_price"] is not None
                    for o in lane["orders"])):
            return {}, {SLOT: {"status": "frozen_signal_mismatch", "fills": 0}}
        symbols = sorted(x["ticker"] for x in selected)
        mode = "open"
    elif book.get("status") == "open":
        if (book.get("last_mark_session") != market["previous"] or
                book.get("unresolved_exit") or
                current.get("forward_book") != source.get("forward_book")):
            return {}, {SLOT: {"status": "source_changed_or_stale", "fills": 0}}
        if book.get("stop_due"):
            if not in_open:
                return {}, {SLOT: {"status": "stop_opening_window_missed", "fills": 0}}
            if (set(book["positions"]) != {o["ticker"] for o in lane["orders"]} or
                any(o["action"] != "sell" or o["signal_session"] != market["previous"]
                    for o in lane["orders"])):
                return {}, {SLOT: {"status": "frozen_stop_mismatch", "fills": 0}}
            mode = "stop"
        elif is_preclose and is_week_end_session(market["session"]):
            if lane["orders"]:
                return {}, {SLOT: {"status": "unexpected_preclose_orders", "fills": 0}}
            mode = "week_end"
        else:
            return {}, {SLOT: {"status": "no_current_execution_due", "fills": 0}}
        symbols = sorted(book["positions"])
    else:
        return {}, {SLOT: {"status": "closed_or_paused", "fills": 0}}

    fresh, missing = _fresh(quotes, symbols, now, market)
    if missing:
        return {}, {SLOT: {"status": "awaiting_fresh_quotes", "missing": missing,
                           "fills": 0}}
    # Fail-closed if any quote was received outside its dedicated execution
    # window; the operator must never book a 15:51 price as a 15:59 fill.
    if mode == "week_end":
        if any(datetime.fromisoformat(q["quote_at_utc"].replace("Z","+00:00")) <
               market["close"] - PRECLOSE_WINDOW for q in fresh.values()):
            return {}, {SLOT: {"status": "preclose_quote_stale", "fills": 0}}
    elif any(datetime.fromisoformat(q["quote_at_utc"].replace("Z","+00:00")) >
             market["open"] + OPEN_WINDOW for q in fresh.values()):
        return {}, {SLOT: {"status": "opening_quote_outside_window", "fills": 0}}

    key = marker_key(market["session"], mode)
    evidence = _evidence(lock, key, fresh)
    prices = {t: quote["price"] for t, quote in fresh.items()}
    if mode == "open":
        changed, fills = open_week(current, config, market["session"], prices, evidence,
                                   expected_signal=market["previous"])
    else:
        reason = ("portfolio_stop_next_open" if mode == "stop"
                  else "week_end_observed_preclose")
        changed, fills = close_week(current, config, market["session"], prices,
                                    evidence, reason)
    marker = {"session": market["session"], "mode": mode,
              "source_commit": lock["source_commit"],
              "lock_sha256": lock["lock_sha256"],
              "quotes_sha256": digest(fresh), "recorded_at_utc": timestamp(now),
              "fills_count": len(fills),
              "fill_tickers": sorted(row["ticker"] for row in fills)}
    changed.setdefault("forward_executions", {})[key] = marker
    return {LEDGER: changed}, {
        SLOT: {"status": "settled_native_paper", "fills": len(fills),
               "marker": marker, "operations": fills}
    }


def verify_published(report_path=ROOT / "data/operational-clock.json", *, remote=_source_at):
    report = json.loads(Path(report_path).read_text(encoding="utf8"))
    lane = report.get("slots", {}).get(SLOT, {})
    if lane.get("status") != "native_forward_settled":
        return []
    marker = lane.get("native_marker")
    if not isinstance(marker, dict):
        raise ValueError("AHP public fill missing marker")
    ledger = remote("origin/main", LEDGER)
    key = marker_key(marker["session"], marker["mode"])
    if ledger.get("forward_executions", {}).get(key) != marker:
        raise ValueError("AHP published paper fill missing in canonical book")
    return [SLOT]
