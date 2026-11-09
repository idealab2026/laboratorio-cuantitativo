"""Forward opening invariants: no hindsight, no stale quote, no canonical mutation."""
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.forward_open_il039 import prepare, observe, verify_plan

UTC = timezone.utc


class ForwardOpeningTest(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.market = {"session": "2026-11-10", "previous": "2026-11-09",
                       "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)}
        self.config = json.loads((ROOT / "buy_the_dip_strategy/config.json").read_text())
        self.book = {"last_session": "2026-11-09", "cash": 1000.0,
                     "positions": {}, "pending": None}

    def quote(self, value=100, *, at=None, observed=None):
        at = at or self.open + timedelta(minutes=1)
        observed = observed or self.open + timedelta(minutes=2)
        return {"price": value, "quote_at_utc": at.isoformat(),
                "observed_at_utc": observed.isoformat()}

    def test_preopen_locked_only_before_open_and_after_last_session(self):
        start = self.open - timedelta(minutes=10)
        plan = prepare(self.book, start, self.market)
        self.assertEqual(plan["session"], "2026-11-10")
        self.assertIsNone(plan["pending"])
        self.assertEqual(plan["source_session"], "2026-11-09")
        verify_plan(plan, self.open + timedelta(minutes=2), self.market)
        with self.assertRaisesRegex(ValueError, "before opening"):
            prepare(self.book, self.open + timedelta(seconds=3), self.market)
        with self.assertRaisesRegex(ValueError, "Ledger not current"):
            prepare({**self.book, "last_session": "2026-11-06"}, start, self.market)
        damaged = {**plan, "cash": 4000}
        with self.assertRaisesRegex(ValueError, "changed"):
            verify_plan(damaged, self.open + timedelta(minutes=2), self.market)
        with self.assertRaisesRegex(ValueError, "late"):
            verify_plan(plan, self.open + timedelta(minutes=35), self.market)

    def test_no_orders_still_reports_active_forward_observation(self):
        plan = prepare(self.book, self.open - timedelta(minutes=10), self.market)
        result = observe(plan, self.open + timedelta(minutes=2), self.market, {}, self.config)
        self.assertEqual(result["status"], "monitoring_no_orders")
        self.assertEqual(result["pending_targets"], 0)
        self.assertEqual(result["indicative_nav"], 1000.0)
        self.assertEqual(result["indicative_fills"], [])

    def test_fills_are_indicative_and_immutable_canonical_book(self):
        pending = {"signal_date": "2026-11-09",
                   "expected_fill_session": "2026-11-10",
                   "target_weights": {"AAA": 0.5},
                   "sectors": {"AAA": "Industrials"}}
        book = {**self.book, "pending": pending}
        pristine = copy.deepcopy(book)
        plan = prepare(book, self.open - timedelta(minutes=10), self.market)
        now = self.open + timedelta(minutes=2)
        result = observe(plan, now, self.market, {"AAA": self.quote()}, self.config)
        self.assertEqual(result["status"], "indicative_fill")
        self.assertTrue(result["indicative_fills"])
        self.assertEqual(result["indicative_fills"][0]["side"], "buy")
        self.assertEqual(result["indicative_fills"][0]["observed_at_utc"], now.isoformat().replace("+00:00","Z"))
        self.assertEqual(book, pristine)
        # Repeated schedule must never execute a second time.
        again = observe(plan, now + timedelta(minutes=3), self.market, {}, self.config, prior=result)
        self.assertEqual(again, result)

    def test_stale_quote_never_leads_to_fill(self):
        plan = prepare({**self.book, "pending": {
            "signal_date": "2026-11-09",
            "expected_fill_session": "2026-11-10",
            "target_weights": {"AAA": 0.5}, "sectors": {"AAA": "Industrials"}
        }}, self.open-timedelta(minutes=10), self.market)
        now = self.open+timedelta(minutes=7)
        stale = self.quote(at=self.open+timedelta(minutes=1), observed=now)
        data = observe(plan, now, self.market, {"AAA": stale}, self.config)
        self.assertEqual(data["status"], "waiting_quotes")
        self.assertEqual(data["missing_quotes"], ["AAA"])
        self.assertEqual(data["indicative_fills"], [])

    def test_wrong_next_session_rejected(self):
        book = {**self.book, "pending": {
            "signal_date": "2026-11-09",
            "expected_fill_session": "2026-11-11", "target_weights": {"AAA": 0.2}
        }}
        with self.assertRaisesRegex(ValueError, "not for this opening"):
            prepare(book, self.open-timedelta(minutes=10), self.market)


if __name__ == "__main__":
    unittest.main()
