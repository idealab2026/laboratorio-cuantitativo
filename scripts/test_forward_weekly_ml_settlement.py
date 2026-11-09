"""Forward IL-019..027 tests: native accounting, causality, missed opens, idempotency."""
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
from forward_weekly_ml_settlement import LEDGER, CONFIG, SLOTS, settle_weekly
from weekly_ml.daily import process_day

UTC = timezone.utc


class ForwardWeeklyMLTests(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.now = self.open + timedelta(minutes=2)
        self.market = {
            "session": "2026-11-10", "previous": "2026-11-09",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)
        }
        self.config = json.loads((ROOT / CONFIG).read_text())
        self.state = json.loads((ROOT / LEDGER).read_text())
        self.state["last_session"] = "2026-11-09"
        self.state["last_signal_session"] = "2026-11-09"
        self.tracks = {}
        for slot, name in SLOTS.items():
            book = self.state["strategies"][name]
            book.update(
                cash=100000.0, nav=100000.0, positions={},
                pending=[{"ticker": "AAPL", "signal_date": "2026-11-09"}],
                events=[], trades=[], equity=[{"date": "2026-11-09", "nav": 100000.0}],
                last_signal_session="2026-11-09"
            )
            book.pop("paused_missing_quotes", None)
            book.pop("forward_executions", None)
            self.tracks[slot] = {
                "status": "recorded", "session": "2026-11-09",
                "holdings": [], "orders": [{
                    "ticker": "AAPL", "action": "buy",
                    "decision_session": "2026-11-09",
                    "target_session": "2026-11-10"
                }]
            }
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10),
                               self.market, self.tracks, "b" * 40)
        self.quotes = {
            "AAPL": {"price": 100.0,
                     "quote_at_utc": (self.open + timedelta(minutes=1)).isoformat(),
                     "observed_at_utc": self.now.isoformat()}
        }

    def reader(self, path):
        return copy.deepcopy(self.state if path == LEDGER else self.config)

    def frozen(self, commit, path):
        self.assertEqual(commit, "b" * 40)
        self.assertEqual(path, LEDGER)
        return copy.deepcopy(self.frozen_state)

    def settle(self, **kwargs):
        return settle_weekly(self.lock, self.now, self.market, self.quotes,
                             reader=self.reader, frozen=self.frozen, **kwargs)

    def test_all_nine_books_have_identical_native_fee_math_and_once_only(self):
        outputs, evidence = self.settle()
        self.assertEqual(set(outputs), {LEDGER})
        after = outputs[LEDGER]
        self.assertEqual(set(evidence), set(SLOTS))
        for slot, name in SLOTS.items():
            book = after["strategies"][name]
            self.assertEqual(evidence[slot]["status"], "settled_native_paper")
            self.assertEqual(len(evidence[slot]["operations"]), 1)
            self.assertEqual(book["pending"], [])
            self.assertEqual(book["nav"], 100000.0)
            self.assertEqual(book["equity"][-1]["date"], "2026-11-09")
            self.assertEqual(book["events"][-1]["execution"], "forward_observed_paper")
            self.assertEqual(book["events"][-1]["source_commit"], "b" * 40)
            self.assertTrue(book["forward_executions"])
            self.assertGreater(book["positions"]["AAPL"]["shares"], 0)
        self.state = copy.deepcopy(after)
        second, repeated = self.settle()
        self.assertEqual(second, {})
        self.assertTrue(all(v["status"] == "already_settled" for v in repeated.values()))

    def test_open_missing_or_stale_quote_does_not_book(self):
        missing = copy.deepcopy(self.quotes)
        self.quotes = {}
        out, evidence = self.settle()
        self.assertEqual(out, {})
        self.assertTrue(all(v["status"] == "awaiting_fresh_quotes" for v in evidence.values()))
        self.quotes = missing
        self.quotes["AAPL"]["quote_at_utc"] = (
            self.open - timedelta(minutes=5)).isoformat()
        out, _ = self.settle()
        self.assertEqual(out, {})
        self.quotes["AAPL"]["quote_at_utc"] = (
            self.open + timedelta(minutes=1)).isoformat()
        out, _ = settle_weekly(
            self.lock, self.open + timedelta(minutes=45), self.market,
            self.quotes, reader=self.reader, frozen=self.frozen)
        self.assertEqual(out, {}, "No fill reconstructed long after the opening")

    def test_source_change_rejects_only_changed_strategy(self):
        self.state["strategies"]["mlp_return"]["cash"] += 50
        output, evidence = self.settle()
        self.assertEqual(evidence["IL-024"]["status"], "source_changed_or_stale")
        self.assertEqual(evidence["IL-023"]["status"], "settled_native_paper")
        self.assertFalse(output[LEDGER]["strategies"]["mlp_return"].get("forward_executions"))

    def test_nightly_marks_forward_buy_once(self):
        output, _ = self.settle()
        after = output[LEDGER]
        prices = {"AAPL": {"open": 100, "close": 101, "split": 0, "dividend": 0}}
        closed, changed = process_day(self.config, after, "2026-11-10", prices,
                                      previous_session="2026-11-09", week_end=False)
        self.assertTrue(changed)
        for name in SLOTS.values():
            book = closed["strategies"][name]
            self.assertEqual(book["equity"][-1]["date"], "2026-11-10")
            self.assertEqual(sum(e["type"] == "buy" for e in book["events"]), 1)

    def test_missed_forward_open_never_backfilled_at_night(self):
        prices = {"AAPL": {"open": 100, "close": 101, "split": 0, "dividend": 0}}
        closed, changed = process_day(self.config, self.state, "2026-11-10", prices,
                                      previous_session="2026-11-09", week_end=False)
        self.assertTrue(changed)
        for name in SLOTS.values():
            book = closed["strategies"][name]
            self.assertEqual(book["pending"], [])
            self.assertFalse(book["positions"])
            self.assertEqual(book["events"][-1]["type"], "missed_forward_open")
            self.assertEqual(book["equity"][-1]["date"], "2026-11-10")


if __name__ == "__main__":
    unittest.main()
