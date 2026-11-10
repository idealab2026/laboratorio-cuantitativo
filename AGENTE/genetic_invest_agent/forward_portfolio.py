"""Prospective, next-session-open paper ledger for the original S&P 500 agent.

Prices are unadjusted OHLC. This is an execution model, not broker fills.
The legacy same-close journal is intentionally never read or modified here.
"""

import json
import math
import os
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

INITIAL_CAPITAL = 100_000.0
COMMISSION = 0.001
SLIPPAGE = 0.0005
MAX_WEIGHT = 0.15
MIN_ORDER = 10.0
SHARE_PRECISION = 6
# The 29 Sep–07 Oct forward cohort is immutable after its 08 Oct publication failure.
# A new prospective cohort is independent: no positions, cash or returns carry over.
ARCHIVED_FILE_NAME = "diario_portfolio_forward.json"
FILE_NAME = "diario_portfolio_forward_2026-10-12.json"
EPOCH_FIRST_SESSION = "2026-10-12"


def _positive(value, name):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} inválido")
    return number


def _fractional_shares(budget, fill):
    """Size a fractional position without ever exceeding the allocated budget."""
    budget = _positive(budget, "presupuesto")
    fill = _positive(fill, "precio")
    raw = budget / (fill * (1 + COMMISSION))
    scale = 10 ** SHARE_PRECISION
    shares = math.floor(raw * scale) / scale
    if shares <= 0 or shares * fill < MIN_ORDER:
        return 0.0
    return shares


def _bar(frame, session):
    if isinstance(frame, pd.DataFrame) and isinstance(frame.columns, pd.MultiIndex):
        raise ValueError("Se esperaba una sola serie de cotizaciones")
    matches = frame.loc[frame.index.strftime("%Y-%m-%d") == session]
    if len(matches) != 1:
        raise RuntimeError(f"Falta vela diaria sin ajustar: {session}")
    row = matches.iloc[0]
    if "Dividends" not in row or "Stock Splits" not in row:
        raise ValueError("Faltan acciones corporativas en la fuente")
    bar = {name: _positive(row[name], name) for name in ("Open", "High", "Low", "Close")}
    if bar["Low"] > min(bar["Open"], bar["Close"]) or bar["High"] < max(bar["Open"], bar["Close"]):
        raise ValueError("OHLC incoherente")
    bar["Dividends"] = float(row["Dividends"])
    bar["Stock Splits"] = float(row["Stock Splits"])
    if not all(math.isfinite(bar[key]) and bar[key] >= 0 for key in ("Dividends", "Stock Splits")):
        raise ValueError("Acción corporativa inválida")
    return bar


def fetch_session(session, tickers, previous=None):
    """Require exactly one elapsed SPY market session; never silently skip a fill."""
    start = previous or (date.fromisoformat(session) - timedelta(days=10)).isoformat()
    end = (date.fromisoformat(session) + timedelta(days=1)).isoformat()
    reference = yf.download("SPY", start=start, end=end, auto_adjust=False,
                            actions=True, progress=False, threads=False, multi_level_index=False)
    sessions = [day for day in reference.index.strftime("%Y-%m-%d")
                if (day == session if previous is None else day > previous)]
    if sessions != [session]:
        raise RuntimeError(f"Sesión incompleta u omitida: esperada {session}, SPY={sessions}")
    bars = {}
    for ticker in sorted(set(tickers)):
        frame = yf.download(ticker, start=session, end=end, auto_adjust=False,
                            actions=True, progress=False, threads=False, multi_level_index=False)
        try:
            bars[ticker] = _bar(frame, session)
        except Exception as exc:
            raise RuntimeError(f"Sin OHLC válido para {ticker} en {session}; diario intacto") from exc
    return bars


def latest_completed_session(today):
    start = (date.fromisoformat(today) - timedelta(days=10)).isoformat()
    reference = yf.download("SPY", start=start, end=today, auto_adjust=False,
                            actions=True, progress=False, threads=False, multi_level_index=False)
    if reference.empty:
        raise RuntimeError("No hay vela SPY completada; diario intacto")
    session = reference.index[-1].strftime("%Y-%m-%d")
    if (date.fromisoformat(today) - date.fromisoformat(session)).days > 5:
        raise RuntimeError("La última sesión SPY está obsoleta; diario intacto")
    return session


