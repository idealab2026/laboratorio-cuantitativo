"""Execution-model tests; never open the tracked legacy diary."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from zoneinfo import ZoneInfo

import forward_portfolio as paper


def bar(open_price, high=None, low=None, close=None, dividend=0, split=0):
    return {"Open": open_price, "High": high or open_price, "Low": low or open_price,
            "Close": close or open_price, "Dividends": dividend, "Stock Splits": split}


class ForwardLedgerTests(unittest.TestCase):
    def test_new_epoch_refuses_skipped_initial_session_and_never_reads_old_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            archived = folder / paper.ARCHIVED_FILE_NAME
            previous = paper._new_state()
            previous["last_session"] = "2026-10-07"
            previous["equity_history"]["2026-10-07"] = 101008.0
            previous["pending"]["buys"] = {"OLD": {"weight": .15, "stop_pct": .05, "target_pct": .15}}
            paper.save(archived, previous)
            old_bytes = archived.read_bytes()
            live = folder / paper.FILE_NAME
            self.assertNotEqual(live, archived)
            with patch.object(paper, "ensure_before_next_open"), \
                 patch.object(paper, "fetch_session") as fetch:
                with self.assertRaisesRegex(RuntimeError, "primera señal"):
                    paper.run(live, "2026-10-13", {}, [])
                fetch.assert_not_called()
            self.assertFalse(live.exists())
            with patch.object(paper, "ensure_before_next_open"), \
                 patch.object(paper, "fetch_session", return_value={}) as fetch:
                fresh = paper.run(live, "2026-10-12", {"NEW": .15}, [], .05, .15)
                fetch.assert_called_once_with("2026-10-12", set(), None)
            self.assertEqual(fresh["first_session"] if "first_session" in fresh else
                             list(fresh["equity_history"]), ["2026-10-12"])
            self.assertEqual(fresh["trades"], [])
            self.assertEqual(fresh["equity_history"], {"2026-10-12": 100000})
            self.assertEqual(list(fresh["pending"]["buys"]), ["NEW"])
            self.assertEqual(archived.read_bytes(), old_bytes)

    def test_delayed_run_cannot_queue_an_order_after_next_open(self):
        timezone = ZoneInfo("America/New_York")
        paper.ensure_before_next_open("2026-09-28", datetime(2026, 9, 29, 9, 29, tzinfo=timezone))
        with self.assertRaisesRegex(RuntimeError, "apertura"):
            paper.ensure_before_next_open("2026-09-28", datetime(2026, 9, 29, 9, 30, tzinfo=timezone))

    def test_fetch_refuses_skipped_market_session(self):
        reference = pd.DataFrame({"Close": [100, 101, 102]},
                                 index=pd.to_datetime(["2026-09-25", "2026-09-28", "2026-09-29"]))
        with patch.object(paper.yf, "download", return_value=reference) as download:
            with self.assertRaisesRegex(RuntimeError, "omitida"):
                paper.fetch_session("2026-09-29", {"TEST"}, "2026-09-25")
        self.assertFalse(download.call_args.kwargs["auto_adjust"])

    def test_fetch_requires_raw_ohlc_for_pending_order(self):
        reference = pd.DataFrame({"Close": [100]}, index=pd.to_datetime(["2026-09-28"]))
        missing = pd.DataFrame()
        with patch.object(paper.yf, "download", side_effect=[reference, missing]):
            with self.assertRaisesRegex(RuntimeError, "Sin OHLC válido para TEST"):
                paper.fetch_session("2026-09-28", {"TEST"}, "2026-09-25")

    def test_signal_at_close_waits_for_next_open_and_charges_costs(self):
        start = paper._new_state()
        first = paper.settle(start, "2026-09-25", {}, {"TEST": .15}, [], .05, .10)
        self.assertEqual(first["trades"], [])
        self.assertEqual(first["equity_history"]["2026-09-25"], 100000)
        second = paper.settle(first, "2026-09-28", {"TEST": bar(110, 112, 109, 111)}, {}, [])
        trade = second["trades"][0]
        self.assertEqual(trade["session"], "2026-09-28")
        self.assertEqual(trade["side"], "BUY")
        self.assertAlmostEqual(trade["fill"], 110 * (1 + paper.SLIPPAGE))
        self.assertLess(second["equity_history"]["2026-09-28"], 100000 + trade["shares"] * (111 - 110))
        self.assertEqual(paper.settle(second, "2026-09-28", {}, {}, []), second)
        self.assertEqual(start["positions"], {})

    def test_fractional_shares_use_full_budget_for_expensive_stock(self):
        start = paper._new_state()
        first = paper.settle(start, "2026-09-25", {}, {"EXP": .15}, [], .05, .10)
        second = paper.settle(first, "2026-09-28", {"EXP": bar(4000, 4050, 3950, 4020)}, {}, [])
        trade = second["trades"][0]
        self.assertEqual(trade["side"], "BUY")
        self.assertIsInstance(trade["shares"], float)
        self.assertGreater(trade["shares"], 3.0)
        self.assertLess(trade["shares"], 4.0)
        allocated = 100000 * .15
        spent = trade["shares"] * trade["fill"] + trade["fee"]
        self.assertLessEqual(spent, allocated + 1e-6)
        self.assertGreater(spent, allocated - 1.0)
        self.assertEqual(second["execution"]["fractional_shares"], True)
        self.assertEqual(second["execution"]["share_precision"], 6)

    def test_gap_stop_uses_open_not_unreachable_stop_price(self):
        state = paper._new_state()
        state["positions"]["TEST"] = {"shares": 10, "entry": 100, "sl": 95, "tp": 110}
        state["cash"] = 99000
        settled = paper.settle(state, "2026-09-28", {"TEST": bar(90, 93, 88, 92)}, {}, [])
        self.assertEqual(settled["trades"][0]["reason"], "STOP_GAP")
        self.assertAlmostEqual(settled["trades"][0]["fill"], 90 * (1 - paper.SLIPPAGE))
        self.assertEqual(settled["positions"], {})

    def test_same_candle_stop_and_target_uses_stop(self):
        state = paper._new_state()
        state["positions"]["TEST"] = {"shares": 10, "entry": 100, "sl": 95, "tp": 110}
        state["cash"] = 99000
        settled = paper.settle(state, "2026-09-28", {"TEST": bar(100, 115, 90, 101)}, {}, [])
        self.assertEqual(settled["trades"][0]["reason"], "STOP")

    def test_split_and_dividend_apply_to_old_position(self):
        state = paper._new_state()
        state["positions"]["TEST"] = {"shares": 10, "entry": 100, "sl": 80, "tp": 130}
        state["cash"] = 99000
        settled = paper.settle(state, "2026-09-28", {"TEST": bar(50, 52, 49, 51, dividend=1, split=2)}, {}, [])
        self.assertEqual(settled["positions"]["TEST"]["shares"], 20)
        self.assertEqual(settled["cash"], 99020)
        self.assertEqual(settled["equity_history"]["2026-09-28"], 100040)

    def test_missing_quote_leaves_file_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / paper.FILE_NAME
            state = paper._new_state()
            state["pending"]["buys"] = {"TEST": {"weight": .15, "stop_pct": .05, "target_pct": .10}}
            paper.save(path, state)
            before = path.read_bytes()
            with patch.object(paper, "ensure_before_next_open"), \
                    patch.object(paper, "fetch_session", side_effect=RuntimeError("sin OHLC")):
                with self.assertRaisesRegex(RuntimeError, "sin OHLC"):
                    paper.run(path, "2026-10-12", {}, [])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(json.loads(before)["cash"], 100000)




class InactiveContinuationTests(unittest.TestCase):
    def setUp(self):
        self.state = paper._new_state()
        self.state.update(last_session="2026-10-28", equity_history={"2026-10-28": 100000.}, cash=99000.)
        self.state["positions"] = {"TEST": {"shares": 10., "entry": 100., "sl": 95., "tp": 120.}}
        self.state["pending"]["buys"] = {"OLD": {"weight": .15, "stop_pct": .05, "target_pct": .10}}
        self.state["trades"] = [{"session": "2026-10-28", "ticker": "TEST", "side": "BUY"}]
        self.days = ["2026-10-29", "2026-10-30", "2026-11-02"]
        self.rows = {self.days[0]: bar(100, 101, 89, 90), self.days[1]: bar(110, 121, 100, 110),
                     self.days[2]: bar(105, 106, 104, 105)}
        self.clock = "2026-11-03T14:00:00+00:00"

    def quotes(self, day):
        return {"TEST": self.rows[day]}, {"session": day, "snapshot_sha256": "a" * 64,
                                         "effective_sha256": "b" * 64}

    def test_retains_capital_positions_and_history_marks_real_loss_and_expired_orders(self):
        before = json.loads(json.dumps(self.state))
        got = paper.mark_inactive_sessions(self.state, self.days, self.quotes, recorded_at=self.clock)
        self.assertEqual(got["positions"], before["positions"])
        self.assertEqual(got["cash"], before["cash"])
        self.assertEqual(got["trades"], before["trades"])
        self.assertEqual(got["equity_history"]["2026-10-28"], 100000.)
        self.assertEqual(got["equity_history"]["2026-10-29"], 99900.)
        self.assertEqual(got["equity_history"]["2026-11-02"], 100050.)
        self.assertEqual(got["pending"], {"buys": {}, "sells": []})
        self.assertEqual(got["inactive_sessions"], self.days)
        events = got["outage_events"]
        self.assertEqual([e["trigger"] for e in events if e["type"] == "unexecuted_during_outage"],
                         ["stop", "target"])
        self.assertEqual(events[-1]["expired_unfilled_orders"], before["pending"])
        self.assertEqual(got["equity_provenance"][self.days[0]]["recorded_at_utc"], self.clock)
        self.assertEqual(self.state, before)
        self.assertEqual(paper.mark_inactive_sessions(got, [], self.quotes, recorded_at=self.clock), got)

    def test_bad_bar_missing_holding_and_wrong_source_never_change_input(self):
        before = json.loads(json.dumps(self.state))
        for mode in ("missing", "date", "identity", "price", "split", "dividend"):
            def bad(day):
                rows, identity = self.quotes(day)
                rows = json.loads(json.dumps(rows))
                if day == self.days[-1]:
                    if mode == "missing": rows = {}
                    if mode == "date": identity["session"] = "2026-11-01"
                    if mode == "identity": identity["effective_sha256"] = "not-a-hash"
                    if mode == "price": rows["TEST"]["Close"] = -1
                    if mode == "split": rows["TEST"]["Stock Splits"] = 2
                    if mode == "dividend": rows["TEST"]["Dividends"] = 1
                return rows, identity
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                paper.mark_inactive_sessions(self.state, self.days, bad, recorded_at=self.clock)
            self.assertEqual(self.state, before)

    def test_reviewed_dividend_once_without_any_past_trade(self):
        self.rows[self.days[0]]["Dividends"] = .5
        reviews = {"reviews": [{"kind": "cash_dividend", "ticker": "TEST", "currency": "USD",
            "vendor_ex_session": self.days[0], "amount": .5,
            "source_url": "https://issuer.example/dividend", "verified_on": "2026-11-03"}]}
        got = paper.mark_inactive_sessions(self.state, self.days, self.quotes,
                                           recorded_at=self.clock, reviews=reviews)
        self.assertEqual(got["cash"], 99005.)
        self.assertEqual(got["equity_history"][self.days[-1]], 100055.)
        self.assertEqual(got["trades"], self.state["trades"])

    def test_full_calendar_and_next_future_open_are_checked_by_exchange_schedule(self):
        from datetime import timezone
        from session_gate import outage_window
        days, first = outage_window("2026-10-28", datetime(2026, 11, 3, 14, 29, tzinfo=timezone.utc))
        self.assertEqual(days, self.days)
        self.assertEqual(first, "2026-11-03")
        days, first = outage_window("2026-10-28", datetime(2026, 11, 3, 14, 30, tzinfo=timezone.utc))
        self.assertEqual(days, self.days)
        self.assertEqual(first, "2026-11-04")

    def test_resume_is_atomic_and_publication_cannot_miss_the_frozen_future_open(self):
        from datetime import timezone
        import session_gate
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "market_data").mkdir()
            (root / "market_data/corporate_action_reviews.json").write_text('{"reviews":[]}')
            path = root / paper.FILE_NAME
            paper.save(path, self.state)
            before = path.read_bytes()
            stamp = datetime(2026, 11, 3, 14, 29, tzinfo=timezone.utc)
            def broken(root, day):
                if day == self.days[-1]: return {}, {"session": day, "snapshot_sha256": "a" * 64,
                                                    "effective_sha256": "b" * 64}
                return self.quotes(day)
            with patch.object(session_gate, "common_quotes", side_effect=broken):
                with self.assertRaises(ValueError): session_gate.resume_outage(path, root=root, write=True, now=stamp)
            self.assertEqual(path.read_bytes(), before)
            with patch.object(session_gate, "common_quotes", side_effect=lambda root, day: self.quotes(day)):
                check = session_gate.resume_outage(path, root=root, write=False, now=stamp)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(check["first_trading_session"], "2026-11-03")
                session_gate.resume_outage(path, root=root, write=True, now=stamp)
            session_gate.check_resume_publication(path, now=stamp)
            with self.assertRaisesRegex(ValueError, "missed"):
                session_gate.check_resume_publication(path, now=datetime(2026, 11, 3, 14, 30, tzinfo=timezone.utc))
            unchanged = path.read_bytes()
            check = session_gate.resume_outage(path, root=root, write=True, now=stamp)
            self.assertFalse(check["written"])
            self.assertEqual(path.read_bytes(), unchanged)

    def test_partial_day_after_late_resume_has_no_stops_but_freezes_future_orders(self):
        import session_gate
        state = json.loads(json.dumps(self.state))
        state["last_session"] = "2026-11-02"
        state["equity_history"]["2026-11-02"] = 100000.
        state["pending"] = {"buys": {}, "sells": []}
        state["outage_control"] = {"first_trading_session": "2026-11-04"}
        quotes = {"TEST": bar(90, 92, 80, 90)}
        identity = {"session": "2026-11-03", "snapshot_sha256": "a" * 64, "effective_sha256": "b" * 64}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / paper.FILE_NAME
            paper.save(path, state)
            with patch.object(paper, "ensure_before_next_open"),                  patch.object(paper, "fetch_session", return_value=quotes),                  patch.object(session_gate, "common_quotes", return_value=(quotes, identity)):
                got = paper.run(path, "2026-11-03", {"NEW": .1}, [], .05, .15)
            self.assertEqual(got["positions"], state["positions"])
            self.assertEqual(got["trades"], state["trades"])
            self.assertEqual(got["equity_history"]["2026-11-03"], 99900.)
            self.assertEqual(got["pending"]["buys"]["NEW"]["weight"], .1)


if __name__ == "__main__":
    unittest.main()
