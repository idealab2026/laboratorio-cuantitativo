"""Native TimesFM EUR paper operations; same weight, FX and fee math as engines.

Strictly observed USD quotes, pre-frozen prior-XNYS EURUSD entry reference,
fresh contemporaneous FX at exit. Only the official weekly/daily books mutate.
"""
from __future__ import annotations
import math
from timesfm_strategy import run as core

CUTOVER = "2026-11-10"


def _buy_event(family, day, ticker, qty, entry, fx, evidence):
    if family == "weekly":
        return {"date": day, "ticker": ticker, "event": "buy",
                "shares": qty, "price_eur": entry, "fx": fx,
                "execution": "forward_observed_paper", **evidence}
    return {"date": day, "type": "buy", "ticker": ticker,
            "shares": qty, "entry_eur": entry, "fx": fx,
            "execution": "forward_observed_paper", **evidence}


def observed_open(book, policy, family, day, previous, prices, fx_entry, provenance, *, book_name):
    """Apply original engine's pending entries, using only timely observations."""
    fx_entry = core._positive(fx_entry, "previous exact FX close")
    if family not in ("weekly", "daily"):
        raise ValueError("Unknown TimesFM family")
    if family == "weekly" and book_name not in ("timesfm", "benchmark_spy"):
        raise ValueError("Unknown TimesFM weekly lane")
    if family == "daily" and book_name not in ("timesfm_daily", "benchmark_spy"):
        raise ValueError("Unknown TimesFM daily lane")
    pending = book["pending"]
    if (not pending or any(order["signal_date"] != previous for order in pending) or
            len({o["ticker"] for o in pending}) != len(pending) or
            set(prices) != {o["ticker"] for o in pending} or
            set(prices) != set(provenance)):
        raise ValueError("TimesFM opening orders not exactly frozen")
    n = len(pending)
    budget = min(float(book["nav"]) * policy["capital_fraction"] / n,
                 float(book["nav"]) * (policy["capital_fraction"]
                                      if book_name == "benchmark_spy"
                                      else policy["max_weight"]))
    operations = []
    for order in pending:
        t = order["ticker"]
        raw = core._positive(prices[t], "observed USD opening")
        entry = raw / fx_entry * (1 + policy["slippage"])
        qty = core._qty(budget, entry, policy)
        if qty <= 0:
            book["events"].append({"date": day, "ticker": t,
                                   "event": "unfilled_below_min_notional",
                                   "execution": "forward_observed_paper"})
            continue
        cost = entry * qty * (1 + policy["commission"])
        if cost > book["cash"] + 1e-7 or t in book["positions"]:
            raise ValueError("TimesFM insufficient EUR cash or duplicate")
        book["cash"] -= cost
        position = {
            "shares": qty, "entry_date": day, "signal_date": previous,
            "entry_price_eur": entry, "cost_eur": cost,
            "dividends_eur": 0.0,
        }
        position["entry_fx" if family == "weekly" else "fx_at_entry"] = fx_entry
        book["positions"][t] = position
        book["events"].append(_buy_event(family, day, t, qty, entry, fx_entry, provenance[t]))
        operations.append({
            "ticker": t, "side": "buy", "quantity": qty,
            "price": entry, "fee": cost-qty*entry,
            "currency": "EUR", "fx_usd_per_eur": fx_entry,
            "observed_at_utc": provenance[t]["observed_at_utc"],
        })
    book["pending"] = []
    return operations


def observed_exit(book, policy, family, day, prices, fx_exit, provenance):
    """Close only TimesFM strategy positions, never passive SPY benchmarks."""
    fx_exit = core._positive(fx_exit, "contemporaneous FX exit")
    expected = set(book["positions"])
    if not expected or expected != set(prices) or expected != set(provenance):
        raise ValueError("TimesFM exit must observe all held symbols")
    operations = []
    for t, position in list(book["positions"].items()):
        raw = core._positive(prices[t], "observed USD exit")
        sell = raw / fx_exit * (1 - policy["slippage"])
        qty = position["shares"]
        fee = qty * sell * policy["commission"]
        proceeds = qty * sell - fee
        book["cash"] += proceeds
        pnl = proceeds + position["dividends_eur"] - position["cost_eur"]
        if family == "weekly":
            book["trades"].append({
                "ticker": t, "entry_date": position["entry_date"],
                "exit_date": day, "signal_date": position["signal_date"],
                "shares_at_exit": qty, "buy_cost_eur": position["cost_eur"],
                "sell_proceeds_eur": proceeds, "dividends_eur": position["dividends_eur"],
                "net_pnl_eur": pnl, "execution": "forward_observed_preclose",
                "fx_usd_per_eur": fx_exit, **provenance[t],
            })
            book["events"].append({
                "date": day, "ticker": t, "event": "sell", "price_eur": sell,
                "execution": "forward_observed_preclose", **provenance[t],
            })
        elif family == "daily":
            book["trades"].append({
                "ticker": t, "signal_date": position["signal_date"],
                "entry_date": position["entry_date"], "exit_date": day,
                "shares": qty, "entry_cost_eur": position["cost_eur"],
                "sale_eur": proceeds, "net_pnl_eur": pnl,
                "execution": "forward_observed_preclose",
                "fx_usd_per_eur": fx_exit, **provenance[t],
            })
            book["events"].append({
                "date": day, "type": "sell", "ticker": t,
                "price_eur": sell,
                "execution": "forward_observed_preclose", **provenance[t],
            })
        else:
            raise ValueError("Unknown family")
        operations.append({
            "ticker": t, "side": "sell", "quantity": qty,
            "price": sell, "fee": fee,
            "currency": "EUR", "fx_usd_per_eur": fx_exit,
            "observed_at_utc": provenance[t]["observed_at_utc"],
        })
    book["positions"] = {}
    return operations
