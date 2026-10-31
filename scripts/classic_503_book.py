#!/usr/bin/env python3
"""Prospective 503-component paper settlement, isolated from archived portfolios.

A common verifiable XNYS source supplies all model books. Never trade, fetch
private accounts, backfill missing opens or fabricate a mark for an unpriced
holding. Model state is HMAC-signed; only checked summaries reach the UI.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
import math

from classic_503 import (
    MODELS, STRATEGY_RISK, MAX_HOLDINGS, WEIGHT_LIMIT,
    COMMISSION, SLIPPAGE, INVEST_FRACTION, STARTING_CAPITAL,
    decisions, frozen_intents, ordered_history,
)
from yahoo_source import DEFAULT_UNIVERSE, verify_snapshot

SCHEMA="idealab_classic_503_paper_v1"
CONFIG={"schema":SCHEMA,"market":"XNYS","source":"Yahoo/yfinance RAW",
        "currency":"USD","capital":STARTING_CAPITAL,
        "commission":COMMISSION,"slippage":SLIPPAGE,
        "invest_fraction":INVEST_FRACTION,"max_weight":WEIGHT_LIMIT,
        "max_positions":MAX_HOLDINGS,"constituents":503,
        "strategies":MODELS,"timing":"close_signal_next_open",
        "quarantine_missing_held_quote":True}
CONFIG_SHA=hashlib.sha256(json.dumps(CONFIG,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def canonical(value):
    return json.dumps({k:v for k,v in value.items() if k!="signature"},
                      sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def authenticate(state,key):
    if not isinstance(key,str) or len(key)<32:
        raise ValueError("Institutional HMAC secret required")
    return hmac.new(key.encode(),canonical(state),hashlib.sha256).hexdigest()


def blank_state():
    return {"schema":SCHEMA,"status":"not_started","session":None,
            "source_sha256":None,"config_sha256":None,
            "books":{},"signature":None}


def account():
    return {"cash":STARTING_CAPITAL,"holdings":{},"pending":[],
            "history":[],"events":[],"paused":None}


def verify_book(state,key=None):
    if not isinstance(state,dict) or set(state)!={"schema","status","session",
        "source_sha256","config_sha256","books","signature"} or state["schema"]!=SCHEMA:
        raise ValueError("Unrecognized classical account format")
    if state["status"]=="not_started":
        if state!=blank_state():raise ValueError("Tampered empty classic campaign")
        return True
    if state["status"]!="prospective_paper" or state["config_sha256"]!=CONFIG_SHA:
        raise ValueError("Foreign classic campaign or model parameters")
    if not isinstance(state["signature"],str) or not hmac.compare_digest(
            authenticate(state,key),state["signature"]):
        raise ValueError("Bad institutional book signature")
    if not isinstance(state["session"],str) or len(state["source_sha256"] or "")!=64:
        raise ValueError("Missing dated source provenance")
    if set(state["books"])!=set(MODELS):
        raise ValueError("Unrecognized strategy set")
    for slot,book in state["books"].items():
        if not isinstance(book,dict) or set(book)!={"cash","holdings","pending",
                                                    "history","events","paused"}:
            raise ValueError("Unknown book properties")
        if not isinstance(book["cash"],(int,float)) or not math.isfinite(book["cash"]) or book["cash"]<-.00001:
            raise ValueError("Inconsistent cash")
        cap=503 if MODELS[slot]=="equal_hold" else MAX_HOLDINGS
        if not isinstance(book["holdings"],dict) or len(book["holdings"])>cap:
            raise ValueError("Position count outside risk contract")
        for ticker,pos in book["holdings"].items():
            if not isinstance(ticker,str) or not isinstance(pos,dict) or set(pos)!={
                    "shares","entry","stop","target","dividends"}:
                raise ValueError("Invalid equity exposure")
            if not math.isfinite(pos["shares"]) or pos["shares"]<=0 or pos["entry"]<=0:
                raise ValueError("Invalid holding quantity/cost")
        if not isinstance(book["pending"],list) or len(book["pending"])>503 or not isinstance(book["events"],list):
            raise ValueError("Invalid event or order history")
        if not 1<=len(book["history"])<=520 or book["history"][-1]["date"]>state["session"]:
            raise ValueError("Incorrect dated NAV records")
        for i,point in enumerate(book["history"]):
            if set(point)!={"date","nav"} or not isinstance(point["nav"],(float,int)) or not math.isfinite(point["nav"]) or point["nav"]<0:
                raise ValueError("Invalid NAV point")
            if i and point["date"]<=book["history"][i-1]["date"]:
                raise ValueError("Unordered NAV history")
        if book["paused"] is None:
            if book["history"][-1]["date"]!=state["session"]:
                raise ValueError("Stale NAV without quarantine")
        elif not isinstance(book["paused"],dict) or set(book["paused"])!={"since","missing"} or not book["paused"]["missing"]:
            raise ValueError("Malformed missing-held-price quarantine")
    return True


def close_holding(book,ticker,price,session,reason):
    pos=book["holdings"].pop(ticker)
    execution=price*(1-SLIPPAGE)
    charge=pos["shares"]*execution*COMMISSION
    book["cash"]+=pos["shares"]*execution-charge
    book["events"].append({"type":"SELL","symbol":ticker,"date":session,
                           "quantity":pos["shares"],"price":execution,
                           "fee":charge,"reason":reason})


def book_step(book,slot,snapshot,session):
    if book["paused"]:
        return
    today=snapshot["bars"]
    mandatory=set(book["holdings"])|{
        q["ticker"] for q in book["pending"] if q["side"]=="sell"}
    absent=sorted(mandatory-set(today))
    if absent:
        book["paused"]={"since":session,"missing":absent}
        book["events"].append({"type":"QUARANTINE","date":session,
                               "missing":absent})
        return
    model=MODELS[slot]
    for ticker,pos in book["holdings"].items():
        source=today[ticker]
        factor=source["split"]
        if factor:
            pos["shares"]*=factor
            if pos["stop"] is not None:pos["stop"]/=factor
            if pos["target"] is not None:pos["target"]/=factor
            book["events"].append({"type":"SPLIT","date":session,
                                   "symbol":ticker,"factor":factor})
        if source["dividend"]:
            amount=pos["shares"]*source["dividend"]
            book["cash"]+=amount
            pos["dividends"]+=amount
            book["events"].append({"type":"DIVIDEND","date":session,
                                   "symbol":ticker,"amount":amount})
    sell_list=sorted(q["ticker"] for q in book["pending"] if q["side"]=="sell")
    for ticker in sell_list:
        if ticker not in book["holdings"]:
            raise ValueError("Unbacked previous-close SELL")
        close_holding(book,ticker,today[ticker]["open"],session,"SIGNAL_NEXT_OPEN")
    buys=sorted(q["ticker"] for q in book["pending"] if q["side"]=="buy")
    nav_at_open=book["cash"]+sum(pos["shares"]*today[t]["open"] for t,pos in book["holdings"].items())
    if buys:
        budget=(nav_at_open*INVEST_FRACTION/503) if model=="equal_hold" else min(
            nav_at_open*INVEST_FRACTION/len(buys),
            nav_at_open*(INVEST_FRACTION if model=="benchmark" else WEIGHT_LIMIT))
        for ticker in buys:
            if ticker in book["holdings"]:
                continue
            if ticker not in today:
                book["events"].append({"type":"UNFILLED_NO_BAR","date":session,
                                       "symbol":ticker})
                continue
            bar=today[ticker]
            execution=bar["open"]*(1+SLIPPAGE)
            lots=math.floor(budget/(execution*(1+COMMISSION))*1_000_000)/1_000_000
            amount=lots*execution*(1+COMMISSION)
            if amount<10 or amount>book["cash"]+.000001:
                book["events"].append({"type":"UNFILLED_NOTIONAL","date":session,
                                       "symbol":ticker})
                continue
            stop,target=STRATEGY_RISK.get(model,(None,None))
            book["holdings"][ticker]={"shares":lots,"entry":execution,
                                      "stop":execution*(1-stop) if stop else None,
                                      "target":execution*(1+target) if target else None,
                                      "dividends":0.0}
            book["cash"]-=amount
            book["events"].append({"type":"BUY","date":session,"symbol":ticker,
                                   "quantity":lots,"price":execution,
                                   "fee":lots*execution*COMMISSION})
    book["pending"]=[]
    # The stop is deliberately checked before a concurrent target; stop wins.
    for ticker,pos in list(book["holdings"].items()):
        bar=today[ticker]
        if pos["stop"] is not None and bar["low"]<=pos["stop"]:
            close_holding(book,ticker,min(bar["open"],pos["stop"]),session,"STOP_FIRST")
        elif pos["target"] is not None and bar["high"]>=pos["target"]:
            close_holding(book,ticker,max(bar["open"],pos["target"]),session,"TARGET")
    nav=book["cash"]+sum(pos["shares"]*today[t]["close"] for t,pos in book["holdings"].items())
    if nav<0 or not math.isfinite(nav):
        raise ValueError("Impossible classic portfolio NAV")
    if len(book["history"])>=520:
        raise ValueError("Reached audited NAV retention capacity")
    book["history"].append({"date":session,"nav":nav})


def advance(state,snapshot,history,*,key):
    """Close-date source, prior frozen orders; no retroactive research backfill."""
    verify_book(state,key)
    manifest=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
    verify_snapshot(snapshot,manifest["symbols"])
    session=snapshot["session"]
    if state["status"]=="prospective_paper" and session<=state["session"]:
        raise ValueError("Duplicate or reversed research session")
    report=decisions(history,session)
    if report["eligible"]<453:
        raise ValueError("Insufficient investable historical coverage")
    # Reject revised or conflicting OHLC across independent pulls of the same day.
    for symbol in report["missing"]:
        if symbol in snapshot["bars"] and symbol in history and history[symbol]:
            raise ValueError("Historical provider row disagrees with canonical source eligibility")
    for symbol in snapshot["bars"]:
        if symbol in history and len(history[symbol])>=80:
            row=ordered_history(history[symbol],session,symbol)[-1]
            bar=snapshot["bars"][symbol]
            if any(abs(row[k]-bar[k])>max(.000001,abs(bar[k])*.0000001)
                   for k in ("open","high","low","close")):
                raise ValueError("History and immutable daily capture disagree")
    if state["status"]=="not_started":
        books={slot:account() for slot in MODELS}
        orders=frozen_intents(report,{slot:[] for slot in MODELS})
        for slot,book in books.items():
            book["pending"]=orders[slot]
            book["history"].append({"date":session,"nav":STARTING_CAPITAL})
            book["events"].append({"type":"SIGNAL","date":session,
                                   "queued":len(book["pending"])})
    else:
        books=deepcopy(state["books"])
        for slot in MODELS:
            book_step(books[slot],slot,snapshot,session)
        orders=frozen_intents(report,{slot:list(books[slot]["holdings"]) for slot in MODELS})
        for slot,book in books.items():
            if book["paused"]:
                continue
            book["pending"]=orders[slot]
            book["events"].append({"type":"SIGNAL","date":session,
                                   "queued":len(book["pending"])})
    result={"schema":SCHEMA,"status":"prospective_paper","session":session,
            "source_sha256":snapshot["sha256"],"config_sha256":CONFIG_SHA,
            "books":books,"signature":None}
    result["signature"]=authenticate(result,key)
    verify_book(result,key)
    return result


def summary_rows(state,snapshot,*,key):
    """Safe scoreboard per institutional slot; never outputs raw Yahoo history."""
    verify_book(state,key)
    if state["source_sha256"]!=snapshot["sha256"] or state["session"]!=snapshot["session"]:
        raise ValueError("Ledger is unrelated to source")
    output=[]
    for slot,book in state["books"].items():
        points=book["history"]
        final=points[-1]["nav"]
        peak=STARTING_CAPITAL
        drawdown=0
        for point in points:
            peak=max(peak,point["nav"])
            drawdown=min(drawdown,100*(point["nav"]/peak-1))
        last_return=None if len(points)<2 or points[-2]["nav"]==0 else (
            100*(points[-1]["nav"]/points[-2]["nav"]-1))
        output.append({
            "slot":slot,"activity":"paused" if book["paused"] else
                ("active" if book["holdings"] else "pending"),
            "currency":"USD","first_session":points[0]["date"],
            "last_session":points[-1]["date"],
            "initial_capital":STARTING_CAPITAL,"last_equity":final,
            "return_pct":100*(final/STARTING_CAPITAL-1),
            "day_return_pct":last_return,
            "risk":{"volatility_pct":None,"max_drawdown_pct":drawdown,
                    "sharpe_0rf":None},
            "positions":len(book["holdings"]),
            "pending_orders":len(book["pending"]),
            "comparison":{"eligible":False,"universe_id":None},
            "history":points,"source_snapshot_sha256":snapshot["sha256"],
            "config_sha256":CONFIG_SHA})
    return output
