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
import operational_clock
from operational_clock import (preclose_target, run_preclose_watch,
                               open_rendezvous_target, run_open_watch,
                               ACTIVE, clock_plan, status_report, verify_lock,
                               verify_prepared_lock, stage_for_actual_time,
                               main, budgeted_quote_targets, quote_batch, LIMIT,
                               record_opening_quote_diagnostic, publish_missed_open)

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

    def test_weekly_exit_only_is_open_holding_not_stale_signal(self):
        tracks = copy.deepcopy(self.tracks)
        tracks["IL-023"] = {
            "status": "paused", "session": self.market["previous"],
            "orders": [], "holdings": ["AKAM", "AMAT"],
        }
        lock = clock_plan(self.open - timedelta(minutes=10),
                          self.market, tracks, self.sha)
        slot = lock["slots"]["IL-023"]
        self.assertFalse(slot["execution_ready"])
        self.assertTrue(slot["exit_only_ready"])
        self.assertEqual(slot["monitor_tickers"], ["AKAM", "AMAT"])
        report = status_report(lock, self.open + timedelta(minutes=2),
                               self.market, {})
        lane = report["slots"]["IL-023"]
        self.assertEqual(lane["status"], "exit_only_waiting_preclose")
        self.assertTrue(lane["exit_only_ready"])
        self.assertEqual(lane["holdings_count"], 2)
        self.assertEqual(lane["planned"], 0)
        self.assertNotIn("fills", lane)
        self.assertEqual(report["slots"]["IL-042"]["status"], "source_stale_or_unavailable")

    def test_stale_and_future_lookahead_rejected(self):
        now = self.open + timedelta(minutes=10)
        old = self.observed(stamp=self.open + timedelta(minutes=1))
        result = status_report(self.ready, now, self.market, {"AAPL": old, "MSFT": old})
        self.assertEqual(result["slots"]["IL-015"]["status"], "partial_data")
        self.assertEqual(result["slots"]["IL-015"]["waiting"], 2)
        future = self.observed(stamp=now + timedelta(minutes=1))
        self.assertEqual(status_report(self.ready, now, self.market,
                         {"AAPL": future})["slots"]["IL-015"]["observed"], 0)

    def test_classic_opening_missing_quotes_audited_without_invented_fills(self):
        lane = {"planned": 2, "orders": copy.deepcopy(self.ready["slots"]["IL-015"]["orders"])}
        before = copy.deepcopy(lane)
        first = self.open + timedelta(minutes=4)
        record_opening_quote_diagnostic(
            lane, {}, self.ready["slots"]["IL-015"],
            {"status": "awaiting_fresh_open_quotes", "fills": 0, "missing": ["MSFT"]},
            first, self.market)
        audit = lane["opening_quote_diagnostic"]
        self.assertEqual(audit["required_tickers"], ["AAPL", "MSFT"])
        self.assertEqual(audit["first_missing_tickers"], ["MSFT"])
        self.assertFalse(audit["all_required_quotes_available_now"])
        self.assertEqual(lane["orders"], before["orders"])
        self.assertNotIn("fills", lane)

        # A later poll cannot silently turn old prices into open-window fills.
        later = self.open + timedelta(minutes=45)
        previous = copy.deepcopy(lane)
        late_lane = copy.deepcopy(before)
        record_opening_quote_diagnostic(
            late_lane, previous, self.ready["slots"]["IL-015"],
            {"status": "opening_window_missed", "fills": 0}, later, self.market)
        late = late_lane["opening_quote_diagnostic"]
        self.assertEqual(late["settlement_status"], "opening_window_missed")
        self.assertEqual(late["first_missing_tickers"], ["MSFT"])
        self.assertEqual(late["first_missing_at_utc"], audit["first_missing_at_utc"])
        self.assertEqual(late["missing_tickers_at_last_attempt"], [])
        self.assertTrue(late["all_required_quotes_available_now"])
        self.assertEqual(late["opening_cutoff_at_utc"],
                         audit["opening_cutoff_at_utc"])
        self.assertNotIn("fills", late_lane)

        unchanged = copy.deepcopy(before)
        record_opening_quote_diagnostic(
            unchanged, {}, self.ready["slots"]["IL-015"],
            {"status": "settled_native_paper", "fills": 1}, first, self.market)
        self.assertEqual(unchanged, before)

    def test_expired_classic_open_is_reported_as_missed_without_phantom_fill(self):
        lane = {"status": "prices_observed_not_settled", "planned": 3,
                "observed": 3, "waiting": 0,
                "orders": [{"ticker": "CMG", "status": "price_observed"}],
                "opening_quote_diagnostic": {
                    "settlement_status": "opening_window_missed",
                    "missing_tickers_at_last_attempt": ["ERIE"]}}
        orders = copy.deepcopy(lane["orders"])
        self.assertTrue(publish_missed_open(lane, {"status": "opening_window_missed", "fills": 0}))
        self.assertEqual(lane["status"], "opening_window_missed")
        self.assertEqual(lane["opening_order_execution"], "unfilled_expired")
        self.assertEqual(lane["orders"], orders)
        self.assertEqual(lane["opening_quote_diagnostic"]["missing_tickers_at_last_attempt"], ["ERIE"])
        self.assertNotIn("fills", lane)
        self.assertNotIn("native_marker", lane)
        # Repeated polling cannot silently label an unfilled order as settled.
        self.assertFalse(publish_missed_open(lane, {"status": "opening_window_missed", "fills": 0}))
        settled = {"status": "native_forward_settled", "fills_count": 1}
        self.assertFalse(publish_missed_open(settled, {"status": "opening_window_missed"}))
        self.assertEqual(settled, {"status": "native_forward_settled", "fills_count": 1})
        unrelated = {"status": "prices_observed_not_settled"}
        self.assertFalse(publish_missed_open(unrelated, {"status": "awaiting_fresh_open_quotes"}))
        self.assertEqual(unrelated["status"], "prices_observed_not_settled")

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
        self.assertEqual(result["AAPL"]["quote_at_utc"],
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
        self.assertIn("11,31,51 8 * * 1-5", raw)
        self.assertIn("7,17 9 * * 1-5", raw)
        self.assertIn("26 12,15 * * 1-5", raw)
        self.assertIn("STAGE=auto", raw)
        self.assertIn("verify_published_lock", raw)
        self.assertIn("ci-{0}", raw)


class PrecloseWatcherTests(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 20, 14, 30, tzinfo=UTC)
        self.market = {
            "session": "2026-11-20", "previous": "2026-11-19",
            "open": self.open, "close": datetime(2026, 11, 20, 21, tzinfo=UTC),
        }
        self.lock = {"session": "2026-11-20", "slots": {
            "IL-023": {"source_status": "paused", "execution_ready": False,
                       "exit_only_ready": True, "monitor_tickers": ["AAPL", "MSFT"]},
            "IL-024": {"source_status": "paused", "execution_ready": False,
                       "exit_only_ready": True, "monitor_tickers": ["AAPL"]},
        }}
        self.start = self.market["close"] - timedelta(minutes=29)
        self.target = self.market["close"] - timedelta(minutes=4, seconds=30)

    def test_friday_paused_weekly_books_arm_at_actual_session_close(self):
        # An early scheduled launch can stay inside the existing workflow
        # and wake at the true last-five-minute observed-quote window.
        self.assertEqual(preclose_target(
            self.market["close"] - timedelta(minutes=34),
            self.market, self.lock), self.target)
        self.assertEqual(preclose_target(
            self.start, self.market, self.lock), self.target)
        self.assertEqual(preclose_target(
            self.market["close"] - timedelta(minutes=7), self.market, self.lock),
            self.target)

    def test_never_watch_if_cron_arrived_after_rendezvous_or_in_old_session(self):
        for time in (self.market["close"] - timedelta(minutes=36),
                     self.market["close"] - timedelta(minutes=5),
                     self.market["close"] + timedelta(minutes=31)):
            self.assertIsNone(preclose_target(
                time, self.market, self.lock))
        old = {**self.lock, "session": "2026-11-19"}
        self.assertIsNone(preclose_target(
            self.start, self.market, old))
        self.assertIsNone(preclose_target(
            self.start.replace(tzinfo=None), self.market, self.lock))

    def test_no_watch_without_a_frozen_position_or_when_not_friday(self):
        empty = {"session": self.market["session"],
                 "slots": {"IL-023": {"exit_only_ready": True,
                                      "monitor_tickers": []}}}
        self.assertIsNone(preclose_target(
            self.start, self.market, empty))
        barred = {"session": self.market["session"],
                  "slots": {"IL-023": {"exit_only_ready": False,
                                       "execution_ready": False,
                                       "monitor_tickers": ["AAPL"]}}}
        self.assertIsNone(preclose_target(
            self.start, self.market, barred))
        midweek = {**self.market, "session": "2026-11-18"}
        self.assertIsNone(preclose_target(
            self.start, midweek, {**self.lock, "session": "2026-11-18"}))
        # A verified daily TimesFM holding warrants a close observation
        # on a weekday even without a Friday liquidation.
        active = {"session": "2026-11-18", "slots": {
            "IL-042": {"execution_ready": True, "monitor_tickers": ["AXON"]}}}
        self.assertEqual(preclose_target(
            self.start, midweek, active), self.target)

    def test_half_session_uses_real_1300_et_close(self):
        early = {**self.market, "session": "2026-11-27",
                 "previous": "2026-11-25",
                 "close": datetime(2026, 11, 27, 18, tzinfo=UTC)}
        lock = {**self.lock, "session": "2026-11-27"}
        self.assertEqual(preclose_target(
            early["close"] - timedelta(minutes=29), early, lock),
            early["close"] - timedelta(minutes=4, seconds=30))

    def _run_mocked(self, wake):
        start = self.start
        class ControlledTime(datetime):
            points = iter((start, wake))
            @classmethod
            def now(cls, tz=None):
                return next(cls.points)
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "forward_open_state").mkdir()
            (work / "forward_open_state/global-lock.json").write_text("{}", encoding="utf8")
            output = work / "github_output"
            with patch.object(operational_clock, "datetime", ControlledTime), \
                                  patch.object(operational_clock, "_read", return_value=self.lock), \
                 patch.object(operational_clock, "market_window",
                              return_value=self.market), \
                 patch.object(operational_clock, "verify_prepared_lock"), \
                 patch.object(operational_clock.time, "sleep") as sleep, \
                 patch.object(operational_clock, "main", return_value=0) as run, \
                 patch.dict(operational_clock.os.environ,
                            {"GITHUB_OUTPUT": str(output)}, clear=False):
                result = run_preclose_watch(work / 'forward_open_state/global-lock.json',
                                             work / 'data/operational-clock.json')
                written = output.read_text(encoding="utf8") if output.exists() else ""
            return result, written, sleep.call_args_list, run.call_args_list

    def test_watcher_calls_original_operator_once_with_new_observation(self):
        code, output, slept, called = self._run_mocked(
            self.target + timedelta(seconds=2))
        self.assertEqual(code, 0)
        self.assertEqual(output, "observed=true\n")
        self.assertEqual(len(slept), 1)
        self.assertAlmostEqual(slept[0].args[0], 24.5 * 60)
        self.assertEqual(len(called), 1)
        self.assertIn("observe", called[0].args[0])
        self.assertNotIn("prepare", called[0].args[0])

    def test_late_wakeup_never_invents_a_sale(self):
        code, output, slept, called = self._run_mocked(
            self.market["close"] + timedelta(seconds=1))
        self.assertEqual(code, 2)
        self.assertFalse(output)
        self.assertEqual(len(slept), 1)
        self.assertFalse(called)


