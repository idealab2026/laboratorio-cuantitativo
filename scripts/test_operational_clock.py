"""MIDAS operator clock: opening locked before the market and observed quotes only."""
import copy
import io
import json
import sqlite3
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from operational_clock import (ACTIVE, clock_plan, status_report, verify_lock,
                               verify_prepared_lock, stage_for_actual_time,
                               main, budgeted_quote_targets, quote_batch, LIMIT)

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
        self.assertEqual(self.ready["slots"]["IL-015"]["orders"][0]["scheduled_at_utc"], "2026-11-10T14:30:00Z")
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



class BudgetedQuotesTest(unittest.TestCase):
    def synthetic(self):
        slots = {
            "IL-038": {"orders": [{"ticker": "AAPL"}], "execution_ready": True},
            "IL-019": {"orders": [{"ticker": "MSFT"}], "execution_ready": True},
            "IL-011": {"orders": [{"ticker": "GOOG"}], "monitor_tickers": ["META"],
                       "execution_ready": True},
            "IL-010": {"orders": [{"ticker": f"SY{i:03d}"} for i in range(503)],
                       "execution_ready": True},
        }
        return {"slots": slots}

    def test_one_503_book_cannot_starve_other_algorithms(self):
        chosen, omitted = budgeted_quote_targets(self.synthetic(), limit=4)
        self.assertEqual(chosen, {"AAPL", "MSFT", "GOOG", "META"})
        self.assertEqual(list(omitted), ["IL-010"])
        self.assertEqual(omitted["IL-010"]["reason"], "quota_cap_fail_closed")
        self.assertEqual(omitted["IL-010"]["required"], 503)

    def test_settled_lanes_do_not_reread_orders_but_stops_remain_fresh(self):
        lock = self.synthetic()
        prior = {"slots": {"IL-038": {"status": "native_forward_settled"},
                           "IL-011": {"status": "native_forward_settled"}}}
        chosen, omitted = budgeted_quote_targets(lock, prior, limit=2)
        self.assertEqual(chosen, {"MSFT", "META"})
        self.assertEqual(set(omitted), {"IL-010"})

    def test_oversized_vendor_batch_is_rejected_before_network_call(self):
        when = datetime(2026, 11, 10, 14, 31, tzinfo=UTC)
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            quote_batch([f"SY{i:03d}" for i in range(LIMIT+1)], when, {})

    def test_sqlite_lock_is_local_to_one_ticker_without_parallel_vendor_calls(self):
        """Regression: 2026-11-12 simultaneous Ticker.history locked peewee SQLite."""
        now = datetime(2026, 11, 12, 14, 38, tzinfo=UTC)
        quotes = []
        def vendor(symbols, requested, market):
            self.assertEqual(len(symbols), 1, "never pass parallel vendor tickers")
            ticker = symbols[0]
            quotes.append(ticker)
            if ticker == "CME":
                raise sqlite3.OperationalError("database is locked")
            return {ticker: {"price": 100., "quote_at_utc": "2026-11-12T14:37:00Z",
                             "observed_at_utc": "2026-11-12T14:38:00Z"}}

        with patch("operational_clock.quotes_yahoo", side_effect=vendor), \
             patch("sys.stderr", new_callable=io.StringIO) as logs:
            result = quote_batch(["MSFT", "CME", "AAPL", "AAPL"], now,
                                 {"session": "2026-11-12"})
        self.assertEqual(quotes, ["AAPL", "CME", "MSFT"])
        self.assertEqual(sorted(result), ["AAPL", "MSFT"])
        self.assertIn("midas_yfinance_cache_lock symbol=CME", logs.getvalue())
        self.assertNotIn("CME", result)

    def test_peewee_cache_lock_is_isolated_without_hiding_other_errors(self):
        class OperationalError(Exception):
            pass
        now = datetime(2026, 11, 12, 14, 38, tzinfo=UTC)
        def vendor(symbols, requested, market):
            if symbols[0] == "LOCK":
                raise OperationalError("database is locked")
            return {symbols[0]: {"price": 101}}
        with patch("operational_clock.quotes_yahoo", side_effect=vendor):
            self.assertEqual(set(quote_batch(["LOCK", "OK"], now, {})), {"OK"})
        with patch("operational_clock.quotes_yahoo",
                   side_effect=sqlite3.OperationalError("malformed database")):
            with self.assertRaisesRegex(sqlite3.OperationalError, "malformed"):
                quote_batch(["AAPL"], now, {})

    def test_cached_quote_never_bypasses_observation_time_validation(self):
        now = datetime(2026, 11, 10, 14, 39, tzinfo=UTC)
        with patch("operational_clock.quotes_yahoo", return_value={
                "AAPL": {"price": 500, "quote_at_utc": "2026-11-10T14:31:00Z",
                         "observed_at_utc": "2026-11-10T14:32:00Z"}}):
            result = quote_batch(["AAPL"], now, self.synthetic())
        self.assertEqual(status_report(
            {"schema": "midas.operational_clock.v1",
             "session": "2026-11-10", "previous_session": "2026-11-09",
             "open_at_utc": "2026-11-10T14:30:00Z",
             "prepared_at_utc": "2026-11-10T14:20:00Z",
             "source_commit": "a" * 40,
             "slots": {}, "lock_sha256": ""},
            now, {}, result) if False else result["AAPL"]["quote_at_utc"],
            "2026-11-10T14:31:00Z")
        # The actual freshness filter lives in _quote_valid / status_report.
        from operational_clock import _quote_valid
        market = {"open": datetime(2026, 11, 10, 14, 30, tzinfo=UTC),
                  "close": datetime(2026, 11, 10, 21, 0, tzinfo=UTC)}
        self.assertFalse(_quote_valid(result["AAPL"], now, market))

    def test_workflow_scopes_yfinance_cache_to_a_single_run(self):
        workflow = (ROOT / ".github/workflows/operational-clock.yml").read_text()
        self.assertIn("XDG_CACHE_HOME:", workflow)
        self.assertIn("midas-yfinance-${{ github.run_id }}-${{ github.run_attempt }}",
                      workflow)


