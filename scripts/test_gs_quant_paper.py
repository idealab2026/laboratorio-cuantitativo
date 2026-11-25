import unittest
from datetime import datetime,timezone
from unittest.mock import patch
import numpy as np
from gs_quant_paper import (blank,validate,targets_for,risk_parity,advance_book,
                            panel_from_snapshots,validate_targets,NAMES,LOOKBACK,run)

class QuantCohortTest(unittest.TestCase):
    def panel(self):
        rng=np.random.default_rng(42)
        return {t:100*np.exp(np.cumsum(rng.normal(.003,.01,LOOKBACK)))
                for t in ["AAPL","MSFT","JPM","JNJ","PG","XOM","COST","UNH","NEE",
                          "CAT","WMT","DUK","KO","PEP","V","MA","CVX","HD","LOW","BAC","CL","SPY"]
                +[f"T{i:03d}" for i in range(350)]}

    def test_five_distinct_algorithms_and_reference(self):
        p=self.panel()
        for slot in NAMES:
            weights=targets_for(slot,p)
            validate_targets(slot,weights,p)
            self.assertLessEqual(sum(abs(w) for w in weights.values()),.90000001)
        self.assertEqual(targets_for("GS-SPY",p),{"SPY":.90})
        self.assertEqual(len(targets_for("GS-01",p)),10)
        self.assertEqual(len(targets_for("GS-03",p)),12)
        self.assertEqual(len(targets_for("GS-05",p)),10)

    def test_erc_balances_risk(self):
        rng=np.random.default_rng(1)
        r=rng.normal(size=(50,4))*np.array([1.,2.,3.,4.])
        w=risk_parity(r)
        cov=np.cov(r,rowvar=False)
        cov=.8*cov+.2*np.diag(np.diag(cov))+np.eye(4)*1e-10
        contributions=w*(cov@w)
        np.testing.assert_allclose(contributions/contributions.sum(),np.ones(4)/4,rtol=1e-6)

    def test_first_signal_then_next_open_only(self):
        b=blank()["books"]["GS-SPY"]
        p=self.panel()
        source={"bars":{"SPY":{"open":100.,"close":101.,"dividend":0.,"split":0}},
                "effective_sha256":"a"*64}
        now=datetime(2026,11,25,23,tzinfo=timezone.utc)
        first=advance_book("GS-SPY",b,"2026-11-25","2026-11-24","2026-11-27",
                           now,source,[],p,p)
        self.assertEqual(first["history"][0]["nav"],100000.)
        self.assertFalse(first["trades"])
        self.assertEqual(first["pending"]["target_session"],"2026-11-27")
        import copy
        invalid=copy.deepcopy(first)
        invalid["pending"]["weights"]["SPY"]=.5
        with self.assertRaisesRegex(ValueError,"provenance"):
            advance_book("GS-SPY",invalid,"2026-11-27","2026-11-25","2026-11-30",
                         now,source,[],p,p)
        second=advance_book("GS-SPY",first,"2026-11-27","2026-11-25","2026-11-30",
                            datetime(2026,11,27,23,tzinfo=timezone.utc),source,[],p,p)
        self.assertEqual(len(second["trades"]),1)
        self.assertAlmostEqual(second["positions"]["SPY"],900.)
        self.assertAlmostEqual(second["cash"],9864.955)
        self.assertEqual(second["trades"][0]["execution"],"next_open_ohlc_paper_not_observed")
        self.assertEqual(advance_book("GS-SPY",second,"2026-11-27","2026-11-25",
                         "2026-11-30",now,source,[],p,p),second)
        with self.assertRaisesRegex(ValueError,"Session gap"):
            advance_book("GS-SPY",first,"2026-11-30","2026-11-27","2026-12-01",
                         now,source,[],p,p)

    def test_preclose_bootstrap_does_not_create_prior_session_signal(self):
        with patch("gs_quant_paper.eligible_session",side_effect=ValueError(
                "La siguiente apertura ya ocurrió; no crear señal retrospectiva")):
            self.assertEqual(run(datetime(2026,11,25,19,49,tzinfo=timezone.utc)),
                             {"status":"waiting_for_next_eligible_close"})

    def test_missing_quotes_and_bad_start(self):
        b=blank()["books"]["GS-SPY"]; p=self.panel()
        with self.assertRaisesRegex(ValueError,"Initial session missed"):
            advance_book("GS-SPY",b,"2026-11-27","2026-11-25","2026-11-30",
                         datetime.now(timezone.utc),{"bars":{}},[],p,p)
        frames=[{"bars":{"AAPL":{"close":100.,"split":0,"provider_symbol":"AAPL"}}}
                for _ in range(LOOKBACK)]
        self.assertIn("AAPL",panel_from_snapshots(frames,["AAPL"]))
        frames[5]["bars"]["AAPL"]["split"]=2
        self.assertNotIn("AAPL",panel_from_snapshots(frames,["AAPL"]))
        self.assertTrue(validate(blank()))
        with self.assertRaises(ValueError): validate_targets("GS-04",{"AAPL":.1},p)
