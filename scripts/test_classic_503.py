import unittest
from datetime import date, timedelta
from copy import deepcopy

from classic_503 import (
    MODELS, MAX_HOLDINGS, MIN_ELIGIBLE,
    action_at_close, decisions, frozen_intents, preflight,
    ordered_history, yahoo_historical_panel,
)
from yahoo_source import DEFAULT_UNIVERSE
import json

MANIFEST=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
SYMBOLS=MANIFEST["symbols"]
DATES=[]
value=date(2026,1,5)
while len(DATES)<90:
    if value.weekday()<5: DATES.append(value.isoformat())
    value+=timedelta(days=1)
SESSION=DATES[-1]
def bars(scale=1.0):
    out=[]
    for i,d in enumerate(DATES):
        close=scale*(80+i*.15+.6*(i%7))
        out.append({"date":d,"open":close*.999,"high":close*1.01,
                    "low":close*.99,"close":close,"volume":10000.0,
                    "dividend":0.0,"split":0.0})
    return out


class Classic503SignalsTest(unittest.TestCase):
    def test_original_configured_503_plus_spy_models_and_risk(self):
        self.assertEqual(preflight()["status"],"source_gated_classic_503_engine")
        self.assertEqual(len(SYMBOLS),503)
        self.assertEqual(len(MODELS),9)
        self.assertEqual(MAX_HOLDINGS,8)
        self.assertEqual(MIN_ELIGIBLE,453)
        self.assertEqual(list(MODELS),["IL-%03d"%i for i in range(10,19)])

    def test_exact_closing_bars_and_bounded_90_percent_coverage(self):
        universe={name:bars() for name in SYMBOLS[:453]}
        universe["SPY"]=bars(1.2)
        outcome=decisions(universe,SESSION)
        self.assertEqual(outcome["eligible"],453)
        self.assertEqual(len(outcome["missing"]),50)
        self.assertEqual(outcome["status"],"RESEARCH_SIGNALS_ONLY_NOT_EXECUTED")
        self.assertEqual(list(outcome["strategies"]),list(MODELS))
        self.assertEqual(len(outcome["strategies"]["IL-010"]),453)
        self.assertEqual(outcome["strategies"]["IL-018"][0]["ticker"],"SPY")
        with self.assertRaisesRegex(ValueError,"coverage insufficient"):
            decisions({k:v for k,v in universe.items() if k!="SPY" and k!=SYMBOLS[452]}|{"SPY":bars(1.2)},SESSION)
        with self.assertRaisesRegex(ValueError,"benchmark absent"):
            decisions({name:bars() for name in SYMBOLS},SESSION)

    def test_decision_freeze_respects_max_eight_and_sell_first(self):
        feed={name:bars() for name in SYMBOLS}
        feed["SPY"]=bars()
        report=decisions(feed,SESSION)
        empty={slot:[] for slot in MODELS}
        orders=frozen_intents(report,empty)
        self.assertEqual(len(orders["IL-010"]),8)
        self.assertEqual(orders["IL-010"][0]["side"],"buy")
        self.assertEqual(len(orders["IL-018"]),1)
        self.assertEqual(orders["IL-018"][0]["ticker"],"SPY")
        self.assertEqual(len(frozen_intents(report,{**empty,"IL-018":["SPY"]})["IL-018"]),0)
        self.assertTrue(all(q["signalAt"]==SESSION for v in orders.values() for q in v))
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            frozen_intents(report,{"IL-010":[]})

    def test_future_data_or_stale_close_rejected_without_forward_fill(self):
        sample=bars()
        with self.assertRaisesRegex(ValueError,"dated closing"):
            ordered_history(sample[:-1],SESSION,"AAPL")
        out=deepcopy(sample);out.append({**out[-1],"date":"2026-12-15"})
        with self.assertRaisesRegex(ValueError,"Future"):
            ordered_history(out,SESSION,"AAPL")
        out=deepcopy(sample);out[-1]["close"]=float("nan")
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            ordered_history(out,SESSION,"AAPL")
        out=deepcopy(sample);out[-1]["date"]=out[-2]["date"]
        with self.assertRaisesRegex(ValueError,"strictly increasing"):
            ordered_history(out,SESSION,"AAPL")
        # Past data is the only input: deleting a future bar leaves a prior close unchanged.
        earlier=ordered_history(sample[:-1],sample[-2]["date"],"AAPL")
        changed=deepcopy(sample);changed[-1]["close"]*=1.01
        unchanged=ordered_history(changed[:-1],sample[-2]["date"],"AAPL")
        self.assertEqual(action_at_close("macd",earlier),action_at_close("macd",unchanged))

    def test_classic_rules_differ_from_unsupported_historical_ml(self):
        steep=[]
        for row in bars():
            o={**row,"open":90,"close":95,"high":96,"low":89}
            steep.append(o)
        steep[-1]={**steep[-1],"close":110,"high":111,"open":100}
        self.assertEqual(action_at_close("breakout_20",steep),"buy")
        self.assertEqual(action_at_close("breakout_55",steep),"buy")
        self.assertEqual(action_at_close("equal_hold",steep),"buy")
        with self.assertRaisesRegex(ValueError,"Unknown classic"):
            action_at_close("timesfm_trained",steep)

    def test_private_provider_access_is_closed_by_default(self):
        with self.assertRaisesRegex(ValueError,"rights not attested"):
            yahoo_historical_panel(SESSION,rights_attested=False)


if __name__=="__main__":
    unittest.main()
