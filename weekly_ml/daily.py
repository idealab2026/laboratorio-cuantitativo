"""Prospective daily paper bookkeeping for frozen WEEKLY ML signals.

The historical weekly ledger is never mutated here. No past open is replayed
when the daily execution window was missed. All prices are RAW unadjusted OHLC.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from market_data.consume import canonical

from paper import BENCHMARKS, _fractional_quantity, _select, digest, strategy_ids

FIRST_DAILY_SIGNAL = "2026-10-09"
ENGINE_VERSION = "weekly_ml_daily_next_open_v1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        json.dump(value, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def _check_config(state, config):
    if (state.get("schema_version") != 1
            or state.get("engine") != ENGINE_VERSION
            or state.get("config_hash") != digest(config)
            or set(state.get("strategies", {})) != set(strategy_ids(config))):
        raise ValueError("Diario daily ML ajeno a campaña o configuración")


def freeze_signal(config, forecast, state=None):
    """Called AFTER Friday's frozen weekly forecast was saved, before next open."""
    day = forecast["asof"]
    if day < FIRST_DAILY_SIGNAL:
        return state, False
    if forecast.get("config_hash") != digest(config):
        raise ValueError("Forecast weekly ML de otra configuración")
    if set(forecast.get("models", {})) != set(config["models"]):
        raise ValueError("Forecast weekly ML incompleto")
    forecast_hash = digest(forecast)
    if state is not None:
        _check_config(state, config)
        previous_signal = state["last_signal_session"]
        if day < previous_signal:
            raise ValueError("No se pueden congelar señales antiguas")
        if day == previous_signal and state["signal_hash"] != forecast_hash:
            raise ValueError("La señal congelada fue revisada")
        if state["last_session"] != day:
            if day == previous_signal:
                return state, False
            raise ValueError("Falta liquidar o valorar el cierre anterior a la nueva señal")
        result = copy.deepcopy(state)
    else:
        previous_signal = None
        capital = float(config["paper_policy"]["capital"])
        result = {
            "schema_version": 1, "engine": ENGINE_VERSION,
            "config_hash": digest(config), "currency": config["currency"],
            "initial_capital": capital, "first_session": day,
            "last_session": day, "strategies": {},
            "gap_sessions": [], "execution_model": "paper_open_recorded_after_session_close"
        }
        for name in strategy_ids(config):
            result["strategies"][name] = {
                "cash": capital, "nav": capital, "positions": {},
                "pending": [], "trades": [], "events": [],
                "equity": [{"date": day, "nav": capital, "decision_recorded": True}]
            }
    result["last_signal_session"] = day
    result["signal_hash"] = forecast_hash
    for name, book in result["strategies"].items():
        signal_day = book.get("last_signal_session", previous_signal)
        if book.get("paused_missing_quotes") or book["equity"][-1]["date"] != day:
            # Remember the old signal before advancing the shared forecast.
            book["last_signal_session"] = signal_day
            continue
        if signal_day == day:
            continue
        if book["positions"] or book["pending"]:
            raise ValueError("No se puede emitir nueva señal con cartera anterior sin liquidar")
        selected = _select(name, forecast["models"].get(name, {}), config["paper_policy"], day)
        book["last_signal_session"] = day
        book["pending"] = selected
        book["events"].append({"date": day, "type": "signal_frozen", "count": len(selected)})
    return (state, False) if result == state else (result, True)


def _price(prices, ticker, key):
    row = prices.get(ticker)
    if not isinstance(row, dict) or key not in row:
        raise ValueError(f"Barra OHLC ausente: {ticker}")
    n = float(row[key])
    if not math.isfinite(n) or n <= 0:
        raise ValueError(f"Precio no válido: {ticker} {key}")
    return n


def _week(day):
    return datetime.fromisoformat(day).isocalendar()[:2]


def _book_symbols(book):
    return set(book["positions"]) | {order["ticker"] for order in book["pending"]}


# The nightly engine and the pre-opening clock share exactly one cost/quantity
# calculation. The clock supplies contemporary prices and dated evidence.
FORWARD_CUTOVER_SESSION = "2026-11-10"


