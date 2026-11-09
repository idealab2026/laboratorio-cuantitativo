"""Native forward paper fills for existing monthly MIDAS campaigns.

Only IL-038 and IL-039 currently use the compatible next-open target-weight
settler. This module NEVER connects to a broker, backfills a missed opening,
or creates a second portfolio. It calls the campaign's own settlement math.
"""
from __future__ import annotations
import copy
import json
import math
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from operational_clock import _quote_valid, digest, timestamp, verify_lock

ROOT = Path(__file__).resolve().parents[1]
NATIVE = {
    "IL-038": ("capital_cycle_state/ledger.json", "capital_cycle/config.json", "capital_cycle"),
    "IL-039": ("buy_the_dip_state/ledger.json", "buy_the_dip_strategy/config.json", "buy_the_dip_strategy"),
}
MAX_DEVIATION_FROM_OPEN = timedelta(minutes=30)


def _read(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def _source_at(commit, path):
    value = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                           check=True, text=True, capture_output=True)
    return json.loads(value.stdout)


def _event_key(slot, session, signal_date):
    return f"{slot}:{signal_date}:{session}:forward_market_observed_v1"


def settle_native(lock, now, market, quotes, *,
                  read=_read, original=_source_at, snapshot=None):
    """Return (new ledgers, per-algorithm evidence). No filesystem mutation."""
    verify_lock(lock, market, now)
    output, results = {}, {}
    for slot, (ledger_path, config_path, module) in NATIVE.items():
        lane = lock["slots"][slot]
        if not lane["orders"]:
            results[slot] = {"status": "no_orders", "fills": 0}
            continue
        if not lane["execution_ready"] or lane["source_session"] != market["previous"]:
            results[slot] = {"status": "not_ready", "fills": 0}
            continue
        existing = read(ledger_path)
        frozen = original(lock["source_commit"], ledger_path)
        if not all(existing.get(k) == frozen.get(k) for k in
                   ("last_session", "pending", "cash", "positions", "events", "config_hash")):
            results[slot] = {"status": "source_changed", "fills": 0}
            continue
        pending = existing.get("pending")
        if not isinstance(pending, dict) or not isinstance(pending.get("target_weights"), dict):
            results[slot] = {"status": "no_pending", "fills": 0}
            continue
        signal_date, expected = pending.get("signal_date"), pending.get("expected_fill_session")
        key = _event_key(slot, market["session"], signal_date)
        if existing.get("forward_executions", {}).get(key):
            results[slot] = {"status": "already_settled", "fills": 0}
            continue
        if signal_date is None or not signal_date < market["session"] or expected != market["session"]:
            results[slot] = {"status": "wrong_target_session", "fills": 0}
            continue
        expected_tickers = set(existing["positions"]) | set(pending["target_weights"])
        proposed = {row["ticker"] for row in lane["orders"]}
        if proposed != set(pending["target_weights"]) | (set(existing["positions"]) - set(pending["target_weights"])):
            results[slot] = {"status": "frozen_signal_mismatch", "fills": 0}
            continue
        if not expected_tickers:
            results[slot] = {"status": "no_positions", "fills": 0}
            continue
        complete = {t: quotes[t] for t in expected_tickers
                    if t in quotes and _quote_valid(quotes[t], now, market)}
        missing = sorted(expected_tickers - complete.keys())
        if missing:
            results[slot] = {"status": "awaiting_fresh_quotes", "fills": 0, "missing": missing}
            continue
        # This is intentionally the first accepted contemporary minute quote.
        # It is NOT claimed to be the official 09:30 auction price.
        if any(datetime.fromisoformat(q["observed_at_utc"].replace("Z", "+00:00")) >
               market["open"] + MAX_DEVIATION_FROM_OPEN for q in complete.values()):
            results[slot] = {"status": "opening_window_missed", "fills": 0}
            continue
        config = read(config_path)
        if config.get("currency") != existing.get("currency") or not math.isfinite(existing["cash"]):
            results[slot] = {"status": "invalid_native_account", "fills": 0}
            continue
        if module == "capital_cycle":
            from capital_cycle.engine import _settle_pending
        else:
            from buy_the_dip_strategy.engine import _settle_pending
        updated = copy.deepcopy(existing)
        previous_events = len(updated.get("events", []))
        bars = {t: {"open": complete[t]["price"]} for t in expected_tickers}
        _settle_pending(updated, bars, market["session"], config["paper_policy"])
        new_events = updated["events"][previous_events:]
        if not any(event.get("type") == "rebalance_filled" for event in new_events):
            raise ValueError(f"{slot}: native engine did not acknowledge rebalance")
        fills = []
        for event in new_events:
            if event.get("type") != "fill":
                continue
            t = event["ticker"]
            event.update({
                "execution_mode": "forward_observed_paper",
                "quote_at_utc": complete[t]["quote_at_utc"],
                "observed_at_utc": complete[t]["observed_at_utc"],
                "source_commit": lock["source_commit"],
                "lock_sha256": lock["lock_sha256"],
                "idempotency_key": key + ":" + event["side"] + ":" + t,
            })
            fills.append({
                "ticker": t, "side": event["side"], "quantity": event["quantity"],
                "price": event["price"], "fee": event["fee"],
                "observed_at_utc": complete[t]["observed_at_utc"],
            })
        marker = {
            "session": market["session"], "signal_date": signal_date,
            "mode": "forward_observed_paper", "source_commit": lock["source_commit"],
            "lock_sha256": lock["lock_sha256"],
            "recorded_at_utc": timestamp(now),
            "quotes_sha256": digest(complete),
            "fills_count": len(fills), "fill_tickers": sorted({f["ticker"] for f in fills}),
        }
        updated.setdefault("forward_executions", {})[key] = marker
        # The last CLOSED NAV stays unchanged until the usual close mark;
        # only cash/positions are settled now, on the SAME authoritative book.
        if updated.get("pending") is not None:
            raise ValueError("Native pending orders were not cleared")
        results[slot] = {"status": "settled_native_paper", "fills": len(fills),
                         "marker": marker, "operations": fills}
        output[ledger_path] = updated
    return output, results
