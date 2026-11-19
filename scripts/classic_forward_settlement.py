"""Prospective paper opening and observed stop/target events for IL-010..018.

Executes only in the existing classic_sp500_state/ledger.json and never uses a
completed daily OHLC bar to imply an intraday fill. A quote is a paper price
proxy, not proof that a real market order could have been filled.
"""
from __future__ import annotations
import copy
import json
import math
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
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
               ("cash", "positions", "pending", "trades", "events", "equity", "nav",
                "receivables", "outage_control", "paused_missing_quotes"))


def _claims_actually_settled(book, previous):
    """A historical right is released ONLY after issuer-reviewed cash settlement.

    A clearing reference price (including OCC option deliverables) or an
    unreviewed receivable never becomes spendable paper cash. The frozen
    closing ledger must already contain the issuer settlement event matching
    the full amount, currency, corporate action and payment date.
    """
    claims = book.get("receivables", {})
    if not isinstance(claims, dict):
        return False
    for key, claim in claims.items():
        if not isinstance(claim, dict) or claim.get("action_id") != key or claim.get("status") != "settled":
            return False
        if key != "KVUE_KMB_2026-11-02" or claim.get("symbol") != "KMB":
            return False
        try:
            payment = claim["payment_session"]
            if (not isinstance(payment, str)
                    or date.fromisoformat(payment).isoformat() != payment
                    or payment > previous):
                return False
            cash = Decimal(claim["settled_cash"])
            fixed = Decimal(claim["fixed_cash"])
            fraction = Decimal(claim["fractional_shares"])
            if (not all(v.is_finite() for v in (cash, fixed, fraction))
                    or cash <= 0 or fixed < 0 or cash < fixed
                    or not 0 <= fraction < 1
                    or cash != cash.quantize(Decimal("0.01"))):
                return False
            url = claim["settlement_source_url"]
            if (not isinstance(url, str) or not url.startswith((
                    "https://www.sec.gov/Archives/",
                    "https://www.investor.kimberly-clark.com/"))):
                return False
            matching = [event for event in book.get("events", [])
                        if isinstance(event, dict)
                        and event.get("type") == "corporate_cash_settlement"
                        and event.get("action_id") == key]
            if len(matching) != 1:
                return False
            event = matching[0]
            when = event["date"]
            if (not isinstance(when, str)
                    or date.fromisoformat(when).isoformat() != when
                    or not payment <= when <= previous
                    or event.get("source_url") != url
                    or Decimal(str(event["amount"])) != cash
                    or Decimal(str(event["allocated_cost"])) !=
                        Decimal(str(claim["allocated_cost"]))):
                return False
        except (KeyError, ValueError, TypeError, InvalidOperation, OverflowError):
            return False
    return True



