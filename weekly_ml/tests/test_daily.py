import copy
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "weekly_ml"))
from daily import freeze_signal, process_day, ENGINE_VERSION
from paper import digest
import daily
from market_data.snapshot import make_snapshot, write_immutable


class CommonDailyPriceTests(unittest.TestCase):
    DAY = "2026-10-27"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(daily, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        names = ["AAPL"] + [f"S{i:03d}" for i in range(502)]
        row = {"date": self.DAY, "open": 100., "high": 103., "low": 99.,
               "close": 102., "volume": 500., "dividend": 0., "split": 0.}
        record = make_snapshot(self.DAY, names,
                               {"AAPL": row, "SPY": row, "S000": row},
                               captured_at_utc="2026-10-27T22:00:00+00:00")
        self.path, _ = write_immutable(self.root / "market_data/snapshots", record)
        self.sha = record["sha256"]

    def test_snapshot_recovers_empty_vendor_with_hash_and_requested_symbols_only(self):
        import pandas as pd
        prior = self.path.read_bytes()
        diagnostic = {}
        with patch("yfinance.download", return_value=pd.DataFrame()):
            got = daily.download_bars(["AAPL", "SPY"], self.DAY, diagnostics=diagnostic)
        self.assertEqual(set(got), {"AAPL", "SPY"})
        self.assertEqual(got["AAPL"]["close"], 102.)
        self.assertEqual(diagnostic["hash"], self.sha)
        self.assertEqual(self.path.read_bytes(), prior)

    def test_partial_vendor_keeps_disagreement_and_recovers_other_ticker(self):
        import pandas as pd
        raw = pd.DataFrame({("AAPL", "Open"): [100.], ("AAPL", "Close"): [101.],
                            ("AAPL", "High"): [103.], ("AAPL", "Low"): [99.]},
                           index=pd.DatetimeIndex([self.DAY]))
        info = {}
        with patch("yfinance.download", return_value=raw):
            got = daily.download_bars(["AAPL", "SPY"], self.DAY, diagnostics=info)
        self.assertEqual(got["AAPL"]["close"], 102.)
        self.assertEqual(got["SPY"]["close"], 102.)
        self.assertEqual(info["status"], "common_raw_primary")

    def test_missing_benchmark_outside_snapshot_is_never_substituted(self):
        import pandas as pd
        with patch("yfinance.download", return_value=pd.DataFrame()):
            with self.assertRaisesRegex(ValueError, "RSP"):
                daily.download_bars(["AAPL", "RSP"], self.DAY)

    def test_wrong_session_and_tampering_remain_closed(self):
        import pandas as pd
        with patch("yfinance.download", return_value=pd.DataFrame()):
            with self.assertRaisesRegex(ValueError, "Missing verified common"):
                daily.download_bars(["AAPL"], "2026-10-28")
            self.path.write_text(self.path.read_text().replace(self.sha, "bad"))
            with self.assertRaisesRegex(ValueError, "Missing verified common"):
                daily.download_bars(["AAPL"], self.DAY)

    def test_independent_rsp_bad_batch_retries_exact_raw_bar(self):
        import pandas as pd
        valid = pd.DataFrame({"Open": [200.], "High": [205.], "Low": [198.],
                              "Close": [203.], "Volume": [500.]},
                             index=pd.DatetimeIndex([self.DAY]))
        invalid = valid.copy()
        invalid["Close"] = float("nan")
        original = self.path.read_bytes()
        with patch("yfinance.download", side_effect=[invalid, valid]) as provider:
            info = {}
            got = daily.download_bars(["AAPL", "RSP"], self.DAY, diagnostics=info)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(got["RSP"]["close"], 203.)
        self.assertEqual(got["AAPL"]["close"], 102.)
        self.assertEqual(info["independent_missing"], [])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(all(not call.kwargs["auto_adjust"] for call in provider.call_args_list))

    def test_independent_rsp_invalid_retry_remains_missing(self):
        import pandas as pd
        invalid = pd.DataFrame({"Open": [200.], "High": [205.], "Low": [198.],
                                "Close": [float("nan")], "Volume": [500.]},
                               index=pd.DatetimeIndex([self.DAY]))
        with patch("yfinance.download", return_value=invalid) as provider:
            with self.assertRaisesRegex(ValueError, "Barra OHLC fechada ausente: RSP"):
                daily.download_bars(["RSP"], self.DAY)
        self.assertEqual(provider.call_count, 2)

    def test_nan_vendor_open_is_missing_and_uses_verified_bar(self):
        import pandas as pd
        raw = pd.DataFrame({"Open": [float("nan")], "Close": [101.]},
                           index=pd.DatetimeIndex([self.DAY]))
        with patch("yfinance.download", return_value=raw):
            got = daily.download_bars(["AAPL"], self.DAY)
        self.assertEqual(got["AAPL"]["open"], 100.)


class DailyPaperTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "models": ["lgbm_return"], "currency": "USD",
            "paper_policy": {
                "capital": 100000, "commission": 0.001, "slippage": 0.0005,
                "invest_fraction": 0.95, "max_entry_weight": 0.12,
                "max_positions": 10, "min_predicted_return": 0.005,
                "min_direction_probability": .55,
                "ensemble_min_positive_votes": 3,
                "fractional_shares": True, "share_precision": 6,
                "min_notional": 10
            }
        }

    def signal(self, day="2026-10-09"):
        return {
            "asof": day, "config_hash": digest(self.config),
            "models": {"lgbm_return": {"AAA": {"predicted_return": 0.02}}}
        }

    def first(self):
        state, changed = freeze_signal(self.config, self.signal())
        self.assertTrue(changed)
        self.assertEqual(state["engine"], ENGINE_VERSION)
        self.assertEqual(state["last_session"], "2026-10-09")
        return state

    def monday(self):
        state = self.first()
        return process_day(self.config, state, "2026-10-12",
                           {"AAA": {"open": 100, "close": 105},
                            "SPY": {"open": 700, "close": 705},
                            "RSP": {"open": 200, "close": 203}},
                           previous_session="2026-10-09",
                           week_end=False)[0]

    def test_frozen_signal_does_not_book_historical_open(self):
        state = self.first()
        self.assertEqual(state["strategies"]["lgbm_return"]["trades"], [])
        self.assertFalse(state["strategies"]["lgbm_return"]["positions"])
        self.assertEqual(len(state["strategies"]["lgbm_return"]["pending"]), 1)
        second, changed = freeze_signal(self.config, self.signal(), state)
        self.assertFalse(changed)
        self.assertEqual(second, state)
        with self.assertRaisesRegex(ValueError, "revisada"):
            changed_signal = self.signal()
            changed_signal["models"]["lgbm_return"]["AAA"]["predicted_return"] = 0.03
            freeze_signal(self.config, changed_signal, state)

    def test_open_day_marks_position_and_costs_then_closes_on_friday(self):
        state = self.monday()
        book = state["strategies"]["lgbm_return"]
        self.assertTrue(book["positions"])
        self.assertFalse(book["pending"])
        self.assertEqual(book["equity"][-1]["date"], "2026-10-12")
        self.assertNotEqual(book["nav"], 100000)
        self.assertLess(book["cash"], 100000)
        self.assertEqual(len(book["trades"]), 0)
        for day, prev, close in [
            ("2026-10-13", "2026-10-12", 106),
            ("2026-10-14", "2026-10-13", 104),
            ("2026-10-15", "2026-10-14", 103),
            ("2026-10-16", "2026-10-15", 110)
        ]:
            state, changed = process_day(self.config, state, day,
                       {"AAA": {"open": 103, "close": close},
                        "SPY": {"open": 710, "close": 705},
                        "RSP": {"open": 204, "close": 205}},
                       previous_session=prev,
                       week_end=(day == "2026-10-16"))
            self.assertTrue(changed)
        book = state["strategies"]["lgbm_return"]
        self.assertFalse(book["positions"])
        self.assertAlmostEqual(book["cash"], book["nav"])
        self.assertEqual(len(book["trades"]), 1)
        self.assertEqual(book["trades"][0]["entry_date"], "2026-10-12")
        self.assertEqual(book["trades"][0]["exit_date"], "2026-10-16")
        self.assertEqual(len(book["equity"]), 6)
        self.assertEqual([e["date"] for e in book["equity"][-5:]],
                         ["2026-10-12","2026-10-13","2026-10-14","2026-10-15","2026-10-16"])
        state2, changed = freeze_signal(self.config, self.signal("2026-10-16"), state)
        self.assertTrue(changed)
        self.assertEqual(state2["last_signal_session"], "2026-10-16")
        self.assertEqual(state2["strategies"]["lgbm_return"]["nav"], book["nav"])

    def test_run_publishes_unaffected_books_and_retries_only_paused_book(self):
        quotes = {"SPY": {"open": 700, "close": 705}, "RSP": {"open": 200, "close": 201}}
        state = self.first()
        with tempfile.TemporaryDirectory() as path:
            config, output = Path(path) / "config.json", Path(path) / "ledger.json"
            daily.write(config, self.config)
            daily.write(output, state)
            with patch.object(daily, "live_calendar", return_value=("2026-10-12", "2026-10-09", "2026-10-13", False)), patch.object(
                    daily, "download_bars", side_effect=[quotes, {"AAA": {"open": 100, "close": 105}}]) as download:
                partial = daily.run(config, path, output, "daily")
                books = daily.read(output)["strategies"]
                self.assertEqual(partial["status"], "paper_recorded_partial")
                self.assertEqual(list(partial["paused_books"]), ["lgbm_return"])
                blocked = books["lgbm_return"]
                self.assertEqual(blocked["cash"], state["strategies"]["lgbm_return"]["cash"])
                self.assertEqual(blocked["equity"], state["strategies"]["lgbm_return"]["equity"])
                self.assertEqual(blocked["pending"], state["strategies"]["lgbm_return"]["pending"])
                self.assertEqual(books["benchmark_rsp"]["equity"][-1]["date"], "2026-10-12")
                self.assertEqual(books["benchmark_spy"]["equity"][-1]["date"], "2026-10-12")
                next_day, _ = process_day(self.config, daily.read(output), "2026-10-13",
                                          {**quotes, "AAA": {"open": 100, "close": 105}},
                                          previous_session="2026-10-12", week_end=False)
                missed_open = next_day["strategies"]["lgbm_return"]
                self.assertEqual(missed_open["equity"], blocked["equity"])
                self.assertEqual(missed_open["pending"], blocked["pending"])
                self.assertEqual(missed_open["positions"], {})
                self.assertEqual(daily.run(config, path, output, "daily")["status"], "daily_recorded")
                final = daily.read(output)["strategies"]
                self.assertEqual(final["benchmark_rsp"], books["benchmark_rsp"])
                self.assertEqual(final["benchmark_spy"], books["benchmark_spy"])
                self.assertEqual(download.call_args.args[0], {"AAA"})
                self.assertTrue(final["lgbm_return"]["equity"][-1]["late_recorded_verified_date"])
                self.assertEqual([e["type"] for e in final["lgbm_return"]["events"]],
                                 ["signal_frozen", "weekly_book_paused", "buy"])
                self.assertEqual(daily.run(config, path, output, "daily")["status"], "already_recorded")

    def test_late_marks_do_not_recreate_orders_or_missed_weekly_sales(self):
        state = self.monday()
        peer_prices = {"SPY": {"close": 705}, "RSP": {"close": 201}}
        partial, _ = process_day(self.config, state, "2026-10-13", peer_prices,
                                 previous_session="2026-10-12", week_end=False)
        quotes = {**peer_prices, "AAA": {"close": 108}}
        identity = {"snapshot_sha256": "example"}
        recovered, _ = process_day(self.config, partial, "2026-10-14", quotes,
                                   previous_session="2026-10-13", week_end=False,
                                   historical={"2026-10-13": (quotes, identity)})
        book = recovered["strategies"]["lgbm_return"]
        self.assertEqual(book["positions"], state["strategies"]["lgbm_return"]["positions"])
        self.assertEqual(book["trades"], [])
        self.assertTrue(book["equity"][-2]["late_mark_only"])
        self.assertEqual(book["equity"][-2]["quote_identity"], identity)
        across_week, _ = process_day(self.config, partial, "2026-10-19", quotes,
                                     previous_session="2026-10-16", week_end=False,
                                     historical={"2026-10-16": (quotes, identity)})
        blocked = across_week["strategies"]["lgbm_return"]
        self.assertEqual(blocked["equity"], partial["strategies"]["lgbm_return"]["equity"])
        self.assertEqual(blocked["paused_missing_quotes"]["reason"], "unreconciled_session")

    def test_frozen_friday_signal_can_admit_a_recovered_book_once(self):
        state = self.monday()
        for day, previous in [("2026-10-13", "2026-10-12"), ("2026-10-14", "2026-10-13"),
                              ("2026-10-15", "2026-10-14")]:
            state, _ = process_day(self.config, state, day,
                                   {"AAA": {"close": 102}, "SPY": {"close": 705}, "RSP": {"close": 201}},
                                   previous_session=previous, week_end=False)
        state, _ = process_day(self.config, state, "2026-10-16",
                               {"SPY": {"close": 705}, "RSP": {"close": 201}},
                               previous_session="2026-10-15", week_end=True)
        forecast = self.signal("2026-10-16")
        state, _ = freeze_signal(self.config, forecast, state)
        self.assertEqual(state["strategies"]["lgbm_return"]["last_signal_session"], "2026-10-09")
        self.assertEqual(state["strategies"]["benchmark_spy"]["last_signal_session"], "2026-10-16")
        settled, _ = process_day(self.config, state, "2026-10-16", {"AAA": {"close": 106}},
                                 previous_session="2026-10-15", week_end=True)
        frozen, changed = freeze_signal(self.config, forecast, settled)
        self.assertTrue(changed)
        model = frozen["strategies"]["lgbm_return"]
        self.assertEqual(len(model["trades"]), 1)
        self.assertEqual(model["pending"][0]["signal_date"], "2026-10-16")
        self.assertEqual(frozen["strategies"]["benchmark_spy"], state["strategies"]["benchmark_spy"])
        self.assertEqual(freeze_signal(self.config, forecast, frozen), (frozen, False))

    def test_idempotence(self):
        state = self.monday()
        again, changed = process_day(self.config, state, "2026-10-12", {},
                        previous_session="2026-10-09",
                        week_end=False)
        self.assertFalse(changed)
        self.assertEqual(again, state)

    def test_refuse_old_signal(self):
        forecast = self.signal("2026-10-02")
        result, changed = freeze_signal(self.config, forecast)
        self.assertIsNone(result)
        self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
