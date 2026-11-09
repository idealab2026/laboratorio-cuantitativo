"""Causal AHP forward tests using preopen locked sources; no market network."""
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tfg_ahp"))

from tfg_ahp.paper import advance, digest
from tfg_ahp.forward import open_week, close_week, mark_close, FIRST_SIGNAL
from operational_clock import clock_plan
from build_opening_plan import plan_track
from forward_ahp_settlement import settle_ahp, LEDGER, CONFIG

UTC = timezone.utc


class AHPForwardTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / CONFIG).read_text())
        self.state = json.loads((ROOT / LEDGER).read_text())
        self.signal = {"asof": FIRST_SIGNAL, "status": "signal",
                       "selections": [{"ticker": "AAA", "weight": 0.45},
                                      {"ticker": "BBB", "weight": 0.45}]}
        self.state["last_signal_session"] = FIRST_SIGNAL
        self.state["pending_signal"] = copy.deepcopy(self.signal)
        self.state["signal_hash"] = digest(self.signal)
        self.state["equity"][-1]["date"] = FIRST_SIGNAL
        self.state.pop("forward_book", None)
        self.state.pop("forward_executions", None)
        self.now = datetime(2026, 11, 16, 14, 32, tzinfo=UTC)
        self.market = self._market("2026-11-16", "2026-11-13")
        self.snapshot = copy.deepcopy(self.state)
        self.lock = self._lock(self.state, self.market)
        self.quotes = self._quotes(["AAA","BBB"], self.market, 100.0)

    def _market(self, current, previous):
        start = datetime.fromisoformat(current+"T14:30:00+00:00")
        return {"session": current, "previous": previous, "open": start,
                "close": start+timedelta(hours=6, minutes=30)}

    def _quotes(self, tickers, market, price):
        return {ticker: {
            "price": price,
            "quote_at_utc": (market["open"]+timedelta(minutes=1)).isoformat(),
            "observed_at_utc": (market["open"]+timedelta(minutes=2)).isoformat(),
        } for ticker in tickers}

    def _lock(self, book, market):
        plan = plan_track("IL-037", book, market["session"], market["previous"])
        return clock_plan(market["open"]-timedelta(minutes=10), market,
                          {"IL-037": plan}, "d"*40)

    def _settle(self, **kwargs):
        return settle_ahp(kwargs.get("lock", self.lock),
                          kwargs.get("now", self.now),
                          kwargs.get("market", self.market),
                          kwargs.get("quotes", self.quotes),
                          reader=lambda path: copy.deepcopy(self.state if path == LEDGER else self.config),
                          frozen=lambda sha,path: copy.deepcopy(self.snapshot))

    def test_friday_signal_scheduled_only_next_eligible_open(self):
        self.assertEqual(self.lock["slots"]["IL-037"]["orders_count"], 2)
        self.assertTrue(self.lock["slots"]["IL-037"]["execution_ready"])
        self.assertEqual([r["target_weight"] for r in self.lock["slots"]["IL-037"]["orders"]],
                         [.45, .45])
        later = plan_track("IL-037", self.state, "2026-11-17", "2026-11-16")
        self.assertEqual(later["status"], "stale")
        old = copy.deepcopy(self.state)
        old["pending_signal"]["asof"] = "2026-11-06"
        old["last_signal_session"] = "2026-11-06"
        self.assertFalse(plan_track("IL-037", old, "2026-11-09", "2026-11-06")["orders"])

    def test_native_cash_weights_and_idempotence(self):
        output, obs = self._settle()
        self.assertEqual(set(output), {LEDGER})
        self.assertEqual(obs["IL-037"]["status"], "settled_native_paper")
        forward = output[LEDGER]["forward_book"]
        self.assertEqual(forward["status"], "open")
        self.assertEqual(set(forward["positions"]), {"AAA", "BBB"})
        self.assertEqual(output[LEDGER]["nav"], self.state["nav"])
        self.assertEqual(len(obs["IL-037"]["operations"]), 2)
        self.assertGreater(forward["cash"], 0)
        total = forward["cash"] + sum(p["cost_basis"] for p in forward["positions"].values())
        self.assertAlmostEqual(total, self.state["nav"], places=4)
        self.state = output[LEDGER]
        again, evidence = self._settle()
        self.assertEqual(again, {})
        self.assertEqual(evidence["IL-037"]["status"], "already_settled")

    def test_missing_quotes_and_missed_open_cannot_backfill(self):
        missing = copy.deepcopy(self.quotes)
        missing.pop("BBB")
        output, info = self._settle(quotes=missing)
        self.assertEqual(output, {})
        self.assertIn("BBB", info["IL-037"]["missing"])
        stale = copy.deepcopy(self.quotes)
        stale["AAA"]["quote_at_utc"] = (self.market["open"]-timedelta(minutes=1)).isoformat()
        out, _ = self._settle(quotes=stale)
        self.assertEqual(out, {})
        late = self.market["open"]+timedelta(minutes=40)
        out, info = self._settle(now=late)
        self.assertEqual(out, {})
        self.assertEqual(info["IL-037"]["status"], "opening_window_missed")

    def _entered(self):
        out, _ = self._settle()
        self.state = out[LEDGER]
        return out[LEDGER]

    def test_stop_triggered_only_by_close_and_exits_next_open(self):
        state = self._entered()
        falling = {"AAA": {"close": 95.0}, "BBB": {"close": 95.0}}
        marked, _ = mark_close(state, self.config, "2026-11-16", "2026-11-13", falling)
        self.assertTrue(marked["forward_book"]["stop_due"])
        self.assertEqual(marked["forward_book"]["stop_observed_date"], "2026-11-16")
        self.state = marked
        self.snapshot = copy.deepcopy(marked)
        market = self._market("2026-11-17", "2026-11-16")
        lock = self._lock(marked, market)
        self.assertEqual([x["action"] for x in lock["slots"]["IL-037"]["orders"]],
                         ["sell","sell"])
        quotes = self._quotes(["AAA","BBB"], market, 94.0)
        out, obs = self._settle(lock=lock, market=market, now=market["open"]+timedelta(minutes=2),
                                quotes=quotes)
        self.assertEqual(obs["IL-037"]["fills"], 2)
        closed = out[LEDGER]["forward_book"]
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(closed["closed_trade"]["exit_reason"], "portfolio_stop_next_open")
        self.assertEqual(closed["closed_trade"]["stop_observed_date"], "2026-11-16")
        self.assertFalse(closed["positions"])
        next_signal = {"asof": "2026-11-20", "status": "no_data", "selections": []}
        advanced, changed = advance(self.config, {}, next_signal, out[LEDGER])
        self.assertTrue(changed)
        self.assertEqual(advanced["trades"][-1]["status"], "settled_forward_observed")
        self.assertEqual(advanced["nav"], closed["closed_trade"]["nav_after"])
        self.assertIsNone(advanced["forward_book"])

    def test_week_end_exit_needs_contemporary_preclose_quotes(self):
        state = self._entered()
        for day, previous in [
            ("2026-11-16", "2026-11-13"),
            ("2026-11-17", "2026-11-16"),
            ("2026-11-18", "2026-11-17"),
            ("2026-11-19", "2026-11-18"),
        ]:
            bars = {"AAA": {"close": 102.0}, "BBB": {"close": 102.0}}
            state, _ = mark_close(state, self.config, day, previous, bars)
        self.state = state
        self.snapshot = copy.deepcopy(state)
        market = self._market("2026-11-20", "2026-11-19")
        lock = self._lock(state, market)
        quotes = self._quotes(["AAA","BBB"], market, 103.0)
        now = market["close"]-timedelta(minutes=1)
        for row in quotes.values():
            row["quote_at_utc"] = (now-timedelta(minutes=1)).isoformat()
            row["observed_at_utc"] = now.isoformat()
        output, obs = self._settle(lock=lock, market=market, now=now, quotes=quotes)
        self.assertEqual(obs["IL-037"]["status"], "settled_native_paper")
        self.assertEqual(output[LEDGER]["forward_book"]["closed_trade"]["exit_reason"],
                         "week_end_observed_preclose")
        stale = copy.deepcopy(quotes)
        for q in stale.values():
            q["quote_at_utc"] = (market["close"]-timedelta(minutes=7)).isoformat()
        missing, _ = self._settle(lock=lock, market=market, now=now, quotes=stale)
        self.assertEqual(missing, {})

    def test_incomplete_weekly_exit_refuses_historical_liquidation(self):
        entered = self._entered()
        next_signal = {"asof":"2026-11-20","status":"no_data","selections":[]}
        with self.assertRaisesRegex(ValueError, "not reconciled"):
            advance(self.config, {}, next_signal, entered)

    def test_previous_legacy_week_not_retro_liquidated_at_cutover(self):
        old = copy.deepcopy(self.state)
        old["pending_signal"] = {"asof":"2026-11-06","status":"signal",
                                 "selections":[{"ticker":"AAA","weight":.4}]}
        old["last_signal_session"] = "2026-11-06"
        old["forward_book"] = None
        new = {"asof":"2026-11-13","status":"no_data","selections":[]}
        updated, changed = advance(self.config, {}, new, old)
        self.assertTrue(changed)
        self.assertEqual(updated["trades"][-1]["status"], "unexecuted")
        self.assertEqual(updated["trades"][-1]["exit_reason"], "cutover_no_forward_open_evidence")
        self.assertEqual(updated["nav"], old["nav"])


if __name__ == "__main__":
    unittest.main()
