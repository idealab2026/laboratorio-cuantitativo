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

    def test_missing_preopen_fx_blocks_all_unchanged(self):
        lock = self._lock(self.market, fx=None)
        out, evidence = self.settle(lock=lock)
        self.assertEqual(out, {})
        self.assertTrue(all(x["status"] == "preopen_fx_missing" for x in evidence.values()))
        after = copy.deepcopy(self.data)
        stale_quotes = self._quotes(self.market, {"AAPL": 100, "SPY": 400})
        stale_quotes["AAPL"]["quote_at_utc"] = (
            self.market["open"]-timedelta(minutes=1)).isoformat()
        out, _ = self.settle(quotes=stale_quotes)
        self.assertEqual(out, {})
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
        self.data = copy.deepcopy(out)
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
        with self.assertRaisesRegex(ValueError,"weekly exit not observed"):
            weekly.process_day(
                bought[WEEKLY_PATH],self.config[WEEKLY_CONFIG],
                "2026-11-16","2026-11-13",bars,
                fx_entry=1.2,fx_mark=1.15,week_end=True)

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
