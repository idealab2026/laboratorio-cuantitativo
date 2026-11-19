"""IL-044 original genetic portfolio: prospective native USD fills only.

Reuses original genetic forward diary and original commission, slippage, lot
sizing and SL/TP. Market observations are paper price proxies, not broker fills.
No retroactive OHLC-based fills and no second diary. The genetic training
workflow remains solely responsible for signals after the exact daily close.
"""
from __future__ import annotations
import copy
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from operational_clock import _quote_valid, digest, timestamp, verify_lock
from native_forward_settlement import _source_at
from AGENTE.genetic_invest_agent import forward_portfolio as core

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ("AGENTE/genetic_invest_agent/registro_historico/"
          "diario_portfolio_forward_2026-10-12.json")
SLOT = "IL-044"
OPEN_WINDOW = timedelta(minutes=30)


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf8"))


def marker_key(day, mode, ticker=None):
    return ":".join([SLOT, day, mode, ticker or "all", "genetic_forward_v1"])


def source_unchanged(a, b):
    keys = ("cash", "positions", "pending", "trades", "equity_history",
            "last_session", "outage_control")
    return all(a.get(key) == b.get(key) for key in keys)


def _metadata(lock, quote, key):
    return {
        "execution": "forward_observed_paper",
        "quote_at_utc": quote["quote_at_utc"],
        "observed_at_utc": quote["observed_at_utc"],
        "source_commit": lock["source_commit"],
        "lock_sha256": lock["lock_sha256"],
        "idempotency_key": key,
    }


def _sale(state, ticker, raw, day, reason, evidence):
    p = state["positions"].pop(ticker)
    qty = p["shares"]
    fill = raw * (1 - core.SLIPPAGE)
    gross = qty * fill
    fee = gross * core.COMMISSION
    state["cash"] += gross - fee
    row = {"session": day, "ticker": ticker, "side": "SELL",
           "reason": reason, "shares": qty, "fill": fill, "fee": fee, **evidence}
    state["trades"].append(row)
    return {"ticker": ticker, "side": "sell", "quantity": qty,
            "price": fill, "fee": fee,
            "observed_at_utc": evidence["observed_at_utc"]}


def _price_guard(position, raw):
    entry = core._positive(position["entry"], "previous entry")
    # A >30% observed discontinuity could be an unreviewed split, stale
    # provider mapping or extraordinary halt. Do not sell on that evidence.
    if not 0.7 * entry <= raw <= 1.3 * entry:
        raise ValueError("Genetic corporate-action/discontinuity review required")


