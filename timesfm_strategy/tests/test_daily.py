import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daily_run
import run


class DailyEURTests(unittest.TestCase):
    def setUp(self):
        self.config = run.read(Path(__file__).resolve().parents[1] / "config-daily.json")
        self.date = "2026-10-13"
        self.orders = [{"ticker": "AAPL", "signal_date": self.date,
                        "predicted_return": .012, "score": .008}]
        self.state = daily_run.initialize(self.config, self.date, self.orders, {"regime": True})
        self.bars = {"AAPL": {"open": 100, "close": 110, "dividend": 0, "split": 0},
                     "SPY": {"open": 400, "close": 405, "dividend": 0, "split": 0}}

    def test_initial_state_is_prospective(self):
        daily_run.verify(self.config)
        self.assertEqual(self.state["first_session"], self.date)
        self.assertEqual(self.state["currency"], "EUR")
        self.assertEqual(self.state["books"]["timesfm_daily"]["trades"], [])
        self.assertEqual(self.state["books"]["timesfm_daily"]["nav"], 100000)
        self.assertEqual(self.state["books"]["benchmark_spy"]["pending"][0]["ticker"], "SPY")

    def test_daily_intraday_fill_settles_at_observed_close(self):
        result, changed = daily_run.process_session(
            self.state, self.config, "2026-10-14", self.date, self.bars,
            fx_entry=1.2, fx_mark=1.15)
        self.assertTrue(changed)
        book = result["books"]["timesfm_daily"]
        self.assertEqual(book["positions"], {})
        self.assertEqual(book["pending"], [])
        self.assertEqual(len(book["trades"]), 1)
        self.assertEqual(book["trades"][0]["entry_date"], "2026-10-14")
        self.assertEqual(book["trades"][0]["exit_date"], "2026-10-14")
        self.assertGreater(book["nav"], 100000)
        self.assertIn("SPY", result["books"]["benchmark_spy"]["positions"])
        self.assertEqual(self.state["last_session"], self.date)

    def test_reject_missed_and_repeated_sessions(self):
        with self.assertRaisesRegex(ValueError, "Missed XNYS"):
            daily_run.process_session(self.state, self.config, "2026-10-15",
                                      "2026-10-14", self.bars, fx_entry=1.2, fx_mark=1.15)
        same, changed = daily_run.process_session(self.state, self.config,
                                                   self.date, "2026-10-12",
                                                   self.bars, fx_entry=1.2, fx_mark=1.15)
        self.assertFalse(changed)
        self.assertEqual(same, self.state)

    def test_frozen_one_day_signal_requires_daily_settlement(self):
        with self.assertRaisesRegex(ValueError, "same-day"):
            daily_run.freeze_signal(self.state, self.config, "2026-10-14", [], {})
        updated, _ = daily_run.process_session(self.state, self.config, "2026-10-14",
                                               self.date, self.bars, fx_entry=1.2, fx_mark=1.15)
        future, changed = daily_run.freeze_signal(updated, self.config, "2026-10-14", [], {})
        self.assertTrue(changed)
        self.assertEqual(future["last_signal_session"], "2026-10-14")
        self.assertEqual(len(future["signal_history"]), 2)
        self.assertEqual(len(self.state["signal_history"]), 1)

    def stalled(self):
        state = copy.deepcopy(self.state)
        state["last_session"] = "2026-11-16"
        state["last_signal_session"] = "2026-11-13"
        state["equity"].append({"date": "2026-11-16", "nav": 102000.})
        for b in state["books"].values():
            b["equity"].append({"date": "2026-11-16", "nav": 102000.})
            b["pending"] = []
        state["books"]["timesfm_daily"]["positions"] = {
            "MSI": {"shares": 5., "entry_date": "2026-11-13", "signal_date": "2026-11-12",
                    "entry_price_eur": 100., "cost_eur": 500.,
                    "dividends_eur": 0., "fx_at_entry": 1.1}}
        state["books"]["benchmark_spy"]["positions"] = {
            "SPY": {"shares": 4., "entry_date": "2026-10-14", "signal_date": "2026-10-13",
                    "entry_price_eur": 300., "cost_eur": 1200.,
                    "dividends_eur": 0., "fx_at_entry": 1.1}}
        state["books"]["timesfm_daily"]["cash"] = 99500.
        state["books"]["benchmark_spy"]["cash"] = 98800.
        return state

    def test_unobserved_daily_exit_is_passive_mark_only_and_idempotent(self):
        state = self.stalled()
        before = copy.deepcopy(state)
        prices = {"MSI": {"close": 130., "dividend": 0., "split": 0.},
                  "SPY": {"close": 410., "dividend": 0., "split": 0.}}
        update, changed = daily_run.mark_unobserved_exit(
            state, self.config, "2026-11-17", "2026-11-16", prices, fx_mark=1.3)
        self.assertTrue(changed)
        self.assertEqual(state, before)
        self.assertEqual(update["last_session"], "2026-11-17")
        self.assertEqual(update["books"]["timesfm_daily"]["nav"], 99500 + 5 * 130 / 1.3)
        self.assertEqual(update["books"]["benchmark_spy"]["nav"], 98800 + 4 * 410 / 1.3)
        for name, previous in before["books"].items():
            book = update["books"][name]
            self.assertEqual(book["cash"], previous["cash"])
            self.assertEqual(book["positions"], previous["positions"])
            self.assertEqual(book["trades"], previous["trades"])
            self.assertTrue(book["equity"][-1]["inactive_no_new_fills"])
            self.assertEqual(book["events"][-1]["type"], "inactive_mark_only_no_execution")
        self.assertEqual(update["last_signal_session"], "2026-11-13")
        self.assertEqual(update["missing_signals"], ["2026-11-17"])
        with self.assertRaisesRegex(ValueError, "continuous open holding"):
            daily_run.mark_unobserved_exit(
                update, self.config, "2026-11-17", "2026-11-16", prices, fx_mark=1.3)

    def test_passive_exit_blocks_missing_prices_corporate_events_and_gaps(self):
        state = self.stalled()
        prices = {"MSI": {"close": 120, "dividend": 0, "split": 0},
                  "SPY": {"close": 400, "dividend": 0, "split": 0}}
        original = copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError, "Missing exact passive close"):
            daily_run.mark_unobserved_exit(state, self.config, "2026-11-17",
                "2026-11-16", {"SPY": prices["SPY"]}, fx_mark=1.2)
        with self.assertRaisesRegex(ValueError, "corporate action"):
            altered = copy.deepcopy(prices)
            altered["MSI"]["dividend"] = 0.25
            daily_run.mark_unobserved_exit(state, self.config, "2026-11-17",
                                           "2026-11-16", altered, fx_mark=1.2)
        with self.assertRaisesRegex(ValueError, "continuous open holding"):
            daily_run.mark_unobserved_exit(state, self.config, "2026-11-17",
                                           "2026-11-15", prices, fx_mark=1.2)
        with self.assertRaises(ValueError):
            daily_run.mark_unobserved_exit(state, self.config, "2026-11-17",
                                           "2026-11-16", prices, fx_mark=0)
        self.assertEqual(state, original)

    def test_passive_exit_expires_old_orders_without_recording_a_trade(self):
        state = self.stalled()
        state["books"]["benchmark_spy"]["pending"] = [
            {"ticker": "MSFT", "signal_date": "2026-11-13"}]
        before_trades = copy.deepcopy(state["books"]["benchmark_spy"]["trades"])
        result, _ = daily_run.mark_unobserved_exit(state, self.config, "2026-11-17",
            "2026-11-16", {"MSI": {"close": 120}, "SPY": {"close": 400}}, fx_mark=1.2)
        self.assertFalse(result["books"]["benchmark_spy"]["pending"])
        self.assertEqual(result["books"]["benchmark_spy"]["trades"], before_trades)
        self.assertEqual(result["books"]["benchmark_spy"]["events"][-2]["type"],
                         "inactive_expired_open_no_fill")

    def test_scheduled_daily_skips_inference_while_exit_remains_open(self):
        import json
        import tempfile
        from unittest.mock import patch
        state = self.stalled()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "ledger.json"
            target.write_text(json.dumps(state), encoding="utf-8")
            with patch.object(run, "calendar", return_value=("2026-11-17", "2026-11-16",
                                                             "2026-11-18", False)), \
                 patch.object(run, "_daily_bars", return_value=(
                     {"MSI": {"close": 130}, "SPY": {"close": 410}}, 1.2, 1.3)), \
                 patch.object(run, "get_forecasts",
                              side_effect=AssertionError("no historical inference allowed")):
                result = daily_run.run(
                    Path(__file__).resolve().parents[1] / "config-daily.json", target)
                self.assertEqual(result["status"], "daily_passive_mark_exit_pending")
                self.assertEqual(result["held"], ["MSI"])
                self.assertTrue(result["changed"])
                again = daily_run.run(
                    Path(__file__).resolve().parents[1] / "config-daily.json", target)
                self.assertFalse(again["changed"])
                self.assertEqual(again["status"], "daily_passive_mark_exit_pending")
                saved = json.loads(target.read_text())
                self.assertEqual(saved["last_session"], "2026-11-17")
                self.assertEqual(saved["books"]["timesfm_daily"]["trades"],
                                 state["books"]["timesfm_daily"]["trades"])

    def test_campaigns_are_independent(self):
        weekly = run.read(Path(__file__).resolve().parents[1] / "config.json")
        self.assertNotEqual(run.digest(weekly), run.digest(self.config))
        self.assertEqual(self.config["model"]["horizon_sessions"], 1)
        self.assertEqual(weekly["model"]["horizon_sessions"], 5)
        self.assertEqual(run.load_universe(self.config["universe_file"]),
                         run.load_universe(weekly["universe_file"]))
        self.assertEqual(len(run.load_universe(self.config["universe_file"])), 503)
        changed = copy.deepcopy(self.config)
        changed["initial_capital"] = 99999
        with self.assertRaises(ValueError):
            daily_run.verify(changed)


if __name__ == "__main__":
    unittest.main()