def _isolated_unsettled_kvue_claim(book, previous):
    """IL-010 and IL-012 may trade unrelated owned shares using REAL cash already
    in book['cash']; the independent merger claim remains nonspendable.
    This is an eligibility check, not issuer settlement or P&L recognition.
    No other unreviewed corporate action gains this exception.
    """
    from classic_sp500.corporate_actions import ACTION, EFFECTIVE, ISSUER, REFERENCE, RATIO, CASH

    claims = book.get("receivables")
    if (not isinstance(claims, dict) or set(claims) != {ACTION}
            or not isinstance(previous, str) or previous < EFFECTIVE
            or not isinstance(book.get("cash"), (int, float))
            or isinstance(book["cash"], bool)
            or not math.isfinite(book["cash"]) or book["cash"] < 0):
        return False
    claim = claims[ACTION]
    if not isinstance(claim, dict):
        return False
    expected = {
        "action_id": ACTION, "effective_session": EFFECTIVE,
        "status": "unsettled", "symbol": "KMB",
        "source_url": ISSUER,
        "valuation_reference_url": REFERENCE,
        "valuation_policy": "occ_temporary_reference_applied_to_paper_claim",
    }
    if (any(claim.get(k) != v for k, v in expected.items())
            or any(k in claim for k in ("settled_cash", "payment_session",
                                       "settlement_source_url"))):
        return False
    entitlements = [event for event in book.get("events", [])
                    if isinstance(event, dict) and
                    event.get("type") == "corporate_merger_entitlement"]
    if len(entitlements) != 1:
        return False
    e = entitlements[0]
    if (e.get("action_id") != ACTION or e.get("date") != EFFECTIVE
            or e.get("source_url") != ISSUER
            or e.get("valuation_reference_url") != REFERENCE
            or e.get("cash_credited") != 0 or e.get("trades_executed") != 0
            or e.get("recorded_at_utc") != claim.get("recorded_at_utc")
            or any(event.get("type") == "corporate_cash_settlement"
                   and event.get("action_id") == ACTION
                   for event in book.get("events", []) if isinstance(event, dict))):
        return False
    old = e.get("original_position")
    if not isinstance(old, dict):
        return False
    try:
        shares = Decimal(str(old["shares"]))
        old_cost = Decimal(str(old["cost"]))
        full = shares * RATIO
        whole = int(full)
        fraction = full - whole
        fixed = (shares * CASH).quantize(Decimal("0.01"))
        allocated_cost = Decimal(str(claim["allocated_cost"]))
        if (not all(v.is_finite() for v in
                    (shares, old_cost, full, fraction, fixed, allocated_cost))
                or shares <= 0 or old_cost <= 0 or not 0 < fraction < 1
                or not 0 < allocated_cost < old_cost
                or e.get("successor_whole_shares") != whole
                or str(claim["fractional_shares"]) != str(fraction)
                or str(e.get("fractional_shares")) != str(fraction)
                or Decimal(claim["fixed_cash"]) != fixed
                or Decimal(e["fixed_cash_receivable"]) != fixed):
            return False
    except (KeyError, ValueError, TypeError, InvalidOperation, OverflowError):
        return False
    return True


def _provenance(q, lock, ticker, key):
    return {"quote_at_utc": q["quote_at_utc"],
            "observed_at_utc": q["observed_at_utc"],
            "source_commit": lock["source_commit"],
            "lock_sha256": lock["lock_sha256"],
            "idempotency_key": key + ":" + ticker}


