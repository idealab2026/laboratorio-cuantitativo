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

    def test_audit_script_entrypoint_resolves_classic_root_claim_contract(self):
        # Running from scripts/ must import the identical shared verifier as
        # the forward executor, without depending on PYTHONPATH or test order.
        import subprocess
        import sys
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; sys.path.insert(0,'scripts'); "
            "from build_opening_plan import plan_track; "
            "p=plan_track('IL-012',"
            "{'equity':[{'date':'2026-11-18'}],"
            "'receivables':{'UNKNOWN':{'status':'unsettled'}},"
            "'positions':{},'pending':{}},"
            "'2026-11-19','2026-11-18'); "
            "assert p['status']=='paused',p"
        )
        executed = subprocess.run(
            [sys.executable, "-I", "-c", code], cwd=root,
            capture_output=True, text=True, timeout=20)
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_il012_19nov_preopen_ready_only_if_18nov_close_and_claim_are_valid(self):
        # Deterministic historical fixture, not the mutable production ledger.
        # This test must still pass AFTER the real 18-Nov close is written.
        from classic_sp500.corporate_actions import ACTION, EFFECTIVE, ISSUER, REFERENCE
        previous, target = "2026-11-18", "2026-11-19"
        observed = "2026-11-03T16:28:14+00:00"
        book = {
            "equity": [{"date": "2026-11-17", "nav": 107741.70}],
            "positions": {ticker: {} for ticker in (
                "ABT", "DRI", "IDXX", "KMB", "LH", "MNST", "SJM", "WELL")},
            "pending": {},
            "cash": 5000.,
            "outage_control": {"first_trading_session": target},
            "receivables": {ACTION: {
                "action_id": ACTION, "effective_session": EFFECTIVE,
                "status": "unsettled", "symbol": "KMB",
                "source_url": ISSUER, "valuation_reference_url": REFERENCE,
                "valuation_policy": "occ_temporary_reference_applied_to_paper_claim",
                "recorded_at_utc": observed, "fixed_cash": "2257.90",
                "fractional_shares": "0.34802970125",
                "allocated_cost": 2169.9297082280136,
            }},
            "events": [{
                "type": "corporate_merger_entitlement",
                "action_id": ACTION, "date": EFFECTIVE,
                "source_url": ISSUER, "valuation_reference_url": REFERENCE,
                "cash_credited": 0, "trades_executed": 0,
                "recorded_at_utc": observed,
                "original_position": {"shares": 645.114733, "cost": 11874.999992119001},
                "successor_whole_shares": 94,
                "fractional_shares": "0.34802970125",
                "fixed_cash_receivable": "2257.90",
            }],
        }
        self.assertEqual(
            plan_track("IL-012", book, target, previous)["status"], "stale")
        book["equity"].append({"date": previous, "nav": 107741.70,
                               "provisional_corporate_valuation": True})
        eligible = plan_track("IL-012", book, target, previous)
        self.assertEqual(eligible["status"], "recorded")
        self.assertEqual(eligible["session"], previous)
        self.assertEqual(eligible["orders"], [])
        self.assertEqual(eligible["holdings"], sorted(book["positions"]))
        market_open = datetime(2026, 11, 19, 14, 30, tzinfo=timezone.utc)
        market = {"session": target, "previous": previous,
                  "open": market_open, "close": market_open + timedelta(hours=6, minutes=30)}
        lane = clock_plan(market_open-timedelta(minutes=10),
                          market, {"IL-012": eligible}, "a"*40)["slots"]["IL-012"]
        self.assertTrue(lane["execution_ready"])
        self.assertEqual(lane["monitor_tickers"], sorted(book["positions"]))
        self.assertEqual(lane["orders"], [])
        self.assertFalse(lane["exit_only_ready"])

        for field, invalid in (("status", "unreviewed"),
                               ("fixed_cash", "999999"),
                               ("action_id", "forged")):
            wrong = copy.deepcopy(book)
            wrong["receivables"][ACTION][field] = invalid
            plan = plan_track("IL-012", wrong, target, previous)
            self.assertEqual((plan["status"], plan["orders"]), ("paused", []), field)
            rejected = clock_plan(market_open-timedelta(minutes=10),
                                  market, {"IL-012": plan}, "a"*40)
            self.assertFalse(rejected["slots"]["IL-012"]["execution_ready"])
            self.assertEqual(rejected["slots"]["IL-012"]["monitor_tickers"], [])
        wrong = copy.deepcopy(book)
        wrong["receivables"]["UNKNOWN"] = {"status": "unsettled"}
        self.assertEqual(plan_track("IL-012", wrong, target, previous)["status"], "paused")
        wrong = copy.deepcopy(book)
        wrong["outage_control"]["first_trading_session"] = "2026-11-20"
        self.assertEqual(plan_track("IL-012", wrong, target, previous)["status"], "paused")
        wrong = copy.deepcopy(book)
        wrong["paused_missing_quotes"] = {"missing_tickers": ["KMB"]}
        self.assertEqual(plan_track("IL-012", wrong, target, previous)["status"], "paused")
        self.assertEqual(book["receivables"][ACTION]["status"], "unsettled")
