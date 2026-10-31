import json
import math
import unittest
from copy import deepcopy
from datetime import date, timedelta

from weekly_baselines import (
    FEATURES, METHODS, walk_forward, research_prediction, fit, infer,
)


def fixture(nweeks=62):
    rows = []
    start = date(2025,1,6)
    for i in range(nweeks):
        d = start + timedelta(days=7*i)
        for j,ticker in enumerate(("AAPL","MSFT")):
            momentum = math.sin(i*.31+j*.45)
            vol = .03 + (i%9)*.008 + j*.003
            reverse = math.cos(i*.29-j*.13)
            y = .027*momentum+.014*reverse-.004 + ((-1)**(i+j))*.009
            rows.append({
                "ticker":ticker,
                "feature_date":d.isoformat(),
                "feature_available_at":d.isoformat(),
                "features":{"momentum20":momentum,"volatility20":vol,"reversal5":reverse},
                "label_end":(d+timedelta(days=5)).isoformat(),
                "label_available_at":(d+timedelta(days=6)).isoformat(),
                "forward_return":y,
                "source_sha256":"a"*64,
            })
    return rows


class BaselineTemporalValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=fixture()
        cls.end=(date(2025,1,6)+timedelta(days=7*63)).isoformat()

    def test_actual_fit_and_auditable_oos_metrics(self):
        self.assertEqual(set(METHODS),{"ridge_baseline","logistic_baseline"})
        for kind in METHODS:
            report=walk_forward(self.rows,self.end,kind)
            self.assertEqual(report["status"],"OFFLINE_OOS_EVALUATED_NOT_MARKET_CERTIFIED")
            self.assertGreater(report["oos_count"],25)
            self.assertTrue(math.isfinite(report["metrics"]["model_error"]))
            self.assertTrue(math.isfinite(report["metrics"]["baseline_error"]))
            for item in report["scored"]:
                self.assertLess(item["training_labels_through"],item["feature_date"])
                self.assertLessEqual(item["label_available_at"],self.end)
                self.assertTrue(math.isfinite(item["prediction"]))
                if kind=="logistic_baseline":
                    self.assertTrue(0<item["prediction"]<1)
            if kind=="ridge_baseline":
                self.assertTrue(math.isfinite(report["metrics"]["model_rmse"]))
            else:
                self.assertTrue(math.isfinite(report["metrics"]["model_brier"]))

    def test_future_targets_cannot_rewrite_past_predictions(self):
        cutoff=(date(2025,1,6)+timedelta(days=7*42)).isoformat()
        baseline=walk_forward(self.rows,cutoff,"ridge_baseline")
        changed=deepcopy(self.rows)
        for r in changed:
            if r["feature_date"]>cutoff:
                r["forward_return"]=-.90
        rerun=walk_forward(changed,cutoff,"ridge_baseline")
        self.assertEqual(baseline,rerun)
        bad=deepcopy(self.rows)
        bad[-1]["label_available_at"]="2027-12-31"
        # Later revisions cannot produce scored OOS labels before their availability.
        limited=walk_forward(bad,self.end,"logistic_baseline")
        self.assertLess(limited["oos_count"],walk_forward(self.rows,self.end,"logistic_baseline")["oos_count"])

    def test_unlabelled_prediction_stays_research_only(self):
        request = {
            "ticker":"AAPL","feature_date":self.end,
            "feature_available_at":self.end,
            "features":{"momentum20":.02,"volatility20":.04,"reversal5":-.2},
            "source_sha256":"b"*64,
        }
        for kind in METHODS:
            pred=research_prediction(self.rows,request,kind)
            self.assertEqual(pred["status"],"RESEARCH_BASELINE_PREDICTION_NOT_EXECUTABLE")
            self.assertFalse(pred["legacy_model_replicated"])
            self.assertLess(pred["train_labels_through"],self.end)
            self.assertGreater(pred["train_rows"],30)
            self.assertEqual(len(pred["training_fingerprint"]),64)

    def test_invalid_sources_and_out_of_sequence_rows_rejected(self):
        wrong=deepcopy(self.rows)
        wrong.append(deepcopy(wrong[0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            walk_forward(wrong,self.end,"ridge_baseline")
        wrong=deepcopy(self.rows)
        wrong[0]["feature_available_at"]="2028-01-01"
        with self.assertRaisesRegex(ValueError,"Feature unavailable"):
            walk_forward(wrong,self.end,"ridge_baseline")
        wrong=deepcopy(self.rows)
        wrong[0]["label_available_at"]=wrong[0]["feature_date"]
        with self.assertRaisesRegex(ValueError,"future label"):
            walk_forward(wrong,self.end,"ridge_baseline")
        wrong=deepcopy(self.rows)
        wrong[0]["features"]["momentum20"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid source-dated"):
            walk_forward(wrong,self.end,"ridge_baseline")
        with self.assertRaises(ValueError):
            walk_forward(self.rows,self.end,"lightgbm")
        with self.assertRaises(ValueError):
            fit(self.rows[:20],"ridge_baseline")
        with self.assertRaises(ValueError):
            infer({"method":"ridge_baseline"}, {"momentum20":2})

    def test_pending_labels_not_in_training_inference(self):
        d=self.end
        request={"ticker":"AAPL","feature_date":d,
                 "feature_available_at":d,
                 "features":dict(self.rows[0]["features"]),
                 "source_sha256":"c"*64}
        base=research_prediction(self.rows,request,"ridge_baseline")
        changed=deepcopy(self.rows)
        changed[-1]["forward_return"]=-.5
        changed[-1]["label_available_at"]=(date.fromisoformat(d)+timedelta(days=10)).isoformat()
        new=research_prediction(changed,request,"ridge_baseline")
        # Only a known, matured label could affect a decision.
        self.assertNotEqual(base["training_fingerprint"],new["training_fingerprint"])
        self.assertLess(new["train_labels_through"],d)


if __name__=="__main__":
    unittest.main()
