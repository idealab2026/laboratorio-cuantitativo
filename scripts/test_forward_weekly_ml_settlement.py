"""Forward IL-019..027 tests: native accounting, causality, missed opens, idempotency."""
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from operational_clock import clock_plan, budgeted_quote_targets
from forward_weekly_ml_settlement import LEDGER, CONFIG, SLOTS, settle_weekly
from weekly_ml.daily import process_day

UTC = timezone.utc


class ForwardWeeklyMLTests(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.now = self.open + timedelta(minutes=2)
        self.market = {
            "session": "2026-11-10", "previous": "2026-11-09",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)
        }
        self.config = json.loads((ROOT / CONFIG).read_text())
        self.state = json.loads((ROOT / LEDGER).read_text())
        self.state["last_session"] = "2026-11-09"
        self.state["last_signal_session"] = "2026-11-09"
        self.tracks = {}
        for slot, name in SLOTS.items():
            book = self.state["strategies"][name]
            book.update(
                cash=100000.0, nav=100000.0, positions={},
                pending=[{"ticker": "AAPL", "signal_date": "2026-11-09"}],
                events=[], trades=[], equity=[{"date": "2026-11-09", "nav": 100000.0}],
                last_signal_session="2026-11-09"
            )
            book.pop("paused_missing_quotes", None)
            book.pop("forward_executions", None)
            self.tracks[slot] = {
                "status": "recorded", "session": "2026-11-09",
                "holdings": [], "orders": [{
                    "ticker": "AAPL", "action": "buy",
                    "decision_session": "2026-11-09",
                    "target_session": "2026-11-10"
                }]
            }
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10),
                               self.market, self.tracks, "b" * 40)
        self.quotes = {
            "AAPL": {"price": 100.0,
                     "quote_at_utc": (self.open + timedelta(minutes=1)).isoformat(),
                     "observed_at_utc": self.now.isoformat()}
        }

    def reader(self, path):
        return copy.deepcopy(self.state if path == LEDGER else self.config)

    def frozen(self, commit, path):
        self.assertEqual(commit, "b" * 40)
        self.assertEqual(path, LEDGER)
        return copy.deepcopy(self.frozen_state)

    def settle(self, **kwargs):
        return settle_weekly(self.lock, self.now, self.market, self.quotes,
                             reader=self.reader, frozen=self.frozen, **kwargs)

    def test_all_nine_books_have_identical_native_fee_math_and_once_only(self):
        outputs, evidence = self.settle()
        self.assertEqual(set(outputs), {LEDGER})
        after = outputs[LEDGER]
        self.assertEqual(set(evidence), set(SLOTS))
        for slot, name in SLOTS.items():
            book = after["strategies"][name]
            self.assertEqual(evidence[slot]["status"], "settled_native_paper")
            self.assertEqual(len(evidence[slot]["operations"]), 1)
            self.assertEqual(book["pending"], [])
            self.assertEqual(book["nav"], 100000.0)
            self.assertEqual(book["equity"][-1]["date"], "2026-11-09")
            self.assertEqual(book["events"][-1]["execution"], "forward_observed_paper")
            self.assertEqual(book["events"][-1]["source_commit"], "b" * 40)
            self.assertTrue(book["forward_executions"])
            self.assertGreater(book["positions"]["AAPL"]["shares"], 0)
        self.state = copy.deepcopy(after)
        second, repeated = self.settle()
        self.assertEqual(second, {})
        self.assertTrue(all(v["status"] == "already_settled" for v in repeated.values()))

    def test_open_missing_or_stale_quote_does_not_book(self):
        missing = copy.deepcopy(self.quotes)
        self.quotes = {}
        out, evidence = self.settle()
        self.assertEqual(out, {})
        self.assertTrue(all(v["status"] == "awaiting_fresh_quotes" for v in evidence.values()))
        self.quotes = missing
        self.quotes["AAPL"]["quote_at_utc"] = (
            self.open - timedelta(minutes=5)).isoformat()
        out, _ = self.settle()
        self.assertEqual(out, {})
        self.quotes["AAPL"]["quote_at_utc"] = (
            self.open + timedelta(minutes=1)).isoformat()
        out, _ = settle_weekly(
            self.lock, self.open + timedelta(minutes=45), self.market,
            self.quotes, reader=self.reader, frozen=self.frozen)
        self.assertEqual(out, {}, "No fill reconstructed long after the opening")

    def test_missing_one_weekly_buy_quote_fills_other_symbol_without_reallocation(self):
        # The frozen original size, rather than a resized 1-of-2 basket,
        # must determine AAPL quantity. MSFT never gets a paper fill.
        slot, name = "IL-023", SLOTS["IL-023"]
        book = self.state["strategies"][name]
        book["pending"].append({"ticker": "MSFT", "signal_date": "2026-11-09"})
        self.tracks[slot]["orders"].append({
            "ticker": "MSFT", "action": "buy",
            "decision_session": "2026-11-09", "target_session": "2026-11-10"})
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10),
                               self.market, self.tracks, "b" * 40)
        all_quotes = dict(self.quotes)
        all_quotes["MSFT"] = {
            **self.quotes["AAPL"], "price": 200.0
        }
        all_filled, _ = settle_weekly(
            self.lock, self.now, self.market, all_quotes,
            reader=self.reader, frozen=self.frozen)
        expected_shares = all_filled[LEDGER]["strategies"][name]["positions"]["AAPL"]["shares"]
        partial, evidence = self.settle()
        self.assertEqual(evidence[slot]["status"], "settled_native_paper")
        self.assertEqual(evidence[slot]["fills"], 1)
        self.assertEqual(evidence[slot]["unfilled_open_quotes"], ["MSFT"])
        after = partial[LEDGER]["strategies"][name]
        self.assertEqual(set(after["positions"]), {"AAPL"})
        self.assertEqual(after["positions"]["AAPL"]["shares"], expected_shares)
        self.assertEqual(after["pending"], [])
        self.assertTrue(any(e.get("ticker") == "MSFT"
                            and e.get("type") == "unfilled_missing_observed_quote"
                            for e in after["events"]))
        self.assertEqual(len([e for e in after["events"] if e.get("type") == "buy"]), 1)
        self.assertEqual(after["equity"], [{"date": "2026-11-09", "nav": 100000.0}])
        self.state = copy.deepcopy(partial[LEDGER])
        no_duplicate, result = settle_weekly(
            self.lock, self.now, self.market, all_quotes,
            reader=self.reader, frozen=self.frozen)
        self.assertEqual(no_duplicate, {})
        self.assertEqual(result[slot]["status"], "already_settled")

    def test_source_change_rejects_only_changed_strategy(self):
        self.state["strategies"]["mlp_return"]["cash"] += 50
        output, evidence = self.settle()
        self.assertEqual(evidence["IL-024"]["status"], "source_changed_or_stale")
        self.assertEqual(evidence["IL-023"]["status"], "settled_native_paper")
        self.assertFalse(output[LEDGER]["strategies"]["mlp_return"].get("forward_executions"))

    def test_weekly_preclose_exit_uses_only_fresh_observations_once(self):
        self.open = datetime(2026, 11, 13, 14, 30, tzinfo=UTC)
        self.market = {"session": "2026-11-13", "previous": "2026-11-12", "open": self.open,
                       "close": self.open + timedelta(hours=6, minutes=30)}
        self.now = self.market["close"] - timedelta(minutes=2)
        self.state["last_session"] = "2026-11-12"
        for slot, name in SLOTS.items():
            b = self.state["strategies"][name]
            b.update(cash=90000., nav=100000., pending=[], last_signal_session="2026-11-06",
                     equity=[{"date": "2026-11-12", "nav": 100000.}],
                     positions={"AAPL": {"shares": 100., "entry_price": 100., "entry_fee": 10.,
                                         "entry_date": "2026-11-09", "signal_date": "2026-11-06"}})
            self.tracks[slot] = {"status": "recorded", "session": "2026-11-12", "holdings": ["AAPL"], "orders": []}
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10), self.market, self.tracks, "b" * 40)
        requested, omitted = budgeted_quote_targets(self.lock, now=self.now, market=self.market)
        self.assertEqual(requested, {"AAPL"})
        self.assertFalse(omitted)
        self.quotes = {"AAPL": {"price": 110., "quote_at_utc": self.now.isoformat(),
                                "observed_at_utc": self.now.isoformat()}}
        missing, evidence = settle_weekly(self.lock, self.now, self.market, {}, reader=self.reader, frozen=self.frozen)
        self.assertEqual(missing, {})
        self.assertTrue(all(e["status"] == "awaiting_verified_weekly_exit_quotes" for e in evidence.values()))
        self.assertEqual(evidence["IL-023"]["missing"], ["AAPL"])
        self.assertEqual((evidence["IL-023"]["valid_count"],
                          evidence["IL-023"]["required_count"]), (0, 1))
        stale = copy.deepcopy(self.quotes)
        stale["AAPL"]["quote_at_utc"] = (self.now - timedelta(minutes=8)).isoformat()
        output, _ = settle_weekly(self.lock, self.now, self.market, stale, reader=self.reader, frozen=self.frozen)
        self.assertEqual(output, {})
        self.state["strategies"]["mlp_return"]["cash"] += 1
        output, evidence = self.settle()
        self.assertEqual(evidence["IL-024"]["status"], "exit_source_changed_or_stale")
        self.assertEqual(output[LEDGER]["strategies"]["mlp_return"]["positions"],
                         self.state["strategies"]["mlp_return"]["positions"])
        self.state["strategies"]["mlp_return"]["cash"] -= 1
        output, evidence = self.settle()
        for slot, name in SLOTS.items():
            book = output[LEDGER]["strategies"][name]
            self.assertEqual(evidence[slot]["fills"], 1)
            self.assertFalse(book["positions"])
            self.assertEqual(book["trades"][-1]["exit_date"], "2026-11-13")
            self.assertEqual(book["events"][-1]["execution"], "observed_preclose_paper")
            self.assertAlmostEqual(book["cash"], 90000 + 100 * 110 * (1-self.config["paper_policy"]["slippage"]) * (1-self.config["paper_policy"]["commission"]))
        self.state = copy.deepcopy(output[LEDGER])
        again, evidence = self.settle()
        self.assertEqual(again, {})
        self.assertTrue(all(e["status"] == "already_settled" for e in evidence.values()))

    def test_paused_positions_exit_only_after_fresh_friday_quotes(self):
        self.open = datetime(2026, 11, 20, 14, 30, tzinfo=UTC)
        self.market = {"session": "2026-11-20", "previous": "2026-11-19",
                       "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)}
        self.now = self.market["close"] - timedelta(minutes=2)
        self.state["last_session"] = "2026-11-19"
        frozen_holdings = {"AAPL": {"shares": 100., "entry_price": 100., "entry_fee": 10.,
                                    "entry_date": "2026-11-02", "signal_date": "2026-10-30"}}
        for slot, name in SLOTS.items():
            book = self.state["strategies"][name]
            book.update(cash=90000., nav=100000., positions=copy.deepcopy(frozen_holdings),
                        pending=[], equity=[{"date": "2026-11-19", "nav": 100000.}],
                        events=[], trades=[], last_signal_session="2026-10-30")
            if slot in {"IL-023", "IL-024", "IL-026"}:
                book["paused_missing_quotes"] = {
                    "date": "2026-11-19", "reason": "unobserved_weekly_exit",
                    "missing_tickers": [], "missed_exit_sessions": ["2026-11-06", "2026-11-13"]}
                status = "paused"
            else:
                book.pop("paused_missing_quotes", None)
                status = "recorded"
            self.tracks[slot] = {"status": status, "session": "2026-11-19",
                                 "holdings": ["AAPL"], "orders": []}
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10), self.market, self.tracks, "b" * 40)
        self.assertTrue(self.lock["slots"]["IL-024"]["exit_only_ready"])
        self.assertFalse(self.lock["slots"]["IL-024"]["execution_ready"])
        chosen, omitted = budgeted_quote_targets(self.lock, now=self.open + timedelta(hours=1), market=self.market)
        self.assertFalse(chosen)
        self.assertFalse(omitted)
        chosen, omitted = budgeted_quote_targets(self.lock, now=self.now, market=self.market)
        self.assertEqual(chosen, {"AAPL"})
        self.assertFalse(omitted)
        self.quotes = {"AAPL": {"price": 111., "quote_at_utc": self.now.isoformat(),
                                "observed_at_utc": self.now.isoformat()}}
        output, evidence = self.settle()
        self.assertEqual(set(output), {LEDGER})
        for slot, name in SLOTS.items():
            book = output[LEDGER]["strategies"][name]
            self.assertEqual(evidence[slot]["status"], "settled_native_paper")
            self.assertFalse(book["positions"])
            self.assertEqual(book["trades"][-1]["exit_date"], "2026-11-20")
            if slot in {"IL-023", "IL-024", "IL-026"}:
                self.assertNotIn("paused_missing_quotes", book)
                self.assertEqual(book["events"][-1]["missed_exit_sessions"],
                                 ["2026-11-06", "2026-11-13"])
                self.assertEqual(book["events"][-1]["type"],
                                 "prospective_unwind_after_unobserved_weekly_exit")
            else:
                self.assertNotIn("paused_missing_quotes", book)
        self.state = copy.deepcopy(output[LEDGER])
        again, evidence = self.settle()
        self.assertEqual(again, {})
        self.assertTrue(all(x["status"] == "already_settled" for x in evidence.values()))

    def test_paused_exit_rejects_stale_ledger_without_partial_sell(self):
        self.open = datetime(2026, 11, 20, 14, 30, tzinfo=UTC)
        self.market = {"session": "2026-11-20", "previous": "2026-11-19",
                       "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)}
        self.now = self.market["close"] - timedelta(minutes=2)
        self.state["last_session"] = "2026-11-19"
        for slot, name in SLOTS.items():
            book = self.state["strategies"][name]
            book.update(positions={"AAPL": {"shares": 1., "entry_price": 100.,
                         "entry_fee": .1, "entry_date": "2026-11-02", "signal_date": "2026-10-30"}},
                        pending=[], equity=[{"date": "2026-11-18", "nav": 100000.}])
            book["paused_missing_quotes"] = {"date": "2026-11-18",
                "reason": "unobserved_weekly_exit", "missing_tickers": [],
                "missed_exit_sessions": ["2026-11-13"]}
            self.tracks[slot] = {"status": "paused", "session": "2026-11-18",
                                 "holdings": ["AAPL"], "orders": []}
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10), self.market, self.tracks, "b" * 40)
        self.quotes = {"AAPL": {"price": 110., "quote_at_utc": self.now.isoformat(),
                                "observed_at_utc": self.now.isoformat()}}
        output, evidence = self.settle()
        self.assertEqual(output, {})
        self.assertTrue(all(x["status"] == "exit_source_changed_or_stale" for x in evidence.values()))
        self.assertEqual(self.state, self.frozen_state)

    def test_multi_symbol_paused_book_settles_only_fresh_names_and_retries_without_replay(self):
        self.open = datetime(2026, 11, 20, 14, 30, tzinfo=UTC)
        self.market = {"session": "2026-11-20", "previous": "2026-11-19",
                       "open": self.open, "close": self.open + timedelta(hours=6, minutes=30)}
        self.now = self.market["close"] - timedelta(minutes=2)
        self.state["last_session"] = "2026-11-19"
        position = {"shares": 100., "entry_price": 100., "entry_fee": 10.,
                    "entry_date": "2026-11-02", "signal_date": "2026-10-30"}
        for slot, name in SLOTS.items():
            book = self.state["strategies"][name]
            book.update(cash=80000., nav=100000.,
                        positions={"AAPL": copy.deepcopy(position), "MSFT": copy.deepcopy(position)},
                        pending=[], trades=[], events=[],
                        equity=[{"date": "2026-11-19", "nav": 100000.}])
            book["paused_missing_quotes"] = {"reason": "unobserved_weekly_exit",
                "date": "2026-11-19", "missing_tickers": [],
                "missed_exit_sessions": ["2026-11-13"]}
            self.tracks[slot] = {"status": "paused", "session": "2026-11-19",
                                 "holdings": ["AAPL", "MSFT"], "orders": []}
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10), self.market, self.tracks, "b"*40)
        requested, omitted = budgeted_quote_targets(self.lock, now=self.now, market=self.market, limit=1)
        self.assertEqual(requested, set())
        self.assertEqual(set(omitted), set(SLOTS))
        self.quotes = {"AAPL": {"price": 110.,
            "quote_at_utc": self.now.isoformat(), "observed_at_utc": self.now.isoformat()}}
        first, evidence = self.settle()
        self.assertEqual(set(first), {LEDGER})
        for slot, name in SLOTS.items():
            self.assertEqual(evidence[slot]["status"], "settled_native_paper")
            self.assertEqual(evidence[slot]["fills"], 1)
            self.assertEqual(evidence[slot]["remaining_tickers"], ["MSFT"])
            self.assertEqual(evidence[slot]["marker"]["mode"], "weekly_observed_exit_symbol")
            book = first[LEDGER]["strategies"][name]
            self.assertEqual(set(book["positions"]), {"MSFT"})
            self.assertIn("paused_missing_quotes", book)
            self.assertEqual(book["nav"], 100000.)
            self.assertEqual(book["equity"], [{"date": "2026-11-19", "nav": 100000.}])
            self.assertEqual([t["ticker"] for t in book["trades"]], ["AAPL"])
        self.state = copy.deepcopy(first[LEDGER])
        repeat, evidence = self.settle()
        self.assertEqual(repeat, {})
        self.assertTrue(all(x["status"] == "awaiting_verified_weekly_exit_quotes"
                            and x["missing"] == ["MSFT"] for x in evidence.values()))

        # No economic divergence or forged receipt can authorize a later sale.
        tampered = copy.deepcopy(self.state)
        self.state["strategies"]["mlp_return"]["cash"] += 1.
        second_quotes = {"MSFT": {"price": 120.,
            "quote_at_utc": self.now.isoformat(), "observed_at_utc": self.now.isoformat()}}
        self.quotes = second_quotes
        blocked, rejected = self.settle()
        self.assertEqual(rejected["IL-024"]["status"], "exit_source_changed_or_stale")
        self.assertEqual(blocked[LEDGER]["strategies"]["mlp_return"]["cash"],
                         self.state["strategies"]["mlp_return"]["cash"])
        self.state = tampered

        second, evidence = self.settle()
        self.assertEqual(set(second), {LEDGER})
        for slot, name in SLOTS.items():
            book = second[LEDGER]["strategies"][name]
            self.assertFalse(book["positions"])
            self.assertNotIn("paused_missing_quotes", book)
            self.assertEqual([t["ticker"] for t in book["trades"]], ["AAPL", "MSFT"])
            self.assertEqual(evidence[slot]["fills"], 1)
            self.assertEqual(evidence[slot]["operations"][0]["ticker"], "MSFT")
            marker = evidence[slot]["marker"]
            self.assertEqual(marker["mode"], "weekly_observed_exit")
            self.assertEqual(marker["fills_count"], 2)
            self.assertEqual(marker["fill_tickers"], ["AAPL", "MSFT"])
        self.state = copy.deepcopy(second[LEDGER])
        no_replay, repeated = self.settle()
        self.assertEqual(no_replay, {})
        self.assertTrue(all(x["status"] == "already_settled" for x in repeated.values()))

    def test_weekly_exit_observes_actual_early_close_not_a_fabricated_1600(self):
        # XNYS Black Friday: US session ends at 13:00 ET, not 16:00 ET.
        self.open = datetime(2026, 11, 27, 14, 30, tzinfo=UTC)
        self.market = {"session": "2026-11-27", "previous": "2026-11-25",
                       "open": self.open, "close": datetime(2026, 11, 27, 18, 0, tzinfo=UTC)}
        self.now = self.market["close"] - timedelta(minutes=2)
        self.state["last_session"] = "2026-11-25"
        for slot, name in SLOTS.items():
            book = self.state["strategies"][name]
            book.update(cash=90000., positions={"AAPL": {"shares": 100., "entry_price": 100.,
                            "entry_fee": 10., "entry_date": "2026-11-23", "signal_date": "2026-11-20"}},
                        pending=[], equity=[{"date": "2026-11-25", "nav": 100000.}],
                        last_signal_session="2026-11-20")
            self.tracks[slot] = {"status": "recorded", "session": "2026-11-25",
                                 "holdings": ["AAPL"], "orders": []}
        self.frozen_state = copy.deepcopy(self.state)
        self.lock = clock_plan(self.open - timedelta(minutes=10), self.market, self.tracks, "b"*40)
        self.quotes = {"AAPL": {"price": 111., "quote_at_utc": self.now.isoformat(),
                                "observed_at_utc": self.now.isoformat()}}
        output, evidence = self.settle()
        self.assertEqual(set(output), {LEDGER})
        self.assertTrue(all(x["status"] == "settled_native_paper" for x in evidence.values()))
        self.assertEqual(output[LEDGER]["strategies"]["mlp_return"]["trades"][-1]["exit_date"], "2026-11-27")

    def test_nightly_marks_forward_buy_once(self):
        output, _ = self.settle()
        after = output[LEDGER]
        prices = {"AAPL": {"open": 100, "close": 101, "split": 0, "dividend": 0}}
        closed, changed = process_day(self.config, after, "2026-11-10", prices,
                                      previous_session="2026-11-09", week_end=False)
        self.assertTrue(changed)
        for name in SLOTS.values():
            book = closed["strategies"][name]
            self.assertEqual(book["equity"][-1]["date"], "2026-11-10")
            self.assertEqual(sum(e["type"] == "buy" for e in book["events"]), 1)

    def test_missed_forward_open_never_backfilled_at_night(self):
        prices = {"AAPL": {"open": 100, "close": 101, "split": 0, "dividend": 0}}
        closed, changed = process_day(self.config, self.state, "2026-11-10", prices,
                                      previous_session="2026-11-09", week_end=False)
        self.assertTrue(changed)
        for name in SLOTS.values():
            book = closed["strategies"][name]
            self.assertEqual(book["pending"], [])
            self.assertFalse(book["positions"])
            self.assertEqual(book["events"][-1]["type"], "missed_forward_open")
            self.assertEqual(book["equity"][-1]["date"], "2026-11-10")


if __name__ == "__main__":
    unittest.main()
