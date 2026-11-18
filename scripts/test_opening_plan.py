import unittest
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from operational_clock import clock_plan

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

    def test_il012_19nov_preopen_ready_only_if_18nov_close_and_claim_are_valid(self):
        # Synthetic future valuation, never written to the canonical paper
        # ledger. The live 17-Nov book is a read-only accounting fixture.
        root = Path(__file__).resolve().parents[1]
        live = json.loads((root / "classic_sp500_state/ledger.json").read_text())
        book = copy.deepcopy(live["books"]["genetic_frozen"])
        previous, target = "2026-11-18", "2026-11-19"
        self.assertEqual(
            plan_track("IL-012", book, target, previous)["status"], "stale")
        self.assertEqual(book["receivables"]["KVUE_KMB_2026-11-02"]["status"], "unsettled")

        # Imagine the nightly 18-Nov mark has actually been published.
        book["equity"].append({"date": previous, "nav": book["nav"],
                               "provisional_corporate_valuation": True})
        eligible = plan_track("IL-012", book, target, previous)
        self.assertEqual(eligible["status"], "recorded")
        self.assertEqual(eligible["session"], previous)
        self.assertEqual(eligible["orders"], [])
        self.assertEqual(eligible["holdings"], sorted(book["positions"]))
        market_open = datetime(2026, 11, 19, 14, 30, tzinfo=timezone.utc)
        frozen = clock_plan(
            market_open - timedelta(minutes=10),
            {"session": target, "previous": previous,
             "open": market_open, "close": market_open + timedelta(hours=6, minutes=30)},
            {"IL-012": eligible}, "a" * 40)
        lane = frozen["slots"]["IL-012"]
        self.assertTrue(lane["execution_ready"])
        self.assertEqual(lane["monitor_tickers"], sorted(book["positions"]))
        self.assertEqual(lane["orders"], [])
        self.assertFalse(lane["exit_only_ready"])

        for field, invalid in (("status", "unreviewed"),
                               ("fixed_cash", "999999"),
                               ("action_id", "forged")):
            wrong = copy.deepcopy(book)
            wrong["receivables"]["KVUE_KMB_2026-11-02"][field] = invalid
            plan = plan_track("IL-012", wrong, target, previous)
            self.assertEqual((plan["status"], plan["orders"]),
                             ("paused", []), field)
            rejected = clock_plan(
                market_open - timedelta(minutes=10),
                {"session": target, "previous": previous,
                 "open": market_open, "close": market_open + timedelta(hours=6, minutes=30)},
                {"IL-012": plan}, "a" * 40)
            self.assertFalse(rejected["slots"]["IL-012"]["execution_ready"])
            self.assertEqual(rejected["slots"]["IL-012"]["monitor_tickers"], [])

        other = copy.deepcopy(book)
        other["receivables"]["UNKNOWN"] = {"status": "unsettled"}
        self.assertEqual(plan_track("IL-012", other, target, previous)["status"], "paused")
        other = copy.deepcopy(book)
        other["outage_control"]["first_trading_session"] = "2026-11-20"
        self.assertEqual(plan_track("IL-012", other, target, previous)["status"], "paused")
        other = copy.deepcopy(book)
        other["paused_missing_quotes"] = {"missing_tickers": ["KMB"]}
        self.assertEqual(plan_track("IL-012", other, target, previous)["status"], "paused")
        self.assertEqual(live["books"]["genetic_frozen"]["equity"][-1]["date"],
                         "2026-11-17")
