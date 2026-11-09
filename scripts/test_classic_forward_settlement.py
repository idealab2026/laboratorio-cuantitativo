"""Classic forward evidence: 9 native books, open arithmetic, stops, no replay."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from operational_clock import clock_plan
from classic_forward_settlement import LEDGER, CONFIG, SLOTS, settle_classic
from classic_sp500 import run as classic

UTC = timezone.utc


class NativeClassicClockTests(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.now = self.open + timedelta(minutes=2)
        self.market = {
            "session": "2026-11-10", "previous": "2026-11-09",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)}
        self.config = json.loads((ROOT / CONFIG).read_text())
        self.book = json.loads((ROOT / LEDGER).read_text())
        self.book["last_session"] = "2026-11-09"
        self.tracks = {}
        for slot, name in SLOTS.items():
            original = self.book["books"][name]
            original.update(cash=100000.0, nav=100000.0, positions={},
                            pending={"AAPL": {"side": "buy", "signal_date": "2026-11-09"}},
                            equity=[{"date": "2026-11-09", "nav": 100000.0}],
                            trades=[], events=[])
            for field in ("paused_missing_quotes", "receivables", "outage_control",
                          "forward_executions"):
                original.pop(field, None)
            self.tracks[slot] = {
                "status": "recorded", "session": "2026-11-09", "holdings": [],
                "orders": [{"ticker": "AAPL", "action": "buy",
                            "decision_session": "2026-11-09",
                            "target_session": "2026-11-10"}]
            }
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(self.open-timedelta(minutes=10),
                               self.market, self.tracks, "c"*40)
        self.quotes = {
            "AAPL": {"price": 100.0,
                     "quote_at_utc": (self.open+timedelta(minutes=1)).isoformat(),
                     "observed_at_utc": self.now.isoformat()}
        }

    def reader(self, path):
        return copy.deepcopy(self.book if path == LEDGER else self.config)

    def frozen(self, sha, path):
        self.assertEqual((sha, path), ("c"*40, LEDGER))
        return copy.deepcopy(self.original)

    def run_clock(self, quotes=None, now=None):
        return settle_classic(
            self.lock, now or self.now, self.market,
            self.quotes if quotes is None else quotes,
            reader=self.reader, frozen=self.frozen)

    def test_all_nine_native_buy_books_and_idempotence(self):
        updated, results = self.run_clock()
        self.assertEqual(set(updated), {LEDGER})
        self.assertEqual(set(results), set(SLOTS))
        fresh = updated[LEDGER]
        for slot, name in SLOTS.items():
            old = self.book["books"][name]
            new = fresh["books"][name]
            self.assertEqual(results[slot]["status"], "settled_native_paper")
            self.assertEqual(results[slot]["fills"], 1)
            self.assertEqual(new["pending"], {})
            self.assertEqual(new["equity"], old["equity"])
            self.assertEqual(new["nav"], old["nav"])
            self.assertGreater(new["positions"]["AAPL"]["shares"], 0)
            self.assertEqual(new["events"][-1]["execution"], "forward_observed_paper")
            self.assertEqual(results[slot]["operations"][0]["quantity"],
                             new["positions"]["AAPL"]["shares"])
            self.assertIn("forward_executions", new)
        self.book = copy.deepcopy(fresh)
        second, repeated = self.run_clock()
        self.assertEqual(second, {})
        self.assertTrue(all(r["status"] == "already_settled" for r in repeated.values()))

    def test_stale_or_missing_quotes_never_fill(self):
        output, results = self.run_clock(quotes={})
        self.assertEqual(output, {})
        self.assertTrue(all(r["status"] == "awaiting_fresh_open_quotes"
                            for r in results.values()))
        stale = copy.deepcopy(self.quotes)
        stale["AAPL"]["quote_at_utc"] = (self.open-timedelta(seconds=10)).isoformat()
        output, _ = self.run_clock(quotes=stale)
        self.assertEqual(output, {})
        output, _ = self.run_clock(now=self.open+timedelta(minutes=45))
        self.assertEqual(output, {})

    def test_native_sell_preserves_real_quantity_and_cash(self):
        # One tactical strategy sells exactly the shares it owns; peers buy.
        slot, name = "IL-011", SLOTS["IL-011"]
        b = self.book["books"][name]
        b["positions"] = {"AAPL": {"shares": 5.0, "entry_date": "2026-11-06",
                                   "entry_price": 90.0, "cost": 450.45,
                                   "dividends": 0.0, "stop": None, "target": None}}
        b["cash"] = 99549.55
        b["pending"]["AAPL"] = {"side": "sell", "signal_date": "2026-11-09"}
        self.tracks[slot]["orders"][0]["action"] = "sell"
        self.tracks[slot]["holdings"] = []
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(self.open-timedelta(minutes=10),
                               self.market, self.tracks, "c"*40)
        updated, results = self.run_clock()
        new = updated[LEDGER]["books"][name]
        self.assertFalse(new["positions"])
        self.assertEqual(new["pending"], {})
        self.assertEqual(results[slot]["operations"][0]["side"], "sell")
        self.assertEqual(results[slot]["operations"][0]["quantity"], 5.0)
        self.assertGreater(new["cash"], b["cash"])

    def test_observed_stop_sells_once_no_ohlc_hindsight(self):
        # A previously held position has no scheduled opening order.
        self.tracks["IL-011"]["orders"] = []
        self.tracks["IL-011"]["holdings"] = ["AAPL"]
        held = {"shares": 3.0, "entry_date": "2026-11-06",
                "entry_price": 100.0, "cost": 300.3, "dividends": 0.0,
                "stop": 95.0, "target": 115.0}
        old = self.book["books"][SLOTS["IL-011"]]
        old["pending"] = {}
        old["positions"] = {"AAPL": held}
        old["cash"] = 99699.7
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(self.open-timedelta(minutes=10),
                               self.market, self.tracks, "c"*40)
        quote = copy.deepcopy(self.quotes)
        quote["AAPL"]["price"] = 94.0
        output, evidence = self.run_clock(quotes=quote)
        trade = output[LEDGER]["books"]["ema_rsi_fixed"]
        self.assertFalse(trade["positions"])
        self.assertEqual(evidence["IL-011"]["status"], "settled_native_paper")
        self.assertEqual(trade["trades"][-1]["reason"], "stop_forward_observed")
        self.assertEqual(evidence["IL-011"]["operations"][0]["quantity"], 3.0)
        self.book = copy.deepcopy(output[LEDGER])
        output2, _ = self.run_clock(quotes=quote)
        self.assertEqual(output2, {})

    def test_nightly_marks_only_no_retroactive_entry_or_stop(self):
        marks = {"AAPL": {"open": 100.0, "high": 150.0, "low": 75.0,
                          "close": 101.0, "dividend": 0.0, "split": 0.0}}
        output, result = self.run_clock()
        after = output[LEDGER]
        # Nightly mark must not add a second AAPL fill or sell on full-day lows.
        closed, changed = classic.settle(
            self.config, after, "2026-11-10", "2026-11-09", marks,
            allow_partial=True)
        self.assertTrue(changed)
        target = closed["books"]["ema_rsi_fixed"]
        self.assertIn("AAPL", target["positions"])
        self.assertEqual(sum(e["type"] == "buy" for e in target["events"]), 1)
        self.assertEqual(sum(e["type"] == "sell" for e in target["events"]), 0)
        # Without any opening evidence, orders are missed, never backfilled.
        missed, _ = classic.settle(self.config, self.original, "2026-11-10",
                                   "2026-11-09", marks, allow_partial=True)
        self.assertEqual(missed["books"]["ema_rsi_fixed"]["positions"], {})
        self.assertEqual(missed["books"]["ema_rsi_fixed"]["events"][-1]["type"],
                         "missed_forward_open")


if __name__ == "__main__":
    unittest.main()