def fill_pending_at_observed_open(name, book, day, prices, policy, *,
                                  execution="simulated_next_open", quote_metadata=None):
    """Apply frozen buy orders to the ORIGINAL ML book; caller owns causality checks."""
    pending = book["pending"]
    if not pending:
        return []
    previous_nav = float(book["nav"])
    budget = previous_nav * float(policy["invest_fraction"])
    if name not in BENCHMARKS:
        budget = min(previous_nav * float(policy["max_entry_weight"]),
                     budget / len(pending))
    operations = []
    for order in pending:
        ticker = order["ticker"]
        entry = _price(prices, ticker, "open") * (1 + float(policy["slippage"]))
        shares = _fractional_quantity(budget, entry, policy)
        if shares <= 0:
            book["events"].append({"date": day, "type": "unfilled",
                                   "ticker": ticker, "reason": "below_min_notional"})
            continue
        fee = entry * shares * float(policy["commission"])
        if entry * shares + fee > book["cash"] + 1e-7:
            raise ValueError("Caja insuficiente para la compra paper")
        if ticker in book["positions"]:
            raise ValueError("Posición duplicada")
        book["positions"][ticker] = {
            "shares": shares, "entry_price": entry, "entry_fee": fee,
            "signal_date": order["signal_date"], "entry_date": day
        }
        book["cash"] -= entry * shares + fee
        event = {"date": day, "type": "buy",
                 "ticker": ticker, "shares": shares, "price": entry, "fee": fee,
                 "execution": execution}
        if quote_metadata is not None:
            if ticker not in quote_metadata:
                raise ValueError("Missing quote provenance for paper fill")
            event.update(quote_metadata[ticker])
        book["events"].append(event)
        operations.append(event)
    book["pending"] = []
    return operations


def _advance_book(name, book, day, prices, policy, *, week_end):
    if book["pending"]:
        fill_pending_at_observed_open(name, book, day, prices, policy)
    # Mark with observed prices for the exact session.
    marks = {ticker: _price(prices, ticker, "close")
             for ticker in book["positions"]}
    if week_end:
        for ticker, position in list(book["positions"].items()):
            shares = position["shares"]
            exit_price = marks[ticker] * (1 - float(policy["slippage"]))
            fee = exit_price * shares * float(policy["commission"])
            received = shares * exit_price - fee
            book["cash"] += received
            net_pnl = received - position["entry_price"] * shares - position["entry_fee"]
            book["trades"].append({
                "ticker": ticker, "signal_date": position["signal_date"],
                "entry_date": position["entry_date"], "exit_date": day,
                "shares": shares, "buy_price": position["entry_price"],
                "sell_price": exit_price, "buy_commission": position["entry_fee"],
                "sell_commission": fee, "net_pnl": net_pnl
            })
            book["events"].append({"date": day, "type": "sell",
                "ticker": ticker, "shares": shares, "price": exit_price,
                "fee": fee, "execution": "simulated_week_close"})
        book["positions"] = {}
    nav = book["cash"] + sum(float(pos["shares"]) * marks[ticker]
                              for ticker, pos in book["positions"].items())
    if not math.isfinite(nav) or nav < 0:
        raise ValueError("NAV paper diario inválido")
    book["nav"] = nav
    book["equity"].append({"date": day, "nav": nav, "decision_recorded": False})


def _pause_book(book, day, missing, reason):
    pause = {"date": day, "missing_tickers": sorted(missing), "reason": reason}
    if book.get("paused_missing_quotes") != pause:
        book["paused_missing_quotes"] = pause
        book["events"].append({"type": "weekly_book_paused", **pause})


def _recover_book(name, book, historical, previous, policy, stamp):
    """Recover only passive marks, in order, within the same trading week."""
    start = book["equity"][-1]["date"]
    if book["pending"] or _week(start) != _week(previous):
        return None
    dates = sorted(date for date in historical if start < date <= previous)
    if not dates or dates[-1] != previous:
        return None
    recovered = copy.deepcopy(book)
    for date in dates:
        prices, identity = historical[date]
        for ticker in book["positions"]:
            row = prices.get(ticker)
            if not row or row.get("split") or row.get("dividend"):
                return None
        _advance_book(name, recovered, date, prices, policy, week_end=False)
        recovered["equity"][-1].update(late_mark_only=True, recorded_at_utc=stamp, quote_identity=identity)
    return recovered


