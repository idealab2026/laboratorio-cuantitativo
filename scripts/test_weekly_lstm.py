import unittest
from copy import deepcopy
from datetime import date,timedelta
import math

from weekly_lstm import fit,predict,research_predict,preflight


def fixture(weeks=32):
    a=[]
    d=date(2025,1,6)
    for k in range(weeks):
        t=d+timedelta(days=7*k)
        for idx,ticker in enumerate(("AAA","BBB")):
            a0=math.sin(.26*k+idx*.35)
            b0=.03+.006*((idx+k)%7)
            c0=math.cos(.21*k-idx*.18)
            y=.015*a0+.013*c0-.008+(.003 if idx else -.003)
            a.append({"ticker":ticker,
                      "feature_date":t.isoformat(),
                      "feature_available_at":t.isoformat(),
                      "features":{"momentum20":a0,"volatility20":b0,
                                  "reversal5":c0},
                      "label_end":(t+timedelta(days=5)).isoformat(),
                      "label_available_at":(t+timedelta(days=6)).isoformat(),
                      "forward_return":y,
                      "source_sha256":"a"*64})
    return a


class LstmCausalResearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=fixture()
        cls.day=(date(2025,1,6)+timedelta(days=7*32)).isoformat()
        cls.current={"ticker":"AAA","feature_date":cls.day,
                     "feature_available_at":cls.day,
                     "features":{"momentum20":.31,"volatility20":.04,"reversal5":-.2},
                     "source_sha256":"b"*64}

    def test_full_four_gate_recurrent_training(self):
        status=preflight()
        self.assertTrue(status["real_recurrent_gate_training"])
        self.assertFalse(status["portfolio_started"])
        trained=fit(self.data,self.data)
        self.assertEqual(trained["status"],"RESEARCH_LSTM_TRAINED_SYNTHETIC_ONLY")
        self.assertEqual(trained["W"].shape,(12,3))
        self.assertEqual(trained["U"].shape,(12,3))
        self.assertEqual(trained["V"].shape,(3,))
        self.assertGreater(trained["trained_sequences"],30)
        self.assertTrue(math.isfinite(predict(trained,self.data+[self.current],self.current)))

    def test_point_in_time_research_predictions_and_source_fingerprint(self):
        res=research_predict(self.data,self.current)
        self.assertEqual(res["status"],"RESEARCH_LSTM_NOT_MARKET_CERTIFIED")
        self.assertFalse(res["original_model_equivalence"])
        self.assertEqual(res["orders_executed"],0)
        self.assertLess(res["trained_labels_through"],self.day)
        self.assertTrue(math.isfinite(res["prediction"]))
        modified=deepcopy(self.data)
        modified[0]["forward_return"]+=.045
        changed=research_predict(modified,self.current)
        self.assertNotEqual(res["training_fingerprint"],changed["training_fingerprint"])

    def test_future_changed_labels_cannot_rewrite_earlier_forecast(self):
        cutoff=(date(2025,1,6)+timedelta(days=7*23)).isoformat()
        current={"ticker":"AAA","feature_date":cutoff,
                 "feature_available_at":cutoff,
                 "features":dict(self.data[0]["features"]),
                 "source_sha256":"c"*64}
        before=research_predict(self.data,current,minimum=30)
        future=deepcopy(self.data)
        for row in future:
            if row["feature_date"]>cutoff:
                row["forward_return"]=-.6
                row["features"]["momentum20"]=9.
        after=research_predict(future,current,minimum=30)
        self.assertEqual(before,after)

    def test_invalid_sources_and_sequence_gaps_fail_closed(self):
        bad=deepcopy(self.data)
        bad[0]["features"]["reversal5"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid source-dated"):
            research_predict(bad,self.current)
        bad=deepcopy(self.data)
        bad.append(deepcopy(bad[0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            research_predict(bad,self.current)
        with self.assertRaisesRegex(ValueError,"embargo"):
            research_predict(self.data,self.current,embargo_days=0)
        with self.assertRaisesRegex(ValueError,"Insufficient"):
            fit(self.data[:15],self.data)
        broken=deepcopy(self.data)
        for row in broken:
            if row["ticker"]=="AAA" and row["feature_date"]==broken[8]["feature_date"]:
                row["feature_date"]=(date.fromisoformat(row["feature_date"])+timedelta(days=3)).isoformat()
                row["feature_available_at"]=row["feature_date"]
        with self.assertRaises(ValueError):
            fit(broken,broken)


if __name__=="__main__":
    unittest.main()
