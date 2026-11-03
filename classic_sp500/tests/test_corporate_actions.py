import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "classic_sp500"))
from classic_sp500 import corporate_actions as ca
from classic_sp500 import run as engine


class MergerTests(unittest.TestCase):
    def setUp(self):
        self.book = {"cash": 500., "nav": 2500., "pending": {"OTHER": {"side": "buy"}},
            "positions": {"KVUE": {"shares": 100., "cost": 1800., "entry_price": 18.,
                "entry_date": "2026-10-15", "dividends": 0., "stop": 16., "target": 23.}},
            "events": [], "trades": [{"original": True}],
            "equity": [{"date": "2026-10-30", "nav": 2500.}],
            "paused_missing_quotes": {"missing_tickers": ["KVUE"], "since": "2026-11-02",
                                      "last_valued_session": "2026-10-30"}}
        self.bars = {"KMB": {"open": 100., "high": 110., "low": 80., "close": 105.,
                              "dividend": 0., "split": 0.}}
        self.identity = {"snapshot_sha256": "a" * 64, "effective_sha256": "b" * 64}
        self.state = {"last_session": "2026-11-02", "books": {"genetic_frozen": self.book,
                        "unaffected": {"cash": 100., "equity": [{"date": "2026-11-02", "nav": 100.}],
                                       "positions": {}, "trades": []}}}

    def recover(self, state=None, bars=None):
        return ca.recover_books(state or self.state,
            lambda day: (bars or self.bars, self.identity),
            recorded_at="2026-11-03T16:00:00+00:00", first_trading="2026-11-04")

    def test_real_entitlement_is_separate_from_cash_and_old_history(self):
        original = copy.deepcopy(self.state)
        got, names = self.recover()
        book = got["books"]["genetic_frozen"]
        self.assertEqual(names, ["genetic_frozen"])
        self.assertEqual(book["positions"]["KMB"]["shares"], 14.)
        claim = book["receivables"][ca.ACTION]
        self.assertEqual(claim["fixed_cash"], "350.00")
        self.assertEqual(claim["fractional_shares"], "0.625000")
        self.assertEqual(book["cash"], 500.)
        self.assertAlmostEqual(book["nav"], 500 + 14 * 105 + 350 + .625 * 105)
        self.assertEqual(book["trades"], original["books"]["genetic_frozen"]["trades"])
        self.assertEqual(book["equity"][:-1], self.book["equity"])
        self.assertEqual(got["books"]["unaffected"], original["books"]["unaffected"])
        self.assertEqual(self.state, original)
        self.assertNotIn("paused_missing_quotes", book)
        self.assertTrue(book["equity"][-1]["provisional_corporate_valuation"])
        self.assertTrue(any(e["type"] == "unexecuted_during_outage" for e in book["events"]))
        self.assertAlmostEqual(book["positions"]["KMB"]["cost"] + claim["allocated_cost"], 1800.)
        twice, names = self.recover(got)
        self.assertEqual(names, [])
        self.assertEqual(twice, got)

    def test_existing_successor_is_aggregated_without_losing_cost_or_shares(self):
        book = self.state["books"]["genetic_frozen"]
        book["positions"]["KVUE"].update(stop=None, target=None)
        book["positions"]["KMB"] = {"shares": 1.5, "cost": 150., "entry_price": 100.,
            "entry_date": "2026-10-01", "dividends": 2., "stop": None, "target": None}
        got, _ = self.recover()
        new = got["books"]["genetic_frozen"]
        self.assertEqual(new["positions"]["KMB"]["shares"], 15.5)
        self.assertAlmostEqual(new["positions"]["KMB"]["cost"] + new["receivables"][ca.ACTION]["allocated_cost"], 1950.)
        self.assertEqual(new["positions"]["KMB"]["dividends"], 2.)

    def test_failed_input_rolls_back_all_books(self):
        for change in ("missing", "split", "bad_ohlc", "unreviewed_dividend"):
            bars = copy.deepcopy(self.bars)
            if change == "missing": bars = {"OTHER": self.bars["KMB"]}
            if change == "split": bars["KMB"]["split"] = 2.
            if change == "bad_ohlc": bars["KMB"]["low"] = 120.
            if change == "unreviewed_dividend": bars["KMB"]["dividend"] = 1.
            before = copy.deepcopy(self.state)
            with self.assertRaises((ValueError, KeyError)):
                self.recover(bars=bars)
            self.assertEqual(self.state, before)

    def test_claim_survives_sale_of_all_successor_shares_and_keeps_its_quote_requirement(self):
        got, _ = self.recover()
        book = got["books"]["genetic_frozen"]
        del book["positions"]["KMB"]
        self.assertEqual(ca.required_claim_quotes(book), {"KMB"})
        self.assertAlmostEqual(ca.portfolio_nav(book, self.bars), 500 + 350 + .625 * 105)
        with self.assertRaises(KeyError): ca.portfolio_nav(book, {})

    def test_reviewed_payment_is_credited_once_without_rewriting_provisional_history(self):
        got, _ = self.recover()
        book = got["books"]["genetic_frozen"]
        old_marks = copy.deepcopy(book["equity"])
        review = {"merger_settlements": [{"action_id": ca.ACTION, "currency": "USD",
            "payment_session": "2026-11-04", "verified_on": "2026-11-04", "payment_verified": True,
            "fractional_cash_price": 102., "source_url": ca.ISSUER}]}
        ca.settle_reviewed_claims(book, "2026-11-03", review, recorded_at="now")
        self.assertEqual(book["cash"], 500.)
        ca.settle_reviewed_claims(book, "2026-11-04", review, recorded_at="now")
        self.assertEqual(book["cash"], 913.75)
        self.assertFalse(ca.required_claim_quotes(book))
        self.assertEqual(book["equity"], old_marks)
        self.assertFalse(ca.valuation_metadata(book))
        again = copy.deepcopy(book)
        ca.settle_reviewed_claims(book, "2026-11-05", review, recorded_at="later")
        self.assertEqual(book, again)

    def test_unverified_payment_is_not_spendable(self):
        got, _ = self.recover()
        book = got["books"]["genetic_frozen"]
        old = copy.deepcopy(book)
        with self.assertRaisesRegex(ValueError, "issuer evidence"):
            ca.settle_reviewed_claims(book, "2026-11-04", {"merger_settlements": [{
                "action_id": ca.ACTION, "payment_session": "2026-11-04"}]}, recorded_at="now")
        self.assertEqual(book, old)

    def test_partial_day_after_recovery_has_no_stops_or_trades_and_next_open_resumes(self):
        got, _ = self.recover()
        book = got["books"]["genetic_frozen"]
        config = json.loads((ROOT / "classic_sp500/config.json").read_text())
        trades = copy.deepcopy(book["trades"])
        engine._settle_book(config, "genetic_frozen", book, "2026-11-03", self.bars)
        self.assertEqual(book["trades"], trades)
        self.assertIn("KMB", book["positions"])
        self.assertTrue(book["equity"][-1]["inactive_no_fills"])
        engine._settle_book(config, "genetic_frozen", book, "2026-11-04", self.bars)
        self.assertNotIn("KMB", book["positions"])
        self.assertEqual(len(book["trades"]), len(trades) + 1)
        self.assertEqual(book["trades"][-1]["exit_date"], "2026-11-04")
        self.assertTrue(book["equity"][-1]["provisional_corporate_valuation"])
        self.assertEqual(book["receivables"][ca.ACTION]["status"], "unsettled")

    def test_receivable_does_not_fund_purchase(self):
        got, _ = self.recover()
        book = got["books"]["genetic_frozen"]
        book["cash"] = 0.
        book["pending"] = {"NEW": {"side": "buy", "signal_date": "2026-11-03"}}
        bars = {**copy.deepcopy(self.bars), "NEW": copy.deepcopy(self.bars["KMB"])}
        bars["KMB"].update(low=100., high=105.)
        config = json.loads((ROOT / "classic_sp500/config.json").read_text())
        engine._settle_book(config, "genetic_frozen", book, "2026-11-04", bars)
        self.assertNotIn("NEW", book["positions"])
        self.assertEqual(book["cash"], 0.)

    def test_future_open_uses_actual_clock(self):
        self.assertEqual(ca.recovery_window("2026-11-02", datetime(2026,11,3,14,29,tzinfo=timezone.utc)), "2026-11-03")
        self.assertEqual(ca.recovery_window("2026-11-02", datetime(2026,11,3,14,30,tzinfo=timezone.utc)), "2026-11-04")

if __name__ == "__main__": unittest.main()