def _verified_previous_stops_only(original, current, session, lock, commission):
    """Permit later protected stops while a frozen opening BUY stayed unfilled.

    The only permissible source divergence is already-reconciled same-session
    stop/target sales, with identical pending orders, NAV and historic prefix.
    No newly frozen buys, inferred bars or edited position economics qualify.
    """
    pending = current.get("pending", {})
    if (not isinstance(pending, dict) or not pending
            or pending != original.get("pending")
            or any(order.get("side") != "buy" for order in pending.values())
            or current.get("equity") != original.get("equity")
            or current.get("nav") != original.get("nav")
            or current.get("signal_counts") != original.get("signal_counts")
            or current.get("receivables") != original.get("receivables")
            or current.get("outage_control") != original.get("outage_control")
            or current.get("paused_missing_quotes") != original.get("paused_missing_quotes")
            or current.get("events", [])[:len(original.get("events", []))] != original.get("events", [])
            or current.get("trades", [])[:len(original.get("trades", []))] != original.get("trades", [])):
        return False
    old_markers = original.get("forward_executions", {})
    markers = current.get("forward_executions", {})
    if not isinstance(old_markers, dict) or not isinstance(markers, dict):
        return False
    if any(markers.get(key) != value for key, value in old_markers.items()):
        return False
    new_keys = set(markers) - set(old_markers)
    if not new_keys or any(markers[key].get("session") != session for key in new_keys):
        return False
    try:
        summary = summarize_session_fills(
            current, original, session, lock["lock_sha256"],
            lock["source_commit"], commission)
    except (ValueError, KeyError, TypeError):
        return False
    fills = summary["fills"]
    sold = {item["ticker"] for item in fills}
    added_events = current["events"][len(original["events"]):]
    added_trades = current["trades"][len(original["trades"]):]
    if (len(sold) != len(fills) or len(fills) != len(new_keys)
            or len(added_events) != len(fills)
            or len(added_trades) != len(fills)
            or any(item["side"] != "sell" for item in fills)
            or any(event.get("reason") not in
                   ("stop_forward_observed", "target_forward_observed")
                   for event in added_events)
            or any(trade.get("reason") not in
                   ("stop_forward_observed", "target_forward_observed")
                   for trade in added_trades)
            or not sold <= set(original["positions"])):
        return False
    expected_positions = {ticker: pos for ticker, pos in original["positions"].items()
                          if ticker not in sold}
    if current.get("positions") != expected_positions:
        return False
    expected_cash = original["cash"] + sum(
        item["quantity"] * item["price"] - item["fee"] for item in fills)
    return math.isclose(current.get("cash", float("nan")), expected_cash,
                        rel_tol=1e-11, abs_tol=1e-6)


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
        outage = book.get("outage_control")
        first_future = outage.get("first_trading_session") if isinstance(outage, dict) else None
        # A completed inactive recovery remains an audit trail, NOT a permanent
        # trading ban. The published future-session boundary is already an
        # explicit release rule in classic_sp500.run._settle_book.
        # Missing/malformed boundaries and actual unsettled claims still block.
        release_known = (isinstance(first_future, str) and len(first_future) == 10
                         and first_future[4] == "-" and first_future[7] == "-"
                         and all(ch.isdigit() for i, ch in enumerate(first_future)
                                 if i not in (4, 7)))
        unresolved_outage = bool(outage) and (
            not release_known or market["session"] < first_future)
        # This narrowly verified paper receivable is not spendable cash.
        # It need not freeze unrelated *fully owned* shares or cash orders:
        # execute_frozen_open checks every BUY against book['cash'].
        unsettled_isolated = (slot in ("IL-010", "IL-012") and
                              _isolated_unsettled_kvue_claim(book, market["previous"]))
        unresolved_claims = not (_claims_actually_settled(book, market["previous"])
                                 or unsettled_isolated)
        if unresolved_claims or unresolved_outage:
            evidence[slot] = {"status": "corporate_action_review_required"
                             if unresolved_claims else "inactive_recovery_not_yet_released",
                             "fills": 0}
            continue
        markers = book.get("forward_executions", {}).copy()
        if not markers and not _source_unchanged(original, book):
            evidence[slot] = {"status": "source_changed", "fills": 0}
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
                # A missing fresh quote may block a BUY while an independently
                # observed protective stop already sold one of the OLD holdings.
                # Never reopen that buy; allow subsequent observed stops only
                # after reconciling every economic change against the frozen
                # source, the same-session markers and the unchanged cash math.
                if not _verified_previous_stops_only(
                        original, book, market["session"], lock,
                        config["execution"]["commission"]):
                    evidence[slot] = {"status": "source_changed", "fills": 0}
                    continue
                evidence[slot] = {"status": "opening_buy_unfilled_after_observed_stop",
                                  "fills": 0, "pending_open_unfilled": sorted(book["pending"])}
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
                executable = set(book["pending"]) & set(valid)
                cutoff = market["open"] + OPEN_WINDOW
                # Individual paper orders can execute without a quote for an
                # unrelated holding. Current NAV is NOT marked using a stale
                # price. If a held quote is absent, use the prior verified NAV
                # *only as a conservative ex-ante sizing reference*.
                if not executable:
                    expired = now > cutoff
                    evidence[slot] = {"status": ("opening_window_missed" if expired
                                                 else "awaiting_fresh_open_quotes"),
                                      "fills": 0, "missing": missing}
                elif now > cutoff or any(
                        datetime.fromisoformat(valid[t]["observed_at_utc"].replace("Z", "+00:00")) > cutoff
                        for t in executable):
                    evidence[slot] = {"status": "opening_window_missed", "fills": 0,
                                      "missing": missing}
                else:
                    prices = {t: {"open": v["price"]} for t, v in valid.items()}
                    provenance = {t: _provenance(q, lock, t, key) for t, q in valid.items()}
                    missing_held = sorted(set(book["positions"]) - set(valid))
                    missing_orders = sorted(set(book["pending"]) - set(valid))
                    frozen_nav = book["nav"] if missing_held else None
                    begin = len(book["events"])
                    execute_frozen_open(
                        config, name, book, market["session"], prices,
                        provenance=provenance, allow_missing_orders=True,
                        sizing_nav_override=frozen_nav)
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
                                      "operations": operations,
                                      "unfilled_open_quotes": missing_orders,
                                      "missing_held_quotes": missing_held,
                                      "sizing_reference": ("previous_verified_close_nav"
                                                           if missing_held else "observed_open_nav")}
        # Intraday stop/target rules use only a fresh OBSERVED quote crossing a
        # frozen level. A missing observation never becomes a retroactive exit.
        # A missing quote for an opening BUY cannot suppress a separately
        # observed stop/target in a position held before today's opening.
        # Never execute a protective sale for the *same* symbol as an
        # unfilled opening SELL; other independently observed stops remain live.
        pending_sell = {ticker for ticker, order in book["pending"].items()
                        if order.get("side") == "sell"}
        for ticker, position in list(book["positions"].items()):
            if ticker in pending_sell:
                continue
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
            if book["pending"]:
                evidence[slot]["pending_open_unfilled"] = sorted(book["pending"])
        if markers_written:
            book["forward_executions"] = markers
        if not lane["orders"] and not operations:
            evidence[slot] = {"status": "active_no_orders", "fills": 0}
    return ({LEDGER: updated} if any_changes else {}), evidence