def open_orders(state, day, prices, proof, *, allow_missing_observed=False,
                verified_previous_nav=None):
    """Preserve native genetic sizing and sell-first order order.

    In prospective mode, one absent ticker cannot block independently quoted
    orders. No missing ticker is assigned a price, execution or cash value.
    When a *held* mark is missing, the existing verified prior-session NAV is
    used only as an ex-ante sizing reference, never a new valuation.
    """
    expected = set(state["positions"]) | set(state["pending"]["buys"]) | set(state["pending"]["sells"])
    if ((not allow_missing_observed and
         (set(prices) != expected or set(proof) != expected))
            or (allow_missing_observed and
                (not prices or not set(prices) <= expected or set(proof) != set(prices)))):
        raise ValueError("Incomplete genetic opening observations")
    if verified_previous_nav is not None and (
            not allow_missing_observed or
            type(verified_previous_nav) not in (int, float) or
            not math.isfinite(verified_previous_nav) or verified_previous_nav <= 0):
        raise ValueError("Genetic prior NAV reference not verified")
    operations = []
    for ticker, pos in list(state["positions"].items()):
        if ticker not in prices:
            continue
        raw = core._positive(prices[ticker], ticker + " observed open")
        _price_guard(pos, raw)
        if raw <= pos["sl"] or raw >= pos["tp"]:
            operations.append(_sale(
                state, ticker, raw, day,
                "STOP_GAP_OBSERVED" if raw <= pos["sl"] else "TARGET_GAP_OBSERVED",
                proof[ticker]))
    for ticker in state["pending"]["sells"]:
        if ticker in state["positions"]:
            if ticker not in prices:
                if not allow_missing_observed:
                    raise ValueError("Missing verified genetic sell quote")
                state.setdefault("outage_events", []).append({
                    "date": day, "type": "unfilled_missing_observed_quote",
                    "ticker": ticker, "side": "sell", "reason": "no_contemporary_opening_quote"})
                continue
            operations.append(_sale(state, ticker,
                                    core._positive(prices[ticker], "sell quote"),
                                    day, "SIGNAL_NEXT_OPEN", proof[ticker]))
    # Exactly as the historical original engine: mark remaining held positions
    # at the observed open BEFORE allocating capital for new entries.
    missing_held = sorted(set(state["positions"]) - set(prices))
    if missing_held:
        if verified_previous_nav is None:
            raise ValueError("Missing verified genetic prior NAV for isolated sizing")
        open_nav = verified_previous_nav
    else:
        open_nav = state["cash"] + sum(
            pos["shares"] * core._positive(prices[t], "held open")
            for t,pos in state["positions"].items())
    for ticker, order in sorted(state["pending"]["buys"].items()):
        if ticker not in prices:
            if not allow_missing_observed:
                raise ValueError("Missing verified genetic buy quote")
            state.setdefault("outage_events", []).append({
                "date": day, "type": "unfilled_missing_observed_quote",
                "ticker": ticker, "side": "buy", "reason": "no_contemporary_opening_quote"})
            continue
        if ticker in state["positions"] or any(
                t["ticker"] == ticker and t["session"] == day
                for t in state["trades"]):
            continue
        raw = core._positive(prices[ticker], "buy quote")
        fill = raw * (1 + core.SLIPPAGE)
        budget = min(open_nav * min(core._positive(order["weight"], "weight"),
                                    core.MAX_WEIGHT), state["cash"] * 0.95)
        shares = core._fractional_shares(budget, fill)
        if shares <= 0:
            state.setdefault("outage_events", []).append({
                "date": day, "type": "unfilled_below_min_notional",
                "ticker": ticker, "execution": "forward_observed_paper",
            })
            continue
        gross = shares * fill
        fee = gross * core.COMMISSION
        if gross + fee > state["cash"]+1e-7:
            raise ValueError("Genetic paper cash exceeded")
        state["cash"] -= gross + fee
        state["positions"][ticker] = {
            "shares": shares, "entry": fill,
            "entry_date": day,
            "sl": fill * (1-core._positive(order["stop_pct"], "stop")),
            "tp": fill * (1+core._positive(order["target_pct"], "target")),
        }
        state["trades"].append({
            "session": day, "ticker": ticker, "side": "BUY",
            "reason": "SIGNAL_NEXT_OPEN", "shares": shares,
            "fill": fill, "fee": fee, **proof[ticker],
            **({"sizing_reference": "verified_previous_close_nav"} if missing_held else {}),
        })
        operations.append({
            "ticker": ticker, "side": "buy", "quantity": shares,
            "price": fill, "fee": fee,
            "observed_at_utc": proof[ticker]["observed_at_utc"],
        })
    state["pending"] = {"buys": {}, "sells": []}
    return operations


