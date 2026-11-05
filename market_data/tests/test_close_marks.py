"""Closing-only evidence can mark passive NAV, never masquerade as OHLC."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from market_data import verified_chart as v
from market_data.snapshot import _digest, make_snapshot, write_immutable, normalize_bar
from market_data.revisions import load_effective
from market_data.close_marks import append_marks, load_marks, passive_marks
from test_verified_chart import receipt, mutate_response, DAY


def close_receipt():
    r=receipt();r["method"]=v.CLOSE;r["sha256"]=_digest(r)
    return r


class PassiveCloseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        names=["DECK"]+["S%03d"%i for i in range(502)]
        bar={"date":DAY,"open":100.,"high":103.,"low":99.,"close":101.,"volume":100.,"dividend":0.,"split":0.}
        doc=make_snapshot(DAY,names,{"SPY":bar},captured_at_utc="2026-11-04T23:30:00+00:00")
        self.base,_=write_immutable(self.root,doc);self.original=self.base.read_bytes()

    def append(self,r=None):
        r=r or close_receipt();mark=v.reconstruct(r)
        return append_marks(self.root,DAY,{"DECK":mark},{"DECK":r},captured_at_utc="2026-11-05T00:15:00+00:00")

    def test_valid_close_is_separate_from_tradable_bars(self):
        r=close_receipt();mark=v.reconstruct(r)
        self.assertEqual(mark["price_scope"],"passive_close_only")
        self.assertNotIn("open",mark);self.assertNotIn("low",mark)
        with self.assertRaises(ValueError):normalize_bar(mark,DAY,"DECK")
        self.append(r)
        self.assertNotIn("DECK",load_effective(self.root,DAY)["bars"])
        marks,identity=passive_marks(self.root,DAY)
        self.assertEqual(marks["DECK"]["close"],101.)
        self.assertEqual(identity["closing_mark_scope"],"passive_nav_only")
        self.assertEqual(len(identity["closing_mark_hashes"]),1)
        self.assertEqual(self.base.read_bytes(),self.original)

    def test_a_nontraded_interior_interval_does_not_invent_an_ohlc_bar(self):
        r=close_receipt()
        def change(x):
            for values in x["indicators"]["quote"][0].values():values[10]=None
        mutate_response(r,"intraday",change)
        self.assertEqual(v.reconstruct(r)["close"],101.)
        # The exact same tape is insufficient for an intraday trading range.
        r["method"]=v.RANGE;r["sha256"]=_digest(r)
        with self.assertRaises(ValueError):v.reconstruct(r)

    def test_terminal_missing_conflicting_or_wrong_date_close_is_rejected(self):
        for mode in ("missing","conflicting","wrong_date"):
            r=close_receipt()
            def change(x):
                if mode=="wrong_date":x["timestamp"][-1]+=86400
                else:x["indicators"]["quote"][0]["close"][-1]=None if mode=="missing" else 102.
            mutate_response(r,"intraday",change)
            with self.assertRaises(ValueError):v.reconstruct(r)

    def test_tampering_identity_duplicate_and_pre_capture_stamp_fail(self):
        path,doc=self.append()
        with self.assertRaises(ValueError):self.append()
        doc["marks"]["DECK"]["close"]=102.;doc["sha256"]=_digest(doc)
        path.unlink();(path.parent/(doc["sha256"]+".json")).write_text(json.dumps(doc))
        with self.assertRaises(ValueError):load_marks(self.root,DAY)

    def test_close_marks_do_not_enable_active_or_stop_based_recovery(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"classic_sp500"))
        from recovery import recover_passive_books
        r=close_receipt();mark=v.reconstruct(r)
        base={"last_session":DAY,"books":{"active":{"positions":{"DECK":{"shares":1,"stop":98.,"target":105.}},
             "pending":{},"equity":[{"date":"2026-11-03","nav":101.}],"paused_missing_quotes":{"missing_tickers":["DECK"]}}}}
        config={"strategies":{"active":{"kind":"ema_rsi"}}}
        got,recovered,blocked=recover_passive_books(config,base,lambda a,b:[DAY],lambda d:({"DECK":mark},{}),recorded_at="2026-11-05T00:15:00+00:00")
        self.assertEqual(got,base);self.assertEqual(recovered,[])
        self.assertEqual(blocked["active"],"historical_trading_rules_require_review")


if __name__=="__main__":unittest.main()
