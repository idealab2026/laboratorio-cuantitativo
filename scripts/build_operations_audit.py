#!/usr/bin/env python3
"""Generate an auditable, read-only per-strategy operations extract.

Only previously committed real paper ledgers and dated OHLC snapshots are read.
No market data is downloaded; missing fills, decisions and prices remain missing.
Inferred holds are visibly identified and are NOT original trading decisions.
"""
from __future__ import annotations
import argparse
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
              basis="not_recorded", origin="executed_ledger", signal_date=None):
    if not date(day) or not clean_ticker(ticker):
        return
    target[day].append({
        "ticker":ticker,"side":side,"price":number(price),"quantity":number(quantity),
        "reason":reason or "Motivo individual no documentado.","reason_basis":basis,
        "evidence":origin,"signal_date":date(signal_date)
    })

def normalize_ledger(ledger, source):
    """Return dated executed actions; do not present unfilled signals as purchases."""
    out=defaultdict(list)
    score_map=selected_scores(ledger)
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
                pr=event.get("price",event.get("price_eur"))
                if pr is None and action=="buy":
                    holding=ledger.get("positions",{}).get(ticker)
                    if isinstance(holding,dict) and holding.get("entry_date")==day:
                        pr=holding.get("entry_price",holding.get("entry_price_eur"))
                add_event(out,day,action,ticker,pr,qty,reason,basis,source,event.get("signal_date"))
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
                          source+"/closed_trade",trade.get("signal_date"))
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
    text=("Posición abierta según los fills; ninguna venta ejecutada para " + ticker +
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

def build():
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
        journal_days=[x["date"] for x in original.get("equity_history",[]) if date(x.get("date"))]
        if not isinstance(book,dict):
            tracks[slot]={"source_id":source_id,"status":"no_executed_actions_documented",
                          "source_path":filename,"source_sha256":digest,"currency":original.get("currency"),
                          "sessions":[{"date":d,"actions":[],
                                       "audit_note":"NAV registrado; no se conserva un detalle verificable de órdenes para esta sesión."}
                                      for d in journal_days],
                          "prices":{}}
            continue
        actions=normalize_ledger(book,filename)
        days=sorted(set(equity_days(book)) | set(actions.keys()) | set(journal_days))
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
        tracks[slot]={"source_id":source_id,"status":status,
                      "source_path":filename,"source_sha256":digest,"currency":original.get("currency"),
                      "sessions":session_rows,"prices":by_symbol}
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
    args=parser.parse_args()
    doc=build()
    assert len(doc["tracks"])==64
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(doc,ensure_ascii=False,separators=(",",":"),sort_keys=True)+"\n",encoding="utf8")
    print("Auditable paper tracks:",len(doc["tracks"]),
          "executed-book tracks:",sum(t["status"]=="partial_executions_documented" for t in doc["tracks"].values()),
          "rows:",sum(len(t["sessions"]) for t in doc["tracks"].values()))
if __name__=="__main__":main()
