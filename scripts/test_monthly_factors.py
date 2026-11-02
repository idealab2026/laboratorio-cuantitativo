import unittest
from copy import deepcopy
from datetime import date,timedelta
import json

from monthly_factors import (
  price_metrics,annual_financials,close_history,score_monthly,preflight,
)
from monthly_selection import choose
from yahoo_source import DEFAULT_UNIVERSE

UNIVERSE=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"]
SESSION="2026-10-30"
DAYS=[]
d=date.fromisoformat(SESSION)
while len(DAYS)<765:
 if d.weekday()<5:DAYS.append(d.isoformat())
 d-=timedelta(days=1)
DAYS.reverse()
PRICES=[{"date":day,"close":80+idx*.03} for idx,day in enumerate(DAYS)]
SPY=[{"date":day,"close":200+idx*.02} for idx,day in enumerate(DAYS)]
PERIODS=[
 {"date":date,"revenue":800+(-index*10),"ocf":180+(-index*5),
  "capex":-45,"assets":1000+(-index*50),
  "operating_income":110,"debt":160,"cash":80,
  "interest_expense":-5,"equity":500,"net_income":75-index*2,
  "repurchases":-12,"issuance":3}
 for index,date in enumerate(["2025-12-31","2024-12-31","2023-12-31","2022-12-31"])
]


def raw(count,bank_every=0):
 rows=[]
 for i,ticker in enumerate(UNIVERSE[:count]):
  sector="Financials" if bank_every and i%bank_every==0 else (
   "Energy","Materials","Industrials","Utilities","Information Technology")[i%5]
  statements=deepcopy(PERIODS)
  if sector=="Financials":
   for row in statements:
    row.pop("ocf");row.pop("capex")
  rows.append({"ticker":ticker,"sector":sector,
      "prices":PRICES,"fundamental":{"available_at":"2026-03-10",
      "market_cap":1000+i*5,"periods":statements}})
 return rows


class FundamentalMonthlyScores(unittest.TestCase):
 def test_raw_price_metrics_use_prior_12_1_and_daily_close(self):
  self.assertEqual(close_history(PRICES,SESSION)[-1],PRICES[-1]["close"])
  metrics=price_metrics([r["close"] for r in PRICES],[r["close"] for r in SPY])
  self.assertEqual(metrics["price_votes"],3)
  self.assertGreater(metrics["momentum_12_1"],0)
  self.assertGreater(metrics["momentum_6m"],0)
  self.assertGreater(metrics["ma200_ratio"],0)
  self.assertGreaterEqual(metrics["volatility_1y"],0)

 def test_capital_cycle_computes_three_year_balance_and_sector_ranks_without_fabricated_trades(self):
  ranked=score_monthly("IL-038",raw(40),SPY,SESSION)
  self.assertEqual(len(ranked),40)
  self.assertTrue(all(x["capital_scarcity_score"]>=0 for x in ranked))
  self.assertTrue(all(x["annual_periods"]==4 for x in ranked))
  self.assertTrue(all(x["statement_period"]=="2025-12-31" for x in ranked))
  self.assertTrue(all(len(x["evidence_sha256"])==64 for x in ranked))
  result=choose("IL-038",ranked,{},SESSION)
  self.assertEqual(result["status"],"RESEARCH_TARGETS_PENDING_NEXT_OPEN_NOT_EXECUTED")
  self.assertLessEqual(len(result["targets"]),12)

 def test_dip_financials_use_earnings_and_roe_without_requirements_for_company_fcf(self):
  ranked=score_monthly("IL-039",raw(85,bank_every=7),SPY,SESSION)
  self.assertEqual(len(ranked),85)
  self.assertTrue(all(x["catalyst_votes"]<=5 for x in ranked))
  self.assertTrue(all(x["valuation_score"]<=100 for x in ranked))
  self.assertTrue(all(x["quality_score"]<=100 for x in ranked))
  self.assertTrue(all("sector" in x and "volatility_1y" in x for x in ranked))
  result=choose("IL-039",ranked,{},SESSION)
  self.assertLessEqual(sum(result["targets"].values()),.95+1e-7)
  bank=next(x for x in ranked if x["sector"]=="Financials")
  self.assertIsInstance(bank["evidence_sha256"],str)

 def test_future_accounting_availability_or_outdated_price_rejects_coverage(self):
  rows=raw(80)
  for row in rows:row["fundamental"]["available_at"]="2026-11-10"
  with self.assertRaisesRegex(ValueError,"Insufficient"):
   score_monthly("IL-039",rows,SPY,SESSION)
  rows=raw(80)
  for row in rows:row["prices"]=PRICES[:-1]
  with self.assertRaisesRegex(ValueError,"Insufficient"):
   score_monthly("IL-039",rows,SPY,SESSION)
  rows=raw(80)
  for row in rows:row["fundamental"]["periods"]=PERIODS[:2]
  with self.assertRaisesRegex(ValueError,"Insufficient"):
   score_monthly("IL-039",rows,SPY,SESSION)
  with self.assertRaisesRegex(ValueError,"Insufficient"):
   score_monthly("IL-038",raw(34),SPY,SESSION)

 def test_duplicate_constituents_and_future_market_observations_block_no_lookahead(self):
  raw_rows=raw(40)
  raw_rows[1]["ticker"]=raw_rows[0]["ticker"]
  with self.assertRaisesRegex(ValueError,"duplicate"):
   score_monthly("IL-038",raw_rows,SPY,SESSION)
  future=deepcopy(PRICES);future.append({"date":"2026-11-02","close":500.0})
  with self.assertRaisesRegex(ValueError,"future"):
   close_history(future,SESSION)
  self.assertFalse(preflight()["live_fundamental_capture"])

 def test_insolvent_business_has_failing_survival_gate(self):
  f=deepcopy(raw(40))
  for row in f:
   for p in row["fundamental"]["periods"]:
    p["ocf"]=-20
  output=score_monthly("IL-038",f,SPY,SESSION)
  self.assertTrue(all(not x["survival_gate"] for x in output))
  decision=choose("IL-038",output,{},SESSION)
  self.assertEqual(decision["targets"],{})


if __name__=="__main__":
 unittest.main()