def ensure_before_next_open(signal_session, now=None):
    """Conservatively reject a delayed run after the next weekday NY open."""
    ny = (now or datetime.now(ZoneInfo("America/New_York"))).astimezone(ZoneInfo("America/New_York"))
    if ny.date() > date.fromisoformat(signal_session) and ny.weekday() < 5 and ny.time() >= time(9, 30):
        raise RuntimeError("La siguiente apertura de Nueva York ya pasó; no se registran señales retrospectivas")


def _new_state():
    return {"schema_version": 1, "model": "next_open_raw_ohlc_v1", "initial_capital": INITIAL_CAPITAL,
            "cash": INITIAL_CAPITAL, "positions": {}, "pending": {"buys": {}, "sells": []},
            "trades": [], "equity_history": {}, "last_session": None,
            "execution": {"fractional_shares": True, "share_precision": SHARE_PRECISION,
                          "min_order": MIN_ORDER}}


def load(path):
    path = Path(path)
    if not path.exists():
        return _new_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(state, dict) or state.get("schema_version") != 1 or
            state.get("model") != "next_open_raw_ohlc_v1" or
            state.get("initial_capital") != INITIAL_CAPITAL or
            not isinstance(state.get("positions"), dict) or
            not isinstance(state.get("pending"), dict) or
            not isinstance(state.get("trades"), list) or
            not isinstance(state.get("equity_history"), dict) or
            (state.get("last_session") is not None and state["last_session"] not in state["equity_history"]) or
            not isinstance(state.get("cash"), (int, float)) or
            not math.isfinite(state["cash"]) or state["cash"] < 0):
        raise ValueError("Diario prospectivo inválido; no se reinicia")
    state.setdefault("execution", {"fractional_shares": True, "share_precision": SHARE_PRECISION,
                                   "min_order": MIN_ORDER})
    return state


