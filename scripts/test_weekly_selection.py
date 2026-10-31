import unittest
from datetime import date, timedelta
import json
from weekly_selection import freeze_weekly_targets,preflight,PREDICTORS
from yahoo_source import DEFAULT_UNIVERSE

TICKERS=json.loads(DEFAULT_UNIVERSE.read_text())["symbols"]
DATES=[]
day=date(2026,3,2)
while len(DATES)<130:
 if day.weekday()<5:DATES.append(day.isoformat())
 day+=timedelta(days=1)
DAY=DATES[-1]
OPEN=(date.fromisoformat(DAY)+timedelta(days=3)).isoformat()
def bars(base):
 return [{"date":d,"open":base+i/10,"high":base+i/10+1,
 "low":base+i/10-1,"close":base+i/10,"volume":1000,
 "dividend":0,"split":0} for i,d in enumerate(DATES)]
def market():
 p={t:bars(100+i%20) for i,t in enumerate(TICKERS[:453])}
 p["SPY"]=bars(200);p["RSP"]=bars(220)
 return p
def predictions():
 scores={t:float(i) for i,t in enumerate(TICKERS[:453])}
 return {slot:{"prediction_asof":DAY,"train_last_label_end":DATES[-6],
 "model_sha256":"b"*64,"scores":scores,"trained_rows":10000} for slot in PREDICTORS}
class WeeklyContract(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.p=market();cls.m=predictions()
 def test_unstarted_nine_slots_and_weight_limits(self):
  self.assertFalse(preflight()["trained_models"])
  x=freeze_weekly_targets(self.p,self.m,DAY,OPEN,"a"*64,week_close=True)
  self.assertEqual(len(x["strategies"]),9)
  self.assertEqual(x["eligible"],453)
  self.assertEqual(x["status"],"RESEARCH_WEEKLY_TARGETS_PENDING_NEXT_OPEN_NOT_EXECUTED")
  for slot in PREDICTORS:
   w=x["strategies"][slot]["target_weights"]
   self.assertEqual(len(w),10)
   self.assertAlmostEqual(sum(w.values()),.95)
   self.assertTrue(all(v<=.12 for v in w.values()))
 def test_future_labels_and_unsigned_or_missing_source(self):
  wrong=predictions();wrong["IL-021"]["train_last_label_end"]="2027-01-01"
  with self.assertRaises(ValueError):freeze_weekly_targets(self.p,wrong,DAY,OPEN,"a"*64,week_close=True)
  with self.assertRaises(ValueError):freeze_weekly_targets(self.p,self.m,DAY,DAY,"a"*64,week_close=True)
  with self.assertRaises(ValueError):freeze_weekly_targets(self.p,self.m,DAY,OPEN,"x",week_close=True)
  with self.assertRaises(ValueError):freeze_weekly_targets(self.p,self.m,DAY,OPEN,"a"*64,week_close=False)
  with self.assertRaises(ValueError):freeze_weekly_targets(self.p,{},DAY,OPEN,"a"*64,week_close=True)
 def test_no_stale_price_or_retroactive_signal(self):
  wrong=market();wrong[TICKERS[0]].pop()
  with self.assertRaises(ValueError):freeze_weekly_targets(wrong,self.m,DAY,OPEN,"a"*64,week_close=True)
  with self.assertRaises(ValueError):freeze_weekly_targets(self.p,self.m,DAY,OPEN,"a"*64,week_close=True,previous_signal=DAY)
if __name__=="__main__":unittest.main()
