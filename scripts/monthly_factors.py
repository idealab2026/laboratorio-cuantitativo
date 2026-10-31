#!/usr/bin/env python3
"""Independent point-in-time monthly accounting and price factor computation.

No Yahoo download in this file. It accepts verified same-close market histories
and annual financial observations first seen before the decision. It emits only
finite scored candidates for the existing independent monthly allocators.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
import math
import statistics

from monthly_selection import SPECS, number
from yahoo_source import DEFAULT_UNIVERSE

CYCLE_SECTORS={
 "Energy","Materials","Industrials","Utilities",
 "Consumer Discretionary","Information Technology"
}
PRICE_REQUIRED=760
PERIOD_MIN=3
PERIOD_MAX=4


def ratio(a,b):
 if not number(a) or not number(b) or abs(b)<1e-10:return None
 return a/b


def med(values):
 clean=[float(v) for v in values if number(v)]
 return statistics.median(clean) if clean else None


def wmean(parts):
 valid=[(v,w) for v,w in parts if number(v) and number(w) and w>0]
 return sum(x*w for x,w in valid)/sum(w for _,w in valid) if valid else None


def percentile(group,x,invert=False):
 vals=[float(v) for v in group if number(v)]
 if not vals or not number(x):return None
 if len(vals)==1:rank=50
 else:rank=100*(sum(v<x for v in vals)+.5*sum(v==x for v in vals))/len(vals)
 return 100-rank if invert else rank


def _date(iso):
 if not isinstance(iso,str) or date.fromisoformat(iso).isoformat()!=iso:
  raise ValueError("Invalid point-in-time ISO date")
 return iso


def close_history(records,session):
 if not isinstance(records,list) or len(records)<PRICE_REQUIRED:
  raise ValueError("Not enough complete daily price history")
 prev=""
 close=[]
 for row in records:
  if not isinstance(row,dict):
   raise ValueError("Missing dated historical price")
  day=_date(row.get("date"))
  if day<=prev or day>session or not number(row.get("close")) or row["close"]<=0:
   raise ValueError("Stale, duplicated, future or invalid closing price")
  close.append(float(row["close"]))
  prev=day
 if prev!=session:raise ValueError("Latest closing bar is not the decision date")
 return close


def price_metrics(closes,reference):
 if len(closes)<253 or len(reference)<253:return None
 m=min(756,len(closes)-1,len(reference)-1)
 relative=(closes[-1]/closes[-m-1]-1)-(reference[-1]/reference[-m-1]-1) if m>=500 else None
 early=closes[-22]/closes[-253]-1
 m6=closes[-1]/closes[-127]-1
 ma=sum(closes[-200:])/200
 mean_ratio=closes[-1]/ma-1
 votes=int(early>0)+int(m6>0)+int(mean_ratio>0)
 changes=[closes[i]/closes[i-1]-1 for i in range(len(closes)-251,len(closes))]
 volatility=statistics.stdev(changes)*math.sqrt(252) if len(changes)>19 else None
 return {"relative":relative,"drawdown":closes[-1]/max(closes[-756:])-1,
         "momentum_12_1":early,"momentum_6m":m6,"ma200_ratio":mean_ratio,
         "price_votes":votes,"volatility_1y":volatility}


def annual_financials(packet,sector,session):
 if not isinstance(packet,dict) or not number(packet.get("market_cap")) or packet["market_cap"]<=0:
  raise ValueError("No verified current market capitalization")
 observed=_date(packet.get("available_at"))
 if observed>session:raise ValueError("Future accounting availability")
 periods=packet.get("periods")
 if not isinstance(periods,list) or not 3<=len(periods)<=4:
  raise ValueError("Need three or four observed annual statements")
 old=""
 order=sorted(periods,key=lambda p:p.get("date",""),reverse=True)
 for period in order:
  d=_date(period.get("date"))
  if d>=old and old:
   raise ValueError("Annual reports not strictly descending")
  if d>observed:raise ValueError("Financial statement not yet available")
  old=d
 latest=order[0];market_cap=packet["market_cap"]
 required=("revenue","ocf","capex")
 fcf,margin=[],[]
 for p in order:
  if all(number(p.get(k)) for k in required):
   value=p["ocf"]-abs(p["capex"])
   fcf.append(value)
   if p["revenue"]>0:margin.append(value/p["revenue"])
 if len(fcf)<3 and sector!="Financials":
  raise ValueError("Incomplete free cash flow history")
 debt=latest.get("debt");cash=latest.get("cash")
 net_cash=(cash if number(cash) else 0)-(debt if number(debt) else 0)
 operating=latest.get("operating_income")
 interest=latest.get("interest_expense")
 coverage=operating/abs(interest) if number(operating) and number(interest) and abs(interest)>1e-9 else (
  100. if number(debt) and debt<=0 else None)
 net_debt=max(0,-net_cash)
 debt_ocf=net_debt/latest["ocf"] if number(latest.get("ocf")) and latest["ocf"]>0 else (math.inf if net_debt>0 else None)
 revenue_growth=ratio(order[0].get("revenue"),order[1].get("revenue"))
 revenue_growth=revenue_growth-1 if number(revenue_growth) else None
 eq=latest.get("equity")
 book_to_market=ratio(eq,market_cap) if number(eq) and eq>0 else None
 buyback=abs(latest.get("repurchases",0))/market_cap if number(latest.get("repurchases",0)) else None
 issuance=abs(latest.get("issuance",0))/market_cap if number(latest.get("issuance",0)) else None
 profit=[p["net_income"] for p in order if number(p.get("net_income"))]
 def accel(vals):
  prev=med(vals[1:3])
  q=ratio(vals[0],prev) if prev is not None else None
  return q-1 if number(q) else None
 if sector=="Financials":
  if len(profit)<3:raise ValueError("Bank earnings history insufficient")
  roe=[p["net_income"]/p["equity"] for p in order[:3]
       if number(p.get("net_income")) and number(p.get("equity")) and p["equity"]>0]
  accelerated=accel(profit)
  fcf_yield=None;fcf_margin=None;positive_fcf=None
  profitable=sum(x>0 for x in profit[:3])
  survival=profitable>=2 and profit[0]>0
  quality_metric=med(roe)
  income_yield=ratio(med(profit[:3]),market_cap)
 else:
  accelerated=accel(fcf)
  fcf_yield=ratio(med(fcf[:3]),market_cap)
  fcf_margin=med(margin[:3])
  positive_fcf=sum(x>0 for x in fcf[:3])
  profitable=None;quality_metric=None;income_yield=None
  survival=bool(positive_fcf>=2 and fcf[0]>0 and
     (debt_ocf is None or debt_ocf<=5) and (coverage is None or coverage>=1.5))
 votes=int(number(revenue_growth) and revenue_growth>0)+int(number(accelerated) and accelerated>0)
 assets=[p.get("assets") for p in order]
 asset_growth=ratio(assets[0],assets[1])
 asset_growth=asset_growth-1 if number(asset_growth) else None
 asset_cagr=(assets[0]/assets[-1])**(1/(len(assets)-1))-1 if (
  all(number(v) and v>0 for v in assets)) else None
 capex_ratios=[abs(p["capex"])/p["revenue"] for p in order if number(p.get("capex")) and
               number(p.get("revenue")) and p["revenue"]>0]
 capex_intensity=med(capex_ratios)
 prior=med(capex_ratios[1:]);contract=ratio(capex_ratios[0],prior) if prior is not None and capex_ratios else None
 contract=contract-1 if number(contract) else None
 capital_survival=bool(number(latest.get("ocf")) and latest["ocf"]>0 and
  positive_fcf is not None and positive_fcf>=2 and
  (debt_ocf is None or debt_ocf<=6) and (coverage is None or coverage>=1.0))
 return {
  "available_at":observed,"statement_period":order[0]["date"],
  "annual_periods":len(order),
  "asset_growth":asset_growth,"asset_cagr":asset_cagr,
  "capex_intensity":capex_intensity,"capex_contraction":contract,
  "fcf_yield":fcf_yield,"fcf_margin":fcf_margin,
  "positive_fcf":positive_fcf,"operating_margin":ratio(operating,latest.get("revenue")),
  "net_debt_to_ocf":debt_ocf,"interest_coverage":coverage,
  "book_to_market":book_to_market,
  "earnings_yield":income_yield,"positive_profit":profitable,
  "roe":quality_metric,"net_cash_to_cap":None if sector=="Financials" else net_cash/market_cap,
  "buyback_yield":buyback,"issuance_yield":issuance,
  "revenue_growth":revenue_growth,
  "fundamental_votes":votes,
  "survival_dip":survival,"survival_cycle":capital_survival,
 }


def _r(peer,metric,value,invert=False):
 return percentile([p.get(metric) for p in peer],value,invert=invert)


def score_monthly(slot,candidates,benchmark,session):
 """Source-neutral monthly factor derivation; no prices fetched/persisted here."""
 if slot not in SPECS or not isinstance(candidates,list):
  raise ValueError("Unsupported fundamental model")
 _date(session)
 benchmark_close=close_history(benchmark,session)
 const=set(json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"])
 groups=defaultdict(list);seen=set()
 for candidate in candidates:
  if not isinstance(candidate,dict):
   raise ValueError("Invalid raw candidate")
  ticker=candidate.get("ticker")
  if ticker not in const or ticker in seen:
   raise ValueError("Foreign or duplicate index constituent")
  seen.add(ticker)
  sector=candidate.get("sector")
  if not isinstance(sector,str) or not sector:
   raise ValueError("No frozen GICS sector")
  if slot=="IL-038" and sector not in CYCLE_SECTORS:continue
  try:
   price=price_metrics(close_history(candidate["prices"],session),benchmark_close)
   finance=annual_financials(candidate["fundamental"],sector,session)
  except (ValueError,KeyError,TypeError,ZeroDivisionError):
   continue
  if not price or not finance:continue
  if slot=="IL-038" and sector=="Financials":continue
  # Evidence hashes only the available numerical research packet, not account metadata.
  sanitized={"ticker":ticker,"sector":sector,
             "prices":candidate["prices"],"fundamental":candidate["fundamental"]}
  evidence=hashlib.sha256(json.dumps(sanitized,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
  groups[sector].append({"ticker":ticker,"sector":sector,
                         **price,**finance,"evidence_sha256":evidence})
 rows=[r for peer in groups.values() for r in peer]
 if len(rows)<SPECS[slot]["minimum_scored"]:
  raise ValueError("Insufficient dated price/accounting factor coverage")
 result=[]
 if slot=="IL-038":
  sector_base={}
  scarcity_keys=("asset_growth","capex_contraction","relative","drawdown")
  for sector,peers in groups.items():
   sector_base[sector]={m:med([r.get(m) for r in peers]) for m in scarcity_keys}
  sector_scores={}
  for sector in groups:
   sector_scores[sector]=wmean([
     (_r(list(sector_base.values()),k,sector_base[sector][k],True),1)
     for k in scarcity_keys]) or 50.
  for sector,peer in groups.items():
   for r in peer:
    firm=wmean([
     (_r(peer,"asset_growth",r["asset_growth"],True),.22),
     (_r(peer,"asset_cagr",r["asset_cagr"],True),.18),
     (_r(peer,"capex_contraction",r["capex_contraction"],True),.22),
     (_r(peer,"relative",r["relative"],True),.20),
     (_r(peer,"drawdown",r["drawdown"],True),.18)])
    scarcity=wmean(((firm,.65),(sector_scores[sector],.35)))
    quality=wmean([
     (_r(peer,"fcf_margin",r["fcf_margin"]),.25),
     (_r(peer,"positive_fcf",r["positive_fcf"]),.15),
     (_r(peer,"operating_margin",r["operating_margin"]),.20),
     (_r(peer,"net_debt_to_ocf",r["net_debt_to_ocf"],True),.20),
     (_r(peer,"interest_coverage",r["interest_coverage"]),.20)])
    valuation=wmean([(_r(peer,"book_to_market",r["book_to_market"]),.45),
                     (_r(peer,"fcf_yield",r["fcf_yield"]),.55)])
    if not all(number(v) for v in (scarcity,quality,valuation,r["capex_intensity"])):
     continue
    result.append({
     "ticker":r["ticker"],"sector":sector,
     "capital_scarcity_score":scarcity,"quality_score":quality,
     "valuation_score":valuation,"inflection_score":100*r["price_votes"]/3,
     "inflection_votes":r["price_votes"],
     "sector_scarcity_score":sector_scores[sector],
     "capex_intensity":r["capex_intensity"],
     "survival_gate":r["survival_cycle"],
     "statement_period":r["statement_period"],"available_at":r["available_at"],
     "annual_periods":r["annual_periods"],"evidence_sha256":r["evidence_sha256"]})
 else:
  for sector,peer in groups.items():
   for r in peer:
    def rank(m,inv=False):return _r(peer,m,r.get(m),inv)
    if sector=="Financials":
     valuation=wmean(((rank("earnings_yield"),.45),(rank("book_to_market"),.55)))
     quality=wmean(((rank("roe"),.45),(rank("positive_profit"),.35),
                    (rank("revenue_growth"),.20)))
    else:
     valuation=wmean(((rank("fcf_yield"),.50),(rank("net_cash_to_cap"),.25),
                      (rank("book_to_market"),.25)))
     quality=wmean(((rank("fcf_margin"),.25),(rank("positive_fcf"),.20),
                    (rank("operating_margin"),.20),(rank("net_debt_to_ocf",True),.20),
                    (rank("interest_coverage"),.15)))
    allocation=wmean(((rank("buyback_yield"),.45),(rank("issuance_yield",True),.30),
                      (rank("net_cash_to_cap"),.25)))
    if allocation is None:
     allocation=wmean(((rank("buyback_yield"),.60),(rank("issuance_yield",True),.40)))
    dislocation=wmean(((rank("relative",True),.55),(rank("drawdown",True),.45)))
    votes=r["price_votes"]+r["fundamental_votes"]
    catalyst=100*votes/5
    if not all(number(v) for v in (valuation,quality,allocation,dislocation,catalyst)):
     continue
    result.append({
     "ticker":r["ticker"],"sector":sector,
     "valuation_score":valuation,"quality_score":quality,
     "capital_allocation_score":allocation,"dislocation_score":dislocation,
     "catalyst_score":catalyst,"catalyst_votes":votes,
     "volatility_1y":r["volatility_1y"],
     "survival_gate":r["survival_dip"],
     "statement_period":r["statement_period"],"available_at":r["available_at"],
     "annual_periods":r["annual_periods"],"evidence_sha256":r["evidence_sha256"]})
 if len(result)<SPECS[slot]["minimum_scored"]:
  raise ValueError("Insufficient complete peer-scored fundamental candidates")
 return result


def preflight():
 return {"status":"point_in_time_factor_scoring_offline",
         "models":list(SPECS),"source_required":"Yahoo/yfinance",
         "live_fundamental_capture":False}


if __name__=="__main__":
 print(json.dumps(preflight(),sort_keys=True))
