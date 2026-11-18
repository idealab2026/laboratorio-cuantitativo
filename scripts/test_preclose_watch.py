"""Offline regressions for the bounded EXISTING shared-clock preclose watch."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import preclose_watch

UTC = timezone.utc


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
        self.assertEqual(preclose_watch.preclose_target(
            self.start, self.market, self.lock), self.target)
        self.assertEqual(preclose_watch.preclose_target(
            self.market["close"] - timedelta(minutes=7), self.market, self.lock),
            self.target)

    def test_never_watch_if_cron_arrived_after_rendezvous_or_in_old_session(self):
        for time in (self.market["close"] - timedelta(minutes=36),
                     self.market["close"] - timedelta(minutes=5),
                     self.market["close"] + timedelta(minutes=31)):
            self.assertIsNone(preclose_watch.preclose_target(
                time, self.market, self.lock))
        old = {**self.lock, "session": "2026-11-19"}
        self.assertIsNone(preclose_watch.preclose_target(
            self.start, self.market, old))
        self.assertIsNone(preclose_watch.preclose_target(
            self.start.replace(tzinfo=None), self.market, self.lock))

    def test_no_watch_without_a_frozen_position_or_when_not_friday(self):
        empty = {"session": self.market["session"],
                 "slots": {"IL-023": {"exit_only_ready": True,
                                      "monitor_tickers": []}}}
        self.assertIsNone(preclose_watch.preclose_target(
            self.start, self.market, empty))
        barred = {"session": self.market["session"],
                  "slots": {"IL-023": {"exit_only_ready": False,
                                       "execution_ready": False,
                                       "monitor_tickers": ["AAPL"]}}}
        self.assertIsNone(preclose_watch.preclose_target(
            self.start, self.market, barred))
        midweek = {**self.market, "session": "2026-11-18"}
        self.assertIsNone(preclose_watch.preclose_target(
            self.start, midweek, {**self.lock, "session": "2026-11-18"}))
        # A verified daily TimesFM holding warrants a close observation
        # on a weekday even without a Friday liquidation.
        active = {"session": "2026-11-18", "slots": {
            "IL-042": {"execution_ready": True, "monitor_tickers": ["AXON"]}}}
        self.assertEqual(preclose_watch.preclose_target(
            self.start, midweek, active), self.target)

    def test_half_session_uses_real_1300_et_close(self):
        early = {**self.market, "session": "2026-11-27",
                 "previous": "2026-11-25",
                 "close": datetime(2026, 11, 27, 18, tzinfo=UTC)}
        lock = {**self.lock, "session": "2026-11-27"}
        self.assertEqual(preclose_watch.preclose_target(
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
            with patch.object(preclose_watch, "datetime", ControlledTime), \
                 patch.object(preclose_watch, "ROOT", work), \
                 patch.object(preclose_watch, "_read", return_value=self.lock), \
                 patch.object(preclose_watch, "market_window",
                              return_value=self.market), \
                 patch.object(preclose_watch, "verify_prepared_lock"), \
                 patch.object(preclose_watch.time, "sleep") as sleep, \
                 patch.object(preclose_watch, "run_operator", return_value=0) as run, \
                 patch.dict(preclose_watch.os.environ,
                            {"GITHUB_OUTPUT": str(output)}, clear=False):
                result = preclose_watch.main()
                written = output.read_text(encoding="utf8") if output.exists() else ""
            return result, written, sleep.call_args_list, run.call_args_list

    def test_watcher_calls_original_operator_once_with_new_observation(self):
        code, output, slept, called = self._run_mocked(
            self.target + timedelta(seconds=2))
        self.assertEqual(code, 0)
        self.assertEqual(output, "observed=true\\n")
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


if __name__ == "__main__":
    unittest.main()
