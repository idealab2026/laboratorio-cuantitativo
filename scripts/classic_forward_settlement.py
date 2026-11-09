"""Prospective paper opening and observed stop/target events for IL-010..018.

Executes only in the existing classic_sp500_state/ledger.json and never uses a
completed daily OHLC bar to imply an intraday fill. A quote is a paper price
proxy, not proof that a real market order could have been filled.
"""
from __future__ import annotations
import copy
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from operational_clock import _quote_valid, digest, timestamp, verify_lock
from native_forward_settlement import _source_at

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "classic_sp500_state/ledger.json"
CONFIG = "classic_sp500/config.json"
SLOTS = {
    "IL-010": "buy_hold_equal_weight",
    "IL-011": "ema_rsi_fixed",
    "IL-012": "genetic_frozen",
    "IL-013": "macd_12_26_9",
    "IL-014": "rsi_reversion_14",
    "IL-015": "bollinger_breakout_20",
    "IL-016": "turtle_20_10_long",
    "IL-017": "turtle_55_20_long",
    "IL-018": "benchmark_spy",
}
OPEN_WINDOW = timedelta(minutes=30)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def event_key(slot, session, action):
    return f"{slot}:{session}:{action}:classic_forward_v1"


def _source_unchanged(frozen, current):
    return all(frozen.get(k) == current.get(k) for k in
               ("cash", "positions", "pending", "trades", "events", "equity", "nav"))


def _provenance(q, lock, ticker, key):
    return {"quote_at_utc": q["quote_at_utc"],
            "observed_at_utc": q["observed_at_utc"],
            "source_commit": lock["source_commit"],
            "lock_sha256": lock["lock_sha256"],
            "idempotency_key": key + ":" + ticker}