def summarize_session_fills(book, frozen, session, lock_sha256, source_commit, commission):
    """Reconcile every native classic paper fill, not just its latest marker.

    For pre-existing sells, the historic trade records net proceeds but omits
    price/quantity. Recover those economically from the FROZEN held shares,
    recorded proceeds and frozen commission rate; never infer a fill from OHLC.
    """
    markers = book.get("forward_executions", {})
    events, trades = book.get("events", []), book.get("trades", [])
    if not isinstance(markers, dict) or not isinstance(events, list) or not isinstance(trades, list):
        raise ValueError("Malformed classic canonical evidence")
    if type(commission) not in (int, float) or not math.isfinite(commission) or not 0 <= commission < 1:
        raise ValueError("Invalid classic commission")
    selected = {k: m for k, m in markers.items()
                if isinstance(m, dict) and m.get("session") == session}
    grouped = {k: [] for k in selected}
    for key, marker in selected.items():
        if marker.get("lock_sha256") != lock_sha256 or marker.get("source_commit") != source_commit:
            raise ValueError("Classic marker provenance conflicts with frozen lock")
        if type(marker.get("fills_count")) is not int or marker["fills_count"] < 0:
            raise ValueError("Invalid classic marker fill count")
    sales = {}
    for trade in trades:
        if trade.get("exit_date") != session or trade.get("execution") != "forward_observed_paper":
            continue
        key = trade.get("idempotency_key")
        if not isinstance(key, str) or key in sales:
            raise ValueError("Missing/duplicate classic sell trade identity")
        sales[key] = trade
    observed = []
    seen = set()
    buys = {}
    for event in events:
        if event.get("date") != session or event.get("execution") != "forward_observed_paper":
            continue
        key = event.get("idempotency_key")
        side = event.get("type")
        ticker = event.get("ticker")
        if (not isinstance(key, str) or key in seen or side not in ("buy", "sell")
                or not isinstance(ticker, str) or not key.endswith(":" + ticker)):
            raise ValueError("Invalid/duplicate classic fill evidence")
        seen.add(key)
        owner = key.rsplit(":", 1)[0]
        if owner not in selected:
            raise ValueError("Classic fill has no matching session marker")
        if (event.get("lock_sha256") != lock_sha256 or
                event.get("source_commit") != source_commit):
            raise ValueError("Classic fill has wrong frozen provenance")
        grouped[owner].append(ticker)
        quantity = event.get("shares")
        price = event.get("price")
        fee = event.get("fee")
        if side == "buy":
            if key in sales:
                raise ValueError("A classic buy cannot match a closing trade")
            if not all(type(v) in (int, float) and math.isfinite(v) and v > 0
                       for v in (quantity, price)) or not (
                       type(fee) in (int, float) and math.isfinite(fee) and fee >= 0):
                raise ValueError("Classic buy has no verified trade economics")
            buys[ticker] = event
        else:
            trade = sales.pop(key, None)
            if trade is None or trade.get("ticker") != ticker or (
                    trade.get("lock_sha256") != lock_sha256 or
                    trade.get("source_commit") != source_commit):
                raise ValueError("Classic sale has no matching canonical trade")
            position = frozen.get("positions", {}).get(ticker)
            if position is None:
                # Support a same-session verified buy followed by a real stop.
                bought = buys.get(ticker)
                if bought is None:
                    raise ValueError("Classic sale lacks frozen or forward bought shares")
                position = {"shares": bought["shares"], "entry_date": session,
                            "cost": bought["shares"] * bought["price"] + bought["fee"]}
            if (trade.get("entry_date") != position.get("entry_date") or
                    not math.isclose(float(trade["entry_cost"]), float(position["cost"]),
                                     rel_tol=1e-10, abs_tol=1e-6)):
                raise ValueError("Classic sale does not match frozen entry cost")
            quantity = position["shares"]
            proceeds = trade.get("proceeds")
            if not all(type(v) in (int, float) and math.isfinite(v) and v > 0
                       for v in (quantity, proceeds)):
                raise ValueError("Classic sale has invalid recorded proceeds")
            price = proceeds / (quantity * (1 - commission))
            fee = quantity * price * commission
            if not math.isclose(quantity * price - fee, proceeds,
                                rel_tol=1e-11, abs_tol=1e-7):
                raise ValueError("Classic sale economics do not reconcile")
            if "shares" in event and not math.isclose(event["shares"], quantity, rel_tol=1e-10):
                raise ValueError("Classic sale quantity disagrees with event")
            if "price" in event and not math.isclose(event["price"], price, rel_tol=1e-10):
                raise ValueError("Classic sale price disagrees with event")
            if "fee" in event and not math.isclose(event["fee"], fee, rel_tol=1e-10):
                raise ValueError("Classic sale fee disagrees with event")
        observed.append((event["observed_at_utc"], key, {
            "ticker": ticker, "side": side, "quantity": quantity,
            "price": price, "fee": fee, "observed_at_utc": event["observed_at_utc"]}))
    if sales:
        raise ValueError("Classic canonical sale has no corresponding event")
    for key, marker in selected.items():
        if (len(grouped[key]) != marker["fills_count"] or
                sorted(grouped[key]) != sorted(marker.get("fill_tickers", []))):
            raise ValueError("Classic marker count/tickers disagree with canonical fills")
    ordered_markers = sorted(selected.items(),
                             key=lambda item: (item[1].get("recorded_at_utc", ""), item[0]))
    return {"fills_count": len(observed),
            "fills": [row for _, _, row in sorted(observed)],
            "native_markers": [{"key": key, "fills_count": marker["fills_count"],
                                "recorded_at_utc": marker["recorded_at_utc"]}
                               for key, marker in ordered_markers],
            "latest_marker": ordered_markers[-1][1] if ordered_markers else None}



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
        if lane.get("session_fill_reconciled"):
            source = remote(report["source_commit"], LEDGER)
            config = json.loads((ROOT / CONFIG).read_text())
            summary = summarize_session_fills(
                book["books"][name], source["books"][name], report["session"],
                report["lock_sha256"], report["source_commit"],
                config["execution"]["commission"])
            if (lane.get("fills_count") != summary["fills_count"] or
                    lane.get("fills") != summary["fills"] or
                    lane.get("native_markers") != summary["native_markers"]):
                raise ValueError(f"{slot}: published classic totals differ from canonical book")
        verified.append(slot)
    return verified
