"""MIDAS operator clock: opening locked before the market and observed quotes only."""
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from operational_clock import ACTIVE, clock_plan, status_report, verify_lock

UTC = timezone.utc


class OperatorClockTest(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.market = {
            "session": "2026-11-10", "previous": "2026-11-09",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30),
        }
        self.sha = "a" * 40
        self.tracks = {
            "IL-015": {
                "status": "recorded", "session": "2026-11-09",
                "holdings": ["MSFT"],
                "orders": [
                    {"ticker": "AAPL", "action": "buy",
                     "decision_session": "2026-11-09", "target_session": "2026-11-10",
                     "target_weight": .2, "limit_price": None},
                    {"ticker": "MSFT", "action": "sell",
                     "decision_session": "2026-11-09", "target_session": "2026-11-10",
                     "target_weight": 0, "limit_price": 300},
                ],
            },
            "IL-039": {
                "status": "recorded", "session": "2026-11-09",
                "holdings": ["PYPL"], "orders": [],
            },
            "IL-042": {
                "status": "stale", "session": "2026-11-06",
                "holdings": [], "orders": [
                    {"ticker": "AAPL", "action": "buy",
                     "decision_session": "2026-11-06", "target_session": "2026-11-10",
                     "target_weight": .3}],
            },
        }
        self.ready = clock_plan(self.open - timedelta(minutes=10), self.market, self.tracks, self.sha)

    def observed(self, price=100, stamp=None):
        mark = stamp or self.open + timedelta(minutes=1)
        received = mark + timedelta(minutes=1)
        return {"price": price, "quote_at_utc": mark.isoformat(),
                "observed_at_utc": received.isoformat()}

    def test_all_non_archived_daily_weekly_and_monthly_slots_share_a_clock(self):
        self.assertEqual(len(ACTIVE), 26)
        self.assertEqual(set(self.ready["slots"]), set(ACTIVE))
        self.assertTrue(self.ready["slots"]["IL-015"]["execution_ready"])
        self.assertEqual(len(self.ready["slots"]["IL-015"]["orders"]), 2)
        self.assertEqual(self.ready["slots"]["IL-039"]["orders"], [])
        self.assertFalse(self.ready["slots"]["IL-042"]["execution_ready"])
        self.assertEqual(self.ready["slots"]["IL-042"]["orders"], [])
        self.assertNotIn("IL-032", self.ready["slots"])

    def test_preopen_guard_and_immutable_signal(self):
        verify_lock(self.ready, self.market, self.open + timedelta(minutes=2))
        with self.assertRaisesRegex(ValueError, "before that opening"):
            clock_plan(self.open + timedelta(seconds=1), self.market, self.tracks, self.sha)
        tampered = copy.deepcopy(self.ready)
        tampered["slots"]["IL-015"]["orders"][0]["ticker"] = "TSLA"
        with self.assertRaisesRegex(ValueError, "modified"):
            verify_lock(tampered, self.market, self.open + timedelta(minutes=2))

    def test_no_hindsight_and_accurate_observed_statuses(self):
        now = self.open + timedelta(minutes=2)
        result = status_report(self.ready, now, self.market,
                               {"AAPL": self.observed(), "MSFT": self.observed(price=310)})
        a = result["slots"]["IL-015"]
        self.assertEqual(a["status"], "prices_observed_not_settled")
        self.assertEqual(a["observed"], 2)
        self.assertEqual(a["planned"], 2)
        self.assertEqual(a["orders"][0]["status"], "price_observed")
        self.assertEqual(a["orders"][1]["status"], "limit_observed")
        self.assertEqual(result["slots"]["IL-039"]["status"], "active_no_orders")
        self.assertEqual(result["slots"]["IL-042"]["status"], "source_stale_or_unavailable")
        self.assertEqual(result["settlement"], "native_engine_batch_until_migrated")
        self.assertNotIn("filled", json.dumps(result))

    def test_stale_and_future_lookahead_rejected(self):
        now = self.open + timedelta(minutes=10)
        old = self.observed(stamp=self.open + timedelta(minutes=1))
        result = status_report(self.ready, now, self.market, {"AAPL": old, "MSFT": old})
        self.assertEqual(result["slots"]["IL-015"]["status"], "partial_data")
        self.assertEqual(result["slots"]["IL-015"]["waiting"], 2)
        future = self.observed(stamp=now + timedelta(minutes=1))
        self.assertEqual(status_report(self.ready, now, self.market,
                         {"AAPL": future})["slots"]["IL-015"]["observed"], 0)

    def test_once_observed_the_order_remains_idempotent_without_new_historical_fill(self):
        first = status_report(self.ready, self.open + timedelta(minutes=2), self.market,
                              {"AAPL": self.observed()})
        second = status_report(self.ready, self.open + timedelta(minutes=12), self.market,
                               {}, first)
        self.assertEqual(second["slots"]["IL-015"]["orders"][0],
                         first["slots"]["IL-015"]["orders"][0])
        self.assertEqual(second["slots"]["IL-015"]["observed"], 1)

    def test_order_date_and_entry_lag_prevents_hindsight(self):
        self.tracks["IL-015"]["orders"].append({
            "ticker": "META", "action": "buy",
            "decision_session": "2026-11-10", "target_session": "2026-11-10",
            "target_weight": .1
        })
        lock = clock_plan(self.open-timedelta(minutes=10), self.market,self.tracks,self.sha)
        self.assertEqual([row["ticker"] for row in lock["slots"]["IL-015"]["orders"]],
                         ["AAPL", "MSFT"])


if __name__ == "__main__":
    unittest.main()
