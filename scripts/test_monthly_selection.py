import unittest
from copy import deepcopy
from datetime import date

from monthly_selection import SPECS,choose,due,preflight,choose_momentum,momentum_calendar
from yahoo_source import DEFAULT_UNIVERSE
import json

UNIVERSE=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"]
SESSION="2026-10-30"
DIGEST="a"*64


def scored(model="IL-038",qualified=12):
 rows=[]
 for i,sym in enumerate(UNIVERSE[:85]):
  good=i<qualified
  base=80 if good else 25
  row={"ticker":sym,"sector":("Energy","Materials","Industrials","Utilities")[i%4],
    "statement_period":"2025-12-31","available_at":"2026-03-10",
    "annual_periods":4,"evidence_sha256":DIGEST,"survival_gate":True}
  if model=="IL-038":
   row.update(capital_scarcity_score=base,quality_score=base,
    valuation_score=base,inflection_score=base,
    inflection_votes=3 if good else 0,
    sector_scarcity_score=base,capex_intensity=.04)
  else:
   row.update(valuation_score=base,quality_score=base,
    capital_allocation_score=base,dislocation_score=base,
    catalyst_score=base,catalyst_votes=4 if good else 0,volatility_1y=.16)
  rows.append(row)
 return rows


class MonthlyTargetModels(unittest.TestCase):
 def test_distinct_configurations_and_offline_preflight(self):
  self.assertEqual(set(SPECS),{"IL-038","IL-039"})
  self.assertEqual((SPECS["IL-038"]["max_positions"],
                    SPECS["IL-039"]["max_positions"]),(12,10))
  self.assertEqual(SPECS["IL-038"]["weights"],(.45,.30,.15,.10))
  self.assertEqual(SPECS["IL-039"]["weights"],(.30,.20,.15,.20,.15))
  self.assertTrue(preflight()["requires_point_in_time_financials"])

 def test_capital_cycle_month_end_12_names_4_per_sector_and_95_percent(self):
  report=choose("IL-038",scored("IL-038",12),{},SESSION)
  self.assertEqual(report["scored"],85)
  self.assertEqual(report["entry_eligible"],12)
  self.assertEqual(len(report["targets"]),12)
  self.assertAlmostEqual(sum(report["targets"].values()),.95)
  self.assertTrue(all(x<=.1 for x in report["targets"].values()))
  from collections import Counter
  sector_counts=Counter(report["sectors"].values())
  self.assertTrue(all(n<=4 for n in sector_counts.values()))
  self.assertEqual(report["status"],"RESEARCH_TARGETS_PENDING_NEXT_OPEN_NOT_EXECUTED")

 def test_buy_the_dip_10_names_3_sector_and_explicit_cash_tiers(self):
  for number,exposure in [(10,.95),(7,.9),(4,.7),(1,.5),(0,0)]:
   result=choose("IL-039",scored("IL-039",number),{},SESSION)
   self.assertEqual(result["invest_fraction"],exposure)
   self.assertLessEqual(sum(result["targets"].values()),exposure+1e-8)
   self.assertLessEqual(len(result["targets"]),10)
   for weight in result["targets"].values():
    self.assertLessEqual(weight,.15)
   from collections import defaultdict
   groups=defaultdict(float)
   for t,w in result["targets"].items():
    groups[result["sectors"][t]]+=w
   self.assertTrue(all(x<=.30+1e-8 for x in groups.values()))

 def test_three_month_hysteresis_and_hard_exit(self):
  rows=scored("IL-039",12)
  target=rows[0]["ticker"]
  rows[0].update(valuation_score=20,quality_score=100,capital_allocation_score=100,
                 dislocation_score=20,catalyst_score=100,catalyst_votes=5)
  young=choose("IL-039",rows,{target:{"entry_date":"2026-09-01"}},SESSION)
  self.assertIn(target,young["targets"])
  old=choose("IL-039",rows,{target:{"entry_date":"2026-06-01"}},SESSION)
  self.assertNotIn(target,old["targets"])
  self.assertEqual(old["exit_reasons"][target],"valuation_rerated")
  rows[0]["survival_gate"]=False
  hard=choose("IL-039",rows,{target:{"entry_date":"2026-10-01"}},SESSION)
  self.assertEqual(hard["exit_reasons"][target],"hard_quality_or_value_exit")

 def test_no_future_filings_or_nonoriginal_universe_inputs(self):
  rows=scored("IL-038")
  for mutation in [
   lambda r:r[0].update(available_at="2026-11-01"),
   lambda r:r[0].update(statement_period="2026-11-01"),
   lambda r:r[0].update(evidence_sha256="not-sha"),
   lambda r:r[0].update(annual_periods=2),
   lambda r:r[0].update(ticker="PRIVATE"),
   lambda r:r[0].update(quality_score=float("nan")),
  ]:
   value=deepcopy(rows);mutation(value)
   with self.assertRaises(ValueError):choose("IL-038",value,{},SESSION)
  with self.assertRaisesRegex(ValueError,"Insufficient"):
   choose("IL-038",rows[:34],{},SESSION)
  with self.assertRaisesRegex(ValueError,"Insufficient"):
   choose("IL-039",scored("IL-039")[:79],{},SESSION)

 def test_launch_month_end_and_missed_month_handling(self):
  self.assertTrue(due(None,SESSION,False))
  self.assertTrue(due("2026-09-30",SESSION,True))
  self.assertFalse(due("2026-10-01",SESSION,False))
  self.assertTrue(due("2026-08-31",SESSION,False))
  with self.assertRaisesRegex(ValueError,"backwards"):
   due("2026-10-31",SESSION,True)