def settle_genetic(lock, now, market, quotes, *, reader=read, frozen=_source_at):
    verify_lock(lock, market, now)
    lane = lock["slots"][SLOT]
    if not lane["execution_ready"] or lane["source_session"] != market["previous"]:
        return {}, {SLOT: {"status": "not_ready", "fills": 0}}
    current = reader(LEDGER)
    source = frozen(lock["source_commit"], LEDGER)
    if (current["last_session"] != market["previous"] or
            source["last_session"] != market["previous"]):
        return {}, {SLOT: {"status": "source_session_changed", "fills": 0}}
    if not isinstance(current.get("pending"), dict) or not isinstance(current.get("positions"), dict):
        raise ValueError("Genetic canonical diary schema invalid")
    same_day = {key:v for key,v in current.get("forward_executions", {}).items()
                if isinstance(v,dict) and v.get("session") == market["session"]}
    if same_day and any(v.get("lock_sha256") != lock["lock_sha256"]
                        for v in same_day.values()):
        raise ValueError("Genetic same-session markers refer to different lock")
    if not source_unchanged(source, current) and not same_day:
        return {}, {SLOT: {"status": "source_changed", "fills": 0}}
    day = market["session"]
    updated = copy.deepcopy(current)
    markers = updated.setdefault("forward_executions", {})
    # Ex-date dividends belong to shares held at yesterday's close, even if
    # a verified stop/signal sells them during this session. Preserve this
    # dated inventory so the nightly engine does not lose entitlements.
    inventory = updated.setdefault("preopen_inventory", {})
    if market["session"] not in inventory:
        inventory[market["session"]] = {
            t: float(position["shares"]) for t,position in source["positions"].items()
        }
    operations = []
    at_open = now <= market["open"]+OPEN_WINDOW
    opening_key = marker_key(day,"open")
    if lane["orders"] and opening_key not in markers:
        if not at_open:
            return {}, {SLOT: {"status": "opening_window_missed", "fills": 0}}
        if not source_unchanged(source, current):
            return {}, {SLOT: {"status": "source_changed_before_open", "fills": 0}}
        expected_buys = set(current["pending"]["buys"])
        expected_sells = set(current["pending"]["sells"])
        original_orders = {x["ticker"]: x["action"] for x in lane["orders"]}
        if (len(original_orders) != len(lane["orders"]) or
                original_orders != {**{t:"buy" for t in expected_buys},
                                    **{t:"sell" for t in expected_sells}} or
                any(o["signal_session"] != market["previous"] or
                    o["target_session"] != day or o.get("limit_price") is not None
                    for o in lane["orders"])):
            return {}, {SLOT: {"status": "frozen_signals_mismatch", "fills": 0}}
        all_needed = (set(current["positions"]) |
                      expected_buys | expected_sells)
        fresh = {t:quotes[t] for t in all_needed
                 if t in quotes and _quote_valid(quotes[t], now, market)}
        missing = sorted(all_needed - set(fresh))
        # Wait for an actual pending-order quote when none is usable; held
        # quotes alone cannot justify expiring a basket prematurely.
        actionable = (expected_buys | expected_sells) & set(fresh)
        if not actionable:
            return {}, {SLOT: {"status": "awaiting_fresh_open_quotes",
                               "fills": 0, "missing": missing}}
        if any(datetime.fromisoformat(q["quote_at_utc"].replace("Z","+00:00")) >
               market["open"]+OPEN_WINDOW for q in fresh.values()):
            return {}, {SLOT: {"status": "opening_quote_late", "fills": 0}}
        proof = {t:_metadata(lock,q,opening_key+":"+t) for t,q in fresh.items()}
        held_missing = sorted(set(current["positions"]) - set(fresh))
        prior_nav = None
        if held_missing:
            prior_nav = current.get("equity_history", {}).get(market["previous"])
            if (type(prior_nav) not in (int, float) or
                    not math.isfinite(prior_nav) or prior_nav <= 0):
                return {}, {SLOT: {"status": "prior_verified_nav_missing",
                                   "fills": 0, "missing": held_missing}}
        try:
            operations = open_orders(
                updated, day, {t:q["price"] for t,q in fresh.items()}, proof,
                allow_missing_observed=bool(missing),
                verified_previous_nav=prior_nav)
        except ValueError as exc:
            if "corporate-action/discontinuity review required" in str(exc):
                return {}, {SLOT: {"status":"corporate_action_review_required",
                                   "fills":0}}
            raise
        marker = {"session": day, "mode": "open", "source_commit":lock["source_commit"],
                  "lock_sha256":lock["lock_sha256"],
                  "recorded_at_utc":timestamp(now), "quotes_sha256":digest(fresh),
                  "fills_count":len(operations),
                  "fill_tickers":sorted(t["ticker"] for t in operations)}
        markers[opening_key] = marker
        opening_isolation = {"unfilled_open_quotes":
                             sorted((expected_buys | expected_sells) - set(fresh)),
                             "missing_held_quotes": held_missing,
                             "sizing_reference": ("verified_previous_close_nav"
                                                  if held_missing else "observed_open_nav")}
    elif lane["orders"] and opening_key in markers:
        # The opening has already settled. Check live SL/TP without replaying
        # the entry. The final report will preserve its initial marker if no
        # new position is triggered.
        marker = markers[opening_key]
    else:
        marker = None

    # A quote is a *new* observation only when it meets the 180s freshness
    # window. Trigger only stocks actually held and never infer a fill from
    # the day's high/low.
    for ticker,position in list(updated["positions"].items()):
        q = quotes.get(ticker)
        if not _quote_valid(q, now, market):
            continue
        raw = core._positive(q["price"], "observed stop quote")
        if not 0.7 * position["entry"] <= raw <= 1.3 * position["entry"]:
            continue
        reason = ("STOP_OBSERVED" if raw <= position["sl"] else
                  "TARGET_OBSERVED" if raw >= position["tp"] else None)
        if reason is None:
            continue
        key = marker_key(day, reason, ticker)
        if key in markers:
            continue
        proof = _metadata(lock,q,key)
        operations.append(_sale(updated,ticker,raw,day,reason,proof))
        marker = {"session":day, "mode":reason,"ticker":ticker,
                  "source_commit":lock["source_commit"],
                  "lock_sha256":lock["lock_sha256"],
                  "recorded_at_utc":timestamp(now),
                  "quotes_sha256":digest({ticker:q}),
                  "fills_count":1,"fill_tickers":[ticker]}
        markers[key] = marker
    if not operations and (not lane["orders"] or opening_key not in markers):
        return {}, {SLOT: {"status": "no_execution_due", "fills": 0}}
    if operations or (opening_key in markers and opening_key not in current.get("forward_executions", {})):
        # New genuine paper event; never rewrite last_session or close NAV.
        latest = marker or markers.get(opening_key)
        return {LEDGER: updated}, {SLOT:{
            "status":"settled_native_paper", "fills":len(operations),
            "marker":latest,"operations":operations,
            **(opening_isolation if opening_key in markers and
               opening_key not in current.get("forward_executions", {}) else {})}}
    if same_day:
        # On a repeated poll preserve the most recent stop/target evidence,
        # never overwrite a later sell marker with the earlier opening buy.
        marker = max(same_day.values(), key=lambda m: m.get("recorded_at_utc",""))
    return {}, {SLOT: {"status":"already_settled" if marker else "no_execution_due",
                       "fills":marker.get("fills_count",0) if marker else 0,
                       "marker":marker}}



