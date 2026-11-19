"""TimesFM EUR four-lane forward tests: FX causality, closes and no retrofills."""
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
from build_opening_plan import plan_track
from operational_clock import budgeted_quote_targets, clock_plan
from forward_timesfm_settlement import (
    settle_timesfm, event_key, COHORTS, FX_TICKER,
)
from timesfm_strategy import run as weekly
from timesfm_strategy import daily_run as daily

UTC = timezone.utc
WEEKLY_PATH, WEEKLY_CONFIG, _ = COHORTS["weekly"]
DAILY_PATH, DAILY_CONFIG, _ = COHORTS["daily"]


class ForwardTimesFMTwoBooksTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            WEEKLY_CONFIG: json.loads((ROOT / WEEKLY_CONFIG).read_text()),
            DAILY_CONFIG: json.loads((ROOT / DAILY_CONFIG).read_text()),
        }
        previous = "2026-11-13"  # Friday, Monday 16 Nov is next XNYS opening
        selected = [{"ticker": "AAPL", "signal_date": previous,
                     "predicted_return": 0.05, "score": 0.03}]
        self.data = {
            WEEKLY_PATH: weekly.initialize(self.config[WEEKLY_CONFIG], previous,
                                            selected, {"synthetic": True}),
            DAILY_PATH: daily.initialize(self.config[DAILY_CONFIG], previous,
                                         selected, {"synthetic": True}),
        }
        self.snapshot = copy.deepcopy(self.data)
        self.market = self._market("2026-11-16", previous)
        self.now = self.market["open"] + timedelta(minutes=2)
        self.lock = self._lock(self.market)
        self.quotes = self._quotes(self.market, {"AAPL": 100, "SPY": 400})

    @staticmethod
    def _market(day, previous):
        opened = datetime.fromisoformat(day+"T14:30:00+00:00")
        return {"session": day, "previous": previous,
                "open": opened, "close": opened+timedelta(hours=6, minutes=30)}

    @staticmethod
    def _quotes(market, entries):
        quote_at = market["open"] + timedelta(minutes=1)
        received = quote_at + timedelta(minutes=1)
        return {t: {"price": v, "quote_at_utc": quote_at.isoformat(),
                    "observed_at_utc": received.isoformat()}
                for t, v in entries.items()}

    def _lock(self, market, *, fx=1.2):
        tracks = {}
        for family, (path, _config, slots) in COHORTS.items():
            for slot, name in slots.items():
                tracks[slot] = plan_track(
                    slot, self.data[path]["books"][name],
                    market["session"], market["previous"])
        stamp = market["open"]-timedelta(minutes=10)
        record = (None if fx is None else {
            "pair": "EURUSD=X", "source": "yfinance_unadjusted_daily_close",
            "source_session": market["previous"],
            "rate_usd_per_eur": fx,
            "captured_at_utc": stamp.isoformat().replace("+00:00","Z"),
            "purpose": "paper_previous_XNYS_session_FX_proxy",
        })
        return clock_plan(stamp, market, tracks, "e"*40, fx_reference=record)

    def settle(self, *, quotes=None, now=None, lock=None, market=None):
        return settle_timesfm(lock or self.lock, now or self.now,
                              market or self.market,
                              self.quotes if quotes is None else quotes,
                              reader=lambda path: copy.deepcopy(
                                  self.config[path] if path in self.config else self.data[path]),
                              frozen=lambda sha,path: copy.deepcopy(self.snapshot[path]))

    def test_four_books_native_eur_math_and_exact_fx_reference(self):
        updated, evidence = self.settle()
        self.assertEqual(set(updated), {WEEKLY_PATH, DAILY_PATH})
        self.assertEqual(set(evidence), {"IL-040","IL-041","IL-042","IL-043"})
        for family,(path, config_path, slots) in COHORTS.items():
            for slot, name in slots.items():
                book = updated[path]["books"][name]
                self.assertEqual(evidence[slot]["status"], "settled_native_paper")
                self.assertEqual(book["pending"], [])
                ticker = "SPY" if name == "benchmark_spy" else "AAPL"
                self.assertIn(ticker, book["positions"])
                position = book["positions"][ticker]
                self.assertAlmostEqual(position["entry_price_eur"],
                    (400 if ticker=="SPY" else 100)/1.2*1.0005)
                self.assertGreater(position["shares"], 0)
                self.assertLess(book["cash"], 100000)
                self.assertEqual(book["equity"][-1]["date"], "2026-11-13")
                self.assertEqual(updated[path]["last_session"], "2026-11-13")
                marker = evidence[slot]["marker"]
                self.assertEqual(marker["fx_reference_sha256"],
                                 weekly.digest(self.lock["fx_reference"]))
        self.data = copy.deepcopy(updated)
        same, repeat = self.settle()
        self.assertEqual(same, {})
        self.assertTrue(all(x["status"] == "already_settled" for x in repeat.values()))

    def test_missing_one_eur_buy_quote_never_blocks_other_or_resizes_budget(self):
        for family, (path, config_path, slots) in COHORTS.items():
            name = "timesfm" if family == "weekly" else "timesfm_daily"
            self.data[path]["books"][name]["pending"].append({
                "ticker": "MSFT", "signal_date": self.market["previous"],
                "predicted_return": 0.04, "score": 0.03})
        self.snapshot = copy.deepcopy(self.data)
        self.lock = self._lock(self.market)
        full_quotes = self._quotes(self.market, {"AAPL": 100, "MSFT": 200, "SPY": 400})
        full, _ = self.settle(quotes=full_quotes)
        partial, evidence = self.settle()
        for family, (path, config_path, slots) in COHORTS.items():
            slot = "IL-040" if family == "weekly" else "IL-042"
            name = "timesfm" if family == "weekly" else "timesfm_daily"
            self.assertEqual(evidence[slot]["status"], "settled_native_paper")
            self.assertEqual(evidence[slot]["unfilled_open_quotes"], ["MSFT"])
            self.assertEqual(evidence[slot]["sizing_reference"], "frozen_order_budget")
            updated = partial[path]["books"][name]
            self.assertEqual(set(updated["positions"]), {"AAPL"})
            self.assertEqual(updated["pending"], [])
            self.assertEqual(updated["positions"]["AAPL"]["shares"],
                full[path]["books"][name]["positions"]["AAPL"]["shares"])
            self.assertTrue(any(e.get("ticker") == "MSFT" and
                (e.get("event") == "unfilled_missing_observed_quote" or
                 e.get("type") == "unfilled_missing_observed_quote")
                for e in updated["events"]))
            self.assertEqual(updated["equity"], self.data[path]["books"][name]["equity"])
        self.data = copy.deepcopy(partial)
        again, repeated = self.settle(quotes=full_quotes)
        self.assertEqual(again, {})
        for slot in ("IL-040", "IL-042"):
            self.assertEqual(repeated[slot]["status"], "already_settled")

    def test_missing_preopen_fx_blocks_all_unchanged(self):
        lock = self._lock(self.market, fx=None)
        out, evidence = self.settle(lock=lock)
        self.assertEqual(out, {})
        self.assertTrue(all(x["status"] == "preopen_fx_missing" for x in evidence.values()))
        after = copy.deepcopy(self.data)
        stale_quotes = self._quotes(self.market, {"AAPL": 100, "SPY": 400})
        stale_quotes["AAPL"]["quote_at_utc"] = (
            self.market["open"]-timedelta(minutes=1)).isoformat()
        out, evidence = self.settle(quotes=stale_quotes)
        # Independent SPY benchmarks may execute with their own fresh quote.
        # Neither TimesFM model may borrow its stale AAPL observation.
        self.assertEqual(evidence["IL-040"]["status"], "awaiting_fresh_open_quotes")
        self.assertEqual(evidence["IL-042"]["status"], "awaiting_fresh_open_quotes")
        for path,name in ((WEEKLY_PATH,"timesfm"),(DAILY_PATH,"timesfm_daily")):
            self.assertEqual(out[path]["books"][name], after[path]["books"][name])
        self.assertEqual(self.data, after)

    def test_daily_exit_requires_nearclose_fx_and_never_sells_passive_spy(self):
        bought, info = self.settle()
        self.data = copy.deepcopy(bought)
        cutoff = self.market["close"]-timedelta(minutes=1)
        self.now = cutoff
        good = {
            ticker: {"price": val,
                     "quote_at_utc": (cutoff-timedelta(minutes=1)).isoformat(),
                     "observed_at_utc": cutoff.isoformat()}
            for ticker,val in {"AAPL": 110, FX_TICKER: 1.1}.items()
        }
        missing, note = self.settle(quotes={"AAPL":good["AAPL"]})
        self.assertEqual(missing, {})
        self.assertEqual(note["IL-042"]["status"],
                         "awaiting_contemporaneous_exit_fx_and_quotes")
        out, status = self.settle(quotes=good)
        self.assertEqual(set(out), {DAILY_PATH})
        self.assertEqual(status["IL-042"]["status"], "settled_native_paper")
        book = out[DAILY_PATH]["books"]["timesfm_daily"]
        self.assertEqual(book["positions"], {})
        self.assertEqual(len(book["trades"]), 1)
        trade=book["trades"][0]
        self.assertEqual(trade["execution"], "forward_observed_preclose")
        self.assertAlmostEqual(trade["sale_eur"],
            trade["shares"]*110/1.1*(1-.0005)*(1-.001), places=3)
        self.assertIn("SPY", out[DAILY_PATH]["books"]["benchmark_spy"]["positions"])
        self.assertFalse(out[DAILY_PATH]["books"]["benchmark_spy"]["trades"])
        self.data.update(copy.deepcopy(out))
        again,_=self.settle(quotes=good)
        self.assertEqual(again, {})

    def test_weekly_friday_exit_cannot_be_retroactively_replaced(self):
        bought, _ = self.settle()
        self.data = copy.deepcopy(bought)
        # Advance every exact session with the pre-existing paper engine; no
        # stop signal or forced weekday close, and held passive SPY remains.
        old="2026-11-13"
        for day in ("2026-11-16","2026-11-17","2026-11-18","2026-11-19"):
            bars = {"AAPL":{"close":104,"open":100},
                    "SPY":{"close":401,"open":400}}
            next_state,changed = weekly.process_day(
                self.data[WEEKLY_PATH],self.config[WEEKLY_CONFIG],day,old,bars,
                fx_entry=1.2,fx_mark=1.2,week_end=False)
            self.assertTrue(changed)
            self.data[WEEKLY_PATH]=next_state
            old=day
        self.snapshot=copy.deepcopy(self.data)
        friday=self._market("2026-11-20","2026-11-19")
        self.market=friday
        self.lock=self._lock(friday,fx=None)
        self.now=friday["close"]-timedelta(minutes=1)
        quotes={
            t: {"price":p, "quote_at_utc":(self.now-timedelta(minutes=1)).isoformat(),
                "observed_at_utc":self.now.isoformat()}
            for t,p in {"AAPL":111.0, FX_TICKER:1.2}.items()}
        out,evidence=self.settle(quotes=quotes)
        self.assertEqual(evidence["IL-040"]["status"],"settled_native_paper")
        self.assertEqual(out[WEEKLY_PATH]["books"]["timesfm"]["positions"],{})
        self.assertIn("SPY",out[WEEKLY_PATH]["books"]["benchmark_spy"]["positions"])
        self.assertEqual(out[WEEKLY_PATH]["books"]["timesfm"]["trades"][-1]["execution"],
                         "forward_observed_preclose")

    def test_weekly_two_stock_friday_exit_is_individual_and_idempotent(self):
        previous = self.market["previous"]
        selected = [
            {"ticker": ticker, "signal_date": previous,
             "predicted_return": 0.05, "score": 0.03}
            for ticker in ("AAPL", "MSFT")]
        self.data[WEEKLY_PATH] = weekly.initialize(
            self.config[WEEKLY_CONFIG], previous, selected, {"synthetic": True})
        self.snapshot = copy.deepcopy(self.data)
        self.lock = self._lock(self.market)
        self.quotes = self._quotes(self.market, {
            "AAPL": 100.0, "MSFT": 200.0, "SPY": 400.0})
        first_open, _ = self.settle()
        self.data.update(copy.deepcopy(first_open))
        previous = "2026-11-13"
        for day in ("2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19"):
            bars = {
                "AAPL": {"close": 104, "open": 100},
                "MSFT": {"close": 204, "open": 200},
                "SPY": {"close": 401, "open": 400},
            }
            daily, changed = weekly.process_day(
                self.data[WEEKLY_PATH], self.config[WEEKLY_CONFIG],
                day, previous, bars, fx_entry=1.2, fx_mark=1.2, week_end=False)
            self.assertTrue(changed)
            self.data[WEEKLY_PATH] = daily
            previous = day
        self.snapshot = copy.deepcopy(self.data)
        friday = self._market("2026-11-20", "2026-11-19")
        self.market = friday
        self.lock = self._lock(friday, fx=None)
        self.now = friday["close"] - timedelta(minutes=2)
        def observed(entries):
            return {t: {"price": v, "quote_at_utc":
                (self.now - timedelta(seconds=30)).isoformat(),
                "observed_at_utc": self.now.isoformat()}
                for t,v in entries.items()}

        # One missing stock does not freeze the valid independent sale.
        only_aapl, proof = self.settle(quotes=observed({
            "AAPL": 111.0, FX_TICKER: 1.2}))
        self.assertEqual(proof["IL-040"]["status"], "settled_native_paper")
        self.assertEqual(proof["IL-040"]["fills"], 1)
        self.assertEqual(proof["IL-040"]["weekly_exit_progress"]["remaining_tickers"], ["MSFT"])
        self.assertEqual(proof["IL-040"]["marker"]["mode"], "exit_symbol")
        first = only_aapl[WEEKLY_PATH]
        self.assertEqual(set(first["books"]["timesfm"]["positions"]), {"MSFT"})
        self.assertEqual(first["books"]["timesfm"]["equity"],
            self.snapshot[WEEKLY_PATH]["books"]["timesfm"]["equity"])
        self.assertEqual(len(first["books"]["timesfm"]["trades"]),
            len(self.snapshot[WEEKLY_PATH]["books"]["timesfm"]["trades"]) + 1)

        # A mismatched cash record is not authorized by prior per-symbol proof.
        self.data[WEEKLY_PATH] = copy.deepcopy(first)
        self.data[WEEKLY_PATH]["books"]["timesfm"]["cash"] += 1.0
        rejected, status = self.settle(quotes=observed({
            "MSFT": 210.0, FX_TICKER: 1.2}))
        self.assertNotIn(WEEKLY_PATH, rejected)
        self.assertEqual(status["IL-040"]["status"], "source_changed")
        self.data[WEEKLY_PATH] = copy.deepcopy(first)
        no_replay, waiting = self.settle(quotes=observed({
            "AAPL": 111.0, FX_TICKER: 1.2}))
        self.assertNotIn(WEEKLY_PATH, no_replay)
        self.assertEqual(waiting["IL-040"]["status"],
                         "awaiting_contemporaneous_exit_fx_and_quotes")

        # A separate valid observation may sell the remaining MSFT once.
        last, status = self.settle(quotes=observed({
            "MSFT": 210.0, FX_TICKER: 1.2}))
        self.assertEqual(status["IL-040"]["fills"], 1)
        self.assertTrue(status["IL-040"]["weekly_exit_progress"]["complete"])
        self.assertEqual(status["IL-040"]["marker"]["mode"], "exit")
        self.assertEqual(status["IL-040"]["marker"]["fills_count"], 2)
        self.assertFalse(last[WEEKLY_PATH]["books"]["timesfm"]["positions"])
        self.assertEqual(len(last[WEEKLY_PATH]["books"]["timesfm"]["trades"]),
                         len(self.snapshot[WEEKLY_PATH]["books"]["timesfm"]["trades"]) + 2)
        from scripts.forward_timesfm_settlement import verified_weekly_exit_fills
        fills = verified_weekly_exit_fills(
            self.lock, friday, self.snapshot[WEEKLY_PATH],
            last[WEEKLY_PATH], self.config[WEEKLY_CONFIG]["execution"])
        self.assertEqual([x["ticker"] for x in fills], ["AAPL", "MSFT"])
        self.data[WEEKLY_PATH] = copy.deepcopy(last[WEEKLY_PATH])
        again, repeated = self.settle(quotes=observed({
            "AAPL": 111, "MSFT": 210, FX_TICKER: 1.2}))
        self.assertNotIn(WEEKLY_PATH, again)
        self.assertEqual(repeated["IL-040"]["status"], "already_settled")

    def test_nightly_cutover_refuses_reconstructed_entries_and_exits(self):
        bars={"AAPL":{"open":100,"high":120,"low":90,"close":110,
                      "split":0,"dividend":0},
              "SPY":{"open":400,"high":410,"low":395,"close":405,
                     "split":0,"dividend":0}}
        weekly_closed,_=weekly.process_day(
            self.data[WEEKLY_PATH],self.config[WEEKLY_CONFIG],
            "2026-11-16","2026-11-13",bars,
            fx_entry=1.2,fx_mark=1.15,week_end=False)
        daily_closed,_=daily.process_session(
            self.data[DAILY_PATH],self.config[DAILY_CONFIG],
            "2026-11-16","2026-11-13",bars,
            fx_entry=1.2,fx_mark=1.15)
        for src in (weekly_closed,daily_closed):
            self.assertEqual(src["books"]["benchmark_spy"]["positions"],{})
        self.assertEqual(weekly_closed["books"]["timesfm"]["positions"],{})
        self.assertEqual(daily_closed["books"]["timesfm_daily"]["positions"],{})
        self.assertEqual(weekly_closed["books"]["timesfm"]["events"][-1]["event"],"missed_forward_open")
        self.assertEqual(daily_closed["books"]["timesfm_daily"]["events"][-1]["type"],"missed_forward_open")
        bought,_=self.settle()
        with self.assertRaisesRegex(ValueError,"exit missing observed"):
            daily.process_session(
                bought[DAILY_PATH],self.config[DAILY_CONFIG],
                "2026-11-16","2026-11-13",bars,
                fx_entry=1.2,fx_mark=1.15)
        # An observed Friday exit may be missing. The nightly ledger MUST
        # value shares still genuinely held, without inventing their sale,
        # and preserve a prospective exit-only flag.
        carried, changed = weekly.process_day(
            bought[WEEKLY_PATH],self.config[WEEKLY_CONFIG],
            "2026-11-16","2026-11-13",bars,
            fx_entry=1.2,fx_mark=1.15,week_end=True)
        self.assertTrue(changed)
        held = carried["books"]["timesfm"]
        self.assertEqual(set(held["positions"]), {"AAPL"})
        self.assertEqual(held["pending_exit"]["from_session"], "2026-11-16")
        self.assertFalse(any(e.get("event") == "sell" and e.get("date") == "2026-11-16"
                             for e in held["events"]))

    def test_missed_friday_unwind_is_marked_and_exits_only_at_future_real_preclose(self):
        bought, _ = self.settle()
        self.data.update(copy.deepcopy(bought))
        previous = "2026-11-13"
        for day in ("2026-11-16", "2026-11-17", "2026-11-18",
                    "2026-11-19", "2026-11-20"):
            bars = {"AAPL": {"close": 104., "open": 100.},
                    "SPY": {"close": 401., "open": 400.}}
            self.data[WEEKLY_PATH], _ = weekly.process_day(
                self.data[WEEKLY_PATH], self.config[WEEKLY_CONFIG],
                day, previous, bars, fx_entry=1.2, fx_mark=1.2,
                week_end=(day == "2026-11-20"))
            previous = day
        original = self.data[WEEKLY_PATH]
        previous_trades = len(original["books"]["timesfm"]["trades"])
        self.assertEqual(original["last_session"], "2026-11-20")
        self.assertEqual(set(original["books"]["timesfm"]["positions"]), {"AAPL"})
        self.assertEqual(original["books"]["timesfm"]["pending_exit"]["from_session"],
                         "2026-11-20")
        self.assertEqual(len(original["books"]["timesfm"]["trades"]), previous_trades)
        self.snapshot = copy.deepcopy(self.data)

        monday = self._market("2026-11-23", "2026-11-20")
        self.market = monday
        self.lock = self._lock(monday, fx=None)
        self.assertTrue(self.lock["slots"]["IL-040"]["exit_only_due"])
        from operational_clock import budgeted_quote_targets, preclose_target
        now = monday["close"] - timedelta(minutes=2)
        targets, omitted = budgeted_quote_targets(
            self.lock, now=now, market=monday, limit=20)
        self.assertTrue({"AAPL", FX_TICKER} <= targets)
        self.assertEqual(omitted, {})
        self.assertIsNotNone(preclose_target(
            monday["close"] - timedelta(minutes=30), monday, self.lock))
        self.now = now
        quote = {"AAPL": 107., FX_TICKER: 1.17}
        observed = {
            t: {"price": p, "quote_at_utc": (now-timedelta(minutes=1)).isoformat(),
                "observed_at_utc": now.isoformat()}
            for t,p in quote.items()}
        sold, receipts = self.settle(quotes=observed)
        self.assertEqual(receipts["IL-040"]["status"], "settled_native_paper")
        self.assertEqual(receipts["IL-040"]["marker"]["unobserved_exit_from_session"],
                         "2026-11-20")
        self.assertEqual(receipts["IL-040"]["fills"], 1)
        sold_state = sold[WEEKLY_PATH]
        self.assertFalse(sold_state["books"]["timesfm"]["positions"])
        self.assertEqual(len(sold_state["books"]["timesfm"]["trades"]),
                         previous_trades + 1)
        self.assertEqual(sold_state["books"]["timesfm"]["trades"][-1]["exit_date"],
                         "2026-11-23")
        # A dated *passive* close then removes the resolved recovery flag
        # without creating an additional trade.
        next_state, _ = weekly.process_day(
            sold_state, self.config[WEEKLY_CONFIG],
            "2026-11-23", "2026-11-20",
            {"SPY": {"close": 404., "open": 403.}},
            fx_entry=1.2, fx_mark=1.17, week_end=False)
        self.assertNotIn("pending_exit", next_state["books"]["timesfm"])
        self.assertEqual(len(next_state["books"]["timesfm"]["trades"]),
                         previous_trades + 1)

    def test_quote_budget_uses_both_fresh_close_values_and_no_fx_at_open(self):
        lock = self._lock(self.market)
        start, omitted = budgeted_quote_targets(
            lock, {}, limit=10, now=self.market["open"]+timedelta(minutes=2),
            market=self.market)
        self.assertIn("AAPL",start)
        self.assertNotIn(FX_TICKER,start)
        end, omitted=budgeted_quote_targets(
            lock, {"slots":{"IL-042":{
                "status":"native_forward_settled",
                "native_marker":{"session":self.market["session"],"mode":"open"}}},
            }, limit=10, now=self.market["close"]-timedelta(minutes=3),
            market=self.market)
        self.assertIn(FX_TICKER,end)
        self.assertIn("AAPL",end)


if __name__=="__main__":
    unittest.main()
