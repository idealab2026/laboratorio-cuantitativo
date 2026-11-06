"""Recovery must preserve economic history and never trade a missed opening."""
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from strategy_comparison.inactive_recovery import (window, reconcile_classic,
                                                   reconcile_weekly, weekly_mark)
NOW = datetime(2026, 11, 4, 16, 0, tzinfo=timezone.utc)
IDENTITY = {"snapshot_sha256": "a" * 64, "effective_sha256": "b" * 64}


def bar(day, close=105.):
    return {"date": day, "open": 100., "high": 110., "low": 90.,
            "close": close, "volume": 1000., "dividend": 0., "split": 0.}


def book():
    return {"cash": 50., "nav": 150., "positions": {"AAA": {
        "shares": 1., "cost": 100., "dividends": 0., "stop": 95., "target": 115.}},
        "pending": {"BBB": {"side": "buy", "signal_date": "2026-11-02"}},
        "equity": [{"date": "2026-11-02", "nav": 150.}],
        "trades": [{"preserved": "prior trade"}], "events": [],
        "paused_missing_quotes": {"since": "2026-11-03", "missing_tickers": ["AAA"]}}


class InactiveRecoveryTests(unittest.TestCase):
    def loader(self, day, required):
        return {"AAA": bar(day)}, IDENTITY

    def test_partial_current_day_is_not_traded_and_weekend_calendar_is_real(self):
        latest, first, days = window("2026-11-02", NOW)
        self.assertEqual((latest, first, days), ("2026-11-03", "2026-11-05", ["2026-11-03"]))
        _, first, days = window("2026-10-30", datetime(2026, 11, 2, 10, tzinfo=timezone.utc))
        self.assertEqual((first, days), ("2026-11-02", []))
        with self.assertRaisesRegex(ValueError, "bounded"):
            window("2026-10-20", NOW)

    def test_classic_marks_cancel_missed_orders_preserve_cash_positions_trades_and_unaffected_book(self):
        state = {"last_session": "2026-11-03", "books": {"affected": book(), "healthy": {"untouched": True}}}
        before = copy.deepcopy(state)
        result, names = reconcile_classic(state, self.loader, now=NOW)
        self.assertEqual(names, ["affected"])
        got, old = result["books"]["affected"], before["books"]["affected"]
        for key in ("cash", "positions", "trades"):
            self.assertEqual(got[key], old[key])
        self.assertEqual(got["equity"][:1], old["equity"])
        self.assertEqual(got["nav"], 155.)
        self.assertEqual(got["pending"], {})
        self.assertTrue(any(e["type"] == "unexecuted_during_outage" for e in got["events"]))
        self.assertEqual(got["events"][-1]["expired_unfilled_orders"], old["pending"])
        self.assertEqual(got["outage_control"]["first_trading_session"], "2026-11-05")
        self.assertEqual(result["books"]["healthy"], before["books"]["healthy"])
        self.assertEqual(state, before)
        twice, names = reconcile_classic(result, self.loader, now=NOW)
        self.assertEqual((twice, names), (result, []))

    def test_classic_missing_quote_bad_identity_or_unreviewed_action_aborts_atomically(self):
        state = {"last_session": "2026-11-03", "books": {"affected": book()}}
        before = copy.deepcopy(state)
        for loader in (lambda *_: ({}, IDENTITY), lambda d, _: ({"AAA": bar(d)}, {}),
                       lambda d, _: ({"AAA": {**bar(d), "split": 2}}, IDENTITY)):
            with self.assertRaises((ValueError, KeyError)):
                reconcile_classic(state, loader, now=NOW)
            self.assertEqual(state, before)

    def test_receivable_is_valued_without_becoming_spendable_cash(self):
        held = book()
        held["receivables"] = {"merger": {"status": "unsettled", "symbol": "KMB",
                                               "fixed_cash": "3.5", "fractional_shares": ".25"}}
        state = {"last_session": "2026-11-03", "books": {"affected": held}}
        def loader(day, required):
            self.assertIn("KMB", required)
            return {"AAA": bar(day), "KMB": bar(day, 104.)}, IDENTITY
        result, _ = reconcile_classic(state, loader, now=NOW)
        got = result["books"]["affected"]
        self.assertEqual(got["cash"], 50.)
        self.assertEqual(got["nav"], 184.5)
        self.assertTrue(got["equity"][-1]["provisional_corporate_valuation"])

    def weekly(self):
        b = book()
        b.pop("paused_missing_quotes")
        b["pending"] = [{"ticker": "BBB", "signal_date": "2026-11-02"}]
        return {"last_session": "2026-11-02", "strategies": {"model": b}, "gap_sessions": []}

    def test_weekly_retains_existing_economics_and_all_historical_points(self):
        state = self.weekly()
        before = copy.deepcopy(state)
        result, names = reconcile_weekly(state, self.loader, now=NOW)
        self.assertEqual(names, ["model"])
        old, got = state["strategies"]["model"], result["strategies"]["model"]
        for key in ("cash", "positions", "trades"):
            self.assertEqual(old[key], got[key])
        self.assertEqual(got["equity"][:1], old["equity"])
        self.assertEqual(got["nav"], 155.)
        self.assertEqual(got["pending"], [])
        self.assertEqual(result["last_session"], "2026-11-03")
        self.assertEqual(result["gap_sessions"], ["2026-11-03"])
        self.assertEqual(result["outage_control"]["first_trading_session"], "2026-11-05")
        self.assertEqual(state, before)
        twice, names = reconcile_weekly(result, self.loader, now=NOW)
        self.assertEqual((twice, names), (result, []))

    def test_weekly_missing_date_or_corporate_action_never_silently_advances(self):
        for bars in ({}, {"AAA": {**bar("2026-11-02")}},
                     {"AAA": {**bar("2026-11-03"), "dividend": .5}}):
            state = self.weekly()
            before = copy.deepcopy(state)
            with self.assertRaises(ValueError):
                reconcile_weekly(state, lambda *_: (bars, IDENTITY), now=NOW)
            self.assertEqual(state, before)

    def test_weekly_partial_current_day_guard_prevents_week_close_sales(self):
        sys.path.insert(0, str(ROOT / "weekly_ml"))
        from weekly_ml.daily import process_day, ENGINE_VERSION
        from weekly_ml.paper import digest, strategy_ids
        import json
        config = json.loads((ROOT / "weekly_ml/config.json").read_text())
        b = self.weekly()["strategies"]["model"]
        b["pending"] = []
        b["equity"] = [{"date": "2026-11-03", "nav": 150.}]
        state = {"schema_version": 1, "engine": ENGINE_VERSION, "config_hash": digest(config),
                 "last_session": "2026-11-03", "last_signal_session": "2026-10-30",
                 "strategies": {n: copy.deepcopy(b) for n in strategy_ids(config)},
                 "outage_control": {"first_trading_session": "2026-11-05"}}
        result, changed = process_day(config, state, "2026-11-04", {"AAA": bar("2026-11-04")},
            previous_session="2026-11-03", week_end=True,
            quote_identity=IDENTITY)
        self.assertTrue(changed)
        for n, got in result["strategies"].items():
            self.assertEqual(got["positions"], state["strategies"][n]["positions"])
            self.assertEqual(got["trades"], state["strategies"][n]["trades"])
            self.assertTrue(got["equity"][-1]["inactive_no_fills"])
