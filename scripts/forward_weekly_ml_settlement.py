"""Native forward entry fills for MIDAS IL-019..IL-027, one shared ML ledger.

A verified quote is a simulated execution price, NOT an exchange fill.
The nightly daily engine owns official closing NAV; weekly exits require a contemporary observation.
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


def _exit_key(slot, session):
    return f"{slot}:{session}:weekly_ml_observed_exit_v1"


def weekly_exit_quote_coverage(book, now, market, quotes):
    """Count only quotes executable in the real five-minute closing window."""
    expected = set(book["positions"])
    first = market["close"] - timedelta(minutes=5)
    valid = set()
    for ticker in expected:
        quote = quotes.get(ticker)
        if not _quote_valid(quote, now, market):
            continue
        stamp = datetime.fromisoformat(quote["quote_at_utc"].replace("Z", "+00:00"))
        if first <= stamp <= now <= market["close"]:
            valid.add(ticker)
    return {"required_count": len(expected), "valid_count": len(valid),
            "missing": sorted(expected - valid)}


def _verified_partial_exit(original, book, slot, market, lock, policy):
    """Reconcile prior same-session symbol sales before observing another one.

    A previously booked close may not be replayed, undone or used to create
    an unrelated entry. Cash, quantities, trades and receipt provenance must
    match the immutable previous-session source and this session's lock.
    """
    if _unchanged(original, book) and (
            original.get("trades") == book.get("trades") and
            original.get("paused_missing_quotes") == book.get("paused_missing_quotes") and
            original.get("forward_executions") == book.get("forward_executions")):
        return True
    if (any(original.get(k) != book.get(k) for k in
            ("nav", "equity", "pending", "last_signal_session", "paused_missing_quotes"))
            or not isinstance(original.get("positions"), dict)
            or not isinstance(book.get("positions"), dict)
            or not isinstance(book.get("forward_executions"), dict)):
        return False
    prefix = _exit_key(slot, market["session"]) + ":"
    old_markers = original.get("forward_executions", {})
    markers = book["forward_executions"]
    if any(markers.get(key) != value for key, value in old_markers.items()):
        return False
    added = {key: value for key, value in markers.items() if key not in old_markers}
    if not added or any(not key.startswith(prefix) for key in added):
        return False
    sold = set(original["positions"]) - set(book["positions"])
    if (len(added) != len(sold) or not sold
            or any(book["positions"].get(t) != original["positions"][t]
                   for t in book["positions"] if t in original["positions"])
            or not set(book["positions"]) <= set(original["positions"])
            or book.get("events", [])[:len(original.get("events", []))] != original.get("events", [])
            or book.get("trades", [])[:len(original.get("trades", []))] != original.get("trades", [])):
        return False
    events = book["events"][len(original["events"]):]
    trades = book["trades"][len(original["trades"]):]
    if len(events) != len(sold) or len(trades) != len(sold):
        return False
    by_event = {e.get("ticker"): e for e in events}
    by_trade = {t.get("ticker"): t for t in trades}
    if set(by_event) != sold or set(by_trade) != sold:
        return False
    cash = float(original["cash"])
    for ticker in sold:
        key = prefix + ticker
        mark = added.get(key)
        event, trade = by_event[ticker], by_trade[ticker]
        old = original["positions"][ticker]
        if (not isinstance(mark, dict)
                or mark.get("mode") != "weekly_observed_exit_symbol"
                or mark.get("session") != market["session"]
                or mark.get("source_commit") != lock["source_commit"]
                or mark.get("lock_sha256") != lock["lock_sha256"]
                or mark.get("fills_count") != 1
                or mark.get("fill_tickers") != [ticker]
                or event.get("execution") != "observed_preclose_paper"
                or event.get("idempotency_key") != key
                or event.get("lock_sha256") != lock["lock_sha256"]
                or event.get("source_commit") != lock["source_commit"]
                or event.get("date") != market["session"]
                or event.get("type") != "sell"
                or trade.get("exit_date") != market["session"]
                or trade.get("entry_date") != old["entry_date"]
                or trade.get("signal_date") != old["signal_date"]):
            return False
        try:
            shares, price, fee = (float(event[x]) for x in ("shares", "price", "fee"))
            if (not all(math.isfinite(x) for x in (shares, price, fee))
                    or shares <= 0 or price <= 0 or fee < 0
                    or not math.isclose(shares, float(old["shares"]), rel_tol=1e-12)
                    or not math.isclose(price, float(trade["sell_price"]), rel_tol=1e-12)
                    or not math.isclose(fee, float(trade["sell_commission"]), rel_tol=1e-12)
                    or not math.isclose(float(trade["net_pnl"]),
                        shares * price - fee - float(old["entry_price"]) * shares
                        - float(old["entry_fee"]), rel_tol=1e-10, abs_tol=1e-6)):
                return False
            time_mark = datetime.fromisoformat(event["quote_at_utc"].replace("Z", "+00:00"))
            received = datetime.fromisoformat(event["observed_at_utc"].replace("Z", "+00:00"))
            if not (market["close"] - timedelta(minutes=5) <= time_mark
                    <= received <= market["close"]):
                return False
            cash += shares * price - fee
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
    return math.isclose(float(book["cash"]), cash, rel_tol=1e-10, abs_tol=1e-6)


def _weekly_exit(book, slot, lock, now, market, quotes, policy):
    """Sell independently priced *held* tickers; leave missing ones untouched.

    Strictly before official close, use only fresh, dated, single-symbol
    observations. A different holding's missing quote never cancels a valid
    independent paper sale. Each sell has an immutable idempotency marker.
    """
    expected = set(book["positions"])
    frozen = set(lock["slots"][slot].get("monitor_tickers", []))
    if not expected or book["pending"] or not expected <= frozen:
        return None
    start = market["close"] - timedelta(minutes=5)
    fresh = {}
    for ticker in expected:
        q = quotes.get(ticker)
        if not _quote_valid(q, now, market):
            continue
        when = datetime.fromisoformat(q["quote_at_utc"].replace("Z", "+00:00"))
        if start <= when <= now <= market["close"]:
            fresh[ticker] = q
    if not fresh:
        return None
    operations = []
    markers = book.setdefault("forward_executions", {})
    last_marker = None
    for ticker in sorted(fresh):
        pos = book["positions"][ticker]
        shares = float(pos["shares"])
        price = float(fresh[ticker]["price"]) * (1 - float(policy["slippage"]))
        fee = shares * price * float(policy["commission"])
        if not all(math.isfinite(v) for v in (shares, price, fee)) or shares <= 0 or price <= 0 or fee < 0:
            raise ValueError("Invalid observed weekly exit economics")
        key = _exit_key(slot, market["session"]) + ":" + ticker
        if key in markers:
            raise ValueError("Weekly exit already marked for still-held ticker")
        book["cash"] += shares * price - fee
        book["trades"].append({"ticker": ticker, "signal_date": pos["signal_date"],
            "entry_date": pos["entry_date"], "exit_date": market["session"], "shares": shares,
            "buy_price": pos["entry_price"], "sell_price": price, "buy_commission": pos["entry_fee"],
            "sell_commission": fee, "net_pnl": shares * price - fee - pos["entry_price"] * shares - pos["entry_fee"]})
        event = {"date": market["session"], "type": "sell", "ticker": ticker, "shares": shares,
                 "price": price, "fee": fee, "execution": "observed_preclose_paper",
                 "quote_at_utc": fresh[ticker]["quote_at_utc"], "observed_at_utc": fresh[ticker]["observed_at_utc"],
                 "source_commit": lock["source_commit"], "lock_sha256": lock["lock_sha256"],
                 "idempotency_key": key}
        book["events"].append(event)
        del book["positions"][ticker]
        operations.append({"ticker": ticker, "side": "sell", "quantity": shares, "price": price,
                           "fee": fee, "observed_at_utc": event["observed_at_utc"]})
        last_marker = {"session": market["session"], "mode": "weekly_observed_exit_symbol",
              "source_commit": lock["source_commit"], "lock_sha256": lock["lock_sha256"],
              "recorded_at_utc": timestamp(now),
              "quotes_sha256": digest({ticker: fresh[ticker]}),
              "fills_count": 1, "fill_tickers": [ticker]}
        markers[key] = last_marker
    if not book["positions"]:
        # Historical missed exits stay disclosed. Complete the unwind only
        # when every position was independently sold at a real observed price.
        if book.get("paused_missing_quotes", {}).get("reason") == "unobserved_weekly_exit":
            missed = list(book["paused_missing_quotes"].get("missed_exit_sessions", []))
            book["events"].append({"date": market["session"],
                "type": "prospective_unwind_after_unobserved_weekly_exit",
                "missed_exit_sessions": missed, "lock_sha256": lock["lock_sha256"]})
            del book["paused_missing_quotes"]
        total = len(frozen)
        final = {"session": market["session"], "mode": "weekly_observed_exit",
                 "lock_sha256": lock["lock_sha256"], "source_commit": lock["source_commit"],
                 "recorded_at_utc": timestamp(now),
                 "observed_fill_events_sha256": digest([
                     e for e in book["events"] if e.get("date") == market["session"]
                     and e.get("execution") == "observed_preclose_paper"
                     and e.get("idempotency_key", "").startswith(_exit_key(slot, market["session"]) + ":")]),
                 "fills_count": total, "fill_tickers": sorted(frozen)}
        markers[_exit_key(slot, market["session"])] = final
        last_marker = final
    return last_marker, operations


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
        exit_key = _exit_key(slot, market["session"])
        prior_exit = book.get("forward_executions", {}).get(exit_key)
        if prior_exit is not None:
            if prior_exit.get("lock_sha256") != lock["lock_sha256"]:
                raise ValueError(f"{slot}: conflicting observed exit lock")
            observations[slot] = {"status": "already_settled", "fills": prior_exit["fills_count"], "marker": prior_exit}
            continue
        from tfg_ahp.data import is_week_end_session
        exit_window = market["close"] - timedelta(minutes=5) <= now <= market["close"]
        if exit_window and is_week_end_session(market["session"]) and book["positions"]:
            paused = book.get("paused_missing_quotes")
            paused_exit = (lane.get("exit_only_ready") and lane.get("source_status") == "paused"
                           and isinstance(paused, dict) and paused.get("reason") == "unobserved_weekly_exit"
                           and original.get("paused_missing_quotes") == paused)
            eligible_exit = lane["execution_ready"] and not paused
            if (not (eligible_exit or paused_exit) or lane["source_session"] != market["previous"]
                    or book["equity"][-1]["date"] != market["previous"]
                    or not _verified_partial_exit(original, book, slot, market, lock, config["paper_policy"])):
                observations[slot] = {"status": "exit_source_changed_or_stale", "fills": 0}
                continue
            outcome = _weekly_exit(book, slot, lock, now, market, quotes, config["paper_policy"])
            if outcome is None:
                observations[slot] = {
                    "status": "awaiting_verified_weekly_exit_quotes", "fills": 0,
                    **weekly_exit_quote_coverage(book, now, market, quotes)}
                continue
            marker, operations = outcome
            observations[slot] = {"status": "settled_native_paper", "fills": len(operations),
                                  "marker": marker, "operations": operations,
                                  "remaining_tickers": sorted(book["positions"]),
                                  "exit_scope": "symbol_isolated_verified_preclose"}
            continue
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
        key = (_exit_key(slot, marker["session"]) if marker.get("mode") == "weekly_observed_exit"
               else _exit_key(slot, marker["session"]) + ":" + marker["fill_tickers"][0]
               if marker.get("mode") == "weekly_observed_exit_symbol"
               else _key(slot, marker["session"], marker["signal_date"]))
        book = ledger["strategies"][name]
        if book.get("forward_executions", {}).get(key) != marker or book.get("pending"):
            raise ValueError(f"{slot}: published ML fill missing from native book")
        checked.append(slot)
    return checked
