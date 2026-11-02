import json
import unittest
from copy import deepcopy
from datetime import date, timedelta

from monthly_selection import choose
from monthly_paper import blank, advance, verify, safe_status, CONFIG_SHA
from yahoo_source import DEFAULT_UNIVERSE, prepare_snapshot

KEY="not-a-real-institutional-monthly-ledger-secret-0123456789"
UNIVERSE=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"]
DAYS=["2026-10-29","2026-10-30","2026-11-02","2026-11-03"]


def candidates(slot,offset):
 out=[]
 for idx,t in enumerate(UNIVERSE[:100]):
  good=offset<=idx<offset+(12 if slot=="IL-038" else 10)
  grade=80 if good else 20
  row={"ticker":t,"sector":("Energy","Materials","Industrials","Utilities")[idx%4],
       "statement_period":"2025-12-31","available_at":"2026-03-12",
       "annual_periods":4,"evidence_sha256":"a"*64,"survival_gate":True}
  if slot=="IL-038":
   row.update(capital_scarcity_score=grade,quality_score=grade,valuation_score=grade,
              inflection_score=grade,inflection_votes=3 if good else 0,
              sector_scarcity_score=grade,capex_intensity=.04)
  else:
   row.update(valuation_score=grade,quality_score=grade,
              capital_allocation_score=grade,dislocation_score=grade,
              catalyst_score=grade,catalyst_votes=4 if good else 0,volatility_1y=.16)
  out.append(row)
 return out


def daily(day,*,missing=None,special=None):
 bars={}
 for t in UNIVERSE+["SPY"]:
  if t==missing:continue
  close=100.0
  payload={"date":day,"open":close,"close":close,"high":103.,
           "low":97.,"volume":1000.,"split":0.,"dividend":0.}
  if special and t==special:
   payload.update(open=50.,close=50.,high=51.5,low=48.5,split=2.,dividend=.3)
  bars[t]=payload
 return prepare_snapshot(UNIVERSE,day,bars,day+"T23:30:00Z")


def first_decisions():
 return {"IL-038":choose("IL-038",candidates("IL-038",0),{},DAYS[0]),
         "IL-039":choose("IL-039",candidates("IL-039",20),{},DAYS[0])}


class MonthEndEconomicLedger(unittest.TestCase):
 def test_unstarted_book_has_zero_positions_and_cannot_claim_performance(self):
  self.assertTrue(verify(blank()))
  self.assertTrue(safe_status()["no" if False else "fundamental_feed"]=="NOT_CONNECTED")
  self.assertEqual(safe_status()["real_positions"],0)
  self.assertEqual(CONFIG_SHA.__len__(),64)

 def test_first_close_freezes_two_targets_without_same_day_fills(self):
  one=advance(blank(),daily(DAYS[0]),key=KEY,decisions=first_decisions(),
              next_session=DAYS[1],month_end=False)
  self.assertTrue(verify(one,KEY))
  self.assertEqual(set(one["books"]),{"IL-038","IL-039"})
  for slot,book in one["books"].items():
   self.assertEqual(book["cash"],100000)
   self.assertEqual(book["holdings"],{})
   self.assertEqual(len(book["history"]),1)
   self.assertEqual(book["pending"]["signal_date"],DAYS[0])
   self.assertEqual(book["pending"]["next_session"],DAYS[1])
   self.assertEqual(len(book["events"]),1)
   self.assertEqual(book["events"][0]["type"],"SIGNAL")

 def test_subsequent_open_rebalances_both_without_cross_cash(self):
  one=advance(blank(),daily(DAYS[0]),key=KEY,decisions=first_decisions(),
              next_session=DAYS[1])
  two=advance(one,daily(DAYS[1]),key=KEY)
  self.assertTrue(verify(two,KEY))
  cycle,dip=two["books"]["IL-038"],two["books"]["IL-039"]
  self.assertEqual(len(cycle["holdings"]),12)
  self.assertEqual(len(dip["holdings"]),10)
  self.assertAlmostEqual(cycle["cash"],5000,delta=.10)
  self.assertLessEqual(dip["cash"],100000)
  self.assertGreater(dip["cash"],0)
  self.assertEqual(len(cycle["history"]),2)
  self.assertEqual(len(dip["history"]),2)
  self.assertTrue(all(e["date"]==DAYS[1] for e in cycle["events"] if e["type"]=="FILL"))
  self.assertTrue(all(e["date"]==DAYS[0] for e in cycle["events"] if e["type"]=="SIGNAL"))
  self.assertIsNone(cycle["pending"])
  self.assertIsNone(dip["pending"])

 def test_exact_open_only_and_signed_state_cannot_be_modified(self):
  one=advance(blank(),daily(DAYS[0]),key=KEY,decisions=first_decisions(),
              next_session=DAYS[1])
  with self.assertRaisesRegex(ValueError,"Skipped scheduled market open"):
   advance(one,daily(DAYS[2]),key=KEY)
  corrupted=deepcopy(one)
  corrupted["books"]["IL-039"]["cash"]+=200
  with self.assertRaisesRegex(ValueError,"Invalid signed"):
   verify(corrupted,KEY)
  with self.assertRaisesRegex(ValueError,"Duplicate or reversed"):
   advance(one,daily(DAYS[0]),key=KEY)
  with self.assertRaisesRegex(ValueError,"Missing due"):
   advance(blank(),daily(DAYS[0]),key=KEY,decisions={"IL-038":first_decisions()["IL-038"]},
           next_session=DAYS[1])

 def test_missing_held_mark_quarantines_only_affected_strategy(self):
  one=advance(blank(),daily(DAYS[0]),key=KEY,decisions=first_decisions(),next_session=DAYS[1])
  two=advance(one,daily(DAYS[1]),key=KEY)
  cap_only=next(iter(two["books"]["IL-038"]["holdings"]))
  self.assertNotIn(cap_only,two["books"]["IL-039"]["holdings"])
  three=advance(two,daily(DAYS[2],missing=cap_only),key=KEY)
  cycle,dip=three["books"]["IL-038"],three["books"]["IL-039"]
  self.assertEqual(cycle["paused"]["missing"],[cap_only])
  self.assertEqual(cycle["history"][-1]["date"],DAYS[1])
  self.assertEqual(dip["history"][-1]["date"],DAYS[2])
  self.assertTrue(verify(three,KEY))

 def test_dividend_and_split_adjust_existing_share_count_and_cash(self):
  one=advance(blank(),daily(DAYS[0]),key=KEY,decisions=first_decisions(),next_session=DAYS[1])
  two=advance(one,daily(DAYS[1]),key=KEY)
  chosen=next(iter(two["books"]["IL-038"]["holdings"]))
  before=two["books"]["IL-038"]["holdings"][chosen]["shares"]
  third=advance(two,daily(DAYS[2],special=chosen),key=KEY)
  cycle=third["books"]["IL-038"]
  self.assertAlmostEqual(cycle["holdings"][chosen]["shares"],2*before,places=5)
  self.assertTrue(any(x["type"]=="DIVIDEND" and x["symbol"]==chosen for x in cycle["events"]))
  self.assertTrue(any(x["type"]=="SPLIT" and x["symbol"]==chosen for x in cycle["events"]))


if __name__=="__main__":
 unittest.main()
