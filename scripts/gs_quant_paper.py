#!/usr/bin/env python3
"""Independent GS Quant-inspired research cohort, NOT Goldman Sachs strategies.
Daily decisions from verified common snapshots; next-open OHLC paper convention
recorded after the session, not a contemporaneous execution or broker fill.
No API credentials, no real-money orders, no backfilled signals.
"""
from __future__ import annotations
import copy
import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from market_data.revisions import load_effective
from tfg_ahp.data import load_universe, eligible_session
from operational_clock import _write

STATE = ROOT / "data/gs-quant-paper.json"
START = "2026-11-25"
CAPITAL = 100000.
FEE = .001
SLIP = .0005
BORROW = .03
LOOKBACK = 21
MIN_COVERAGE = 350
NAMES = {
    "GS-01": "Momentum ajustado por volatilidad",
    "GS-02": "Reversión a la media (z-score)",
    "GS-03": "Risk parity (ERC)",
    "GS-04": "Pairs trading (OLS long/short)",
    "GS-05": "Multifactor cuantitativo",
    "GS-SPY": "Referencia SPY"
}
PAIRS = (("KO","PEP"),("V","MA"),("XOM","CVX"),("HD","LOW"),("JPM","BAC"),("PG","CL"))
RISK_SET = ("AAPL","MSFT","JPM","JNJ","PG","XOM","COST","UNH","NEE","CAT","WMT","DUK")

def blank():
    return {"schema":"midas.gs_quant_research.v1","campaign_start":START,
            "currency":"USD","initial_capital":CAPITAL,
            "execution_policy":"prospective_next_open_ohlc_simulation_after_close",
            "commission":FEE,"slippage":SLIP,"annual_short_borrow_assumption":BORROW,
            "books":{k:{"name":name,"cash":CAPITAL,"positions":{},"pending":None,
                       "last_session":None,"history":[],"trades":[],"signals":[],
                       "status":"awaiting_first_signal","diagnostic":None}
                     for k,name in NAMES.items()}}

def sha(value):
    import hashlib
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
                         allow_nan=False).encode()).hexdigest()

def dates_for(session):
    import pandas_market_calendars as calendars
    day=date.fromisoformat(session)
    sch=calendars.get_calendar("XNYS").schedule(
        start_date=day-timedelta(days=60),end_date=day+timedelta(days=12))
    days=[d.date().isoformat() for d in sch.index]
    i=days.index(session)
    if i<LOOKBACK-1 or i==len(days)-1:
        raise ValueError("Insufficient exchange calendar")
    return days[i-LOOKBACK+1:i+1], days[i-1], days[i+1], sch.loc[days[i+1],"market_open"].to_pydatetime()

def panel_from_snapshots(snapshots, symbols):
    # Exact consecutive sessions only. No filling missing bars, no price
    # normalization across a split or ticker transition. Price signals only;
    # cash distributions enter the ledger separately.
    result={}
    for t in sorted(symbols):
        rows=[s["bars"].get(t) for s in snapshots]
        if any(r is None or r.get("split") for r in rows):
            continue
        if len({r["provider_symbol"] for r in rows})!=1:
            continue
        p=np.array([r["close"] for r in rows],dtype=float)
        if len(p)==LOOKBACK and np.isfinite(p).all() and (p>0).all():
            result[t]=p
    return result

def equal_top(scores, n=10, fraction=.90):
    return {t:fraction/n for t,score in sorted(scores.items(),key=lambda r:(-r[1],r[0]))[:n]}

def risk_parity(returns):
    """Long-only equal risk contribution, diagonal shrinkage for stability."""
    cov=np.cov(returns,rowvar=False,ddof=1)
    cov=.8*cov+.2*np.diag(np.diag(cov))+np.eye(cov.shape[0])*1e-10
    x=np.ones(cov.shape[0])/np.sqrt(np.diag(cov))
    for _ in range(1000):
        old=x.copy()
        for i in range(len(x)):
            a=cov[i,i]; b=cov[i]@x-a*x[i]
            x[i]=2/(math.sqrt(b*b+4*a)+b)
        if np.max(np.abs(x-old)/(1+np.abs(old)))<1e-10:
            break
    else:
        raise ValueError("Risk parity did not converge")
    return x/x.sum()

