import unittest
from datetime import date, datetime, timezone

from yahoo_source import (
    BENCHMARK, MIN_COVERAGE, SCHEMA, SOURCE, UNIVERSE_SIZE,
    normalize, prepare_snapshot, verify_snapshot, verify_universe, yahoo_symbol, verify_closed_xnys_session,
)

SESSION = "2026-10-30"
STAMP = "2026-10-31T01:30:00+00:00"
UNIVERSE = [f"S{i:04}" for i in range(503)]


def bar(close=100, day=SESSION):
    return {
        "date": day, "open": close - 1, "high": close + 1,
        "low": close - 2, "close": close, "volume": 1200,
        "dividend": 0, "split": 0,
    }


class YahooSourceContractTest(unittest.TestCase):
    def test_source_is_yahoo_yfinance_raw_and_action_aware(self):
        self.assertEqual(UNIVERSE_SIZE, 503)
        self.assertEqual(BENCHMARK, "SPY")
        self.assertEqual(MIN_COVERAGE, 453)
        self.assertEqual(SOURCE["vendor"], "Yahoo Finance")
        self.assertEqual(SOURCE["client"], "yfinance")
        self.assertIs(SOURCE["auto_adjust"], False)
        self.assertIs(SOURCE["actions"], True)
        self.assertEqual(yahoo_symbol("BRK.B"), "BRK-B")
        self.assertEqual(len(verify_universe(UNIVERSE)), 503)
        self.assertEqual(SCHEMA, "idealab.xnys_ohlc.v1")

    def test_exact_date_no_stale_candles_or_adjusted_close_substitution(self):
        self.assertEqual(normalize("AAPL", SESSION, bar())["close"], 100)
        for modified in [
            bar(day="2026-10-29"),
            {**bar(), "close": 0},
            {**bar(), "low": 102},
            {**bar(), "volume": float("nan")},
            {**bar(), "split": -1},
            {**bar(), "dividend": -1},
        ]:
            with self.subTest(sample=modified):
                with self.assertRaises(ValueError):
                    normalize("AAPL", SESSION, modified)

    def test_full_coverage_provenance_and_hash_reproducibility(self):
        feed = {ticker: bar() for ticker in UNIVERSE}
        feed["SPY"] = bar(200)
        snapshot = prepare_snapshot(UNIVERSE, SESSION, feed, STAMP)
        self.assertEqual(snapshot["coverage"]["observed"], 504)
        self.assertEqual(snapshot["coverage"]["constituents_observed"], 503)
        self.assertEqual(snapshot["coverage"]["missing"], 0)
        self.assertEqual(snapshot["requested_symbols"][-1], "SPY")
        self.assertTrue(verify_snapshot(snapshot, UNIVERSE))
        self.assertEqual(snapshot, prepare_snapshot(UNIVERSE, SESSION, feed, STAMP))

    def test_below_90_percent_or_missing_spy_is_rejected(self):
        feed = {ticker: bar() for ticker in UNIVERSE[:452]}
        feed["SPY"] = bar(200)
        with self.assertRaisesRegex(ValueError, "under 90%"):
            prepare_snapshot(UNIVERSE, SESSION, feed, STAMP)
        feed = {ticker: bar() for ticker in UNIVERSE}
        with self.assertRaisesRegex(ValueError, "SPY missing"):
            prepare_snapshot(UNIVERSE, SESSION, feed, STAMP)
        feed = {ticker: bar() for ticker in UNIVERSE[:453]}
        feed["SPY"] = bar(200)
        snap = prepare_snapshot(UNIVERSE, SESSION, feed, STAMP)
        self.assertEqual(snap["coverage"]["constituents_observed"], 453)
        self.assertEqual(snap["coverage"]["missing"], 50)
        self.assertTrue(verify_snapshot(snap, UNIVERSE))

    def test_tampering_source_hash_currency_dates_or_universe_blocks(self):
        feed = {ticker: bar() for ticker in UNIVERSE}
        feed["SPY"] = bar(200)
        snap = prepare_snapshot(UNIVERSE, SESSION, feed, STAMP)
        changes = [
            lambda x: x["source"].update(vendor="Alternate vendor"),
            lambda x: x["bars"]["S0001"].update(close=105),
            lambda x: x["coverage"].update(observed=503),
            lambda x: x["missing"].update(S0001="allegedly missing"),
        ]
        import copy
        for change in changes:
            bad = copy.deepcopy(snap)
            change(bad)
            with self.assertRaises(ValueError):
                verify_snapshot(bad, UNIVERSE)

    def test_no_personal_accounts_or_external_provider_in_source_file(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parent / "yahoo_source.py").read_text(encoding="utf8")
        self.assertNotIn("alphavantage", source.lower())
        self.assertNotIn("alpha vantage", source.lower())
        self.assertNotIn("drive.google.com", source)
        self.assertNotIn("github.com/mamg", source)
        self.assertIn('INSTITUTIONAL_YAHOO_INTERNAL_RIGHTS', source)


    def test_unsafe_or_premature_nyse_capture_rejected(self):
        with self.assertRaisesRegex(ValueError, "18:00 New York"):
            verify_closed_xnys_session(
                "2026-10-30", datetime(2026, 10, 30, 21, 30, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, "18:00 New York"):
            verify_closed_xnys_session(
                "2026-10-30", datetime(2026, 11, 1, 1, 30, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            verify_closed_xnys_session(
                "2026-10-31", datetime(2026, 10, 31, 23, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
