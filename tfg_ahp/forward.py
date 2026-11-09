"""Prospective incremental TFG/AHP paper book. USD, no broker and no hindsight.

The historical weekly ledger stays in tfg_state/ledger.json. A forward_book
inside that SAME ledger owns all next-open positions, real daily marks, the
portfolio stop and an observed Friday near-close exit. Every missing session
or unobserved exit fails closed: never synthesize a historical paper fill.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tfg_ahp"))
from paper import _fractional_quantity, _validate_signal, digest

FIRST_SIGNAL = "2026-11-13"
ENGINE = "tfg_ahp_forward_observed_v1"


def _positive(value, description):
    n = float(value)
    if not math.isfinite(n) or n <= 0:
        raise ValueError("AHP invalid " + description)
    return n


def _book(state):
    book = state.get("forward_book")
    return book if isinstance(book, dict) else None


def _ensure_state(state, config):
    if state.get("config_hash") != digest(config) or state.get("currency") != "USD":
        raise ValueError("AHP canonical ledger/config mismatch")


def _event(signal, ticker, side, quantity, price, fee, day, provenance):
    return {"date": day, "ticker": ticker, "side": side,
            "quantity": quantity, "price": price, "fee": fee,
            "execution": "forward_observed_paper", **provenance[ticker]}


def open_week(state, config, day, prices, provenance, *, expected_signal):
    """Only invoked by preopen-locked shared operator clock within 30min of open."""
    _ensure_state(state, config)
    signal = state["pending_signal"]
    _validate_signal(signal)
    if (signal["asof"] != expected_signal or expected_signal < FIRST_SIGNAL or
            state["last_signal_session"] != expected_signal or
            _book(state) is not None):
        raise ValueError("Unverified or already consumed AHP weekly signal")
    if signal["status"] != "signal":
        raise ValueError("AHP has no tradable selection")
    selected = signal["selections"]
    if len({i["ticker"] for i in selected}) != len(selected):
        raise ValueError("Duplicate AHP selections")
    if set(prices) != {x["ticker"] for x in selected} or set(prices) != set(provenance):
        raise ValueError("AHP incomplete observed opening")
    policy = config["portfolio"]
    capital = float(state["nav"])
    cash = capital
    positions, operations = {}, []
    for item in selected:
        ticker = item["ticker"]
        raw = _positive(prices[ticker], "opening quote")
        price = raw * (1 + float(policy["slippage"]))
        quantity = _fractional_quantity(capital * float(item["weight"]), price, policy)
        if quantity <= 0:
            continue
        fee = quantity * price * float(policy["commission"])
        cost = quantity * price + fee
        if cost > cash + 1e-6:
            raise ValueError("AHP available cash insufficient")
        cash -= cost
        positions[ticker] = {
            "ticker": ticker, "weight_target": float(item["weight"]),
            "quantity": quantity, "entry_date": day,
            "raw_open": raw, "buy_price": price,
            "buy_fee": fee, "cost_basis": cost,
            "dividends": 0.0,
        }
        operations.append(_event(signal, ticker, "buy", quantity, price, fee,
                                 day, provenance))
    if not positions:
        raise ValueError("AHP no executable position: require explicit no-fill record")
    if cash < -1e-6:
        raise ValueError("AHP negative cash")
    result = copy.deepcopy(state)
    result["forward_book"] = {
        "engine": ENGINE, "status": "open",
        "signal_date": signal["asof"], "signal_hash": digest(signal),
        "entry_date": day, "last_mark_session": expected_signal,
        "nav_before": capital, "cash": cash, "positions": positions,
        "stop_due": False, "stop_observed_date": None,
        "equity_marks": [], "operations": operations, "closed_trade": None,
    }
    # The last *official* weekly NAV remains dated to the frozen signal.
    # Only the forward_book records the intraday cash/positions until close.
    return result, operations


def close_week(state, config, day, prices, provenance, reason):
    """Exit existing book at a contemporary observed next-open or near-close."""
    _ensure_state(state, config)
    book = _book(state)
    if not book or book.get("status") != "open" or not book["positions"]:
        raise ValueError("AHP no open forward positions")
    if reason not in ("portfolio_stop_next_open", "week_end_observed_preclose"):
        raise ValueError("AHP unsupported execution reason")
    if set(prices) != set(book["positions"]) or set(provenance) != set(prices):
        raise ValueError("Missing AHP exit observations")
    if reason == "portfolio_stop_next_open" and not book["stop_due"]:
        raise ValueError("No stop decision from previous verified close")
    if reason == "week_end_observed_preclose" and book["stop_due"]:
        raise ValueError("Pending stop cannot silently turn into weekly exit")
    result = copy.deepcopy(state)
    book = result["forward_book"]
    received = float(book["cash"])
    positions = []
    operations = []
    policy = config["portfolio"]
    for ticker, item in book["positions"].items():
        raw = _positive(prices[ticker], "observed exit")
        price = raw * (1 - float(policy["slippage"]))
        qty = item["quantity"]
        fee = qty * price * float(policy["commission"])
        proceeds = qty * price - fee
        received += proceeds
        position = copy.deepcopy(item)
        position.update({
            "exit_date": day, "exit_mode": "open" if reason == "portfolio_stop_next_open"
                                               else "observed_preclose",
            "raw_exit": raw, "sell_price": price, "sell_fee": fee,
            "net_pnl": proceeds - position["cost_basis"],
            "net_return_pct": 100 * (proceeds / position["cost_basis"] - 1),
        })
        positions.append(position)
        operations.append(_event(result["pending_signal"], ticker, "sell",
                                 qty, price, fee, day, provenance))
    nav_before = float(book["nav_before"])
    trade = {
        "signal_date": book["signal_date"], "status": "settled_forward_observed",
        "entry_date": book["entry_date"], "exit_date": day,
        "stop_observed_date": book["stop_observed_date"],
        "exit_reason": reason,
        "nav_before": nav_before, "nav_after": received,
        "return_pct": 100 * (received / nav_before - 1),
        "positions": positions,
        "execution_model": ENGINE,
        "source_evidence": list(book["operations"]) + operations,
    }
    book.update(status="closed", cash=received, positions={}, closed_trade=trade,
                exit_date=day, operations=book["operations"] + operations)
    return result, operations


def mark_close(state, config, day, previous_session, bars, *, week_end=False,
               evidence=None):
    """Mark an exact dated official close; stop becomes due only NEXT opening.

    On a last trading session of the week, the separate shared clock should
    have made a verified pre-close exit. If not, leave the book OPEN, visibly
    unresolved and prevent the weekly runner from inventing a closing fill.
    """
    _ensure_state(state, config)
    original = _book(state)
    if not original or original["status"] == "closed":
        return copy.deepcopy(state), False
    if original.get("engine") != ENGINE or original["last_mark_session"] != previous_session:
        raise ValueError("AHP missing or out-of-order daily mark")
    if day <= previous_session:
        raise ValueError("AHP cannot replay a dated close")
    positions = original["positions"]
    missing = sorted(set(positions) - set(bars))
    if missing:
        raise ValueError("AHP missing exact close: " + ",".join(missing))
    result = copy.deepcopy(state)
    book = result["forward_book"]
    if book.get("stop_due"):
        # The next-open stop has not executed. Marking further history would
        # silently move the stop to a later price; the book must stay blocked.
        raise ValueError("AHP unexecuted prior-close portfolio stop")
    nav = float(book["cash"])
    for ticker, position in book["positions"].items():
        bar = bars[ticker]
        close = _positive(bar["close"], "verified close")
        split = float(bar.get("split", 0))
        dividend = float(bar.get("dividend", 0))
        if not math.isfinite(split) or not math.isfinite(dividend) or dividend < 0 or split < 0:
            raise ValueError("AHP invalid corporate action")
        if position["entry_date"] != day:
            if split:
                position["quantity"] *= _positive(split, "split ratio")
                book["operations"].append({"type": "split", "date": day,
                                           "ticker": ticker, "ratio": split})
            if dividend:
                cash_div = position["quantity"] * dividend
                book["cash"] += cash_div
                position["dividends"] += cash_div
                book["operations"].append({"type": "dividend", "date": day,
                                           "ticker": ticker, "amount": cash_div})
        elif split or dividend:
            # A purchase at today's open is not entitled to an ex-dividend
            # or a pre-opening split. Require a separately reviewed quote.
            raise ValueError("AHP corporate action on entry session needs review")
        nav += position["quantity"] * close
    nav = float(book["cash"]) + sum(
        p["quantity"] * _positive(bars[t]["close"], "close")
        for t, p in book["positions"].items())
    if not math.isfinite(nav) or nav < 0:
        raise ValueError("Invalid marked AHP NAV")
    book["last_mark_session"] = day
    mark = {"date": day, "nav": nav, "return_pct": 100 * (nav / book["nav_before"] - 1)}
    if evidence:
        mark["source_identity"] = evidence
    book["equity_marks"].append(mark)
    if mark["return_pct"] <= 100 * float(config["portfolio"]["portfolio_stop_pct"]):
        if not week_end:
            book["stop_due"] = True
            book["stop_observed_date"] = day
        else:
            book["unresolved_exit"] = {"date": day,
                "reason": "week_end_preclose_quote_missing_no_retro_fill"}
    elif week_end:
        book["unresolved_exit"] = {"date": day,
            "reason": "week_end_preclose_quote_missing_no_retro_fill"}
    return result, True


def latest_due_session(now=None):
    import pandas_market_calendars as mcal
    now = now or datetime.now(timezone.utc)
    cal = mcal.get_calendar("XNYS")
    schedule = cal.schedule(start_date=(now-timedelta(days=15)).date(),
                            end_date=(now+timedelta(days=8)).date())
    valid = [(str(day.date()), row["market_close"].to_pydatetime())
             for day, row in schedule.iterrows()
             if now >= row["market_close"].to_pydatetime()+timedelta(minutes=90)]
    if not valid:
        return None
    day = valid[-1][0]
    nexts = [str(d.date()) for d in schedule.index if str(d.date()) > day]
    if not nexts:
        raise ValueError("No next market session")
    if now >= schedule.loc[nexts[0]]["market_open"].to_pydatetime():
        raise ValueError("Daily mark attempted after next opening")
    previous = [str(d.date()) for d in schedule.index if str(d.date()) < day][-1]
    week_end = datetime.fromisoformat(day).isocalendar()[:2] != datetime.fromisoformat(nexts[0]).isocalendar()[:2]
    return day, previous, week_end


def cli(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark-close", action="store_true")
    parser.add_argument("--state", default=str(ROOT / "tfg_state/ledger.json"))
    parser.add_argument("--config", default=str(ROOT / "tfg_ahp/config.json"))
    a = parser.parse_args(argv)
    if not a.mark_close:
        parser.error("Specify --mark-close")
    import os
    import tempfile
    from market_data.consume import canonical
    state_path = Path(a.state)
    state = json.loads(state_path.read_text(encoding="utf8"))
    config = json.loads(Path(a.config).read_text(encoding="utf8"))
    book = _book(state)
    if not book or book["status"] == "closed":
        print(json.dumps({"status": "no_open_AHP_book"}))
        return 0
    window = latest_due_session()
    if not window:
        print(json.dumps({"status": "no_completed_market_close"}))
        return 0
    day, previous, week_end = window
    if book["last_mark_session"] == day:
        print(json.dumps({"status": "already_marked", "date": day}))
        return 0
    symbols = sorted(book["positions"])
    bars, identity = canonical(day, symbols, ROOT / "market_data/snapshots")
    if symbols and (set(symbols) - set(bars) or identity["independent_symbols"]):
        raise ValueError("Missing canonical AHP raw exact-date market data")
    result, changed = mark_close(state, config, day, previous, bars,
                                 week_end=week_end, evidence=identity)
    if changed:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf8", dir=state_path.parent,
                                         delete=False) as temp:
            json.dump(result, temp, ensure_ascii=False, indent=2, sort_keys=True)
            temp.write("\n")
            tmp = temp.name
        os.replace(tmp, state_path)
    print(json.dumps({"status": "marked_close", "date": day,
                      "stop_due": result["forward_book"]["stop_due"],
                      "changed": changed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