class OpeningRendezvousTests(unittest.TestCase):
    """Fallback for delayed/dropped scheduled 09:31 ET opening workflows."""

    def setUp(self):
        self.open = datetime(2026, 11, 18, 14, 30, tzinfo=UTC)
        self.market = {
            "session": "2026-11-18", "previous": "2026-11-17",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)
        }
        self.lock = {"session": "2026-11-18", "slots": {
            "IL-011": {"execution_ready": True, "orders": [{"ticker":"AES"}],
                       "monitor_tickers": ["CZR"]},
            "IL-023": {"execution_ready": False, "exit_only_ready": True,
                       "orders": [], "monitor_tickers": ["AAPL"]},
        }}
        self.start = self.open - timedelta(minutes=64)
        self.target = self.open + timedelta(minutes=4)

    def test_ordered_immutable_preopen_lock_arms_one_fresh_opening_quote(self):
        self.assertEqual(open_rendezvous_target(self.start, self.market, self.lock),
                         self.target)
        self.assertEqual(open_rendezvous_target(
            self.open - timedelta(minutes=79), self.market, self.lock), self.target)
        self.assertIsNone(open_rendezvous_target(
            self.open - timedelta(minutes=81), self.market, self.lock))
        self.assertIsNone(open_rendezvous_target(
            self.open - timedelta(minutes=4), self.market, self.lock))

    def test_stale_source_and_ineligible_lanes_never_create_new_open_plan(self):
        stale = {**self.lock, "session": "2026-11-17"}
        self.assertIsNone(open_rendezvous_target(self.start, self.market, stale))
        paused = {"session": "2026-11-18", "slots": {
            "IL-023": {"execution_ready": False, "exit_only_ready": True,
                       "orders": [], "monitor_tickers": ["AAPL"]}}}
        self.assertIsNone(open_rendezvous_target(self.start, self.market, paused))
        self.assertIsNone(open_rendezvous_target(
            self.start.replace(tzinfo=None), self.market, self.lock))

    def test_real_half_day_open_still_has_first_and_last_causal_window(self):
        # The opening target follows XNYS official calendar, not an
        # unverified fixed Madrid timestamp or close-time backfill.
        half = {"session":"2026-11-27", "previous":"2026-11-25",
                "open":datetime(2026,11,27,14,30,tzinfo=UTC),
                "close":datetime(2026,11,27,18,0,tzinfo=UTC)}
        frozen={**self.lock, "session":"2026-11-27"}
        self.assertEqual(open_rendezvous_target(
            half["open"]-timedelta(minutes=64), half, frozen),
            half["open"]+timedelta(minutes=4))

    def test_wakeup_observes_once_and_only_from_fresh_original_operator(self):
        class Clock(datetime):
            values=iter((self.start, self.target+timedelta(seconds=3)))
            @classmethod
            def now(cls, tz=None):
                return next(cls.values)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            lockpath=root/"lock.json"; lockpath.write_text("{}",encoding="utf8")
            public=root/"public.json"
            output=root/"output"
            with patch.object(operational_clock,"datetime",Clock), \
                 patch.object(operational_clock,"market_window",
                              return_value=self.market), \
                 patch.object(operational_clock,"_read",return_value=self.lock), \
                 patch.object(operational_clock,"verify_prepared_lock") as verify, \
                 patch.object(operational_clock.time,"sleep") as slept, \
                 patch.object(operational_clock,"main",return_value=0) as observed, \
                 patch.dict(operational_clock.os.environ,{"GITHUB_OUTPUT":str(output)}):
                result=run_open_watch(lockpath,public)
            self.assertEqual(result,0)
            verify.assert_called_once()
            self.assertAlmostEqual(slept.call_args.args[0],
                                   (self.target-self.start).total_seconds())
            self.assertEqual(observed.call_count,1)
            self.assertEqual(observed.call_args.args[0][1],"observe")
            self.assertIn("--lock",observed.call_args.args[0])
            self.assertEqual(output.read_text(),"observed=true\n")

    def test_late_wakeup_refuses_fill_and_never_emits_publication_signal(self):
        class Clock(datetime):
            values=iter((self.start, self.open+timedelta(minutes=21)))
            @classmethod
            def now(cls, tz=None):
                return next(cls.values)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            path=root/"lock.json";path.write_text("{}",encoding="utf8")
            output=root/"output"
            with patch.object(operational_clock,"datetime",Clock), \
                 patch.object(operational_clock,"market_window",
                              return_value=self.market), \
                 patch.object(operational_clock,"_read",return_value=self.lock), \
                 patch.object(operational_clock,"verify_prepared_lock"), \
                 patch.object(operational_clock.time,"sleep"), \
                 patch.object(operational_clock,"main") as observed, \
                 patch.dict(operational_clock.os.environ,{"GITHUB_OUTPUT":str(output)}):
                result=run_open_watch(path,root/"public.json")
            self.assertEqual(result,2)
            observed.assert_not_called()
            self.assertFalse(output.exists())

    def test_production_flow_requires_real_observed_flag_for_second_commit(self):
        workflow=(ROOT/".github/workflows/operational-clock.yml").read_text()
        self.assertIn("--stage observe --watch-open",workflow)
        self.assertIn("id: open_watch",workflow)
        self.assertIn("steps.open_watch.outputs.observed == 'true'",workflow)
        self.assertIn("Verify native fills survived publication",workflow)


if __name__ == "__main__":
    unittest.main()