def settle_classic(lock, now, market, quotes, *, reader=read, frozen=_source_at):
    verify_lock(lock, market, now)
    from classic_sp500.run import (validate_state, execute_frozen_open, _close_position)
    config = reader(CONFIG)
    before = reader(LEDGER)
    source = frozen(lock["source_commit"], LEDGER)
    validate_state(before, config)
    validate_state(source, config)
    updated = copy.deepcopy(before)
    evidence = {}
    if before["last_session"] != market["previous"] or source["last_session"] != market["previous"]:
        return {}, {slot: {"status": "source_session_changed", "fills": 0} for slot in SLOTS}
    any_changes = False
    for slot, name in SLOTS.items():
        lane = lock["slots"][slot]
        book = updated["books"][name]
        original = source["books"][name]
        if not lane["execution_ready"] or lane["source_session"] != market["previous"]:
            evidence[slot] = {"status": "not_ready", "fills": 0}
            continue
        if book["equity"][-1]["date"] != market["previous"] or book.get("paused_missing_quotes"):
            evidence[slot] = {"status": "paused_or_stale_book", "fills": 0}
            continue
        if book.get("receivables") or book.get("outage_control"):
            # Corporate action claims cannot be silently repriced as ordinary orders.
            evidence[slot] = {"status": "corporate_action_review_required", "fills": 0}
            continue
        markers = book.setdefault("forward_executions", {})
        if not markers and not _source_unchanged(original, book):
            evidence[slot] = {"status": "source_changed", "fills": 0}
            book.pop("forward_executions", None)
            continue
        if markers and not all(m.get("lock_sha256") == lock["lock_sha256"]
                               for k, m in markers.items() if
                               m.get("session") == market["session"]):
            raise ValueError(f"{slot}: conflicting session lock")
        operations = []
        markers_written = []
        if lane["orders"]:
            key = event_key(slot, market["session"], "open")
            marker = markers.get(key)
            if marker:
                if marker["lock_sha256"] != lock["lock_sha256"]:
                    raise ValueError(f"{slot}: opening marker conflict")
                evidence[slot] = {"status": "already_settled", "fills": marker["fills_count"],
                                  "marker": marker}
            elif not _source_unchanged(original, book):
                evidence[slot] = {"status": "source_changed", "fills": 0}
                continue
            elif not (isinstance(book["pending"], dict) and
                      len(book["pending"]) == len(lane["orders"]) and
                      set(book["pending"]) == {o["ticker"] for o in lane["orders"]} and
                      all(book["pending"][o["ticker"]].get("side") == o["action"] and
                          book["pending"][o["ticker"]].get("signal_date") == market["previous"] and
                          o["signal_session"] == market["previous"] and
                          o["target_session"] == market["session"] and
                          o.get("limit_price") is None
                          for o in lane["orders"])):
                evidence[slot] = {"status": "frozen_order_mismatch", "fills": 0}
                continue
            else:
                required = set(book["positions"]) | set(book["pending"])
                valid = {t: quotes[t] for t in required
                         if t in quotes and _quote_valid(quotes[t], now, market)}
                missing = sorted(required - set(valid))
                if missing:
                    evidence[slot] = {"status": "awaiting_fresh_open_quotes",
                                      "fills": 0, "missing": missing}
                elif any(datetime.fromisoformat(q["observed_at_utc"].replace("Z", "+00:00")) >
                         market["open"] + OPEN_WINDOW for q in valid.values()):
                    evidence[slot] = {"status": "opening_window_missed", "fills": 0}
                else:
                    # The engine's same cost/quantity formula, with all held
                    # symbols quoted before computing the portfolio's open NAV.
                    prices = {t: {"open": v["price"]} for t, v in valid.items()}
                    provenance = {t: _provenance(q, lock, t, key) for t, q in valid.items()}
                    begin = len(book["events"])
                    execute_frozen_open(config, name, book, market["session"], prices,
                                        provenance=provenance)
                    recent = book["events"][begin:]
                    for row in recent:
                        if row.get("execution") != "forward_observed_paper":
                            continue
                        t = row["ticker"]
                        side = row["type"]
                        if side == "buy":
                            quantity = row["shares"]
                            price = row["price"]
                            fee = row["fee"]
                        else:
                            quantity = row["shares"]
                            price = row["price"]
                            fee = row["fee"]
                        operations.append({"ticker": t, "side": side,
                                           "quantity": quantity, "price": price,
                                           "fee": fee, "observed_at_utc": valid[t]["observed_at_utc"]})
                    marker = {"session": market["session"], "mode": "forward_observed_paper",
                              "source_commit": lock["source_commit"],
                              "lock_sha256": lock["lock_sha256"],
                              "recorded_at_utc": timestamp(now),
                              "quotes_sha256": digest(valid),
                              "fills_count": len(operations),
                              "fill_tickers": sorted({op["ticker"] for op in operations})}
                    markers[key] = marker
                    markers_written.append(marker)
                    any_changes = True
                    evidence[slot] = {"status": "settled_native_paper",
                                      "fills": len(operations), "marker": marker,
                                      "operations": operations}
        # Intraday stop/target rules use only a fresh OBSERVED quote crossing a
        # frozen level. A missing observation never becomes a retroactive exit.
        # Books still carrying an unexecuted opening order cannot trade stops.
        if book["pending"]:
            continue
        for ticker, position in list(book["positions"].items()):
            stop = position.get("stop")
            target = position.get("target")
            if stop is None and target is None:
                continue
            quote = quotes.get(ticker)
            if not _quote_valid(quote, now, market):
                continue
            price = float(quote["price"])
            # A >30% discontinuity could be a same-day split rather than an
            # executable stop; require separate corporate-action validation.
            entry = float(position["entry_price"])
            if price < .7 * entry or price > 1.3 * entry:
                continue
            reason = ("stop" if stop is not None and price <= stop
                      else "target" if target is not None and price >= target
                      else None)
            if not reason:
                continue
            key = event_key(slot, market["session"], reason + ":" + ticker)
            if key in markers:
                continue
            shares = position["shares"]
            _close_position(book, ticker, price, market["session"], config,
                            reason + "_forward_observed")
            fill = book["trades"][-1]
            meta = _provenance(quote, lock, ticker, key)
            book["trades"][-1].update({"execution": "forward_observed_paper", **meta})
            book["events"][-1].update({"execution": "forward_observed_paper", **meta})
            actual_price = price * (1 - config["execution"]["slippage"])
            fee = shares * actual_price * config["execution"]["commission"]
            operation = {"ticker": ticker, "side": "sell", "quantity": shares,
                         "price": actual_price, "fee": fee,
                         "observed_at_utc": quote["observed_at_utc"]}
            marker = {"session": market["session"], "mode": "forward_observed_paper",
                      "source_commit": lock["source_commit"],
                      "lock_sha256": lock["lock_sha256"],
                      "recorded_at_utc": timestamp(now),
                      "quotes_sha256": digest({ticker: quote}),
                      "fills_count": 1, "fill_tickers": [ticker]}
            markers[key] = marker
            markers_written.append(marker)
            operations.append(operation)
            any_changes = True
            evidence[slot] = {"status": "settled_native_paper", "fills": len(operations),
                              "marker": marker, "operations": operations}
        if not lane["orders"] and not operations:
            evidence[slot] = {"status": "active_no_orders", "fills": 0}
    return ({LEDGER: updated} if any_changes else {}), evidence


def verify_published(report_path=ROOT / "data/operational-clock.json", *, remote=_source_at):
    report = json.loads(Path(report_path).read_text(encoding="utf8"))
    lanes = report.get("slots", {})
    if not any(lanes.get(slot, {}).get("status") == "native_forward_settled" for slot in SLOTS):
        return []
    book = remote("origin/main", LEDGER)
    verified = []
    for slot, name in SLOTS.items():
        lane = lanes.get(slot, {})
        if lane.get("status") != "native_forward_settled":
            continue
        marker = lane.get("native_marker")
        if not isinstance(marker, dict):
            raise ValueError(f"{slot}: missing execution evidence")
        matches = [m for m in book["books"][name].get("forward_executions", {}).values()
                   if m == marker]
        if not matches:
            raise ValueError(f"{slot}: published forward marker missing from canonical book")
        verified.append(slot)
    return verified
