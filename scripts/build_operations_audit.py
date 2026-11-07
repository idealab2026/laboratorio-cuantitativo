#!/usr/bin/env python3
"""Generate an auditable, read-only per-strategy operations extract.

Only previously committed real paper ledgers and dated OHLC snapshots are read.
No market data is downloaded; missing fills, decisions and prices remain missing.
Inferred holds are visibly identified and are NOT original trading decisions.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDES = {"buy", "sell"}
PRICE_FILES = sorted((ROOT / "market_data/snapshots/XNYS").glob("????-??-??.json"))

def read(path):
    file = ROOT / path
    if not file.is_file() or file.stat().st_size == 0:
        return None, None
    raw = file.read_bytes()
    try:
        return json.loads(raw), hashlib.sha256(raw).hexdigest()
    except (ValueError, UnicodeDecodeError):
        return None, None

def number(n):
    return float(n) if isinstance(n, (float, int)) and not isinstance(n, bool) and 0 < n < 10**8 else None

def date(value):
    return value if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-" else None

def clean_ticker(s):
    if not isinstance(s, str) or not s or len(s) > 14:
        return None
    return s if all(ch.isupper() or ch.isdigit() or ch in ".-" for ch in s) else None

def price_history():
    observations = defaultdict(list)
    for file in PRICE_FILES:
        doc, digest = read(str(file.relative_to(ROOT)))
        if not isinstance(doc, dict) or not date(doc.get("session")) or not isinstance(doc.get("bars"), dict):
            continue
        for ticker, bar in doc["bars"].items():
            if clean_ticker(ticker) and isinstance(bar, dict):
                close = number(bar.get("close"))
                if close is not None:
                    observations[ticker].append({"date":doc["session"], "price":close,
                                                 "low":number(bar.get("low")),
                                                 "high":number(bar.get("high")),
                                                 "source":"dated_market_close", "snapshot_sha256":digest})
    return {key: sorted(vals, key=lambda a:a["date"]) for key, vals in observations.items()}

def rule_reason(event, score=None):
    """Describe only stored decision fields, never invent latent rationale."""
    code = event.get("reason") or event.get("exit_reason")
    signals = {
        "monthly_rebalance":"Rebalanceo mensual documentado en el libro paper.",
        "monthly_rotation":"Rotación mensual documentada en el libro paper.",
        "next_open":"Ejecución a la apertura posterior a la señal.",
        "close_signal":"Señal al cierre del día anterior; ejecución posterior registrada.",
        "signal_next_open":"Orden ejecutada tras señal al cierre anterior.",
        "stop":"Salida por nivel stop registrado.",
        "target":"Salida por objetivo de precio registrado.",
    }
    if isinstance(code, str) and code:
        phrase = signals.get(code, "Motivo literal del registro: "+code[:80])
        basis = "recorded"
    else:
        phrase = "Motivo específico no documentado en el libro paper."
        basis = "not_recorded"
    if isinstance(score, dict):
        labels = {
            "composite_score":"puntuación global",
            "capital_scarcity_score":"escasez de capital",
            "quality_score":"calidad",
            "valuation_score":"valoración",
            "inflection_votes":"votos de inflexión",
            "dislocation_score":"dislocación",
            "capital_allocation_score":"asignación de capital",
            "catalyst_votes":"catalizadores",
        }
        parts = [label+" "+str(score[k]) for k,label in labels.items()
                 if isinstance(score.get(k), (float,int))]
        if parts:phrase += " Señal original: "+", ".join(parts[:7])+"."
    return phrase, basis

def selected_scores(ledger):
    scored = {}
    for signal in ledger.get("signals",[]) if isinstance(ledger.get("signals"),list) else []:
        fill_date = signal.get("expected_fill_session")
        if not date(fill_date):continue
        for candidate in signal.get("selected",[]) or []:
            ticker=clean_ticker(candidate.get("ticker"))
            if ticker:scored[fill_date,ticker] = candidate
    return scored

def add_event(target, day, side, ticker, price=None, quantity=None, reason=None,
              basis="not_recorded", origin="executed_ledger", signal_date=None,
              price_basis=None, fee=None):
    if not date(day) or not clean_ticker(ticker):
        return
    target[day].append({
        "ticker":ticker,"side":side,"price":number(price),"quantity":number(quantity),
        "reason":reason or "Motivo individual no documentado.","reason_basis":basis,
        "evidence":origin,"signal_date":date(signal_date),
        "price_basis":price_basis or ("book_fill" if number(price) else "not_recorded"),
        "fee":float(fee) if isinstance(fee,(int,float)) and not isinstance(fee,bool) and 0<=fee<10**8 else None
    })


def corporate_events(ledger):
    """Return original corporate conversion records, never exchange trades."""
    events=[]
    for item in ledger.get("events",[]):
        if not isinstance(item,dict) or item.get("type")!="corporate_merger_entitlement":
            continue
        parts=str(item.get("action_id","")).split("_")
        if len(parts)<3:continue
        previous,successor=clean_ticker(parts[0]),clean_ticker(parts[1])
        original=item.get("original_position")
        if not previous or not successor or not isinstance(original,dict) or not date(item.get("date")):
            continue
        if number(original.get("shares")) is None or number(original.get("entry_price")) is None:
            continue
        events.append((previous,successor,item))
    return events

def classic_execution_prices(ledger):
    """Resolve classic buy/sell fills from verifiable book data and fee math.

    A converted predecessor's original_position retains its real entry fill.
    Closed trades store gross cost and net proceeds; recover price only when
    matching a unique executed buy with shares and a documented commission.
    Missing or ambiguous information is deliberately not guessed.
    """
    out={}
    positions=ledger.get("positions",{})
    if not isinstance(positions,dict):positions={}
    for ticker,position in positions.items():
        if not isinstance(position,dict):continue
        entry=date(position.get("entry_date"))
        price=number(position.get("entry_price"))
        if entry and price and clean_ticker(ticker):
            out[(entry,ticker,"buy")]=(price,"position_entry")
    for old,new,change in corporate_events(ledger):
        pos=change["original_position"]
        entry=date(pos.get("entry_date"))
        if entry:
            out[(entry,old,"buy")]=(number(pos["entry_price"]),"corporate_original_entry")
    configuration,_=read("classic_sp500/config.json")
    if not isinstance(configuration,dict):return out
    commission=(configuration.get("execution") or {}).get("commission")
    if not isinstance(commission,(int,float)) or isinstance(commission,bool) or not 0<=commission<.05:
        return out
    buys=defaultdict(list)
    splits=defaultdict(list)
    for event in ledger.get("events",[]):
        if not isinstance(event,dict):continue
        ticker=clean_ticker(event.get("ticker"))
        if not ticker or not date(event.get("date")):continue
        if event.get("type")=="buy" and number(event.get("shares")):
            buys[(event["date"],ticker)].append(number(event["shares"]))
        if event.get("type")=="split":
            splits[ticker].append(event["date"])
    for trade in ledger.get("trades",[]):
        if not isinstance(trade,dict):continue
        ticker=clean_ticker(trade.get("ticker"))
        entry=date(trade.get("entry_date"));exit_day=date(trade.get("exit_date"))
        if not ticker or not entry or not exit_day or entry>=exit_day:continue
        records=buys[(entry,ticker)]
        if len(records)!=1:continue
        if any(entry<split<=exit_day for split in splits[ticker]):continue
        qty=records[0]
        cost=number(trade.get("entry_cost"))
        proceeds=number(trade.get("proceeds"))
        dividends=trade.get("dividends")
        pnl=trade.get("net_pnl")
        if cost is None or proceeds is None:continue
        if isinstance(dividends,(int,float)) and isinstance(pnl,(int,float)):
            if abs((proceeds+dividends-cost)-pnl)>max(1e-5,abs(pnl)*1e-8):
                continue
        # Gross buy cost includes commission; net sell proceeds exclude it.
        if (entry,ticker,"buy") not in out:
            out[(entry,ticker,"buy")]=(cost/qty/(1+commission),"trade_entry_cost_derived")
        out[(exit_day,ticker,"sell")]=(proceeds/qty/(1-commission),"trade_net_proceeds_derived")
    return out

def normalize_ledger(ledger, source):
    """Return dated executed actions; do not present unfilled signals as purchases."""
    out=defaultdict(list)
    score_map=selected_scores(ledger)
    classic_prices=classic_execution_prices(ledger) if source=="classic_sp500_state/ledger.json" else {}
    events=ledger.get("events",[])
    if isinstance(events,list):
        for event in events:
            if not isinstance(event,dict):continue
            action=event.get("type") if event.get("type") in SIDES else (
                event.get("side") if event.get("type")=="fill" else
                event.get("event") if event.get("event") in SIDES else None)
            if action in SIDES:
                day=date(event.get("date")) or date(event.get("fill_date"))
                ticker=clean_ticker(event.get("ticker"))
                score=score_map.get((day,ticker))
                reason,basis=rule_reason(event,score)
                qty=event.get("quantity",event.get("shares"))
                pr=event.get("price",event.get("price_eur",event.get("entry_eur")))
                price_basis="book_fill" if number(pr) else "not_recorded"
                recovered=classic_prices.get((day,ticker,action))
                if pr is None and recovered:
                    pr,price_basis=recovered
                if pr is None and action=="buy":
                    holding=ledger.get("positions",{}).get(ticker)
                    if isinstance(holding,dict) and holding.get("entry_date")==day:
                        pr=holding.get("entry_price",holding.get("entry_price_eur"))
                        if number(pr):price_basis="position_entry"
                add_event(out,day,action,ticker,pr,qty,reason,basis,source,
                          event.get("signal_date"),price_basis=price_basis,fee=event.get("fee"))
    # Closed trades with explicit entry/exit prices are a separate, verifiable
    # representation; skip them if corresponding event rows already exist.
    trades=ledger.get("trades",[])
    if isinstance(trades,list):
        for trade in trades:
            if not isinstance(trade,dict):continue
            ticker=clean_ticker(trade.get("ticker"))
            entry=date(trade.get("entry_date",trade.get("first_session")))
            leave=date(trade.get("exit_date",trade.get("last_session")))
            if ticker is None:continue
            for when,side,price in ((entry,"buy",trade.get("buy_price",trade.get("entry_price"))),
                                    (leave,"sell",trade.get("sell_price",trade.get("exit_price")))):
                if not when or any(x["ticker"]==ticker and x["side"]==side for x in out[when]):
                    continue
                note=trade.get("reason") or trade.get("exit_reason")
                entry_score=trade.get("score") or trade.get("predicted_return")
                reason,basis=rule_reason({"reason":note})
                if side=="buy" and isinstance(entry_score,(int,float)):
                    reason += " Señal guardada: puntuación de selección "+str(round(float(entry_score),6))+"."
                add_event(out,when,side,ticker,price,
                          trade.get("quantity",trade.get("shares")),reason,basis,
                          source+"/closed_trade",trade.get("signal_date"),
                          fee=trade.get("buy_commission" if side=="buy" else "sell_commission"))
    return out


# These descriptions are grounded in the public classic engine source. They
# describe policy, not a retrospectively invented per-ticker signal decision.
CLASSIC_POLICY = {
    "benchmark_spy": "Referencia SPY: compra una vez y mantiene la exposición mientras no se registre salida.",
    "buy_hold_equal_weight": "Equiponderación: compra componentes elegibles que aún no mantiene y no emite ventas ordinarias.",
    "genetic_frozen": "Reglas genéticas congeladas: el motor evalúa señales al cierre y puede cerrar posiciones por señal, stop u objetivo.",
    "ema_rsi_fixed": "Regla EMA/RSI: evaluación de tendencia y fortaleza relativa al cierre; ejecución posterior de señales y controles stop/objetivo.",
    "macd_12_26_9": "Regla MACD 12/26/9: cruces de tendencia al cierre, con ejecución posterior y controles stop/objetivo.",
    "rsi_reversion_14": "Regla RSI 14: selección por reversión a la media y salidas por señal o controles de riesgo.",
    "bollinger_breakout_20": "Regla Bollinger 20: ruptura de bandas, salida por señal o controles de riesgo.",
    "turtle_20_10_long": "Regla Turtle 20/10: ruptura de canal con posible salida por la ventana de mínimos.",
    "turtle_55_20_long": "Regla Turtle 55/20: ruptura de canal con posible salida por la ventana de mínimos.",
}
def classic_model(source,key):
    if source == "classic_sp500_state/ledger.json" and key in CLASSIC_POLICY:
        return key
    return None

def explain_classic_buy(model, event):
    name = CLASSIC_POLICY[model]
    return ("Ejecución acreditada por el libro. Política de entrada del motor: " + name +
            " Las órdenes se congelan tras el cierre y se ejecutan en una apertura posterior."
            " El registro no conserva la lectura exacta del indicador de este ticker que motivó la orden.")

def explain_classic_hold(model,ticker,day,position,price_point,is_latest):
    policy=CLASSIC_POLICY[model]
    original=bool(isinstance(position,dict) and
                  position.get("basis_origin")=="corporate_conversion_no_purchase")
    source_text=("Posición recibida por conversión corporativa, no compra bursátil; " if original else
                 "Posición abierta según las compras ejecutadas; ")
    text=(source_text+"ninguna venta ejecutada para " + ticker +
          " en esta sesión. Regla del motor: " + policy +
          " Esta fila es continuidad contable, no una señal explícita de MANTENER.")
    # The published ledger's current risk thresholds are NOT historical unless
    # the observation matches its final session; do not project backwards.
    if is_latest and isinstance(position,dict):
        stop=number(position.get("stop"))
        target=number(position.get("target"))
        if stop is not None or target is not None:
            parts=[]
            if stop is not None:parts.append("stop vigente %.3f" % stop)
            if target is not None:parts.append("objetivo vigente %.3f" % target)
            text+=" Umbrales documentados para este último cierre: "+", ".join(parts)+"."
            if price_point:
                low=price_point.get("low")
                high=price_point.get("high")
                if low is not None and high is not None:
                    if (stop is None or low>stop) and (target is None or high<target):
                        text+=(" Rango de mercado observado %.3f–%.3f: no cruzó"
                                " esos umbrales en esta sesión." % (low,high))
                    else:
                        text+=(" El rango observado cruzó un umbral o no permite"
                                " descartar su activación; revisar la ejecución"
                                " y la secuencia de órdenes.")
    return text[:950]

def equity_days(ledger):
    values=ledger.get("equity") or []
    if isinstance(values,list):
        return sorted({x["date"] for x in values if isinstance(x,dict) and date(x.get("date"))})
    return []

def source_for(source_id):
    if source_id=="capital_cycle_inflection_2026":
        return "capital_cycle_state/ledger.json",None
    if source_id=="buy_the_dip_corpus_2026_v0":
        return "buy_the_dip_state/ledger.json",None
    if source_id.startswith("classic_sp500_"):
        return "classic_sp500_state/ledger.json",source_id.removeprefix("classic_sp500_")
    weekly_aliases={"arima":"arima_return","lstm":"lstm_return","mlp":"mlp_return","ensemble":"ensemble_consensus"}
    if source_id.startswith("weekly_legacy_weekly_ml_"):
        suffix=source_id.removeprefix("weekly_legacy_weekly_ml_").removesuffix("_2026")
        return "weekly_ml_state/ledger.json",weekly_aliases.get(suffix,suffix)
    if source_id.startswith("weekly_ml_"):
        suffix=source_id.removeprefix("weekly_ml_").removesuffix("_2026")
        return "weekly_ml_daily_state/ledger.json",weekly_aliases.get(suffix,suffix)
    if source_id in ("timesfm_2p5_eur_paper","timesfm_spy_eur"):
        return "timesfm_state/ledger.json",("timesfm" if source_id=="timesfm_2p5_eur_paper" else "benchmark_spy")
    if source_id=="tfg_corrected_2026":
        return "tfg_state/ledger.json",None
    if source_id.startswith("tfm_") and source_id.endswith("_2023"):
        return "tfm_state/ledger.json",source_id[4:-5]
    if source_id in ("benchmark_spy","buy_hold_equal_weight","ema_rsi_fixed",
                     "genetic_frozen","macd_12_26_9","rsi_reversion_14",
                     "bollinger_breakout_20","turtle_20_10_long","turtle_55_20_long"):
        return "paper_state/state.json",source_id
    return None,None

def source_book(doc,source,key):
    if not isinstance(doc,dict):return None
    if source=="paper_state/state.json":return (doc.get("strategies") or {}).get(key)
    if source=="classic_sp500_state/ledger.json":return (doc.get("books") or {}).get(key)
    if source=="timesfm_state/ledger.json":return (doc.get("books") or {}).get(key)
    if source=="weekly_ml_state/ledger.json":return (doc.get("strategies") or {}).get(key)
    if source=="weekly_ml_daily_state/ledger.json":return (doc.get("strategies") or {}).get(key)
    if source=="tfm_state/ledger.json":return (doc.get("models") or {}).get(key)
    return doc

def signal_book(source_id, book, source, parent, *, read_source=read):
    """Read admitted paper orders without exposing forecasts or position sizes."""
    if source_id in ("timesfm_2p5_daily_eur_paper", "timesfm_daily_spy_eur"):
        source = "timesfm_daily_state/ledger.json"
        parent, _ = read_source(source)
        key = "timesfm_daily" if source_id == "timesfm_2p5_daily_eur_paper" else "benchmark_spy"
        book = (parent or {}).get("books", {}).get(key)
    elif source_id == "genetic_sp500_legacy":
        source = "AGENTE/genetic_invest_agent/registro_historico/diario_portfolio_forward_2026-10-12.json"
        book, _ = read_source(source)
        parent = book
    return book, source, parent


def pending_signals(book):
    positions = {ticker for ticker in (book.get("positions") or {}) if clean_ticker(ticker)}
    pending = book.get("pending")
    output = []

    def add(ticker, action, order, *, weight=None):
        if not clean_ticker(ticker) or action not in ("buy", "sell", "rebalance", "hold"):
            return
        output.append({"ticker": ticker, "action": action,
                       "decision_session": date(order.get("signal_date") or order.get("asof")),
                       "target_session": date(order.get("expected_fill_session")),
                       "limit_price": number(order.get("limit_price")), "target_weight": weight})

    if isinstance(pending, dict) and isinstance(pending.get("target_weights"), dict):
        targets = {t: w for t, w in pending["target_weights"].items()
                   if clean_ticker(t) and number(w) is not None and w <= 1}
        for ticker in sorted(positions - targets.keys()):
            add(ticker, "sell", pending, weight=0)
        for ticker, weight in sorted(targets.items()):
            add(ticker, "rebalance" if ticker in positions else "buy", pending, weight=weight)
    elif isinstance(pending, dict) and ("buys" in pending or "sells" in pending):
        for ticker, order in sorted(pending.get("buys", {}).items()):
            add(ticker, "buy", order if isinstance(order, dict) else pending)
        for ticker in sorted(pending.get("sells", [])):
            add(ticker, "sell", pending)
    elif isinstance(pending, dict):
        for ticker, order in sorted(pending.items()):
            if isinstance(order, dict):
                add(ticker, order.get("side"), order)
    elif isinstance(pending, list):
        for order in pending:
            if isinstance(order, dict):
                add(order.get("ticker"), order.get("side", "buy"), order)
    weekly = book.get("pending_signal")
    if isinstance(weekly, dict):
        for item in weekly.get("selections", []):
            if isinstance(item, dict):
                add(item.get("ticker"), "buy", weekly)
    for ticker in sorted(positions - {row["ticker"] for row in output}):
        add(ticker, "hold", {})
    return output


def analysis_trace(book, source, parent, key):
    """Publish a small projection of recorded evaluations, without raw diagnostics."""
    if source == "classic_sp500_state/ledger.json":
        traces = (item for item in reversed(parent.get("coverage", []))
                  if key in item.get("rule_trace", {}).get("hits", {}))
        item = next(traces, None)
        if item:
            evidence = item["rule_trace"]
            hits = evidence["hits"][key]
            rows = [[ticker, hits.get(ticker, "no_trigger"), []]
                    for ticker in evidence["evaluated"] if clean_ticker(ticker)]
            return {"date": date(item.get("date")), "method": "classic", "rows": rows,
                    "excluded": len(item.get("missing", {}))}
    if source == "tfg_state/ledger.json":
        signal = book.get("pending_signal") or {}
        selected = {row.get("ticker") for row in signal.get("selections", [])}
        checks = ("rsi", "macd", "bollinger", "stochastic")
        rows = [[row["ticker"], "selected" if row["ticker"] in selected else
                 "passed" if row.get("technical_pass") is True else "filtered",
                 [name for name in checks if row.get(name + "_pass") is True]]
                for row in signal.get("diagnostics", []) if clean_ticker(row.get("ticker"))]
        if rows:
            ratios = {}
            for record in signal.get("diagnostics", []):
                ticker = clean_ticker(record.get("ticker"))
                if not ticker:
                    continue
                ratios[ticker] = {
                    name: value for name in checks
                    if type(value := record.get(name + "_ratio")) in (int, float) and 0 <= value <= 1
                }
            return {"date": date(signal.get("asof")), "method": "ahp", "rows": rows, "ratios": ratios,
                    "excluded": len(signal.get("market_failures", []))}
    if source in {"capital_cycle_state/ledger.json", "buy_the_dip_state/ledger.json"}:
        signals = book.get("signals") or []
        if signals:
            signal = signals[-1]
            rows = [[row["ticker"], "selected", []] for row in signal.get("selected", [])
                    if clean_ticker(row.get("ticker"))]
            if rows:
                return {"date": date(signal.get("date")), "method": "monthly", "rows": rows,
                        "excluded": None}
    return None


def live_book(original, book, source, parent, key=None):
    latest = date(original.get("last_session"))
    base = {"label": original["label"], "currency": original.get("currency"),
            "session": latest, "decision_session": None,
            "status": "unavailable", "signals": [], "executions": []}
    if not isinstance(book, dict):
        return base
    history = book.get("equity") or []
    latest = (date(history[-1].get("date")) if history else date(book.get("last_session"))) or latest
    signals = pending_signals(book)
    last_signal = book.get("last_signal_session", (parent or {}).get("last_signal_session"))
    decision = max([d for d in [date(last_signal), *(item["decision_session"] for item in signals)] if d],
                   default=None)
    pause = book.get("paused_missing_quotes") or {}
    pause_reason = pause.get("reason") if isinstance(pause, dict) else None
    actions = normalize_ledger(book, source).get(latest, [])
    if source == "AGENTE/genetic_invest_agent/registro_historico/diario_portfolio_forward_2026-10-12.json":
        actions = [{"ticker": trade["ticker"], "side": trade["side"].lower(),
                    "price": number(trade.get("fill")), "signal_date": date(trade.get("signal_date"))}
                   for trade in book.get("trades", []) if trade.get("session") == latest
                   and clean_ticker(trade.get("ticker")) and str(trade.get("side")).lower() in SIDES]
    executions = [{"ticker": item["ticker"], "action": item["side"], "price": item["price"],
                   "decision_session": item["signal_date"]} for item in actions]
    return {**base, "session": latest, "decision_session": decision, "signals": signals,
            "status": "paused" if pause else "recorded",
            "pause_date": date(pause.get("date")) if isinstance(pause, dict) else None,
            "pause_reason": pause_reason if pause_reason in
            ("missing_ohlc", "unreconciled_session", "expired_open") else None,
            "executions": executions,
            "analysis": analysis_trace(book, source, parent, key)}


def build(signal_tracks=None):
    registry,_=read("data/original-track-map.json")
    dashboard,_=read("strategy_state/dashboard.json")
    if not isinstance(registry,dict) or len(registry)!=64 or len(dashboard.get("tracks",[]))!=64:
        raise ValueError("Incomplete strategy registry")
    prices=price_history()
    tracks={}
    for original in dashboard["tracks"]:
        source_id=original["id"]
        slot=registry[source_id]
        filename,key=source_for(source_id)
        doc,digest=read(filename) if filename else (None,None)
        book=source_book(doc,filename,key) if filename else None
        if signal_tracks is not None and 10 <= int(slot[3:]) <= 44:
            signal_tracks[slot] = live_book(original, *signal_book(source_id, book, filename, doc), key=key)
        journal_days=[x["date"] for x in original.get("equity_history",[]) if date(x.get("date"))]
        if not isinstance(book,dict):
            tracks[slot]={"source_id":source_id,"status":"no_executed_actions_documented",
                          "source_path":filename,"source_sha256":digest,"currency":original.get("currency"),
                          "sessions":[{"date":d,"actions":[],
                                       "audit_note":"NAV registrado; no se conserva un detalle verificable de órdenes para esta sesión."}
                                      for d in journal_days],
                          "prices":{},
                          "coverage":{"executions":0,"priced_executions":0,
                                      "unpriced_executions":0,"corporate_conversions":0}}
            continue
        actions=normalize_ledger(book,filename)
        mergers=corporate_events(book) if filename=="classic_sp500_state/ledger.json" else []
        mergers_by_day=defaultdict(list)
        for previous,successor,event in mergers:
            mergers_by_day[event["date"]].append((previous,successor,event))
        days=sorted(set(equity_days(book)) | set(actions.keys()) | set(journal_days)
                    | set(mergers_by_day))
        # Replay *executed* quantity changes (never pending orders or signals).
        # Only classic_sp500/run.py has the documented full-position sell
        # semantics needed to attribute the entire remaining quantity.
        classic=classic_model(filename,key)
        holdings={}
        latest=max(days) if days else None
        positions=book.get("positions",{}) if isinstance(book.get("positions"),dict) else {}
        split_events=defaultdict(list)
        if classic:
            for e in book.get("events",[]):
                if isinstance(e,dict) and e.get("type")=="split" and date(e.get("date")):
                    split_events[e["date"]].append(e)
        session_rows=[]
        ever=set()
        for day in days:
            for split in split_events.get(day,[]):
                ticker=clean_ticker(split.get("ticker"))
                ratio=number(split.get("ratio"))
                if ticker in holdings and ratio:
                    holdings[ticker]*=ratio
            events=list(actions.get(day,[]))
            traded={x["ticker"] for x in events}
            for item in events:
                ticker=item["ticker"]
                if item["side"]=="buy":
                    if classic and item["reason_basis"]=="not_recorded":
                        item["reason"]=explain_classic_buy(classic,item)
                        item["reason_basis"]="engine_rule"
                        item["rule_source"]="classic_sp500/run.py"
                    qty=item.get("quantity")
                    if qty is not None:
                        holdings[ticker]=holdings.get(ticker,0)+qty
                    else:
                        holdings.pop(ticker,None)
                elif item["side"]=="sell":
                    if classic and item.get("quantity") is None and ticker in holdings:
                        # The classic engine always liquidates entire positions.
                        item["quantity"]=holdings[ticker]
                    holdings.pop(ticker,None)
                ever.add(ticker)
            for previous,successor,event in mergers_by_day.get(day,[]):
                original_position=event["original_position"]
                expected=number(original_position.get("shares"))
                held=holdings.get(previous)
                # Never pretend a corporate conversion is a market sale.
                if held is None or expected is None or abs(held-expected)>max(.00001,expected*.000001):
                    raise ValueError("Corporate predecessor quantity cannot be reconciled: "+previous)
                holdings.pop(previous)
                successors=number(event.get("successor_whole_shares"))
                if successors is None:
                    raise ValueError("Missing corporate successor shares")
                holdings[successor]=holdings.get(successor,0)+successors
                ever.add(previous);ever.add(successor)
                traded.add(previous)
                fixed_receivable=event.get("fixed_cash_receivable")
                try:cash=float(fixed_receivable)
                except (ValueError,TypeError):raise ValueError("Invalid corporate receivable")
                if not 0<=cash<10**8:raise ValueError("Nonpositive corporate receivable")
                recorded_at=event.get("recorded_at_utc")
                if not isinstance(recorded_at,str) or not recorded_at.endswith("+00:00"):
                    raise ValueError("Corporate event timestamp not verified")
                events.append({
                    "ticker":previous,"side":"corporate_action","price":None,
                    "quantity":expected,"price_basis":"not_applicable",
                    "reason":("Conversión corporativa registrada: "+previous+" → "+successor+
                              "; "+str(int(successors))+" acciones sucesoras enteras y "+
                              ("%.2f" % cash)+" USD de derecho de cobro pendiente. "+
                              "No es una venta ni una compra ejecutada. Registro: "+recorded_at+"."),
                    "reason_basis":"recorded","evidence":filename,"signal_date":None,
                    "successor_ticker":successor,"successor_quantity":successors,
                    "receivable_cash":cash,"recorded_at_utc":recorded_at,
                    "action_id":event.get("action_id")
                })
            for ticker in sorted(holdings.keys()-traded):
                price_point=next((p for p in prices.get(ticker,[]) if p["date"]==day),None)
                current_pos=positions.get(ticker)
                # The final positions file only proves the entry price for the
                # currently held lot, not for an earlier closed/reopened lot.
                same_lot=isinstance(current_pos,dict) and date(current_pos.get("entry_date")) and current_pos["entry_date"]<=day
                qty=holdings[ticker] if holdings[ticker]>0 else None
                record={"ticker":ticker,"side":"hold","price":None,
                        "quantity":qty,
                        "reason":"Posición abierta sin orden de venta registrada; continuidad contable inferida.",
                        "reason_basis":"inferred_position_continuity",
                        "evidence":filename,"signal_date":None}
                if same_lot:
                    record["entry_price"]=number(current_pos.get("entry_price"))
                    record["entry_date"]=current_pos["entry_date"]
                if price_point is not None and original.get("currency")=="USD":
                    record["reference_close"]=price_point["price"]
                    record["reference_sha256"]=price_point["snapshot_sha256"]
                if classic:
                    record["reason"]=explain_classic_hold(classic,ticker,day,current_pos if same_lot else None,
                                                          price_point,day==latest)
                    record["rule_source"]="classic_sp500/run.py"
                events.append(record)
            if day in journal_days or day in actions:
                session_rows.append({"date":day,"actions":events,
                                     "audit_note":None if events else
                                     "Sin operaciones ni posiciones reconstruibles del libro en esta sesión."})
        # A source with no event history is NOT transformed into a fictional cash strategy.
        if not actions and not (book.get("trades") or []):
            status="nav_only_or_no_actions"
        else:status="partial_executions_documented"
        by_symbol={}
        for ticker in sorted(ever):
            by_symbol[ticker]=prices.get(ticker,[]) if original.get("currency")=="USD" else []
        executed=[a for row in session_rows for a in row["actions"] if a["side"] in ("buy","sell")]
        conversions=[a for row in session_rows for a in row["actions"] if a["side"]=="corporate_action"]
        coverage={"executions":len(executed),
                  "priced_executions":sum(number(a.get("price")) is not None for a in executed),
                  "unpriced_executions":sum(number(a.get("price")) is None for a in executed),
                  "corporate_conversions":len(conversions)}
        # Preserve split events as adjustments, not as simulated orders.
        split_adjustments = [
            {"date":item["date"],"ticker":item["ticker"],"ratio":float(item["ratio"])}
            for item in book.get("events",[]) if isinstance(item,dict)
            and item.get("type")=="split" and date(item.get("date"))
            and clean_ticker(item.get("ticker")) and number(item.get("ratio"))
        ]
        tracks[slot]={"source_id":source_id,"status":status,
                      "source_path":filename,"source_sha256":digest,"currency":original.get("currency"),
                      "sessions":session_rows,"prices":by_symbol,"splits":split_adjustments,
                      "coverage":coverage}
    return {"schema":"midas_operations_audit_v1","purpose":"read_only_paper_decision_evidence",
            "asof":max((x.get("last_session") or "" for x in dashboard["tracks"]),default=""),
            "notes":["Solo constan las operaciones disponibles en libros versionados.",
                     "MANTENER es continuidad contable inferida, no una señal explícita.",
                     "Los cierres bursátiles publicados cubren únicamente las sesiones con snapshots locales; no se interpolan precios intermedios.",
                     "No se atribuyen retornos adicionales ni se generan órdenes."],
            "tracks":tracks}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--signals-output", type=Path)
    parser.add_argument("--opening-plans", action="store_true")
    args=parser.parse_args()
    signal_tracks = {} if args.signals_output else None
    doc=build(signal_tracks)
    if args.signals_output:
        assert len(signal_tracks) == 35
        args.signals_output.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        extra = {}
        if args.opening_plans:
            from build_opening_plan import opening_plans
            extra["opening_plans"] = opening_plans(now)
        args.signals_output.write_text(json.dumps({
            "schema": "midas_execution_signals_v1", "tracks": signal_tracks,
            "published_at_utc": now.isoformat(), **extra,
        }, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf8")
    assert len(doc["tracks"])==64
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(doc,ensure_ascii=False,separators=(",",":"),sort_keys=True)+"\n",encoding="utf8")
    print("Auditable paper tracks:",len(doc["tracks"]),
          "executed-book tracks:",sum(t["status"]=="partial_executions_documented" for t in doc["tracks"].values()),
          "rows:",sum(len(t["sessions"]) for t in doc["tracks"].values()),
          "executions:",sum(t["coverage"]["executions"] for t in doc["tracks"].values()),
          "priced executions:",sum(t["coverage"]["priced_executions"] for t in doc["tracks"].values()),
          "unpriced dated executions:",sum(t["coverage"]["unpriced_executions"] for t in doc["tracks"].values()),
          "corporate conversions:",sum(t["coverage"]["corporate_conversions"] for t in doc["tracks"].values()))
if __name__=="__main__":main()
