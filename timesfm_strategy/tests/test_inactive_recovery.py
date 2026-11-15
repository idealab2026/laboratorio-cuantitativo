"""Deterministic regressions for EUR inactive-only recovery; no vendor required."""
import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from timesfm_strategy import daily_run
from timesfm_strategy import run as weekly
from timesfm_strategy.inactive_recovery import reconcile

UTC = timezone.utc
NOW = datetime(2026, 11, 15, 22, 0, tzinfo=UTC)
IDENTITY = {"snapshot_sha256": "a" * 64, "effective_sha256": "b" * 64}


class MarkOnlyGapTest(unittest.TestCase):
    def setUp(self):
        self.weekly_config = json.loads(
            (ROOT / "timesfm_strategy/config.json").read_text())
        self.daily_config = json.loads(
            (ROOT / "timesfm_strategy/config-daily.json").read_text())
        self.day = "2026-11-11"
        self.week = weekly.initialize(
            self.weekly_config, self.day, [], {"frozen": "historical"})
        self.daily = daily_run.initialize(
            self.daily_config, self.day, [], {"frozen": "historical"})
        for state, name in ((self.week, "timesfm"), (self.daily, "timesfm_daily")):
            book = state["books"][name]
            book["pending"] = []
            book["positions"]["MSI"] = {
                "shares": 2.0, "entry_date": "2026-11-11",
                "signal_date": "2026-11-10",
                "entry_price_eur": 400., "cost_eur": 800.,
                "dividends_eur": 0.,
            }
            book["cash"] -= 800.
            state["forward_executions"] = {"IL-042:2026-11-11:open": {"sha": "frozen"}}
        self.days = ["2026-11-12", "2026-11-13"]
        self.bars = {
            "2026-11-12": ({
                "MSI": {"close": 530., "split": 0, "dividend": 0},
                "SPY": {"close": 750., "split": 0, "dividend": 0},
            }, IDENTITY),
            "2026-11-13": ({
                "MSI": {"close": 535., "split": 0, "dividend": 0},
                "SPY": {"close": 745., "split": 0, "dividend": 0},
            }, IDENTITY),
        }
        self.fx = {"2026-11-12": 1.1, "2026-11-13": 1.2}

    def mark(self, family, state=None, days=None, bars=None, fx=None):
        return reconcile(
            state or (self.week if family == "weekly" else self.daily),
            self.weekly_config if family == "weekly" else self.daily_config,
            family, self.days if days is None else days,
            self.bars if bars is None else bars,
            self.fx if fx is None else fx,
            now=NOW, first_future="2026-11-16",
        )

    def test_daily_recovery_preserves_forward_buy_and_does_not_invent_exit(self):
        before = copy.deepcopy(self.daily)
        result = self.mark("one_day")
        self.assertEqual(result["last_session"], "2026-11-13")
        self.assertEqual(result["last_signal_session"], "2026-11-11")
        self.assertEqual(result["missing_signals"], self.days)
        self.assertEqual(result["forward_executions"], before["forward_executions"])
        self.assertEqual(result["books"]["timesfm_daily"]["positions"],
                         before["books"]["timesfm_daily"]["positions"])
        self.assertEqual(result["books"]["timesfm_daily"]["trades"], [])
        self.assertEqual(result["books"]["timesfm_daily"]["cash"],
                         before["books"]["timesfm_daily"]["cash"])
        self.assertEqual(len(result["books"]["timesfm_daily"]["equity"]),
                         len(before["books"]["timesfm_daily"]["equity"]) + 2)
        self.assertTrue(result["books"]["timesfm_daily"]["equity"][-1]["inactive_no_new_fills"])
        self.assertAlmostEqual(result["books"]["timesfm_daily"]["nav"],
                               100000 - 800 + 2 * 535 / 1.2)
        self.assertEqual(result["outage_control"]["historical_fills_created"], 0)
        self.assertEqual(result["outage_control"]["first_future_trading_session"],
                         "2026-11-16")
        self.assertEqual(self.daily, before)
        daily_run.check(result, self.daily_config)

    def test_weekly_recovery_marks_without_creating_friday_exit_or_signal(self):
        before = copy.deepcopy(self.week)
        result = self.mark("weekly")
        self.assertEqual(result["last_session"], "2026-11-13")
        self.assertEqual(result["last_signal_session"], "2026-11-11")
        self.assertIn("2026-11-13", result["missed_weekly_signal_sessions"])
        self.assertEqual(result["books"]["timesfm"]["trades"],
                         before["books"]["timesfm"]["trades"])
        self.assertIn("MSI", result["books"]["timesfm"]["positions"])
        self.assertEqual(result["forward_executions"], before["forward_executions"])
        weekly._check(result, self.weekly_config)

    def test_missing_held_quote_blocks_entire_recovery(self):
        bars = copy.deepcopy(self.bars)
        bars["2026-11-13"][0].pop("MSI")
        with self.assertRaisesRegex(ValueError, "No verified historical held mark"):
            self.mark("one_day", bars=bars)

    def test_corporate_action_requires_entitlement_review(self):
        bars = copy.deepcopy(self.bars)
        bars["2026-11-12"][0]["MSI"]["split"] = 2
        with self.assertRaisesRegex(ValueError, "Corporate action demands"):
            self.mark("weekly", bars=bars)

    def test_fx_not_available_cannot_fabricate_eur_mark(self):
        with self.assertRaisesRegex(ValueError, "Missing canonical daily OHLC"):
            self.mark("one_day", fx={"2026-11-12": 1.1})
        with self.assertRaisesRegex(ValueError, "Invalid historical FX"):
            self.mark("one_day", fx={"2026-11-12": 0, "2026-11-13": 1.2})

    def test_future_dated_holdings_are_rejected(self):
        altered = copy.deepcopy(self.daily)
        altered["books"]["timesfm_daily"]["positions"]["MSI"]["entry_date"] = "2026-11-13"
        with self.assertRaisesRegex(ValueError, "Future-dated held"):
            self.mark("one_day", state=altered)

    def test_no_gap_is_copy_only(self):
        result = self.mark("one_day", days=[])
        self.assertEqual(result, self.daily)
        self.assertIsNot(result, self.daily)

    def test_no_rewrite_of_prior_equity(self):
        result = self.mark("one_day")
        self.assertEqual(result["equity"][:len(self.daily["equity"])],
                         self.daily["equity"])
        self.assertFalse(any(e.get("type") in ("buy", "sell")
                             for e in result["books"]["timesfm_daily"]["events"]))


if __name__ == "__main__":
    unittest.main()
