#!/usr/bin/env python3
"""Independent research contracts for two MIDAS monthly fundamental strategies.

Produces only closed-session *target weights* on a candidate set that has already
been derived from appropriately dated Yahoo accounting/price evidence. It does
not fabricate fundamentals, reconstruct prior decisions or submit market orders.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
import math
import re

SPECS = {
 "IL-038": {
  "kind": "capital_cycle", "minimum_scored": 35, "max_positions": 12,
  "max_sector_positions": 4, "max_weight": .10, "capital_fraction": .95,
  "entry": 60, "retention": 45, "hard_exit": 35,
  "min_quality": 40, "min_sector_scarcity": 35,
  "minimum_votes": 2, "hold_months": 3,
  "fields": ("capital_scarcity_score","quality_score","valuation_score","inflection_score"),
  "weights": (.45,.30,.15,.10)
 },
 "IL-039": {
  "kind": "buy_the_dip", "minimum_scored": 80, "max_positions": 10,
  "max_sector_positions": 3, "max_sector_weight": .30,
  "max_weight": .15, "entry": 60, "retention": 45, "hard_exit": 30,
  "min_quality": 35, "min_valuation": 50, "min_dislocation": 40,
  "minimum_votes": 2, "hold_months": 3,
  "fields": ("valuation_score","quality_score","capital_allocation_score",
             "dislocation_score","catalyst_score"),
  "weights": (.30,.20,.15,.20,.15),
  "exposure_tiers": ((10,.95),(7,.90),(4,.70),(1,.50),(0,.0))
 }
}
SYMBOL=re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
SHA=re.compile(r"^[a-f0-9]{64}$")


def number(value):
 return type(value) in (int,float) and math.isfinite(value)


def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def months_between(a,b):
 first,last=date.fromisoformat(a),date.fromisoformat(b)
 return (last.year-first.year)*12+last.month-first.month


def due(last_signal,session,month_end):
 """Launch immediately, next monthly close thereafter; report missed-month recovery."""
 if last_signal is None:return True
 if session<=last_signal:raise ValueError("Monthly signal cannot run backwards")
 if month_end:return True
 return months_between(last_signal,session)>=2


def _weighted(values,weights):
 usable=[(x,w) for x,w in zip(values,weights) if number(x) and number(w) and w>0]
 return sum(x*w for x,w in usable)/sum(w for _,w in usable) if usable else None


def _verify_candidates(slot,rows,session):
 from yahoo_source import DEFAULT_UNIVERSE
 universe=set(json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"])
 if slot not in SPECS or not isinstance(rows,list):
  raise ValueError("Unknown monthly model or absent scored candidates")
 if not isinstance(session,str) or date.fromisoformat(session).isoformat()!=session:
  raise ValueError("Noncanonical decision date")
 spec=SPECS[slot]
 if len(rows)<spec["minimum_scored"]:
  raise ValueError("Insufficient point-in-time fundamental candidate coverage")
 seen=set()
 normalized=[]
 for item in rows:
  if not isinstance(item,dict):
   raise ValueError("Invalid scored row")
  ticker=item.get("ticker")
  if not isinstance(ticker,str) or not SYMBOL.fullmatch(ticker) or ticker not in universe or ticker in seen:
   raise ValueError("Foreign or duplicate instrument in frozen universe")
  seen.add(ticker)
  if not isinstance(item.get("sector"),str) or not 2<=len(item["sector"])<=80:
   raise ValueError("Missing frozen sector identity")
  for name in ("statement_period","available_at"):
   value=item.get(name)
   if not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value:
    raise ValueError("Missing dated accounting availability")
  if not item["statement_period"]<=item["available_at"]<=session:
   raise ValueError("Future/unavailable financial statement or score")
  if type(item.get("annual_periods")) is not int or item["annual_periods"]<3 or item["annual_periods"]>4:
   raise ValueError("Insufficient annual financial statements")
  if not isinstance(item.get("evidence_sha256"),str) or not SHA.fullmatch(item["evidence_sha256"]):
   raise ValueError("Untraceable fundamental source")
  if not isinstance(item.get("survival_gate"),bool):
   raise ValueError("Unverified solvency gate")
  for field in spec["fields"]:
   if not number(item.get(field)) or not 0<=item[field]<=100:
    raise ValueError("Missing point-in-time factor: "+field)
  computed=_weighted((item[f] for f in spec["fields"]),spec["weights"])
  if not number(computed):
   raise ValueError("Missing composite score")
  row=dict(item,composite_score=computed)
  if slot=="IL-038":
   if not number(item.get("capex_intensity")) or item["capex_intensity"]<0:
    raise ValueError("Missing capex-to-revenue intensity")
   votes=item.get("inflection_votes")
   scarcity=item.get("sector_scarcity_score")
   if type(votes) is not int or not 0<=votes<=3 or not number(scarcity) or not 0<=scarcity<=100:
    raise ValueError("Invalid capital-cycle phase evidence")
   row["entry_eligible"]=bool(
     item["survival_gate"] and item["quality_score"]>=spec["min_quality"] and
     scarcity>=spec["min_sector_scarcity"] and votes>=spec["minimum_votes"] and
     item.get("capex_intensity",0)>=.025 and computed>=spec["entry"])
   row["hard_exit"]=not item["survival_gate"] or votes==0 or computed<spec["hard_exit"]
  else:
   votes=item.get("catalyst_votes")
   vol=item.get("volatility_1y")
   if type(votes) is not int or not 0<=votes<=5 or (
      vol is not None and (not number(vol) or vol<0)):
    raise ValueError("Invalid dislocation/volatility evidence")
   opportunity=item["dislocation_score"]>=spec["min_dislocation"] or item["valuation_score"]>=70
   row["entry_eligible"]=bool(
     item["survival_gate"] and opportunity and item["quality_score"]>=spec["min_quality"] and
     item["valuation_score"]>=spec["min_valuation"] and votes>=spec["minimum_votes"] and
     computed>=spec["entry"])
   row["hard_exit"]=not item["survival_gate"] or computed<spec["hard_exit"]
   row["rerated"]=item["valuation_score"]<25 and item["dislocation_score"]<30
  normalized.append(row)
 return sorted(normalized,key=lambda r:(-r["composite_score"],r["ticker"]))


def _safe_positions(positions,universe,session):
 if not isinstance(positions,dict):
  raise ValueError("Holdings must be an explicit dictionary")
 for ticker,pos in positions.items():
  if ticker not in universe or not isinstance(pos,dict) or "entry_date" not in pos:
   raise ValueError("Unrecognized held position")
  if date.fromisoformat(pos["entry_date"])>date.fromisoformat(session):
   raise ValueError("Future position entry")


def _buy_the_dip_weights(selected,exposure,spec):
 if not selected or exposure<=0:return {}
 raw={}
 for row in selected:
  vol=row.get("volatility_1y")
  if not number(vol):vol=.35
  raw[row["ticker"]]=(max(row["composite_score"],1)/100)**2/math.sqrt(max(.12,vol))
 total=sum(raw.values())
 weights={t:min(exposure*w/total,spec["max_weight"]) for t,w in raw.items()}
 sectors={}
 for row in selected:sectors.setdefault(row["sector"],[]).append(row["ticker"])
 for tickers in sectors.values():
  current=sum(weights[t] for t in tickers)
  if current>spec["max_sector_weight"]:
   scale=spec["max_sector_weight"]/current
   for t in tickers:weights[t]*=scale
 return {t:w for t,w in weights.items() if w>0}


def choose(slot,rows,positions,session):
 """Select next-month long target weights from attested prospective scored rows."""
 ranked=_verify_candidates(slot,rows,session)
 spec=SPECS[slot]; lookup={x["ticker"]:x for x in ranked}
 from yahoo_source import DEFAULT_UNIVERSE
 _safe_positions(positions,set(json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"]),session)
 picked=[];sectors=Counter();exits={}
 def add(row,*,strict=False):
  if len(picked)>=spec["max_positions"] or sectors[row["sector"]]>=spec["max_sector_positions"]:
   if strict:raise ValueError("Locked holding exceeds sector or portfolio limit")
   return False
  picked.append(row);sectors[row["sector"]]+=1
  return True
 if slot=="IL-038":
  keep=[]
  for ticker,pos in sorted(positions.items()):
   row=lookup.get(ticker)
   if row is None:
    exits[ticker]="data_missing";continue
   held=months_between(pos["entry_date"],session)
   if row["hard_exit"]:exits[ticker]="hard_cycle_or_quality_exit"
   elif held>=spec["hold_months"] and row["composite_score"]<spec["retention"]:
    exits[ticker]="score_below_retention"
   else:keep.append(row)
  for row in keep:add(row)
  for row in ranked:
   if len(picked)>=spec["max_positions"]:break
   if row in picked or not row["entry_eligible"]:continue
   add(row)
  weight=min(spec["max_weight"],spec["capital_fraction"]/len(picked)) if picked else 0
  targets={row["ticker"]:weight for row in picked}
  exposure=sum(targets.values())
 else:
  locked=[];candidates=[]
  for row in ranked:
   ticker=row["ticker"];pos=positions.get(ticker)
   if pos:
    held=months_between(pos["entry_date"],session)
    if row["hard_exit"]:
     exits[ticker]="hard_quality_or_value_exit";continue
    if held>=spec["hold_months"] and row["rerated"]:
     exits[ticker]="valuation_rerated";continue
    if held>=spec["hold_months"] and row["composite_score"]<spec["retention"]:
     exits[ticker]="score_below_retention";continue
    if held<spec["hold_months"]:locked.append(row)
    else:candidates.append((row["composite_score"]+4,row))
   elif row["entry_eligible"]:
    candidates.append((row["composite_score"],row))
  for row in sorted(locked,key=lambda r:(-r["composite_score"],r["ticker"])):
   add(row,strict=True)
  for _,row in sorted(candidates,key=lambda pair:(-pair[0],pair[1]["ticker"])):
   if len(picked)>=spec["max_positions"]:break
   add(row)
  eligible=sum(bool(r["entry_eligible"]) for r in ranked)
  opportunities=max(eligible,len(picked))
  exposure=next(frac for threshold,frac in spec["exposure_tiers"] if opportunities>=threshold)
  targets=_buy_the_dip_weights(picked,exposure,spec)
  for ticker,pos in sorted(positions.items()):
   if ticker in exits or ticker in targets:continue
   exits[ticker]="rank_replaced" if months_between(pos["entry_date"],session)>=spec["hold_months"] else "position_limit"
 if sum(targets.values())>1+1e-9:
  raise ValueError("Monthly model exceeds financed capital")
 return {"schema":"idealab_monthly_decision_v1","slot":slot,"signal_date":session,
         "model_version":"capital-cycle-v1" if slot=="IL-038" else "buy-the-dip-v0",
         "scored":len(ranked),"entry_eligible":sum(bool(r["entry_eligible"]) for r in ranked),
         "targets":targets,"sectors":{r["ticker"]:r["sector"] for r in picked},
         "exit_reasons":exits,"invest_fraction":exposure,
         "status":"RESEARCH_TARGETS_PENDING_NEXT_OPEN_NOT_EXECUTED"}


def preflight():
 return {"status":"month_end_rules_verified_offline","models":list(SPECS),
         "requires_point_in_time_financials":True,"market_data":"Yahoo/yfinance",
         "no_active_market_portfolios":True}


if __name__=="__main__":
 print(json.dumps(preflight(),sort_keys=True))
