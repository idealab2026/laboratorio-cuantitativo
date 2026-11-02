#!/usr/bin/env python3
"""Independent, source-gated monthly paper book for two fundamental strategies.

Two accounts have their own cash, exposure, frozen monthly target orders and
signed NAV. No brokerage, historical backfill or fabricated market inputs.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import hmac
import json
import math

from monthly_selection import SPECS, due
from yahoo_source import DEFAULT_UNIVERSE, verify_snapshot

SCHEMA="idealab_monthly_paper_v1"
CAPITAL=100000.0
COMMISSION=.001
SLIPPAGE=.0005
MIN_NOTIONAL=10.0
SHARE_DECIMALS=6
CONFIG={"schema":SCHEMA,"slots":list(SPECS),"currency":"USD",
        "initial_capital":CAPITAL,"commission":COMMISSION,"slippage":SLIPPAGE,
        "min_notional":MIN_NOTIONAL,"share_decimals":SHARE_DECIMALS,
        "signal":"monthly_close","execution":"next_XNYS_open",
        "risk":"constrained_by_model_target_weights",
        "missing_held_bar":"quarantine_only_affected_book"}
CONFIG_SHA=hashlib.sha256(json.dumps(CONFIG,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def signature(doc,key):
 if not isinstance(key,str) or len(key)<32:
  raise ValueError("Institutional HMAC key required")
 raw=json.dumps({k:v for k,v in doc.items() if k!="signature"},
                sort_keys=True,separators=(",",":"),allow_nan=False).encode()
 return hmac.new(key.encode(),raw,hashlib.sha256).hexdigest()


def blank():
 return {"schema":SCHEMA,"status":"not_started","session":None,"source_sha256":None,
         "config_sha256":None,"books":{},"signature":None}


def _book():
 return {"cash":CAPITAL,"holdings":{},"pending":None,"history":[],
         "events":[],"last_signal":None,"paused":None}


def _positive(v):
 return type(v) in (int,float) and math.isfinite(v) and v>0


def verify(state,key=None):
 if not isinstance(state,dict) or set(state)!={
   "schema","status","session","source_sha256","config_sha256","books","signature"
 } or state["schema"]!=SCHEMA:
  raise ValueError("Untrusted monthly accounting schema")
 if state["status"]=="not_started":
  if state!=blank():raise ValueError("Tampered monthly campaign placeholder")
  return True
 if state["status"]!="prospective_paper" or state["config_sha256"]!=CONFIG_SHA or (
   not isinstance(state["signature"],str) or
   not hmac.compare_digest(state["signature"],signature(state,key))
 ):
  raise ValueError("Invalid signed monthly campaign or changed parameters")
 if not isinstance(state["session"],str) or len(state["source_sha256"] or "")!=64:
  raise ValueError("Unverified monthly market source")
 if set(state["books"])!=set(SPECS):
  raise ValueError("Both monthly strategies must be tracked separately")
 for slot,book in state["books"].items():
  if not isinstance(book,dict) or set(book)!={
    "cash","holdings","pending","history","events","last_signal","paused"
  }:
   raise ValueError("Unknown monthly book properties")
  if not _positive(book["cash"]+1e-8) or book["cash"] < -1e-7:
   raise ValueError("Negative or nonfinite paper cash")
  if not isinstance(book["holdings"],dict) or len(book["holdings"])>SPECS[slot]["max_positions"]:
   raise ValueError("Monthly position limit exceeded")
  for t,p in book["holdings"].items():
   if not isinstance(t,str) or not isinstance(p,dict) or set(p)!={
     "shares","entry_price","entry_date","sector"
   } or not _positive(p["shares"]) or not _positive(p["entry_price"]):
    raise ValueError("Malformed monthly position")
  if not isinstance(book["history"],list) or not 1<=len(book["history"])<=520:
   raise ValueError("Missing monthly NAV history")
  if book["history"][-1]["date"]>state["session"]:
   raise ValueError("Future monthly NAV")
  if book["paused"] is None and book["history"][-1]["date"]!=state["session"]:
   raise ValueError("Stale NAV without quarantine")
  if not isinstance(book["events"],list) or len(book["events"])>4000:
   raise ValueError("Unbounded monthly event history")
  if book["pending"] is not None:
   if not isinstance(book["pending"],dict) or set(book["pending"])!={
      "signal_date","next_session","targets","sectors"
   } or book["pending"]["signal_date"]!=book["last_signal"]:
    raise ValueError("Untrusted monthly pending order")
  for x in book["history"]:
   if not isinstance(x,dict) or set(x)!={"date","nav"} or not (
     type(x["nav"]) in (int,float) and math.isfinite(x["nav"]) and x["nav"]>=0
   ):
    raise ValueError("Invalid monthly NAV")
  if any(a["date"]>=b["date"] for a,b in zip(book["history"],book["history"][1:])):
   raise ValueError("Monthly NAV dates not increasing")
 return True


def _event(book,kind,session,**extra):
 book["events"].append({"type":kind,"date":session,**extra})
 book["events"]=book["events"][-4000:]


def _issue(book,decision,slot,session,next_session):
 if not isinstance(next_session,str) or date.fromisoformat(next_session)<=date.fromisoformat(session):
  raise ValueError("A closing signal must fill in a later XNYS session")
 if (not isinstance(decision,dict) or decision.get("slot")!=slot or
   decision.get("signal_date")!=session or
   decision.get("status")!="RESEARCH_TARGETS_PENDING_NEXT_OPEN_NOT_EXECUTED"
 ):
  raise ValueError("Missing point-in-time model decision")
 targets=decision.get("targets");sectors=decision.get("sectors")
 if not isinstance(targets,dict) or not isinstance(sectors,dict) or set(targets)!=set(sectors):
  raise ValueError("Mismatch in scored target sectors")
 spec=SPECS[slot]
 max_sector=spec["max_sector_positions"];weights_by_sector={}
 counts={}
 if len(targets)>spec["max_positions"]:
  raise ValueError("Too many monthly target securities")
 total=0
 for ticker,weight in targets.items():
  if not isinstance(ticker,str) or not isinstance(sectors[ticker],str) or not (
     type(weight) in (float,int) and math.isfinite(weight) and 0<weight<=spec["max_weight"]+1e-8
  ):raise ValueError("Invalid target entry weights")
  total+=weight;sector=sectors[ticker]
  counts[sector]=counts.get(sector,0)+1
  weights_by_sector[sector]=weights_by_sector.get(sector,0)+weight
  if counts[sector]>max_sector:raise ValueError("Sector exceeds name concentration")
 if total>min(decision.get("invest_fraction",1),.95)+1e-7:
  raise ValueError("Monthly target exceeds allowed exposure")
 if slot=="IL-039" and any(v>.30+1e-7 for v in weights_by_sector.values()):
  raise ValueError("Buy The Dip sector weight exceeds 30 percent")
 book["pending"]={"signal_date":session,"next_session":next_session,
                  "targets":dict(targets),"sectors":dict(sectors)}
 book["last_signal"]=session
 _event(book,"SIGNAL",session,positions=len(targets),expected_open=next_session)


def _sell(book,ticker,units,bar,session):
 current=book["holdings"][ticker]
 units=min(units,current["shares"])
 if units<=0:return
 execution=bar["open"]*(1-SLIPPAGE)
 proceeds=units*execution*(1-COMMISSION)
 book["cash"]+=proceeds
 current["shares"]-=units
 _event(book,"FILL",session,side="SELL",symbol=ticker,shares=units,price=execution)
 if current["shares"]<1e-8:del book["holdings"][ticker]


def _buy(book,ticker,budget,sector,bar,session):
 px=bar["open"]*(1+SLIPPAGE)
 scale=10**SHARE_DECIMALS
 units=math.floor(budget/(px*(1+COMMISSION))*scale)/scale
 cost=units*px*(1+COMMISSION)
 if units<=0 or cost<MIN_NOTIONAL or cost>book["cash"]+1e-8:
  _event(book,"SKIP",session,symbol=ticker,reason="notional_or_cash")
  return
 prior=book["holdings"].get(ticker)
 if prior:
  q=prior["shares"]+units
  prior["entry_price"]=(prior["shares"]*prior["entry_price"]+px*units)/q
  prior["shares"]=q
 else:
  book["holdings"][ticker]={"shares":units,"entry_price":px,
                            "entry_date":session,"sector":sector}
 book["cash"]-=cost
 _event(book,"FILL",session,side="BUY",symbol=ticker,shares=units,price=px)


def _settle(book,session,bars):
 pending=book["pending"]
 if pending is None:return
 if session!=pending["next_session"]:
  raise ValueError("Skipped scheduled market open: no retrospective fills")
 targets=pending["targets"]
 open_nav=book["cash"]+sum(p["shares"]*bars[t]["open"]
                            for t,p in book["holdings"].items())
 # Reduce holdings before adding positions. The goal is a frozen *weight*, not
 # a new signal calculated using today's price.
 for ticker in sorted(book["holdings"]):
  shares=book["holdings"][ticker]["shares"]
  over=shares*bars[ticker]["open"]-open_nav*targets.get(ticker,0)
  if over>MIN_NOTIONAL:_sell(book,ticker,over/bars[ticker]["open"],bars[ticker],session)
 open_nav=book["cash"]+sum(p["shares"]*bars[t]["open"]
                            for t,p in book["holdings"].items())
 for ticker,weight in sorted(targets.items()):
  current=book["holdings"].get(ticker,{}).get("shares",0)*bars[ticker]["open"]
  gap=open_nav*weight-current
  if gap>MIN_NOTIONAL:_buy(book,ticker,gap,pending["sectors"][ticker],bars[ticker],session)
 _event(book,"REBALANCE",session,previous_signal=pending["signal_date"])
 book["pending"]=None


def advance(state,snapshot,*,key,decisions=None,next_session=None,month_end=False):
 """One real closed session. The research scorer is a separately verified input."""
 verify(state,key)
 manifest=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
 verify_snapshot(snapshot,manifest["symbols"])
 session=snapshot["session"]
 if state["status"]=="prospective_paper" and session<=state["session"]:
  raise ValueError("Duplicate or reversed monthly source session")
 if decisions is None:decisions={}
 if not isinstance(decisions,dict) or set(decisions)-set(SPECS):
  raise ValueError("Unknown monthly decision")
 if not isinstance(month_end,bool):raise ValueError("Month-end calendar flag required")
 result=deepcopy(state)
 if result["status"]=="not_started":
  result["status"]="prospective_paper"
  result["books"]={slot:_book() for slot in SPECS}
  result["config_sha256"]=CONFIG_SHA
 bars=snapshot["bars"]
 for slot,book in result["books"].items():
  if book["paused"]:continue
  mandatory=set(book["holdings"])
  if book["pending"]:mandatory|=set(book["pending"]["targets"])
  missing=sorted(mandatory-set(bars))
  if missing:
   book["paused"]={"since":session,"missing":missing}
   _event(book,"QUARANTINE",session,missing=missing)
   continue
  for ticker,position in book["holdings"].items():
   bar=bars[ticker]
   if bar["split"]:
    position["shares"]*=bar["split"]
    position["entry_price"]/=bar["split"]
    _event(book,"SPLIT",session,symbol=ticker,factor=bar["split"])
   if bar["dividend"]:
    amount=position["shares"]*bar["dividend"]
    book["cash"]+=amount
    _event(book,"DIVIDEND",session,symbol=ticker,cash=amount)
  _settle(book,session,bars)
  nav=book["cash"]+sum(p["shares"]*bars[t]["close"] for t,p in book["holdings"].items())
  if not math.isfinite(nav) or nav<0 or len(book["history"])>=520:
   raise ValueError("Invalid or overlong month-end paper NAV")
  book["history"].append({"date":session,"nav":nav})
  needs_signal=due(book["last_signal"],session,month_end)
  if needs_signal:
   if slot not in decisions:
    raise ValueError("Missing due point-in-time month-end signal: "+slot)
   _issue(book,decisions[slot],slot,session,next_session)
  elif slot in decisions:
   raise ValueError("Unexpected intramonth research signal")
 result["session"]=session
 result["source_sha256"]=snapshot["sha256"]
 result["signature"]=signature(result,key)
 verify(result,key)
 return result


def safe_status():
 return {"status":"MONTHLY_PAPER_NOT_STARTED",
         "policy_books":list(SPECS),
         "fundamental_feed":"NOT_CONNECTED",
         "broker_orders":0,"real_positions":0}


if __name__=="__main__":
 print(json.dumps(safe_status(),sort_keys=True))
