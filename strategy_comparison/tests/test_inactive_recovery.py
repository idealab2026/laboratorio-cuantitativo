"""Recovery must preserve economic history and never trade a missed opening."""
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from strategy_comparison.inactive_recovery import (window, reconcile_classic,
                                                   reconcile_weekly, reconcile_weekly_paused, weekly_mark)
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

    def test_selective_macd_passive_mark_only_keeps_unrelated_claim_frozen(self):
        stale = book()
        stale["paused_missing_quotes"]["missing_tickers"] = ["AAA"]
        unrelated = copy.deepcopy(stale)
        unrelated["receivables"] = {"KVUE_KMB_2026-11-02": {
            "status": "unsettled", "symbol": "AAA", "fixed_cash": "10",
            "fractional_shares": ".1"}}
        state = {"last_session": "2026-11-03",
                 "books": {"macd_12_26_9": stale, "genetic_frozen": unrelated}}
        previous = copy.deepcopy(state)
        def validated_close(day, symbols):
            self.assertEqual(symbols, {"AAA"})
            return {"AAA": {"date": day, "close": 105.,
                            "price_scope": "passive_close_only", "split": 0,
                            "dividend": 0}}, {**IDENTITY,
                "closing_mark_scope": "passive_nav_only",
                "passive_close_provenance": {"AAA": {
                    "document_sha256": "c" * 64, "session": day,
                    "close": 105., "captured_at_utc": "2026-11-03T23:43:00+00:00"}}}
        recover, names = reconcile_classic(
            state, validated_close,
            now=datetime(2026, 11, 4, 16, tzinfo=timezone.utc),
            only_book="macd_12_26_9")
        self.assertEqual(names, ["macd_12_26_9"])
        new = recover["books"]["macd_12_26_9"]
        for field in ("cash", "trades", "positions"):
            self.assertEqual(new[field], previous["books"]["macd_12_26_9"][field])
        self.assertEqual(new["nav"], 155.)
        self.assertEqual(len(new["equity"]), 2)
        self.assertEqual(new["events"][-1]["type"], "inactive_mark_no_trades")
        self.assertTrue(any(e["type"] == "intraday_trigger_unknown_during_outage"
                            for e in new["events"]))
        self.assertFalse(any(e["type"] == "unexecuted_during_outage"
                             for e in new["events"]))
        self.assertEqual(recover["books"]["genetic_frozen"],
                         previous["books"]["genetic_frozen"])
        self.assertEqual(state, previous)
        with self.assertRaisesRegex(ValueError, "Unknown"):
            reconcile_classic(state, validated_close, now=NOW, only_book="wrong")
        missing = lambda d, s: ({"AAA": {"date": d, "close": 105.,
                             "price_scope": "passive_close_only", "split": 0, "dividend": 0}},
                             IDENTITY)
        with self.assertRaisesRegex(ValueError, "passive closing"):
            reconcile_classic(state, missing, now=NOW, only_book="macd_12_26_9")

    def test_reviewed_genetic_nine_session_outage_marks_only_no_cash_credit(self):
        now = datetime(2026, 11, 18, 15, 45, tzinfo=timezone.utc)
        days = ["2026-11-05", "2026-11-06", "2026-11-09", "2026-11-10",
                "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16",
                "2026-11-17"]
        self.assertEqual(window("2026-11-04", now, max_sessions=9,
                                reviewed_genetic_nine=True)[2], days)
        with self.assertRaisesRegex(ValueError, "bounded"):
            window("2026-11-04", now)
        with self.assertRaisesRegex(ValueError, "four to eight"):
            window("2026-11-04", now, max_sessions=10)
        with self.assertRaisesRegex(ValueError, "four to eight"):
            window("2026-11-04", now, max_sessions=9)

        genetic = book()
        genetic.update(equity=[{"date": "2026-11-04", "nav": 150.}],
                       paused_missing_quotes={
                           "since": "2026-11-05", "last_valued_session": "2026-11-04",
                           "missing_tickers": ["KMB"]},
                       receivables={"KVUE_KMB_2026-11-02": {
                           "status": "unsettled", "symbol": "KMB",
                           "fractional_shares": "0.25", "fixed_cash": "3.50"}})
        state = {"last_session": "2026-11-17", "books": {
            "genetic_frozen": genetic,
            "unrelated": {"trades": [{"preserve": True}]}}}
        before = copy.deepcopy(state)
        def observed(day, required):
            self.assertEqual(required, {"AAA", "KMB"})
            return {"AAA": bar(day, 105.), "KMB": bar(day, 109.)}, IDENTITY

        with self.assertRaisesRegex(ValueError, "bounded"):
            reconcile_classic(state, observed, now=now, only_book="genetic_frozen")
        with self.assertRaisesRegex(ValueError, "genetic_frozen alone"):
            reconcile_classic(state, observed, now=now, reviewed_genetic_nine=True)
        got, names = reconcile_classic(
            state, observed, now=now, only_book="genetic_frozen",
            reviewed_genetic_nine=True)
        self.assertEqual(names, ["genetic_frozen"])
        updated = got["books"]["genetic_frozen"]
        self.assertEqual(len(updated["equity"]), 10)
        self.assertEqual([p["date"] for p in updated["equity"][1:]], days)
        self.assertTrue(all(p["inactive_no_fills"] for p in updated["equity"][1:]))
        self.assertTrue(all(p["provisional_corporate_valuation"]
                            for p in updated["equity"][1:]))
        self.assertEqual(updated["outage_control"]["first_trading_session"], "2026-11-19")
        self.assertNotIn("paused_missing_quotes", updated)
        for field in ("cash", "positions", "trades", "receivables"):
            self.assertEqual(updated[field], before["books"]["genetic_frozen"][field])
        self.assertEqual(got["books"]["unrelated"], before["books"]["unrelated"])
        self.assertEqual(state, before)
        self.assertFalse(any(evt.get("type") in ("buy", "sell", "fill")
                             for evt in updated["events"]))
        again, names = reconcile_classic(
            got, observed, now=now, only_book="genetic_frozen",
            reviewed_genetic_nine=True)
        self.assertEqual((again, names), (got, []))

        def no_kmb(day, required):
            return {"AAA": bar(day)}, IDENTITY
        with self.assertRaisesRegex(ValueError, "Missing exact held"):
            reconcile_classic(state, no_kmb, now=now,
                              only_book="genetic_frozen", reviewed_genetic_nine=True)
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

    def test_weekly_stale_three_books_only_mark_and_remain_paused(self):
        then = datetime(2026, 11, 9, 16, tzinfo=timezone.utc)
        names = ["arima_return", "lgbm_ranker", "mlp_return"]
        stale = book()
        stale["equity"][-1]["date"] = "2026-11-05"
        stale["paused_missing_quotes"] = {
            "date": "2026-11-06", "reason": "unreconciled_session",
            "missing_tickers": []}
        state = {"last_session": "2026-11-06",
                 "strategies": {**{n: copy.deepcopy(stale) for n in names},
                                "healthy": {"untouched": True}}}
        before = copy.deepcopy(state)
        revised, selected = reconcile_weekly_paused(state, self.loader, now=then)
        self.assertEqual(selected, names)
        self.assertEqual(revised["strategies"]["healthy"], before["strategies"]["healthy"])
        for n in names:
            old, updated = before["strategies"][n], revised["strategies"][n]
            self.assertEqual(updated["cash"], old["cash"])
            self.assertEqual(updated["positions"], old["positions"])
            self.assertEqual(updated["trades"], old["trades"])
            self.assertEqual(updated["equity"][:len(old["equity"])], old["equity"])
            self.assertEqual(updated["equity"][-1]["date"], "2026-11-06")
            self.assertTrue(updated["equity"][-1]["inactive_no_fills"])
            self.assertEqual(updated["paused_missing_quotes"]["reason"],
                             "unobserved_weekly_exit")
            self.assertEqual(updated["paused_missing_quotes"]["missed_exit_sessions"],
                             ["2026-11-06"])
            self.assertTrue(updated["outage_control"]["held_exits_require_future_observed_quote"])
        self.assertEqual(state, before)
        again, selected = reconcile_weekly_paused(revised, self.loader, now=then)
        self.assertEqual((again, selected), (revised, []))

    def test_weekly_close_only_requires_symbol_receipt_not_ohlc_imagination(self):
        b = book()
        stamp = "2026-11-06T20:00:00+00:00"
        row = {"date": "2026-11-06", "close": 105.,
               "price_scope": "passive_close_only", "dividend": 0, "split": 0}
        proof = {**IDENTITY, "closing_mark_scope": "passive_nav_only",
                 "passive_close_provenance": {"AAA": {
                     "document_sha256": "f"*64, "session": "2026-11-06",
                     "captured_at_utc": "2026-11-06T19:00:00+00:00",
                     "close": 105.}}}
        weekly_mark(b, "2026-11-06", {"AAA": row}, stamp=stamp, identity=proof)
        self.assertEqual(b["nav"], 155.)
        self.assertEqual(b["pending"], [])
        self.assertEqual(b["trades"], [{"preserved": "prior trade"}])
        wrong = copy.deepcopy(proof)
        wrong["passive_close_provenance"]["AAA"]["close"] = 106.
        with self.assertRaisesRegex(ValueError, "passive close receipt"):
            weekly_mark(book(), "2026-11-06", {"AAA": row},
                        stamp=stamp, identity=wrong)

    def test_eight_reviewed_weekly_sessions_are_bounded(self):
        then = datetime(2026, 11, 17, 17, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "bounded"):
            window("2026-11-04", then)
        self.assertEqual(len(window("2026-11-04", then, max_sessions=8)[2]), 8)
        with self.assertRaisesRegex(ValueError, "integer from four to eight"):
            window("2026-11-04", then, max_sessions=9)

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
