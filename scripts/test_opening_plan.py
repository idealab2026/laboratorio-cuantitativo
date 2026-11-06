import unittest

from build_opening_plan import plan_track


class OpeningPlanTest(unittest.TestCase):
    def test_only_orders_for_target_are_admitted_and_missing_days_stay_stale(self):
        previous, target = "2026-11-05", "2026-11-06"
        book = {
            "equity": [{"date": "2026-11-04"}],
            "positions": {"SPY": {}},
            "pending": [
                {"ticker": "AAPL", "signal_date": previous},
                {"ticker": "MSFT", "signal_date": "2026-11-04"},
                {"ticker": "NVDA", "signal_date": previous, "expected_fill_session": "2026-11-09"},
                {"ticker": "TSLA", "signal_date": target, "expected_fill_session": target},
            ],
        }
        daily = plan_track("IL-042", book, target, previous)
        self.assertEqual(daily["status"], "stale")
        self.assertEqual(daily["holdings"], ["SPY"])
        self.assertEqual([(o["ticker"], o["target_session"]) for o in daily["orders"]], [("AAPL", target)])
        self.assertEqual(daily["undated"], 1)

        monthly = plan_track("IL-039", book, target, previous)
        self.assertEqual(monthly["orders"], [])
        self.assertEqual(monthly["undated"], 2)

        archived = plan_track("IL-032", book, target, previous)
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(archived["orders"], [])
