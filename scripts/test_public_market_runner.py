import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from public_market_runner import (
    CONFIG_SHA, EIGHT, CAPITAL, PORTFOLIOS, empty_state,
    advance, validate_state, preflight, seal, is_exchange_session
)
from yahoo_source import DEFAULT_UNIVERSE, prepare_snapshot

SECRET = "institutional-fixture-only-not-a-production-secret-20261031"
ROSTER = json.loads((DEFAULT_UNIVERSE.parents[0] / "competition-roster.json").read_text(encoding="utf8"))
UNIVERSE = json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"]


def source_snapshot(session, stamp, close=100.0, skip=None):
    feeds={}
    for symbol in UNIVERSE+["SPY"]:
        if symbol==skip:
            continue
        price=200 if symbol=="SPY" else close
        feeds[symbol]={"date":session,"open":price,"high":price*1.05,
                       "low":price*.95,"close":price*(1.01 if symbol=="SPY" else 1.005),
                       "volume":100000,"dividend":0,"split":0}
    return prepare_snapshot(UNIVERSE,session,feeds,stamp)


def patched_calendar(days):
    dates=[datetime.fromisoformat(d) for d in days]
    cal=SimpleNamespace(schedule=lambda **kwargs:SimpleNamespace(index=dates))
    module=SimpleNamespace(get_calendar=lambda name:cal)
    return patch.dict(sys.modules,{"pandas_market_calendars":module})


class PublicYahooExecutionTests(unittest.TestCase):
    def test_public_repo_runner_preflight_has_no_prices_or_creds(self):
        result=preflight()
        self.assertEqual(result["universe_constituents"],503)
        self.assertEqual(result["capital_reference_books"],2)
        self.assertFalse(result["public_raw_prices_written"])
        self.assertEqual(result["status"],"source_gate_required")
        self.assertEqual(len(EIGHT),8)

    def test_first_session_only_records_close_signals(self):
        first=source_snapshot("2026-10-29","2026-10-29T23:20:00Z")
        state,feed=advance(empty_state(),first,key=SECRET,roster=ROSTER,
                           issued_at="2026-10-29T23:21:00Z")
        self.assertTrue(validate_state(state,SECRET))
        self.assertEqual(feed["status"],"source_verified")
        self.assertEqual(len(feed["tracks"]),2)
        self.assertEqual(state["config_sha256"],CONFIG_SHA)
        for slot,stocks in PORTFOLIOS.items():
            account=state["portfolios"][slot]
            self.assertEqual(account["cash"],CAPITAL)
            self.assertEqual(account["holdings"],{})
            self.assertEqual(set(account["pending"]),set(stocks))
            self.assertEqual(account["history"],[{"date":"2026-10-29","nav":CAPITAL}])
            self.assertEqual(feed["tracks"][list(PORTFOLIOS).index(slot)]["positions"],0)
            self.assertIsNone(feed["tracks"][list(PORTFOLIOS).index(slot)]["day_return_pct"])

    def test_next_market_open_has_independent_portfolios_and_fees(self):
        first=source_snapshot("2026-10-29","2026-10-29T23:20:00Z")
        state,_=advance(empty_state(),first,key=SECRET,roster=ROSTER,
                        issued_at="2026-10-29T23:21:00Z")
        later=source_snapshot("2026-10-30","2026-10-30T23:20:00Z",close=101)
        with patched_calendar(["2026-10-29","2026-10-30"]):
            result,feed=advance(state,later,key=SECRET,roster=ROSTER,
                                 issued_at="2026-10-30T23:21:00Z")
        self.assertEqual(result["last_session"],"2026-10-30")
        self.assertEqual(len(result["portfolios"]["IL-001"]["holdings"]),1)
        self.assertEqual(len(result["portfolios"]["IL-002"]["holdings"]),8)
        for slot,expected in (("IL-001",1),("IL-002",8)):
            book=result["portfolios"][slot]
            self.assertEqual(len([x for x in book["events"] if x["type"]=="FILL"]),expected)
            self.assertAlmostEqual(book["cash"],5000,places=5)
            self.assertEqual(len(book["history"]),2)
            self.assertFalse(book["pending"])
        self.assertEqual(feed["tracks"][0]["positions"],1)
        self.assertEqual(feed["tracks"][1]["positions"],8)
        self.assertNotEqual(feed["tracks"][0]["last_equity"],feed["tracks"][1]["last_equity"])

    def test_missing_original_instrument_never_generates_interpolated_fill(self):
        snapshot=source_snapshot("2026-10-29","2026-10-29T23:20:00Z",skip="JNJ")
        with self.assertRaisesRegex(ValueError,"required portfolio instrument"):
            advance(empty_state(),snapshot,key=SECRET,roster=ROSTER,
                    issued_at="2026-10-29T23:21:00Z")

    def test_signed_books_reject_changes_before_any_new_session(self):
        first=source_snapshot("2026-10-29","2026-10-29T23:20:00Z")
        state,_=advance(empty_state(),first,key=SECRET,roster=ROSTER,
                        issued_at="2026-10-29T23:21:00Z")
        bad=deepcopy(state)
        bad["portfolios"]["IL-001"]["cash"]+=1200
        with self.assertRaisesRegex(ValueError,"signature"):
            validate_state(bad,SECRET)
        with self.assertRaisesRegex(ValueError,"signature"):
            validate_state(state,"wrong-institution-secret-longer-than-32-chars")


    def test_genuine_nyse_holidays_are_not_algorithm_failures(self):
        class Closed:
            def schedule(self, **kwargs):
                return SimpleNamespace(empty=True)
        class Active:
            def schedule(self, **kwargs):
                return SimpleNamespace(empty=False)
        self.assertFalse(is_exchange_session("2026-12-25",Closed()))
        self.assertTrue(is_exchange_session("2026-12-24",Active()))

    def test_fail_closed_for_skipped_exchange_sessions(self):
        first=source_snapshot("2026-10-28","2026-10-28T23:20:00Z")
        state,_=advance(empty_state(),first,key=SECRET,roster=ROSTER,
                        issued_at="2026-10-28T23:21:00Z")
        later=source_snapshot("2026-10-30","2026-10-30T23:20:00Z")
        with patched_calendar(["2026-10-28","2026-10-29","2026-10-30"]):
            with self.assertRaisesRegex(ValueError,"Missed market session"):
                advance(state,later,key=SECRET,roster=ROSTER,
                        issued_at="2026-10-30T23:21:00Z")


if __name__=="__main__":
    unittest.main()
