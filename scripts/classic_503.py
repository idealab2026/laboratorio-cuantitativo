#!/usr/bin/env python3
"""Independent 503-issuer classical MIDAS decision engine.

Retains the frozen index, original Yahoo OHLC fields and the eight published
classical variants. Evaluates ONLY dated closing bars. No transaction,
broker interaction, price publication, or private prior trading history.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta
from pathlib import Path
from statistics import pstdev

from yahoo_source import DEFAULT_UNIVERSE, yahoo_symbol, normalize, verify_universe

MODELS = {
    "IL-010": "equal_hold",
    "IL-011": "ema_rsi",
    "IL-012": "frozen_genetic",
    "IL-013": "macd",
    "IL-014": "rsi_reversal",
    "IL-015": "bollinger",
    "IL-016": "breakout_20",
    "IL-017": "breakout_55",
    "IL-018": "benchmark",
}
PARAMS = {"ema_rsi": (12, 26, 14, 30, 70),
          "frozen_genetic": (4, 22, 6, 20, 72)}
STRATEGY_RISK = {
    "ema_rsi": (.08, .15),
    "frozen_genetic": (.0903, .2367),
    "macd": (.08, .15),
    "rsi_reversal": (.08, .15),
    "bollinger": (.08, .15),
}
MAX_HOLDINGS = 8
WEIGHT_LIMIT = .15
STARTING_CAPITAL = 100000
INVEST_FRACTION = .95
COMMISSION = .001
SLIPPAGE = .0005
MIN_ELIGIBLE = 453
WARMUP = 80


def trend(values, period):
    a = 2 / (period + 1)
    last = None
    output = []
    for value in values:
        last = value if last is None else last + a * (value - last)
        output.append(last)
    return output


def momentum_oscillator(closes, period):
    if len(closes) <= period:
        return None
    differences = [right - left for left, right in zip(closes, closes[1:])]
    average_up = sum(max(delta, 0) for delta in differences[:period]) / period
    average_down = sum(max(-delta, 0) for delta in differences[:period]) / period
    for delta in differences[period:]:
        average_up = (average_up * (period - 1) + max(delta, 0)) / period
        average_down = (average_down * (period - 1) + max(-delta, 0)) / period
    if average_down == 0:
        return 50.0 if average_up == 0 else 100.0
    return 100 - 100 / (1 + average_up / average_down)


def crossed(old_left, old_right, new_left, new_right, upward):
    return (old_left <= old_right and new_left > new_right) if upward else (
        old_left >= old_right and new_left < new_right)


def action_at_close(model, bars):
    if model == "benchmark" or model == "equal_hold":
        return "buy"
    if not isinstance(bars, list) or len(bars) < WARMUP:
        return "hold"
    prices = [bar["close"] for bar in bars]
    if model in PARAMS:
        fast, slow, period, lower, upper = PARAMS[model]
        a, b = trend(prices, fast), trend(prices, slow)
        strength = momentum_oscillator(prices, period)
        if strength < lower:
            return "sell"
        if model == "frozen_genetic":
            entry = a[-2] < b[-2] and a[-1] >= b[-1]
        else:
            entry = crossed(a[-2], b[-2], a[-1], b[-1], True)
        return "buy" if entry and strength < upper else "hold"
    if model == "macd":
        short, long = trend(prices, 12), trend(prices, 26)
        diffs = [short[i] - long[i] for i in range(len(prices))]
        smoothing = trend(diffs, 9)
        prev, now = diffs[-2], diffs[-1]
        return ("buy" if crossed(prev, smoothing[-2], now, smoothing[-1], True)
                else "sell" if crossed(prev, smoothing[-2], now, smoothing[-1], False)
                else "hold")
    if model == "rsi_reversal":
        previous, current = momentum_oscillator(prices[:-1], 14), momentum_oscillator(prices, 14)
        return ("buy" if previous >= 30 > current else
                "sell" if previous <= 55 < current else "hold")
    if model == "bollinger":
        old_window, new_window = prices[-21:-1], prices[-20:]
        old_average = sum(old_window) / 20
        average = sum(new_window) / 20
        old_ceiling = old_average + 2 * pstdev(old_window)
        ceiling = average + 2 * pstdev(new_window)
        return ("buy" if crossed(prices[-2], old_ceiling, prices[-1], ceiling, True)
                else "sell" if crossed(prices[-2], old_average, prices[-1], average, False)
                else "hold")
    if model in ("breakout_20", "breakout_55"):
        entry, exit_days = (20, 10) if model == "breakout_20" else (55, 20)
        highest = max(bar["high"] for bar in bars[-entry-1:-1])
        lowest = min(bar["low"] for bar in bars[-exit_days-1:-1])
        return "buy" if prices[-1] > highest else "sell" if prices[-1] < lowest else "hold"
    raise ValueError("Unknown classic strategy")


def ordered_history(rows, session, symbol):
    """No stale closes, duplicate dates, invalid prices or post-close data."""
    if not isinstance(rows, list):
        raise ValueError("No historic Yahoo bars")
    normalized = []
    previous = None
    for row in rows:
        day = row.get("date") if isinstance(row, dict) else None
        if not isinstance(day, str) or day > session:
            raise ValueError("Future or invalid session in historical series")
        if previous is not None and day <= previous:
            raise ValueError("Historic sessions must be strictly increasing")
        normalized.append(normalize(symbol, day, row))
        previous = day
    if len(normalized) < WARMUP or previous != session:
        raise ValueError("Insufficient history or no current dated closing bar")
    return normalized[-300:]


def decisions(history, session, *, universe=None):
    """Only source-complete 503-denominator research decisions; no fills."""
    manifest = json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
    constituents = verify_universe(universe if universe is not None else manifest["symbols"])
    if set(history) - (set(constituents) | {"SPY"}):
        raise ValueError("Unknown foreign market symbol")
    usable = {}
    missing = {}
    for symbol in constituents:
        try:
            usable[symbol] = ordered_history(history.get(symbol), session, symbol)
        except (ValueError, TypeError):
            missing[symbol] = "missing_or_short_dated_ohlc"
    if len(usable) < MIN_ELIGIBLE:
        raise ValueError(f"Classic universe coverage insufficient: {len(usable)}/503")
    if "SPY" not in history:
        raise ValueError("SPY benchmark absent")
    ordered_history(history["SPY"], session, "SPY")
    ranked = {}
    for slot,model in MODELS.items():
        if model == "benchmark":
            ranked[slot] = [{"ticker": "SPY", "action": "buy", "momentum21": None}]
            continue
        candidates = []
        for symbol,rows in usable.items():
            signal = action_at_close(model, rows)
            if signal == "hold":
                continue
            # Frozen sorting: descending last 21-session price momentum,
            # lexical tie-break, never future labels or trained scores.
            value = rows[-1]["close"] / rows[-22]["close"] - 1
            candidates.append({"ticker": symbol,"action": signal,"momentum21": value})
        ranked[slot] = sorted(candidates, key=lambda x: (-x["momentum21"], x["ticker"]))
    return {"session":session,"market":"XNYS","source":"Yahoo/yfinance raw daily closes",
            "denominator":len(constituents),"eligible":len(usable),
            "missing":missing,"strategies":ranked,
            "timing":"closing_decision_for_next_exchange_open",
            "status":"RESEARCH_SIGNALS_ONLY_NOT_EXECUTED"}


def frozen_intents(report, existing):
    """Per-method pending buys/sells, frozen after close, never fills."""
    if report.get("status") != "RESEARCH_SIGNALS_ONLY_NOT_EXECUTED":
        raise ValueError("Source decision report not verified")
    if set(existing) != set(MODELS):
        raise ValueError("Untrusted classic portfolios")
    orders = {}
    for slot,model in MODELS.items():
        held = existing[slot]
        limit = 503 if model == "equal_hold" else MAX_HOLDINGS
        if not isinstance(held, list) or len(held) > limit or len(set(held)) != len(held):
            raise ValueError("Invalid frozen holdings")
        owns = set(held)
        if model == "benchmark":
            orders[slot] = [{"ticker":"SPY","side":"buy","signalAt":report["session"]}] if "SPY" not in owns else []
            continue
        if model == "equal_hold":
            orders[slot] = [{"ticker":item["ticker"],"side":"buy","signalAt":report["session"]}
                            for item in report["strategies"][slot]
                            if item["action"]=="buy" and item["ticker"] not in owns]
            continue
        ranked = report["strategies"][slot]
        sells = [item["ticker"] for item in ranked if item["action"]=="sell" and item["ticker"] in owns]
        entries = [item["ticker"] for item in ranked if item["action"]=="buy" and item["ticker"] not in owns]
        slots = MAX_HOLDINGS - len(owns) + len(sells)
        orders[slot] = ([{"ticker":s,"side":"sell","signalAt":report["session"]} for s in sells] +
                        [{"ticker":s,"side":"buy","signalAt":report["session"]}
                         for s in entries[:slots]])
    return orders


def yahoo_historical_panel(session, *, rights_attested=False):
    """Isolated on-runner Yahoo 420-day RAW history, never stored in public Git."""
    if not rights_attested or os.environ.get("MIDAS_YAHOO_RIGHTS_CONFIRMED") != "true":
        raise ValueError("Institutional Yahoo usage rights not attested")
    import yfinance as yf
    manifest = json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
    symbols = verify_universe(manifest["symbols"]) + ["SPY"]
    after = (date.fromisoformat(session) + timedelta(days=1)).isoformat()
    before = (date.fromisoformat(session) - timedelta(days=420)).isoformat()
    history = {}
    for k in range(0, len(symbols), 40):
        batch = symbols[k:k+40]
        mapping = {name: yahoo_symbol(name, session) for name in batch}
        frame = yf.download(list(mapping.values()), start=before, end=after,
                            interval="1d", auto_adjust=False, actions=True,
                            group_by="ticker", threads=False, progress=False)
        for identifier,vendor in mapping.items():
            try:
                part = frame[vendor] if hasattr(frame.columns, "levels") else frame
                values = []
                for when,item in part.iterrows():
                    day = when.strftime("%Y-%m-%d")
                    if day > session:
                        raise ValueError("Future Yahoo bar")
                    if any(not math.isfinite(float(item.get(k, float("nan")))) for k in
                           ("Open","High","Low","Close","Volume")):
                        continue
                    values.append({"date":day, "open":float(item["Open"]),
                        "high":float(item["High"]),"low":float(item["Low"]),
                        "close":float(item["Close"]),"volume":float(item["Volume"]),
                        "dividend":float(item.get("Dividends",0)),
                        "split":float(item.get("Stock Splits",0))})
                history[identifier] = values
            except (KeyError, TypeError, ValueError):
                continue
    return history


def preflight():
    manifest = json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
    assert len(verify_universe(manifest["symbols"])) == 503
    assert len(MODELS) == 9 and set(MODELS)=={
        "IL-010","IL-011","IL-012","IL-013","IL-014","IL-015",
        "IL-016","IL-017","IL-018"}
    return {"status":"source_gated_classic_503_engine","models":len(MODELS),
            "universe":503,"orders_placed":0,"raw_prices_published":False}


if __name__=="__main__":
    print(json.dumps(preflight(),sort_keys=True))
