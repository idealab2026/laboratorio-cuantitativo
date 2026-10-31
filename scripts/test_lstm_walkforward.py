import math
import unittest
from copy import deepcopy
from datetime import date,timedelta

from lstm_walkforward import walk_forward
from test_weekly_lstm import fixture

START=date(2025,1,6)
DAY=lambda n: (START+timedelta(days=7*n)).isoformat()


class LSTMIndependentOOSAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=fixture(32)

    def test_training_and_chronological_scoring_are_real_but_synthetic(self):
        x=walk_forward(self.rows,DAY(34),max_decisions=3)
        self.assertEqual(x["status"],"RESEARCH_SYNTHETIC_OOS_VALIDATED_NOT_MARKET_CERTIFIED")
        self.assertEqual(x["decisions"],3)
        self.assertEqual(x["observations"],6)
        self.assertFalse(x["equivalent_to_original_model"])
        self.assertFalse(x["market_performance"])
        self.assertFalse(x["paper_ledger_activated"])
        self.assertGreaterEqual(x["metrics"]["lstm_rmse"],0)
        self.assertTrue(math.isfinite(x["metrics"]["training_mean_rmse"]))
        for scored in x["scored"]:
            self.assertLess(scored["training_labels_through"],scored["date"])
            self.assertLessEqual(scored["label_available_at"],DAY(34))
            self.assertTrue(math.isfinite(scored["prediction"]))
            self.assertEqual(len(scored["training_fingerprint"]),64)

    def test_later_revisions_cannot_change_any_earlier_oos_result(self):
        cutoff=DAY(26)
        before=walk_forward(self.rows,cutoff,max_decisions=3)
        future=deepcopy(self.rows)
        for row in future:
            if row["feature_date"]>cutoff:
                row["forward_return"]=-.80
                row["features"]["momentum20"]=90.
        after=walk_forward(future,cutoff,max_decisions=3)
        self.assertGreater(before["observations"],0)
        self.assertEqual(before,after)

    def test_incomplete_labels_never_enter_scored_oos(self):
        previous=walk_forward(self.rows,DAY(34),max_decisions=3)
        changed=deepcopy(self.rows)
        for row in changed:
            if row["feature_date"]==DAY(31):
                row["label_available_at"]=DAY(36)
        r=walk_forward(changed,DAY(34),max_decisions=3)
        self.assertTrue(all(item["label_available_at"]<=DAY(34)
                            for item in r["scored"]))
        self.assertNotEqual(previous["decision_dates"],r["decision_dates"])

    def test_malformed_history_and_bad_protocol_fail(self):
        for key,value in [("embargo_days",0),("stride_weeks",0),
                          ("max_decisions",0),("max_decisions",100)]:
            with self.assertRaises(ValueError):
                walk_forward(self.rows,DAY(34),**{key:value})
        invalid=deepcopy(self.rows)
        invalid[0]["features"]["volatility20"]=float("nan")
        with self.assertRaisesRegex(ValueError,"invalid source-dated"):
            walk_forward(invalid,DAY(34))
        invalid=deepcopy(self.rows)
        invalid.append(deepcopy(invalid[0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            walk_forward(invalid,DAY(34))


if __name__=="__main__":
    unittest.main()
