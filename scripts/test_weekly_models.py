import json
import math
import unittest
from copy import deepcopy
from datetime import date, timedelta

from weekly_models import (
    MODEL_IDS, fit_mlp, fit_arima_100, predict_mlp, predict_arima_100,
    walk_forward_models, research_inference,
)

def fixture(weeks=64):
    result=[]
    start=date(2025,1,6)
    for i in range(weeks):
        when=start+timedelta(days=7*i)
        for j,ticker in enumerate(("AAA","BBB")):
            momentum=math.sin(i*.23+j*.31)
            volatility=.02+(.005*(i%7))+.002*j
            reversal=math.cos(i*.20+j*.37)
            y=.028*momentum+.01*reversal+.001*(i%3)-.01+.004*((-1)**(i+j))
            result.append({
                "ticker":ticker,
                "feature_date":when.isoformat(),
                "feature_available_at":when.isoformat(),
                "features":{"momentum20":momentum,"volatility20":volatility,
                            "reversal5":reversal},
                "label_end":(when+timedelta(days=5)).isoformat(),
                "label_available_at":(when+timedelta(days=6)).isoformat(),
                "forward_return":y,"source_sha256":"a"*64
            })
    return result


class TrainedResearchModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=fixture()
        cls.end=(date(2025,1,6)+timedelta(days=7*65)).isoformat()

    def test_models_are_actually_fitted_and_evaluated(self):
        self.assertEqual(len(MODEL_IDS),2)
        for kind in MODEL_IDS:
            result=walk_forward_models(self.rows,self.end,kind)
            self.assertEqual(result["status"],"SYNTHETIC_OOS_EVALUATED_NOT_MARKET_CERTIFIED")
            self.assertGreater(result["n"],15)
            self.assertTrue(math.isfinite(result["metrics"]["rmse"]))
            self.assertTrue(math.isfinite(result["metrics"]["null_rmse"]))
            self.assertTrue(all(x["train_labels_through"]<x["date"] for x in result["scored"]))
            self.assertTrue(all(len(x["training_fingerprint"])==64 for x in result["scored"]))

    def test_no_future_labels_can_change_previous_oos_predictions(self):
        limit=(date(2025,1,6)+timedelta(days=7*44)).isoformat()
        for kind in MODEL_IDS:
            before=walk_forward_models(self.rows,limit,kind)
            changed=deepcopy(self.rows)
            for row in changed:
                if row["feature_date"]>limit:
                    row["forward_return"]=-.5
                    row["features"]["momentum20"]=15.0
            after=walk_forward_models(changed,limit,kind)
            self.assertEqual(before,after)

    def test_research_inference_has_frozen_training_and_no_legacy_claim(self):
        d=self.end
        request={
            "ticker":"AAA","feature_date":d,"feature_available_at":d,
            "features":{"momentum20":.2,"volatility20":.07,"reversal5":-.2},
            "source_sha256":"f"*64
        }
        for kind in MODEL_IDS:
            result=research_inference(self.rows,request,kind)
            self.assertEqual(result["status"],"RESEARCH_ONLY_NOT_CERTIFIED_NOT_EXECUTED")
            self.assertFalse(result["original_model_equivalence"])
            self.assertLess(result["train_labels_through"],d)
            self.assertTrue(math.isfinite(result["prediction"]))
            changed=deepcopy(self.rows)
            changed[0]["forward_return"]+=.08
            new=research_inference(changed,request,kind)
            self.assertNotEqual(result["training_fingerprint"],new["training_fingerprint"])

    def test_source_availability_and_invalid_windows_are_rejected(self):
        rows=deepcopy(self.rows)
        rows[0]["label_available_at"]="2028-05-01"
        # Exclude unavailable label rather than leaking it into historical fit.
        for kind in MODEL_IDS:
            before=walk_forward_models(self.rows,self.end,kind)
            after=walk_forward_models(rows,self.end,kind)
            self.assertNotEqual(before["n"],after["n"])
        rows=deepcopy(self.rows)
        rows[0]["features"]["momentum20"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid source-dated"):
            walk_forward_models(rows,self.end,"mlp_regression_research")
        rows=deepcopy(self.rows)
        rows.append(deepcopy(rows[0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            walk_forward_models(rows,self.end,"arima_1_0_0_research")
        with self.assertRaises(ValueError):
            walk_forward_models(self.rows,self.end,"lstm")
        with self.assertRaises(ValueError):
            fit_mlp(self.rows[:20])
        with self.assertRaises(ValueError):
            fit_arima_100(self.rows[:20],"AAA")
        model=fit_mlp(self.rows[:90])
        with self.assertRaises(ValueError):
            predict_mlp(model,{"momentum20":float("nan")})
        with self.assertRaises(ValueError):
            predict_arima_100({"phi":.5,"intercept":.01},float("inf"))

    def test_arima_only_uses_issuer_consecutive_weekly_labels(self):
        a=[r for r in self.rows if r["ticker"]=="AAA"]
        model=fit_arima_100(a[:40],"AAA")
        self.assertLessEqual(abs(model["phi"]),.98)
        self.assertTrue(math.isfinite(predict_arima_100(model,.05)))
        corrupt=deepcopy(a[:40])
        corrupt[7]["feature_date"]=(date.fromisoformat(corrupt[7]["feature_date"])+timedelta(days=3)).isoformat()
        corrupt[7]["feature_available_at"]=corrupt[7]["feature_date"]
        with self.assertRaisesRegex(ValueError,"Nonconsecutive"):
            fit_arima_100(corrupt,"AAA")

if __name__=="__main__":
    unittest.main()