def targets_for(slot,panel):
    if slot=="GS-SPY":
        if "SPY" not in panel: raise ValueError("Missing benchmark history")
        return {"SPY":.90}
    if len(set(panel)-{"SPY"})<MIN_COVERAGE:
        raise ValueError("Insufficient complete price history")
    ret={t:np.diff(np.log(p)) for t,p in panel.items() if t!="SPY"}
    vol={t:float(np.std(r,ddof=1)) for t,r in ret.items()}
    mom={t:float(np.log(panel[t][-1]/panel[t][0])) for t in ret}
    if slot=="GS-01":
        return equal_top({t:mom[t]/vol[t] for t in ret if vol[t]>1e-8 and mom[t]>0})
    if slot=="GS-02":
        scores={}
        for t in ret:
            p=np.log(panel[t]); s=float(np.std(p[:-1],ddof=1))
            if s>1e-8:
                z=float((p[-1]-p[:-1].mean())/s)
                if z < -1.5: scores[t]=-z
        return equal_top(scores)
    if slot=="GS-03":
        names=[t for t in RISK_SET if t in ret and vol[t]>1e-8]
        if len(names)<8: raise ValueError("Insufficient risk-parity basket")
        w=risk_parity(np.column_stack([ret[t] for t in names]))
        return {t:float(.90*v) for t,v in zip(names,w)}
    if slot=="GS-04":
        ranked=[]
        for a,b in PAIRS:
            if a not in ret or b not in ret: continue
            x=np.log(panel[b]); y=np.log(panel[a])
            if np.std(x[:-1])<1e-8: continue
            beta,alpha=np.polyfit(x[:-1],y[:-1],1)
            resid=y[:-1]-alpha-beta*x[:-1]
            std=float(np.std(resid,ddof=1))
            corr=float(np.corrcoef(ret[a][:-1],ret[b][:-1])[0,1])
            if std<=1e-8 or not math.isfinite(corr) or corr<.4 or not .2<=beta<=3: continue
            z=float((y[-1]-alpha-beta*x[-1]-resid.mean())/std)
            if abs(z)>=1.5: ranked.append((abs(z),a,b,z))
        out={}
        for _,a,b,z in sorted(ranked,key=lambda x:(-x[0],x[1],x[2]))[:5]:
            # Dollar-neutral legs; beta is signal estimation, not hedge sizing.
            out[a]=-.09 if z>0 else .09
            out[b]=-out[a]
        return out
    if slot=="GS-05":
        def ranks(values):
            order=sorted(values,key=lambda t:(values[t],t))
            return {t:i/max(1,len(order)-1) for i,t in enumerate(order)}
        r1=ranks(mom); r2=ranks({t:-vol[t] for t in ret})
        r3=ranks({t:-float(np.sum(ret[t][-5:])) for t in ret})
        return equal_top({t:.5*r1[t]+.3*r2[t]+.2*r3[t] for t in ret})
    raise ValueError("Unknown strategy")

def validate_targets(slot,weights,universe):
    if not isinstance(weights,dict) or set(weights)-set(universe):
        raise ValueError("Foreign target")
    if any(type(w) not in (float,int) or not math.isfinite(w) or abs(w)>.90 for w in weights.values()):
        raise ValueError("Invalid target")
    gross=sum(abs(w) for w in weights.values())
    if gross>.90000001 or (slot!="GS-04" and any(w<0 for w in weights.values())):
        raise ValueError("Exposure violation")
    if slot=="GS-04" and abs(sum(weights.values()))>1e-8:
        raise ValueError("Pairs not dollar neutral")
    if slot=="GS-SPY" and set(weights)!={"SPY"}:
        raise ValueError("Invalid benchmark")

def validate(state):
    seed=blank()
    for k in ("schema","campaign_start","currency","initial_capital","execution_policy",
              "commission","slippage","annual_short_borrow_assumption"):
        if state.get(k)!=seed[k]: raise ValueError("Changed campaign contract")
    if set(state["books"])!=set(NAMES): raise ValueError("Changed cohort")
    for slot,b in state["books"].items():
        if b["name"]!=NAMES[slot] or not math.isfinite(b["cash"]) or b["cash"]<0:
            raise ValueError("Invalid cash or identity")
        if any(not math.isfinite(v) or v==0 or (v<0 and slot!="GS-04") for v in b["positions"].values()):
            raise ValueError("Invalid position")
        h=b["history"]
        if h:
            if b["last_session"]!=h[-1]["date"] or any(x["date"]<START or not math.isfinite(x["nav"]) or x["nav"]<=0 for x in h):
                raise ValueError("Invalid dated NAV")
            if any(a["date"]>=z["date"] for a,z in zip(h,h[1:])):
                raise ValueError("Nonmonotone NAV")
        elif b["last_session"] is not None or b["positions"] or b["trades"]:
            raise ValueError("Economics without ledger")
        if b["pending"] and b["pending"]["signal_session"]!=b["last_session"]:
            raise ValueError("Pending decision does not match last session")
    return True