def save(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".forward-", suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            json.dump(state, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


FORWARD_CUTOVER_SESSION = "2026-11-10"


def settle_observed_close(state, session, bars, buy_signals, sell_signals,
                          stop_pct=None, target_pct=None):
    """Mark-only state transition after the shared real-time executor cutover.

    Daily candle OHLC is strictly for official valuation/corporate actions.
    No same-day opening or high/low-derived fill may ever be recorded here.
    """
    if not state.get("last_session") or session <= state["last_session"]:
        raise ValueError("Genetic forward mark is not newer than recorded session")
    for weight in buy_signals.values():
        if not 0 < _positive(weight, "weight") <= MAX_WEIGHT:
            raise ValueError("Invalid genetic weight")
    if buy_signals and (stop_pct is None or target_pct is None or
                        not 0 < _positive(stop_pct, "stop") < 1 or
                        not 0 < _positive(target_pct, "target") < 1):
        raise ValueError("Future genetic stop or target invalid")
    result = json.loads(json.dumps(state))
    pending = result["pending"]
    if pending["buys"] or pending["sells"]:
        result.setdefault("outage_events", []).append({
            "date": session, "type": "missed_forward_open",
            "reason": "no_verified_native_opening_fill",
            "buys": sorted(pending["buys"]), "sells": sorted(pending["sells"]),
        })
    preopen = result.get("preopen_inventory", {}).get(session, {})
    if not isinstance(preopen, dict):
        raise ValueError("Invalid genetic preopening inventory")
    required = set(result["positions"]) | set(preopen)
    if required - set(bars):
        raise ValueError("Missing verified exact-date genetic closing bar")
    cash = result["cash"]
    for ticker, shares in preopen.items():
        if ticker in result["positions"]:
            continue
        bar = bars[ticker]
        split = float(bar.get("Stock Splits", 0))
        dividend = float(bar.get("Dividends", 0))
        if split:
            raise ValueError("Genetic sold ex-date split requires audited reconciliation")
        if not math.isfinite(dividend) or dividend < 0:
            raise ValueError("Genetic sold ex-date dividend invalid")
        if dividend:
            accrued = float(shares) * dividend
            cash += accrued
            result.setdefault("outage_events", []).append({
                "date": session, "type": "observed_dividend_after_sale",
                "ticker": ticker, "gross_usd": accrued,
            })
    for ticker, position in result["positions"].items():
        row = bars[ticker]
        close = _positive(row["Close"], "close")
        high = _positive(row["High"], "high")
        low = _positive(row["Low"], "low")
        opened = _positive(row["Open"], "open")
        if low > min(opened, close) or high < max(opened, close):
            raise ValueError("Invalid genetic daily OHLC")
        split = float(row.get("Stock Splits", 0))
        dividend = float(row.get("Dividends", 0))
        if not all(math.isfinite(v) and v >= 0 for v in (split, dividend)):
            raise ValueError("Invalid genetic corporate action")
        if position.get("entry_date") == session and (split or dividend):
            raise ValueError("Genetic entry-date corporate action needs review")
        if split:
            # Split is performed exactly once at its ex-date, never by the
            # live quote clock. Unusual raw prices during the session must
            # therefore not trigger stops without a reviewed split.
            position["shares"] *= _positive(split, "split ratio")
            position["entry"] /= split
            position["sl"] /= split
            position["tp"] /= split
        if dividend:
            value = position["shares"] * dividend
            cash += value
            result.setdefault("outage_events", []).append({
                "date": session, "type": "observed_dividend",
                "ticker": ticker, "gross_usd": value,
            })
        if low <= position["sl"] or high >= position["tp"]:
            result.setdefault("outage_events", []).append({
                "date": session, "type": "unexecuted_intraday_level",
                "ticker": ticker,
                "reason": "daily_extreme_not_a_causal_fill",
            })
    result["cash"] = cash
    result["pending"] = {
        "buys": {ticker: {
            "weight": float(weight), "stop_pct": float(stop_pct),
            "target_pct": float(target_pct),
        } for ticker, weight in buy_signals.items() if ticker not in result["positions"]},
        "sells": sorted(set(sell_signals) & set(result["positions"])),
    }
    equity = cash + sum(pos["shares"] * _positive(bars[t]["Close"], "close")
                        for t, pos in result["positions"].items())
    if not math.isfinite(equity) or equity < 0:
        raise ValueError("Invalid genetic mark NAV")
    result["equity_history"][session] = equity
    result["last_session"] = session
    return result


def settle(state, session, bars, buy_signals, sell_signals, stop_pct=None, target_pct=None):
    """Return new state. Pending orders from prior close execute at this open."""
    if state["last_session"] == session:
        return state
    if state["last_session"] and session <= state["last_session"]:
        raise ValueError("Sesión anterior al diario")
    if session >= FORWARD_CUTOVER_SESSION:
        return settle_observed_close(state, session, bars, buy_signals,
                                     sell_signals, stop_pct, target_pct)
    required = set(state["positions"]) | set(state["pending"]["buys"]) | set(state["pending"]["sells"])
    if required - bars.keys():
        raise RuntimeError("Faltan cotizaciones para cartera u órdenes pendientes")
    if buy_signals and (stop_pct is None or target_pct is None):
        raise ValueError("Se requieren SL/TP para compras pendientes")
    if buy_signals and (not 0 < _positive(stop_pct, "stop") < 1 or
                        not 0 < _positive(target_pct, "objetivo") < 1):
        raise ValueError("SL/TP fuera de rango")
    for weight in buy_signals.values():
        if not 0 < _positive(weight, "peso") <= MAX_WEIGHT:
            raise ValueError("Peso fuera de rango")
    next_state = json.loads(json.dumps(state))
    positions = next_state["positions"]
    trades = next_state["trades"]

    def sale(ticker, raw_price, reason):
        position = positions.pop(ticker)
        fill = raw_price * (1 - SLIPPAGE)
        gross = position["shares"] * fill
        next_state["cash"] += gross * (1 - COMMISSION)
        trades.append({"session": session, "ticker": ticker, "side": "SELL", "reason": reason,
                       "shares": position["shares"], "fill": fill, "fee": gross * COMMISSION})

    # Ex-date entitlement belongs to positions held before today's opening.
    for ticker, position in list(positions.items()):
        bar = bars[ticker]
        if bar["Stock Splits"]:
            ratio = bar["Stock Splits"]
            position["shares"] *= ratio
            position["entry"] /= ratio
            position["sl"] /= ratio
            position["tp"] /= ratio
        if bar["Dividends"]:
            next_state["cash"] += position["shares"] * bar["Dividends"]
        if bar["Open"] <= position["sl"]:
            sale(ticker, bar["Open"], "STOP_GAP")
        elif bar["Open"] >= position["tp"]:
            sale(ticker, bar["Open"], "TARGET_GAP")

    for ticker in next_state["pending"]["sells"]:
        if ticker in positions:
            sale(ticker, bars[ticker]["Open"], "SIGNAL")

    open_equity = next_state["cash"] + sum(pos["shares"] * bars[ticker]["Open"] for ticker, pos in positions.items())
    for ticker, order in sorted(next_state["pending"]["buys"].items()):
        if ticker in positions or any(trade["ticker"] == ticker and trade["session"] == session for trade in trades):
            continue
        bar = bars[ticker]
        fill = bar["Open"] * (1 + SLIPPAGE)
        budget = min(open_equity * min(_positive(order["weight"], "peso"), MAX_WEIGHT),
                     next_state["cash"] * 0.95)
        shares = _fractional_shares(budget, fill)
        if shares <= 0:
            continue
        gross = shares * fill
        fee = gross * COMMISSION
        next_state["cash"] -= gross + fee
        positions[ticker] = {"shares": shares, "entry": fill,
                             "sl": fill * (1 - _positive(order["stop_pct"], "stop")),
                             "tp": fill * (1 + _positive(order["target_pct"], "objetivo"))}
        trades.append({"session": session, "ticker": ticker, "side": "BUY", "reason": "SIGNAL",
                       "shares": shares, "fill": fill, "fee": fee})

    # With daily candles the order of intraday extremes is unknown: stop wins ties.
    for ticker, position in list(positions.items()):
        bar = bars[ticker]
        if bar["Low"] <= position["sl"]:
            sale(ticker, position["sl"], "STOP")
        elif bar["High"] >= position["tp"]:
            sale(ticker, position["tp"], "TARGET")

    next_state["pending"] = {
        "buys": {ticker: {"weight": float(weight),
                           "stop_pct": float(stop_pct), "target_pct": float(target_pct)}
                 for ticker, weight in buy_signals.items() if ticker not in positions},
        "sells": sorted(set(sell_signals) & set(positions)),
    }
    missing = set(positions) - bars.keys()
    if missing:
        raise RuntimeError("Falta precio de cierre de una posición")
    equity = next_state["cash"] + sum(pos["shares"] * bars[ticker]["Close"] for ticker, pos in positions.items())
    if not math.isfinite(equity) or equity < 0:
        raise ValueError("Patrimonio inválido")
    next_state["equity_history"][session] = equity
    next_state["last_session"] = session
    return next_state


def mark_inactive_sessions(state, sessions, quote_loader, *, recorded_at, reviews=None):
    """Value retained holdings through a disclosed outage, without past fills.

    The caller supplies every XNYS session from the last recorded close and
    SHA-verified common bars. Stops crossed while the executor was inactive are
    evidence of missed execution, never retrospectively profitable exits.
    """
    if not state.get("last_session") or state["last_session"] not in state["equity_history"]:
        raise ValueError("Inactive recovery requires an existing canonical portfolio")
    if not sessions:
        return json.loads(json.dumps(state))
    if (sessions != sorted(set(sessions)) or sessions[0] <= state["last_session"]
            or any(date.fromisoformat(day).isoformat() != day for day in sessions)):
        raise ValueError("Inactive sessions must be new, unique and ordered")
    stamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Inactive recovery needs the actual recording timestamp")
    result = json.loads(json.dumps(state))
    expired = json.loads(json.dumps(result["pending"]))
    result["pending"] = {"buys": {}, "sells": []}
    events = result.setdefault("outage_events", [])
    for day in sessions:
        bars, identity = quote_loader(day)
        if (identity.get("session") != day or
                any(not isinstance(identity.get(k), str) or len(identity[k]) != 64
                    or any(c not in "0123456789abcdef" for c in identity[k])
                    for k in ("snapshot_sha256", "effective_sha256"))):
            raise ValueError("Inactive mark lacks exact immutable common source identity")
        if not set(result["positions"]) <= set(bars):
            raise ValueError("Inactive mark lacks a held position's exact dated bar")
        for ticker, position in result["positions"].items():
            bar = bars[ticker]
            o, h, l, c = (_positive(bar[k], k) for k in ("Open", "High", "Low", "Close"))
            if l > min(o, c) or h < max(o, c):
                raise ValueError("Inactive recovery OHLC inconsistent")
            shares = _positive(position["shares"], "shares")
            sl, tp = _positive(position["sl"], "stop"), _positive(position["tp"], "target")
            split, dividend = float(bar["Stock Splits"]), float(bar["Dividends"])
            if not all(math.isfinite(v) and v >= 0 for v in (split, dividend)):
                raise ValueError("Inactive recovery corporate action invalid")
            if split:
                raise ValueError("Inactive recovery split requires issuer review")
            if dividend:
                # Share the exact issuer-versus-rounded-vendor review already
                # used by the other original paper books. Raw input is intact.
                from classic_sp500.recovery import reviewed_dividend_action
                action = reviewed_dividend_action(reviews or {}, ticker, day, dividend)
                if not action:
                    raise ValueError("Inactive recovery dividend requires issuer review")
                amount = shares * float(action.get("issuer_amount", dividend))
                result["cash"] += amount
                events.append({"date": day, "type": "outage_dividend_accrual",
                    "ticker": ticker, "amount": amount, "source_url": action["source_url"],
                    "recognition": "existing_paper_ex_session_model",
                    "recorded_at_utc": recorded_at})
            crossed = "stop" if l <= sl else "target" if h >= tp else None
            if crossed:
                events.append({"date": day, "type": "unexecuted_during_outage",
                    "ticker": ticker, "trigger": crossed, "stop": sl, "target": tp,
                    "low": l, "high": h, "quote_identity": identity,
                    "recorded_at_utc": recorded_at})
        equity = result["cash"] + sum(pos["shares"] * float(bars[ticker]["Close"])
                                        for ticker, pos in result["positions"].items())
        if not math.isfinite(equity) or equity < 0:
            raise ValueError("Inactive recovery NAV invalid")
        result["equity_history"][day] = equity
        result.setdefault("equity_provenance", {})[day] = {
            "kind": "inactive_holding_mark_only", "quote_identity": identity,
            "recorded_at_utc": recorded_at, "trades_executed": 0}
        result.setdefault("inactive_sessions", []).append(day)
        result["last_session"] = day
    events.append({"date": sessions[-1], "type": "outage_valuations_reconciled_no_trades",
                   "sessions": sessions, "expired_unfilled_orders": expired,
                   "recorded_at_utc": recorded_at})
    return result


def _freeze_after_inactive_close(state, buy_signals, sell_signals, stop_pct, target_pct):
    if buy_signals and (stop_pct is None or target_pct is None or
            not 0 < _positive(stop_pct, "stop") < 1 or
            not 0 < _positive(target_pct, "target") < 1):
        raise ValueError("Future pending buys require valid SL/TP")
    for weight in buy_signals.values():
        if not 0 < _positive(weight, "weight") <= MAX_WEIGHT:
            raise ValueError("Future pending weight invalid")
    state["pending"] = {
        "buys": {ticker: {"weight": float(weight), "stop_pct": float(stop_pct),
                            "target_pct": float(target_pct)}
                 for ticker, weight in buy_signals.items() if ticker not in state["positions"]},
        "sells": sorted(set(sell_signals) & set(state["positions"]))}
    return state


def run(path, session, buy_signals, sell_signals, stop_pct=None, target_pct=None):
    state = load(path)
    if state["last_session"] == session:
        print(f"Diario prospectivo ya actualizado para {session}; sin duplicar operaciones")
        return state
    ensure_before_next_open(session)
    if state["last_session"] is None and session != EPOCH_FIRST_SESSION:
        raise RuntimeError("La campaña nueva exige su primera señal el 2026-10-12; "
                           "no se salta esa sesión ni se reconstruye retrospectivamente")
    # From cutover, pending entries may be valid signals but NOT executed
    # prices; only held positions need closing bars for a prospective mark.
    required = ((set(state["positions"]) |
                 set(state.get("preopen_inventory", {}).get(session, {})))
                if session >= FORWARD_CUTOVER_SESSION
                else set(state["positions"]) | set(state["pending"]["buys"])
                     | set(state["pending"]["sells"]))
    bars = fetch_session(session, required, state["last_session"])
    first_trading = state.get("outage_control", {}).get("first_trading_session")
    if first_trading and session < first_trading:
        # If recovery was published after today's open, this partial day also
        # remains inactive. Only its fresh closing signal targets a FUTURE open.
        from session_gate import common_quotes
        bars, identity = common_quotes(Path(__file__).resolve().parents[2], session)
        reviews = json.loads((Path(__file__).resolve().parents[2] /
                              "market_data/corporate_action_reviews.json").read_text())
        updated = mark_inactive_sessions(state, [session], lambda day: (bars, identity),
            recorded_at=datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"), reviews=reviews)
        updated = _freeze_after_inactive_close(updated, buy_signals, sell_signals, stop_pct, target_pct)
    else:
        updated = settle(state, session, bars, buy_signals, sell_signals, stop_pct, target_pct)
    save(path, updated)
    print(f"Diario prospectivo {session}: ${updated['equity_history'][session]:,.2f}; "
          f"{len(updated['trades']) - len(state['trades'])} operaciones; "
          f"{len(updated['pending']['buys'])} compras pendientes")
    return updated