def process_day(config, state, day, prices, *, previous_session, week_end,
                quote_identity=None, historical=None):
    """Settle each independent book once, even when a peer lacks a quote."""
    _check_config(state, config)
    if day < state["last_session"]:
        return state, False
    policy = config["paper_policy"]
    result = copy.deepcopy(state)
    inactive = day < state.get("outage_control", {}).get("first_trading_session", "")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for name, original in state["strategies"].items():
        last = original["equity"][-1]["date"]
        if last >= day:
            continue
        book = result["strategies"][name]
        signal_day = book.get("last_signal_session", state["last_signal_session"])
        required = set(book["positions"]) if inactive or day >= FORWARD_CUTOVER_SESSION else _book_symbols(book)
        missing = required - prices.keys()
        if missing:
            _pause_book(book, day, missing, "missing_ohlc")
            continue
        if last != previous_session:
            # A gap across a weekly close could hide a sale. Never replay it.
            same_week = _week(previous_session) == _week(day)
            recovered = _recover_book(name, book, historical or {}, previous_session, policy, stamp) if same_week else None
            if recovered is None:
                _pause_book(book, day, (), "unreconciled_session")
                continue
            book = result["strategies"][name] = recovered
        if not inactive and book["pending"] and (
                signal_day != previous_session or
                any(order["signal_date"] != previous_session for order in book["pending"])):
            _pause_book(book, day, (), "expired_open")
            continue
        if not inactive and day >= FORWARD_CUTOVER_SESSION and book["pending"]:
            # From cutover onwards a missing contemporary opening is a missed
            # paper order, NEVER a simulated 09:30 fill reconstructed at night.
            book["events"].append({
                "date": day, "type": "missed_forward_open",
                "reason": "no_verified_opening_execution",
                "signal_date": signal_day,
                "tickers": sorted(order["ticker"] for order in book["pending"]),
            })
            book["pending"] = []
        if inactive:
            from strategy_comparison.inactive_recovery import weekly_mark
            weekly_mark(book, day, prices, stamp=stamp, identity=quote_identity)
        else:
            _advance_book(name, book, day, prices, policy, week_end=week_end)
        pause = book.pop("paused_missing_quotes", None)
        if pause and pause["date"] == day:
            book["equity"][-1].update(late_recorded_verified_date=True, recorded_at_utc=stamp,
                                       quote_identity=quote_identity)
    result["last_session"] = day
    if inactive:
        result["gap_sessions"] = sorted(set(result.get("gap_sessions", [])) | {day})
    return (state, False) if result == state else (result, True)


def live_calendar(now=None):
    import pandas_market_calendars as mcal
    import pandas as pd
    now = now or datetime.now(timezone.utc)
    schedule = mcal.get_calendar("XNYS").schedule(
        start_date=(now - timedelta(days=17)).date(),
        end_date=(now + timedelta(days=9)).date())
    eligible = [str(day.date()) for day, row in schedule.iterrows()
                if now >= row["market_close"].to_pydatetime() + timedelta(minutes=90)]
    if not eligible:
        return None
    day = eligible[-1]
    future = schedule.loc[schedule.index.date > datetime.fromisoformat(day).date()]
    if future.empty or now >= future.iloc[0]["market_open"].to_pydatetime():
        raise ValueError("Valoración fuera de la ventana antes de siguiente apertura")
    days = [str(d.date()) for d in schedule.index]
    index = days.index(day)
    previous = days[index - 1]
    next_day = days[index + 1]
    week_end = pd.Timestamp(day).to_period("W-FRI") != pd.Timestamp(next_day).to_period("W-FRI")
    return day, previous, next_day, week_end


