"""Native forward entry fills for MIDAS IL-019..IL-027, one shared ML ledger.

A verified quote is a simulated execution price, NOT an exchange fill.
The nightly daily engine still owns official closing NAV and weekly exits.
All mutations are made to the existing weekly_ml_daily_state/ledger.json.
"""
from __future__ import annotations

import copy
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

from operational_clock import _quote_valid, digest, timestamp, verify_lock
from native_forward_settlement import _source_at

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "weekly_ml"))
from daily import _check_config, fill_pending_at_observed_open

LEDGER = "weekly_ml_daily_state/ledger.json"
CONFIG = "weekly_ml/config.json"
SLOTS = {
    "IL-019": "benchmark_spy",
    "IL-020": "benchmark_rsp",
    "IL-021": "lgbm_return",
    "IL-022": "lgbm_direction",
    "IL-023": "lgbm_ranker",
    "IL-024": "mlp_return",
    "IL-025": "lstm_return",
    "IL-026": "arima_return",
    "IL-027": "ensemble_consensus",
}
MAX_OPEN_LAG = timedelta(minutes=30)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def _key(slot, session, signal):
    return f"{slot}:{signal}:{session}:weekly_ml_forward_v1"


def _unchanged(original, current):
    return all(original.get(k) == current.get(k) for k in
               ("cash", "nav", "positions", "pending", "equity", "events",
                "last_signal_session"))


def settle_weekly(lock, now, market, quotes, *, reader=read, frozen=_source_at):
    """Compute fresh next-open buys and evidence, without mutating the filesystem."""
    verify_lock(lock, market, now)
    output = {}
    observations = {}
    source = frozen(lock["source_commit"], LEDGER)
    current = reader(LEDGER)
    config = reader(CONFIG)
    _check_config(current, config)
    _check_config(source, config)
    if (current["last_session"] != market["previous"] or
            source["last_session"] != market["previous"]):
        return {}, {s: {"status": "source_session_changed", "fills": 0} for s in SLOTS}
    changed = copy.deepcopy(current)
    for slot, name in SLOTS.items():
        lane = lock["slots"][slot]
        original = source["strategies"][name]
        book = changed["strategies"][name]
        signal = book.get("last_signal_session", current.get("last_signal_session"))
        key = _key(slot, market["session"], signal)
        previous_marker = book.get("forward_executions", {}).get(key)
        if previous_marker:
            if previous_marker.get("lock_sha256") != lock["lock_sha256"]:
                raise ValueError(f"{slot}: conflicting marker for prior opening")
            observations[slot] = {"status": "already_settled", "fills": previous_marker["fills_count"],
                                  "marker": previous_marker}
            continue
        if not lane["orders"]:
            observations[slot] = {"status": "no_orders", "fills": 0}
            continue
        if not lane["execution_ready"] or lane["source_session"] != market["previous"]:
            observations[slot] = {"status": "not_ready", "fills": 0}
            continue
        if (not _unchanged(original, book) or
                book["equity"][-1]["date"] != market["previous"] or
                signal != market["previous"] or
                book.get("paused_missing_quotes")):
            observations[slot] = {"status": "source_changed_or_stale", "fills": 0}
            continue
        pending = book.get("pending")
        if not isinstance(pending, list) or not pending:
            observations[slot] = {"status": "no_pending", "fills": 0}
            continue
        expected = {o.get("ticker") for o in pending}
        planned = {o["ticker"] for o in lane["orders"]}
        if (len(expected) != len(pending) or
                expected != planned or
                any(o.get("signal_date") != market["previous"] for o in pending) or
                any(o["action"] != "buy" or o["signal_session"] != signal
                    or o["target_session"] != market["session"] or
                    o["limit_price"] is not None for o in lane["orders"])):
            observations[slot] = {"status": "frozen_signal_mismatch", "fills": 0}
            continue
        fresh = {ticker: quotes[ticker] for ticker in expected
                 if ticker in quotes and _quote_valid(quotes[ticker], now, market)}
        missing = sorted(expected - fresh.keys())
        if missing:
            observations[slot] = {"status": "awaiting_fresh_quotes", "fills": 0,
                                  "missing": missing}
            continue
        if any(datetime.fromisoformat(q["observed_at_utc"].replace("Z", "+00:00")) >
               market["open"] + MAX_OPEN_LAG for q in fresh.values()):
            observations[slot] = {"status": "opening_window_missed", "fills": 0}
            continue
        if not math.isfinite(book["cash"]) or book["cash"] < 0:
            raise ValueError(f"{slot}: invalid available cash")
        prices = {ticker: {"open": row["price"]} for ticker, row in fresh.items()}
        meta = {ticker: {
            "quote_at_utc": row["quote_at_utc"],
            "observed_at_utc": row["observed_at_utc"],
            "source_commit": lock["source_commit"],
            "lock_sha256": lock["lock_sha256"],
            "idempotency_key": key + ":" + ticker,
        } for ticker, row in fresh.items()}
        # Uses the EXACT sizing/slippage/fee helper used by nightly ML accounting.
        fills = fill_pending_at_observed_open(
            name, book, market["session"], prices, config["paper_policy"],
            execution="forward_observed_paper", quote_metadata=meta)
        marker = {
            "session": market["session"], "signal_date": signal,
            "mode": "forward_observed_paper", "lock_sha256": lock["lock_sha256"],
            "source_commit": lock["source_commit"], "recorded_at_utc": timestamp(now),
            "quotes_sha256": digest(fresh), "fills_count": len(fills),
            "fill_tickers": sorted(e["ticker"] for e in fills),
        }
        book.setdefault("forward_executions", {})[key] = marker
        observations[slot] = {
            "status": "settled_native_paper", "fills": len(fills),
            "marker": marker, "operations": [{
                "ticker": e["ticker"], "side": "buy", "quantity": e["shares"],
                "price": e["price"], "fee": e["fee"],
                "observed_at_utc": e["observed_at_utc"],
            } for e in fills]}
    if any(item["status"] == "settled_native_paper" for item in observations.values()):
        changed["execution_model"] = "forward_observed_paper_open_from_2026-11-10"
        output[LEDGER] = changed
    return output, observations


def verify_published(path=ROOT / "data/operational-clock.json", *, remote=_source_at):
    report = json.loads(Path(path).read_text(encoding="utf8"))
    lanes = {slot: report.get("slots", {}).get(slot, {}) for slot in SLOTS}
    checked = []
    if not any(lane.get("status") == "native_forward_settled" for lane in lanes.values()):
        return checked
    ledger = remote("origin/main", LEDGER)
    for slot, lane in lanes.items():
        if lane.get("status") != "native_forward_settled":
            continue
        marker = lane.get("native_marker")
        if not isinstance(marker, dict):
            raise ValueError(f"{slot}: public ML fill has no marker")
        name = SLOTS[slot]
        key = _key(slot, marker["session"], marker["signal_date"])
        book = ledger["strategies"][name]
        if book.get("forward_executions", {}).get(key) != marker or book.get("pending"):
            raise ValueError(f"{slot}: published ML fill missing from native book")
        checked.append(slot)
    return checked