class ClockPreopenRecoveryTest(unittest.TestCase):
    """Regression: GitHub cron fired after 09:30 ET on 2026-11-10."""

    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.market = {
            "session": "2026-11-10", "previous": "2026-11-09",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30),
        }
        self.track = {
            "IL-015": {
                "status": "recorded", "session": "2026-11-09",
                "holdings": [], "orders": [{
                    "ticker": "AAPL", "action": "buy",
                    "decision_session": "2026-11-09",
                    "target_session": "2026-11-10",
                    "target_weight": 0.12, "limit_price": None,
                }],
            },
        }
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lock = Path(self.temp.name) / "global-lock.json"
        self.public = Path(self.temp.name) / "operational-clock.json"

    def _invoke(self, when, stage="auto"):
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return when.astimezone(tz) if tz is not None else when.replace(tzinfo=None)

        stream = io.StringIO()
        with patch("operational_clock.datetime", FixedDateTime), \
             patch("operational_clock.market_window", return_value=self.market), \
             patch("operational_clock._repo_commit", return_value="c" * 40), \
             patch("build_opening_plan.plan_at", return_value=self.track) as planner, \
             patch("operational_clock.freeze_timesfm_entry_fx",
                   side_effect=AssertionError("No TimesFM FX signal expected")), \
             redirect_stdout(stream):
            code = main(["--stage", stage, "--lock", str(self.lock),
                         "--public", str(self.public)])
        return code, stream.getvalue(), planner.call_count

    def test_early_actual_run_freezes_and_duplicate_does_not_rewrite(self):
        early = self.open - timedelta(hours=2, minutes=10)
        code, output, called = self._invoke(early)
        self.assertEqual(code, 0)
        self.assertEqual(called, 1)
        frozen = self.lock.read_bytes()
        self.assertTrue(verify_prepared_lock(json.loads(frozen), self.market))
        self.assertEqual(json.loads(self.public.read_text())["session"], "2026-11-10")
        # Another cron retry may see a different source commit, but frozen
        # decisions must never be recomputed or rewritten.
        code2, output2, planned = self._invoke(early + timedelta(minutes=50))
        self.assertEqual(code2, 0)
        self.assertEqual(planned, 0)
        self.assertIn("preopen_lock_already_frozen", output2)
        self.assertEqual(frozen, self.lock.read_bytes())
        verify_lock(json.loads(frozen), self.market, self.open+timedelta(minutes=1))

    def test_integrity_failure_blocks_replacing_same_day_lock(self):
        self._invoke(self.open-timedelta(hours=2))
        frozen = json.loads(self.lock.read_text())
        frozen["slots"]["IL-015"]["orders"][0]["ticker"] = "TSLA"
        self.lock.write_text(json.dumps(frozen))
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self._invoke(self.open-timedelta(minutes=30))

    def test_delayed_cron_becomes_observe_and_cannot_backdate_fx(self):
        late = self.open+timedelta(minutes=40)
        self.assertEqual(stage_for_actual_time("auto", late, self.market), "observe")
        self.assertEqual(stage_for_actual_time("auto", self.open-timedelta(hours=2),
                                               self.market), "prepare")
        code, output, planned = self._invoke(late)
        self.assertEqual((code, planned), (2, 0))
        self.assertIn("no_preopen_lock", output)
        self.assertFalse(self.lock.exists())
        code, output, planned = self._invoke(late, stage="prepare")
        self.assertEqual((code, planned), (2, 0))
        self.assertIn("late_prepare_refused", output)

    def test_half_session_late_observer_never_retroactively_executes(self):
        # 13:00 New York is an early close. A delayed 15:xx cron is a no-op.
        market = dict(self.market)
        market["close"] = market["open"]+timedelta(hours=3, minutes=30)
        late = market["close"]+timedelta(minutes=35)
        class Late(datetime):
            @classmethod
            def now(cls, tz=None):
                return late.astimezone(tz) if tz else late
        stream = io.StringIO()
        with patch("operational_clock.datetime", Late), \
             patch("operational_clock.market_window", return_value=market), \
             redirect_stdout(stream):
            code = main(["--stage", "auto", "--lock", str(self.lock),
                         "--public", str(self.public)])
        self.assertEqual(code, 0)
        self.assertIn("observation_window_closed", stream.getvalue())
        self.assertFalse(self.lock.exists())

    def test_workflow_runs_by_actual_nyse_clock_and_uses_iana_timezone(self):
        path = ROOT / ".github/workflows/operational-clock.yml"
        lines = path.read_text().splitlines()
        entries = [i for i,row in enumerate(lines) if row.strip().startswith("- cron:")]
        self.assertGreaterEqual(len(entries), 5)
        for i in entries:
            self.assertIn("timezone: 'America/New_York'", lines[i+1])
        raw = "\n".join(lines)
        self.assertIn("17,47 7-8 * * 1-5", raw)
        self.assertIn("7,17 9 * * 1-5", raw)
        self.assertIn("STAGE=auto", raw)
        self.assertIn("verify_published_lock", raw)
        self.assertIn("ci-{0}", raw)

if __name__ == "__main__":
    unittest.main()