def download_bars(tickers, day, *, diagnostics=None, allow_missing=False):
    if not tickers:
        return {}
    ordered = sorted(set(tickers))
    prices, info = canonical(day, ordered, ROOT / "market_data/snapshots")
    independent = info["independent_symbols"]
    if independent:
        # RSP remains outside the common frozen universe. Use the same strict
        # RAW/exact-date parser and bounded isolated retry as the common reader,
        # without substituting another ETF or changing the immutable snapshot.
        from market_data.collect import collect
        recovered, failures = collect(day, independent, include_benchmark=False)
        prices.update(recovered)
        info["independent_missing"] = sorted(failures)
    if diagnostics is not None:
        diagnostics.update(info)
    missing = sorted(set(ordered) - set(prices))
    if missing and not allow_missing:
        raise ValueError("Barra OHLC fechada ausente: " + ",".join(missing))
    return prices


def run(config_path, forecast_dir, output, phase):
    config = read(config_path)
    output = Path(output)
    state = read(output) if output.exists() else None
    if phase == "signal":
        files = sorted(Path(forecast_dir).glob("????-??-??.json"))
        if not files:
            return {"status": "no_forecast"}
        forecast = read(files[-1])
        state, changed = freeze_signal(config, forecast, state)
        if changed:
            write(output, state)
        return {"status": "signal_frozen" if changed else "already_frozen",
                "session": forecast["asof"], "changed": changed}
    if phase != "daily":
        raise ValueError("Fase desconocida")
    if state is None:
        return {"status": "waiting_for_first_new_signal", "changed": False}
    calendar = live_calendar()
    if calendar is None:
        return {"status": "market_not_closed", "changed": False}
    day, previous, next_day, week_end = calendar
    unfinished = [book for book in state["strategies"].values() if book["equity"][-1]["date"] < day]
    quote_source, historical = {}, {}
    if unfinished:
        tickers = set().union(*(_book_symbols(book) for book in unfinished))
        prices = download_bars(tickers, day, diagnostics=quote_source, allow_missing=True)
        lagging = [book for book in unfinished
                   if not book["pending"] and book["equity"][-1]["date"] < previous
                   and _week(book["equity"][-1]["date"]) == _week(day)]
        if lagging:
            earliest = min(book["equity"][-1]["date"] for book in lagging)
            import pandas_market_calendars as mcal
            days = mcal.get_calendar("XNYS").valid_days(start_date=earliest, end_date=previous)
            held = {ticker for book in lagging for ticker in book["positions"]}
            for date in (x.date().isoformat() for x in days[1:]):
                info = {}
                try:
                    bars = download_bars(held, date, diagnostics=info, allow_missing=True)
                except ValueError:
                    # Keep this date in the sequence: affected held books must
                    # fail closed, while cash books can still mark observed cash.
                    bars = {}
                historical[date] = (bars, {"snapshot_sha256": info.get("hash"),
                                            "effective_sha256": info.get("effective_sha256")})
        updated, _ = process_day(config, state, day, prices, previous_session=previous,
                                 week_end=week_end, historical=historical,
                                 quote_identity={"snapshot_sha256": quote_source.get("hash"),
                                                 "effective_sha256": quote_source.get("effective_sha256")})
    else:
        updated = state
    changed = updated != state
    if changed:
        write(output, updated)
    # The weekly forecast can finish before or after the daily publisher.
    # Admit a repaired book to that same frozen forecast before the next open.
    forecast_path = Path(forecast_dir) / (day + ".json")
    if week_end and updated["last_session"] == day and forecast_path.is_file():
        forecast = read(forecast_path)
        if forecast["asof"] != day:
            raise ValueError("La fecha del forecast no coincide con su archivo")
        updated, frozen = freeze_signal(config, forecast, updated)
        if frozen:
            write(output, updated)
            changed = True
    paused = {name: book["paused_missing_quotes"] for name, book in updated["strategies"].items()
              if book.get("paused_missing_quotes")}
    return {"status": "paper_recorded_partial" if paused else "daily_recorded" if changed else "already_recorded",
            "session": day, "quote_source": quote_source, "paused_books": paused,
            "week_end": week_end, "changed": changed}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["daily", "signal"], required=True)
    p.add_argument("--config", default="weekly_ml/config.json")
    p.add_argument("--forecast-dir", default="weekly_ml_state/forecasts")
    p.add_argument("--output", default="weekly_ml_daily_state/ledger.json")
    args = p.parse_args()
    try:
        result = run(args.config, args.forecast_dir, args.output, args.phase)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print("Weekly ML daily error: " + repr(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
