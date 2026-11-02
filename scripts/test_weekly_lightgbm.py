import json
import math
import unittest
from copy import deepcopy
from datetime import date, timedelta

from weekly_lightgbm import (
    METHODS,fit,predict,walk_forward,research_predict,
)

ISSUERS=("AAA","BBB","CCC","DDD","EEE","FFF")
START=date(2025,1,6)
WEEKS=17
END=(START+timedelta(days=7*(WEEKS+1))).isoformat()
MID=(START+timedelta(days=7*13)).isoformat()


def evidence():
    records=[]
    for week in range(WEEKS):
        day=START+timedelta(days=7*week)
        for i,ticker in enumerate(ISSUERS):
            a=math.sin(week*.31+i*.62)
            b=.02+.005*((week+i)%9)
            c=math.cos(week*.23-i*.17)
            real=.027*a-.16*b+.011*c+.006*(i-2.5)+.004*((-1)**(week+i))
            records.append({
                "ticker":ticker,
                "feature_date":day.isoformat(),
                "feature_available_at":day.isoformat(),
                "features":{"momentum20":a,"volatility20":b,"reversal5":c},
                "label_end":(day+timedelta(days=5)).isoformat(),
                "label_available_at":(day+timedelta(days=6)).isoformat(),
                "forward_return":real,
                "source_sha256":"a"*64,
            })
    return records


def request(when=END):
    return {"ticker":"AAA","feature_date":when,"feature_available_at":when,
            "features":{"momentum20":.13,"volatility20":.04,"reversal5":-.14},
            "source_sha256":"c"*64}


class AuthenticLightGBMResearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=evidence()

    def test_real_library_fits_three_distinct_objectives(self):
        self.assertEqual(METHODS,("return","direction","rank"))
        for mode in METHODS:
            model=fit(self.rows[:72],mode)
            self.assertEqual(model["library"],"lightgbm")
            self.assertGreater(model["booster"].current_iteration(),0)
            self.assertGreaterEqual(model["trained_dates"],8)
            out=predict(model,request())
            self.assertTrue(math.isfinite(out))
            if mode=="direction":
                self.assertGreaterEqual(out,0)
                self.assertLessEqual(out,1)
            self.assertEqual(len(model["fingerprint"]),64)

    def test_actual_synthetic_walk_forward_errors_are_truthfully_labeled(self):
        for mode in METHODS:
            result=walk_forward(self.rows,END,mode)
            self.assertEqual(result["status"],"SYNTHETIC_OOS_NOT_MARKET_CERTIFIED")
            self.assertGreater(result["observations"],10)
            self.assertTrue(all(s["train_labels_through"]<s["feature_date"]
                                for s in result["scored"]))
            self.assertTrue(all(math.isfinite(s["prediction"]) for s in result["scored"]))
            if mode=="rank":
                self.assertGreater(result["metrics"]["pairs"],10)
                self.assertTrue(0<=result["metrics"]["pairwise_accuracy"]<=1)
            else:
                name="brier" if mode=="direction" else "rmse"
                self.assertTrue(math.isfinite(result["metrics"][name]))
                self.assertTrue(math.isfinite(result["metrics"]["baseline_"+name]))

    def test_future_results_never_rewrite_past_out_of_sample_scores(self):
        for mode in METHODS:
            reference=walk_forward(self.rows,MID,mode)
            changed=deepcopy(self.rows)
            for row in changed:
                if row["feature_date"]>MID:
                    row["forward_return"]=-.77
                    row["features"]["momentum20"]=55.0
            second=walk_forward(changed,MID,mode)
            self.assertEqual(reference,second)

    def test_mutated_training_content_changes_fingerprint(self):
        for mode in METHODS:
            original=research_predict(self.rows,request(),mode)
            self.assertFalse(original["original_model_parity"])
            self.assertFalse(original["source_rights_attested"])
            self.assertEqual(original["status"],"RESEARCH_ONLY_NOT_CERTIFIED_OR_EXECUTED")
            modified=deepcopy(self.rows)
            modified[1]["forward_return"]+=.05
            changed=research_predict(modified,request(),mode)
            self.assertNotEqual(original["model_fingerprint"],
                                changed["model_fingerprint"])

    def test_refuse_future_labels_invalid_sources_duplicate_and_wrong_objective(self):
        invalid=deepcopy(self.rows)
        invalid[0]["features"]["momentum20"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid source-dated"):
            walk_forward(invalid,END,"return")
        invalid=deepcopy(self.rows)
        invalid[0]["feature_available_at"]="2028-01-01"
        with self.assertRaisesRegex(ValueError,"Feature unavailable"):
            walk_forward(invalid,END,"rank")
        invalid=deepcopy(self.rows)
        invalid.append(deepcopy(invalid[0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            walk_forward(invalid,END,"return")
        invalid=deepcopy(self.rows)
        invalid[0]["label_available_at"]=invalid[0]["feature_date"]
        with self.assertRaisesRegex(ValueError,"future label"):
            walk_forward(invalid,END,"direction")
        with self.assertRaisesRegex(ValueError,"Unknown LightGBM"):
            fit(self.rows[:72],"lstm")
        with self.assertRaisesRegex(ValueError,"Insufficient"):
            fit(self.rows[:12],"return")
        with self.assertRaisesRegex(ValueError,"Invalid availability embargo"):
            research_predict(self.rows,request(),"return",embargo_days=0)
        with self.assertRaisesRegex(ValueError,"Missing source content"):
            research_predict(self.rows,{**request(),"source_sha256":"bad"},"return")

    def test_rank_refuses_single_issuer_or_insufficient_cross_sections(self):
        thin=[r for r in self.rows if r["ticker"] in ("AAA","BBB")]
        with self.assertRaisesRegex(ValueError,"Insufficient matured cross-sectional"):
            fit(thin[:60],"rank")


if __name__=="__main__":
    unittest.main()
