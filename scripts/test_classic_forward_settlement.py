"""Classic forward evidence: 9 native books, open arithmetic, stops, no replay."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from operational_clock import clock_plan
from classic_forward_settlement import LEDGER, CONFIG, SLOTS, settle_classic, summarize_session_fills
from classic_sp500 import run as classic

UTC = timezone.utc


class NativeClassicClockTests(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.now = self.open + timedelta(minutes=2)
        self.market = {
            "session": "2026-11-10", "previous": "2026-11-09",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)}
        self.config = json.loads((ROOT / CONFIG).read_text())
        self.book = json.loads((ROOT / LEDGER).read_text())
        self.book["last_session"] = "2026-11-09"
        self.tracks = {}
        for slot, name in SLOTS.items():
            original = self.book["books"][name]
            original.update(cash=100000.0, nav=100000.0, positions={},
                            pending={"AAPL": {"side": "buy", "signal_date": "2026-11-09"}},
                            equity=[{"date": "2026-11-09", "nav": 100000.0}],
                            trades=[], events=[])
            for field in ("paused_missing_quotes", "receivables", "outage_control",
                          "forward_executions"):
                original.pop(field, None)
            self.tracks[slot] = {
                "status": "recorded", "session": "2026-11-09", "holdings": [],
                "orders": [{"ticker": "AAPL", "action": "buy",
                            "decision_session": "2026-11-09",
                            "target_session": "2026-11-10"}]
            }
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(self.open-timedelta(minutes=10),
                               self.market, self.tracks, "c"*40)
        self.quotes = {
            "AAPL": {"price": 100.0,
                     "quote_at_utc": (self.open+timedelta(minutes=1)).isoformat(),
                     "observed_at_utc": self.now.isoformat()}
        }

    def reader(self, path):
        return copy.deepcopy(self.book if path == LEDGER else self.config)

    def frozen(self, sha, path):
        self.assertEqual((sha, path), ("c"*40, LEDGER))
        return copy.deepcopy(self.original)

    def run_clock(self, quotes=None, now=None):
        return settle_classic(
            self.lock, now or self.now, self.market,
            self.quotes if quotes is None else quotes,
            reader=self.reader, frozen=self.frozen)

    def test_all_nine_native_buy_books_and_idempotence(self):
        updated, results = self.run_clock()
        self.assertEqual(set(updated), {LEDGER})
        self.assertEqual(set(results), set(SLOTS))
        fresh = updated[LEDGER]
        for slot, name in SLOTS.items():
            old = self.book["books"][name]
            new = fresh["books"][name]
            self.assertEqual(results[slot]["status"], "settled_native_paper")
            self.assertEqual(results[slot]["fills"], 1)
            self.assertEqual(new["pending"], {})
            self.assertEqual(new["equity"], old["equity"])
            self.assertEqual(new["nav"], old["nav"])
            self.assertGreater(new["positions"]["AAPL"]["shares"], 0)
            self.assertEqual(new["events"][-1]["execution"], "forward_observed_paper")
            self.assertEqual(results[slot]["operations"][0]["quantity"],
                             new["positions"]["AAPL"]["shares"])
            self.assertIn("forward_executions", new)
        self.book = copy.deepcopy(fresh)
        second, repeated = self.run_clock()
        self.assertEqual(second, {})
        self.assertTrue(all(r["status"] == "already_settled" for r in repeated.values()))

    def test_stale_or_missing_quotes_never_fill(self):
        output, results = self.run_clock(quotes={})
        self.assertEqual(output, {})
        self.assertTrue(all(r["status"] == "awaiting_fresh_open_quotes"
                            for r in results.values()))
        stale = copy.deepcopy(self.quotes)
        stale["AAPL"]["quote_at_utc"] = (self.open-timedelta(seconds=10)).isoformat()
        output, _ = self.run_clock(quotes=stale)
        self.assertEqual(output, {})
        output, _ = self.run_clock(now=self.open+timedelta(minutes=45))
        self.assertEqual(output, {})

    def test_native_sell_preserves_real_quantity_and_cash(self):
        # One tactical strategy sells exactly the shares it owns; peers buy.
        slot, name = "IL-011", SLOTS["IL-011"]
        b = self.book["books"][name]
        b["positions"] = {"AAPL": {"shares": 5.0, "entry_date": "2026-11-06",
                                   "entry_price": 90.0, "cost": 450.45,
                                   "dividends": 0.0, "stop": None, "target": None}}
        b["cash"] = 99549.55
        b["pending"]["AAPL"] = {"side": "sell", "signal_date": "2026-11-09"}
        self.tracks[slot]["orders"][0]["action"] = "sell"
        self.tracks[slot]["holdings"] = []
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(self.open-timedelta(minutes=10),
                               self.market, self.tracks, "c"*40)
        updated, results = self.run_clock()
        new = updated[LEDGER]["books"][name]
        self.assertFalse(new["positions"])
        self.assertEqual(new["pending"], {})
        self.assertEqual(results[slot]["operations"][0]["side"], "sell")
        self.assertEqual(results[slot]["operations"][0]["quantity"], 5.0)
        self.assertGreater(new["cash"], b["cash"])

    def test_observed_stop_sells_once_no_ohlc_hindsight(self):
        # A previously held position has no scheduled opening order.
        self.tracks["IL-011"]["orders"] = []
        self.tracks["IL-011"]["holdings"] = ["AAPL"]
        held = {"shares": 3.0, "entry_date": "2026-11-06",
                "entry_price": 100.0, "cost": 300.3, "dividends": 0.0,
                "stop": 95.0, "target": 115.0}
        old = self.book["books"][SLOTS["IL-011"]]
        old["pending"] = {}
        old["positions"] = {"AAPL": held}
        old["cash"] = 99699.7
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(self.open-timedelta(minutes=10),
                               self.market, self.tracks, "c"*40)
        quote = copy.deepcopy(self.quotes)
        quote["AAPL"]["price"] = 94.0
        output, evidence = self.run_clock(quotes=quote)
        trade = output[LEDGER]["books"]["ema_rsi_fixed"]
        self.assertFalse(trade["positions"])
        self.assertEqual(evidence["IL-011"]["status"], "settled_native_paper")
        self.assertEqual(trade["trades"][-1]["reason"], "stop_forward_observed")
        self.assertEqual(evidence["IL-011"]["operations"][0]["quantity"], 3.0)
        self.book = copy.deepcopy(output[LEDGER])
        output2, _ = self.run_clock(quotes=quote)
        self.assertEqual(output2, {})

    def test_two_independent_stops_count_across_polls_and_retries(self):
        # One portfolio holds two names. Their stops occur in different polls:
        # the public view must retain both even though each poll has one marker.
        slot, name = "IL-011", SLOTS["IL-011"]
        self.tracks[slot]["orders"] = []
        self.tracks[slot]["holdings"] = ["AAPL", "MSFT"]
        book = self.book["books"][name]
        book["pending"] = {}
        book["positions"] = {
            t: {"shares": q, "entry_date": "2026-11-06", "entry_price": 100.,
                "cost": q * 100.1, "dividends": 0., "stop": 95., "target": 115.}
            for t, q in (("AAPL", 3.), ("MSFT", 4.))}
        book["cash"] = 99299.3
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(
            self.open - timedelta(minutes=10), self.market, self.tracks, "c"*40)
        first_quotes = {
            t: {"price": value,
                "quote_at_utc": (self.now - timedelta(minutes=1)).isoformat(),
                "observed_at_utc": self.now.isoformat()}
            for t, value in (("AAPL", 94.), ("MSFT", 100.))}
        output1, evidence1 = self.run_clock(quotes=first_quotes)
        self.assertEqual(evidence1[slot]["fills"], 1)
        self.book = copy.deepcopy(output1[LEDGER])
        later = self.now + timedelta(minutes=14)
        second_quotes = {"MSFT": {"price": 94.,
            "quote_at_utc": (later - timedelta(minutes=1)).isoformat(),
            "observed_at_utc": later.isoformat()}}
        output2, evidence2 = self.run_clock(quotes=second_quotes, now=later)
        self.assertEqual(evidence2[slot]["fills"], 1)
        after = output2[LEDGER]["books"][name]
        frozen = self.original["books"][name]
        summary = summarize_session_fills(
            after, frozen, self.market["session"], self.lock["lock_sha256"],
            self.lock["source_commit"], self.config["execution"]["commission"])
        self.assertEqual(summary["fills_count"], 2)
        self.assertEqual([(v["ticker"], v["side"]) for v in summary["fills"]],
                         [("AAPL", "sell"), ("MSFT", "sell")])
        self.assertEqual(sum(x["fills_count"] for x in summary["native_markers"]), 2)
        self.assertEqual(summary["fills"][0]["quantity"], 3.)
        self.assertEqual(summary["fills"][1]["quantity"], 4.)
        self.assertEqual(summary, summarize_session_fills(
            after, frozen, self.market["session"], self.lock["lock_sha256"],
            self.lock["source_commit"], self.config["execution"]["commission"]))
        corrupted = copy.deepcopy(after)
        corrupted["events"].append(copy.deepcopy(corrupted["events"][-1]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize_session_fills(
                corrupted, frozen, self.market["session"], self.lock["lock_sha256"],
                self.lock["source_commit"], self.config["execution"]["commission"])
        corrupted = copy.deepcopy(after)
        stop_key = next(k for k, v in corrupted["forward_executions"].items()
                        if "MSFT" in k)
        corrupted["forward_executions"][stop_key]["fills_count"] = 2
        with self.assertRaisesRegex(ValueError, "disagree"):
            summarize_session_fills(
                corrupted, frozen, self.market["session"], self.lock["lock_sha256"],
                self.lock["source_commit"], self.config["execution"]["commission"])

    def test_il016_protective_stops_continue_when_unrelated_opening_buy_misses_quote(self):
        slot, name = "IL-016", SLOTS["IL-016"]
        self.tracks[slot]["holdings"] = ["COST", "ERIE", "MTD"]
        self.tracks[slot]["orders"] = [{
            "ticker": "VLTO", "action": "buy", "decision_session": "2026-11-09",
            "target_session": "2026-11-10",
        }]
        book = self.book["books"][name]
        book["pending"] = {"VLTO": {"side": "buy", "signal_date": "2026-11-09"}}
        book["positions"] = {
            ticker: {"shares": shares, "entry_date": "2026-11-06",
                     "entry_price": 100., "cost": shares * 100.1,
                     "dividends": 0., "stop": 95., "target": 115.}
            for ticker, shares in (("COST", 3.), ("ERIE", 4.), ("MTD", 2.))}
        book["cash"] = 100000 - 9 * 100.1
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(
            self.open - timedelta(minutes=10), self.market,
            self.tracks, "c" * 40)

        def fresh(ticker, price, now):
            return {ticker: {"price": price,
                "quote_at_utc": (now - timedelta(minutes=1)).isoformat(),
                "observed_at_utc": now.isoformat()}}

        # ERIE is unavailable; VLTO has a quote but its BUY cannot fill.
        # COST was held before the opening and its independent stop is real
        # observed paper evidence, not a historic high/low reconstruction.
        first = {**fresh("VLTO", 120., self.now),
                 **fresh("COST", 94., self.now),
                 **fresh("MTD", 100., self.now)}
        updated, results = self.run_clock(quotes=first)
        first_book = updated[LEDGER]["books"][name]
        self.assertEqual(results[slot]["status"], "settled_native_paper")
        self.assertEqual(results[slot]["pending_open_unfilled"], ["VLTO"])
        self.assertEqual(results[slot]["fills"], 1)
        self.assertEqual(results[slot]["operations"][0]["ticker"], "COST")
        self.assertEqual(set(first_book["positions"]), {"ERIE", "MTD"})
        self.assertEqual(set(first_book["pending"]), {"VLTO"})
        self.assertFalse(any(event.get("ticker") == "VLTO" and
                             event.get("type") == "buy" for event in first_book["events"]))

        # A same-day altered cash amount cannot be excused by a valid stop
        # marker. No subsequent sale or buy is permitted from a changed book.
        self.book = copy.deepcopy(updated[LEDGER])
        later = self.now + timedelta(minutes=10)
        next_quotes = fresh("MTD", 94., later)
        self.book["books"][name]["cash"] += 1.
        invalid, rejected = self.run_clock(quotes=next_quotes, now=later)
        self.assertEqual(rejected[slot]["status"], "source_changed")
        self.assertNotIn(LEDGER, invalid)
        self.book = copy.deepcopy(updated[LEDGER])

        # On the next true minute observation, MTD's stop is independently
        # booked once, although the frozen VLTO buy remains unexecuted.
        second, later_result = self.run_clock(quotes=next_quotes, now=later)
        final_book = second[LEDGER]["books"][name]
        self.assertEqual(later_result[slot]["fills"], 1)
        self.assertEqual(later_result[slot]["pending_open_unfilled"], ["VLTO"])
        self.assertEqual(later_result[slot]["operations"][0]["ticker"], "MTD")
        self.assertEqual(set(final_book["positions"]), {"ERIE"})
        self.assertEqual(set(final_book["pending"]), {"VLTO"})
        self.assertEqual(len([e for e in final_book["events"] if e.get("type") == "sell"]), 2)
        summary = summarize_session_fills(
            final_book, self.original["books"][name], "2026-11-10",
            self.lock["lock_sha256"], self.lock["source_commit"],
            self.config["execution"]["commission"])
        self.assertEqual(summary["fills_count"], 2)
        self.assertEqual({x["ticker"] for x in summary["fills"]}, {"COST", "MTD"})

        self.book = copy.deepcopy(second[LEDGER])
        third, evidence = self.run_clock(quotes={}, now=later+timedelta(minutes=1))
        self.assertEqual(third, {})
        self.assertEqual(evidence[slot]["status"],
                         "opening_buy_unfilled_after_observed_stop")
        self.assertEqual(evidence[slot]["pending_open_unfilled"], ["VLTO"])

    def test_unexecuted_sell_never_competes_with_an_independent_stop(self):
        slot, name = "IL-016", SLOTS["IL-016"]
        book = self.book["books"][name]
        book["positions"] = {
            "COST": {"shares": 3., "entry_date": "2026-11-06",
                     "entry_price": 100., "cost": 300.3,
                     "dividends": 0., "stop": 95., "target": 115.},
            "ERIE": {"shares": 1., "entry_date": "2026-11-06",
                     "entry_price": 100., "cost": 100.1,
                     "dividends": 0., "stop": 95., "target": 115.},
        }
        book["pending"] = {"COST": {"side": "sell", "signal_date": "2026-11-09"}}
        self.tracks[slot]["holdings"] = ["COST", "ERIE"]
        self.tracks[slot]["orders"] = [{
            "ticker": "COST", "action": "sell", "decision_session": "2026-11-09",
            "target_session": "2026-11-10",
        }]
        self.original = copy.deepcopy(self.book)
        self.lock = clock_plan(self.open - timedelta(minutes=10),
                               self.market, self.tracks, "c" * 40)
        quote = {"COST": {"price": 94.,
                  "quote_at_utc": (self.now - timedelta(minutes=1)).isoformat(),
                  "observed_at_utc": self.now.isoformat()}}
        updated, results = self.run_clock(quotes=quote)
        self.assertEqual(results[slot]["status"], "awaiting_fresh_open_quotes")
        self.assertEqual(results[slot]["missing"], ["ERIE"])
        self.assertNotIn(LEDGER, updated)
        self.assertEqual(self.book["books"][name]["trades"], [])
        self.assertIn("COST", self.book["books"][name]["positions"])


    def test_expired_inactive_recovery_boundary_allows_real_next_open_only(self):
        slot, name = "IL-011", SLOTS["IL-011"]
        old = self.book["books"][name]
        old["outage_control"] = {
            "first_trading_session": "2026-11-05",
            "registered_at_utc": "2026-11-04T18:03:08+00:00",
        }
        self.original = copy.deepcopy(self.book)
        changed, result = self.run_clock()
        self.assertEqual(result[slot]["status"], "settled_native_paper")
        self.assertEqual(result[slot]["fills"], 1)
        self.assertEqual(len(changed[LEDGER]["books"][name]["positions"]), 1)
        self.assertEqual(changed[LEDGER]["books"][name]["outage_control"],
                         old["outage_control"])
        self.assertEqual(old["pending"]["AAPL"]["signal_date"], "2026-11-09")

    def test_active_outage_and_unsettled_receivable_still_fail_closed(self):
        slot, name = "IL-011", SLOTS["IL-011"]
        old = self.book["books"][name]
        for boundary in ["2026-11-12", "not-a-date"]:
            old["outage_control"] = {"first_trading_session": boundary}
            self.original = copy.deepcopy(self.book)
            changed, result = self.run_clock()
            self.assertEqual(result[slot]["status"], "inactive_recovery_not_yet_released")
            self.assertEqual(result[slot]["fills"], 0)
            self.assertEqual(changed[LEDGER]["books"][name]["pending"], old["pending"])
        old["outage_control"] = {"first_trading_session": "2026-11-05"}
        old["receivables"] = {"CORP_ACTION": {"status": "unsettled"}}
        self.original = copy.deepcopy(self.book)
        changed, result = self.run_clock()
        self.assertEqual(result[slot]["status"], "corporate_action_review_required")
        self.assertEqual(result[slot]["fills"], 0)
        self.assertEqual(changed[LEDGER]["books"][name]["pending"], old["pending"])

    def test_nightly_marks_only_no_retroactive_entry_or_stop(self):
        marks = {"AAPL": {"open": 100.0, "high": 150.0, "low": 75.0,
                          "close": 101.0, "dividend": 0.0, "split": 0.0}}
        output, result = self.run_clock()
        after = output[LEDGER]
        # Nightly mark must not add a second AAPL fill or sell on full-day lows.
        closed, changed = classic.settle(
            self.config, after, "2026-11-10", "2026-11-09", marks,
            allow_partial=True)
        self.assertTrue(changed)
        target = closed["books"]["ema_rsi_fixed"]
        self.assertIn("AAPL", target["positions"])
        self.assertEqual(sum(e["type"] == "buy" for e in target["events"]), 1)
        self.assertEqual(sum(e["type"] == "sell" for e in target["events"]), 0)
        # Without any opening evidence, orders are missed, never backfilled.
        missed, _ = classic.settle(self.config, self.original, "2026-11-10",
                                   "2026-11-09", marks, allow_partial=True)
        self.assertEqual(missed["books"]["ema_rsi_fixed"]["positions"], {})
        self.assertEqual(missed["books"]["ema_rsi_fixed"]["events"][-1]["type"],
                         "missed_forward_open")


if __name__ == "__main__":
    unittest.main()