class MomentumResearchContract(unittest.TestCase):
 def rows(self):
  return [{"ticker":t,"start_session":"2025-11-28","end_session":"2026-10-30",
           "price_basis":"adjusted_close_same_retrieval","currency":"USD",
           "captured_at_utc":"2026-11-30T21:20:00Z","evidence_sha256":DIGEST,
           "start_price":100.,"end_price":200.-i/10}
          for i,t in enumerate(UNIVERSE)]

 def decide(self,rows,positions=None,session="2026-11-30",stamp="2026-11-30T21:30:00Z"):
  return choose_momentum(rows,positions or {},session,stamp)

 def test_month_end_12_minus_1_and_fixed_weights(self):
  result=self.decide(self.rows(),{UNIVERSE[-1]:{"entry_date":"2026-10-01"}})
  self.assertEqual(result["start_session"],"2025-11-28")
  self.assertEqual(result["end_session"],"2026-10-30")
  self.assertEqual(result["next_session"],"2026-12-01")
  self.assertEqual(set(result["targets"]),set(UNIVERSE[:20]))
  self.assertAlmostEqual(sum(result["targets"].values()),.95)
  self.assertEqual(result["exit_reasons"][UNIVERSE[-1]],"outside_positive_top_20")
  self.assertEqual(result["status"],"RESEARCH_TARGETS_PENDING_SOURCE_AND_LEDGER_NOT_EXECUTED")
  self.assertEqual(result["evidence_sha256"],self.decide(list(reversed(self.rows())))["evidence_sha256"])

 def test_few_positive_names_leave_cash(self):
  rows=self.rows()
  for row in rows[2:]:row["end_price"]=90.
  result=self.decide(rows)
  self.assertEqual(set(result["targets"]),set(UNIVERSE[:2]))
  self.assertAlmostEqual(result["invest_fraction"],.095)

 def test_coverage_held_names_future_and_wrong_dates_fail_closed(self):
  with self.assertRaisesRegex(ValueError,"coverage"):self.decide(self.rows()[:400])
  with self.assertRaisesRegex(ValueError,"held instrument"):
   self.decide(self.rows()[:-1],{UNIVERSE[-1]:{"entry_date":"2026-10-01"}})
  for bad in [{"captured_at_utc":"2026-12-01T15:00:00Z"},
              {"end_session":"2026-11-30"}, {"start_price":0},
              {"price_basis":"raw_close"},{"evidence_sha256":"invalid"}]:
   rows=self.rows();rows[0].update(bad)
   with self.assertRaises(ValueError):self.decide(rows)
  with self.assertRaisesRegex(ValueError,"final XNYS"):self.decide(self.rows(),session="2026-11-24")
  with self.assertRaisesRegex(ValueError,"causal"):
   self.decide(self.rows(),stamp="2026-12-01T14:31:00Z")


if __name__=="__main__":
 unittest.main()