def advance_book(slot,old,session,previous,next_session,now,source,history_hashes,panel,universe):
    b=copy.deepcopy(old)
    if b["last_session"]==session: return b
    if b["last_session"] and b["last_session"]!=previous:
        raise ValueError("Session gap: manual mark-only recovery required")
    if not b["last_session"] and session!=START:
        raise ValueError("Initial session missed; no retroactive launch")
    bars=source["bars"]; held=set(b["positions"])
    if any(t not in bars or bars[t].get("split") for t in held):
        raise ValueError("Held quote or corporate action unavailable")
    if b["last_session"]:
        # Only the prior close holdings earn/pay ex-date cash distributions;
        # a short has a manufactured-dividend debit and assumed borrow charge.
        days=(date.fromisoformat(session)-date.fromisoformat(previous)).days
        b["cash"]+=sum(q*bars[t]["dividend"] for t,q in b["positions"].items())
        b["cash"]-=sum(-q*bars[t]["open"]*BORROW*days/365
                       for t,q in b["positions"].items() if q<0)
    p=b["pending"]
    if p:
        if p["target_session"]!=session:
            raise ValueError("Expired order: never execute retrospectively")
        weights=p["weights"]; validate_targets(slot,weights,universe)
        required=held|set(weights)
        if any(t not in bars or bars[t].get("split") for t in required):
            b["diagnostic"]="opening_rebalance_cancelled_missing_exact_bar_or_split"
        else:
            open_nav=b["cash"]+sum(q*bars[t]["open"] for t,q in b["positions"].items())
            if open_nav<=0: raise ValueError("Nonpositive opening NAV")
            desired={t:math.trunc(open_nav*w/bars[t]["open"]*1e6)/1e6
                     for t,w in weights.items()}
            fills=[]
            for t in sorted(required):
                delta=desired.get(t,0)-b["positions"].get(t,0)
                if abs(delta)<1e-9: continue
                px=bars[t]["open"]*(1+SLIP if delta>0 else 1-SLIP)
                fee=abs(delta)*px*FEE
                b["cash"]-=delta*px+fee
                fills.append({"date":session,"ticker":t,"shares":delta,"price":px,
                              "fee":fee,"signal_sha256":p["sha256"],
                              "source_sha256":source["effective_sha256"],
                              "recorded_at_utc":now.isoformat(),
                              "execution":"next_open_ohlc_paper_not_observed"})
            if b["cash"]<0: raise ValueError("Cash constraint")
            b["positions"]={t:q for t,q in desired.items() if q}
            b["trades"].extend(fills)
            b["diagnostic"]=None
    nav=b["cash"]+sum(q*bars[t]["close"] for t,q in b["positions"].items())
    if not math.isfinite(nav) or nav<=0 or b["cash"]<0:
        raise ValueError("Invalid closing economics")
    b["history"].append({"date":session,"nav":nav,"source_sha256":source["effective_sha256"]})
    b["last_session"]=session
    b["pending"]=None
    try:
        weights=targets_for(slot,panel)
        validate_targets(slot,weights,universe)
        signal={"signal_session":session,"target_session":next_session,
                "issued_at_utc":now.isoformat(),"weights":weights,
                "source_hashes":history_hashes}
        signal["sha256"]=sha(signal)
        b["signals"].append(signal)
        b["pending"]=signal
        b["status"]="paper_signal_frozen"
    except ValueError as exc:
        b["status"]="marked_no_new_signal"
        b["diagnostic"]=str(exc)
    return b

def run(now=None):
    now=now or datetime.now(timezone.utc)
    session=eligible_session(now)
    if session is None or session<START:
        return {"status":"awaiting_inaugural_close"}
    dates,previous,next_session,next_open=dates_for(session)
    if now>=next_open: raise ValueError("Missed causal decision window")
    symbols,_=load_universe(ROOT/"weekly_ml/universe_sp500_2026-09-29.csv")
    if len(symbols)!=503: raise ValueError("Wrong frozen universe")
    universe=set(symbols)|{"SPY"}
    snapshots=[load_effective(ROOT/"market_data/snapshots",d) for d in dates]
    if any(datetime.fromisoformat(s["last_captured_at_utc"].replace("Z","+00:00"))>now
           for s in snapshots): raise ValueError("Snapshot unavailable at decision time")
    panel=panel_from_snapshots(snapshots,universe)
    hashes=[{"session":d,"sha256":s["effective_sha256"]} for d,s in zip(dates,snapshots)]
    state=json.loads(STATE.read_text())
    validate(state)
    updated=copy.deepcopy(state)
    for slot,b in state["books"].items():
        if b["last_session"]==session: continue
        try:
            updated["books"][slot]=advance_book(slot,b,session,previous,next_session,now,
                                               snapshots[-1],hashes,panel,universe)
        except ValueError as exc:
            updated["books"][slot]["status"]="blocked"
            updated["books"][slot]["diagnostic"]=str(exc)
    validate(updated)
    if updated!=state: _write(STATE,updated)
    return {"status":"cohort_checked","session":session,"history_coverage":len(panel)-("SPY" in panel),
            "books":{k:{"status":v["status"],"last_session":v["last_session"],
                        "trades":len(v["trades"])} for k,v in updated["books"].items()}}

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