def summarize_session_fills(book, session, lock_sha256):
    """Reconstruct an IL-044 session from *canonical* verified ledger events.

    A native_marker only identifies the latest event. Genetic SL/TP orders
    can settle in separate intraday polls; adding the most recent count alone
    under-reports earlier executions. Never infer trades from prices.
    """
    markers = book.get("forward_executions", {})
    trades = book.get("trades", [])
    if not isinstance(markers, dict) or not isinstance(trades, list):
        raise ValueError("Genetic ledger has malformed execution evidence")
    selected = {key: val for key, val in markers.items()
                if isinstance(val, dict) and val.get("session") == session}
    for key, marker in selected.items():
        if marker.get("lock_sha256") != lock_sha256:
            raise ValueError("Genetic session has conflicting preopen locks")
        if type(marker.get("fills_count")) is not int or marker["fills_count"] < 0:
            raise ValueError("Genetic session marker has invalid fill count")
    trades_by_marker = {key: [] for key in selected}
    seen_keys = set()
    session_trades = []
    for trade in trades:
        if trade.get("session") != session or trade.get("execution") != "forward_observed_paper":
            continue
        key = trade.get("idempotency_key")
        if not isinstance(key, str) or key in seen_keys:
            raise ValueError("Genetic session contains missing/duplicate trade identity")
        seen_keys.add(key)
        owner = key if key in selected else key.rsplit(":", 1)[0]
        if owner not in selected or trade.get("lock_sha256") != lock_sha256:
            raise ValueError("Genetic session trade has no matching frozen marker")
        if trade.get("source_commit") != selected[owner].get("source_commit"):
            raise ValueError("Genetic session trade provenance does not match marker")
        trades_by_marker[owner].append(trade)
        session_trades.append(trade)
    for key, marker in selected.items():
        associated = trades_by_marker[key]
        if (len(associated) != marker["fills_count"] or
                sorted(x["ticker"] for x in associated) !=
                sorted(marker.get("fill_tickers", []))):
            raise ValueError("Genetic marker count/tickers disagree with canonical fills")
    ordered_markers = sorted(selected.items(),
                             key=lambda item: (item[1].get("recorded_at_utc", ""), item[0]))
    ordered_trades = sorted(session_trades,
                            key=lambda row: (row["observed_at_utc"], row["idempotency_key"]))
    return {
        "fills_count": len(ordered_trades),
        "fills": [{"ticker": row["ticker"], "side": row["side"].lower(),
                   "quantity": row["shares"], "price": row["fill"],
                   "fee": row["fee"], "observed_at_utc": row["observed_at_utc"]}
                  for row in ordered_trades],
        "native_markers": [{"key": key, "mode": marker["mode"],
                            "ticker": marker.get("ticker"),
                            "fills_count": marker["fills_count"],
                            "recorded_at_utc": marker["recorded_at_utc"]}
                           for key, marker in ordered_markers],
        "latest_marker": ordered_markers[-1][1] if ordered_markers else None,
    }


def verify_published(report_path=ROOT/"data/operational-clock.json", *, remote=_source_at):
    doc=json.loads(Path(report_path).read_text(encoding="utf8"))
    lane=doc.get("slots",{}).get(SLOT,{})
    if lane.get("status")!="native_forward_settled":
        return []
    marker=lane.get("native_marker")
    if not isinstance(marker,dict):
        raise ValueError("Genetic public forward marker missing")
    record=remote("origin/main",LEDGER)
    if marker not in record.get("forward_executions",{}).values():
        raise ValueError("Genetic marker not persisted in native original book")
    if lane.get("session_fill_reconciled"):
        summary = summarize_session_fills(record, doc["session"], marker["lock_sha256"])
        if (lane.get("fills_count") != summary["fills_count"] or
                lane.get("fills") != summary["fills"] or
                lane.get("native_markers") != summary["native_markers"]):
            raise ValueError("Genetic public session totals differ from canonical ledger")
    return [SLOT]
