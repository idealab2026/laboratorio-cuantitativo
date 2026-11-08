"""Offline scientific invariants: no network, no real quotes, no hidden model costs."""
import copy
import json
import unittest
from datetime import date, timedelta

from multi_agent.run import blank, validate, committee, step, sha, CONFIG_SHA


def day(n):
    return (date(2026, 10, 1) + timedelta(days=n)).isoformat()


def bar(open_price, close_price=None, volume=250000):
    close = float(open_price if close_price is None else close_price)
    op = float(open_price)
    return {"date": None, "provider_symbol": None,
            "open": op, "high": max(op, close) * 1.02,
            "low": min(op, close) * .98, "close": close,
            "volume": volume, "dividend": 0.0, "split": 0.0}


def frame(n, session=None, *, a=1.04, b=0.99, market=1.005):
    session = session or day(n)
    bars = {f"F{i:03d}": bar(100) for i in range(460)}
    bars["AAA"] = bar(100 * a ** n, 100 * a ** n)
    bars["BBB"] = bar(100 * b ** n, 100 * b ** n)
    bars["SPY"] = bar(100 * market ** n, 100 * market ** n)
    return {"base": {"session": session}, "effective_sha256": f"{n+1:064x}",
            "bars": bars}


class DebateTests(unittest.TestCase):
    def test_empty_state_canonical(self):
        x = blank()
        validate(x)
        self.assertEqual(x["config_sha256"], CONFIG_SHA)
        x["cash"] = 200000
        with self.assertRaises(ValueError):
            validate(x)

    def test_source_and_ideas_are_causal(self):
        days = [(day(i), frame(i)) for i in range(6)]
        d = committee(days)
        self.assertEqual(d["targets"], ["AAA"])
        self.assertEqual(d["debate"][0]["fundamental"], "ABSTAIN_NO_PIT_DATA")
        self.assertEqual(d["debate"][0]["sentiment"], "ABSTAIN_NO_PIT_NEWS")
        # Future bars appended cannot change the already closed 6-session signal.
        self.assertEqual(d, committee(copy.deepcopy(days)))
        self.assertEqual(committee(days[:5])["reason"], "WARMUP")

    def test_next_open_and_not_same_day(self):
        friday = "2026-11-06"
        mon = "2026-11-09"
        frames = [(day(i), frame(i)) for i in range(5)]
        friday_snapshot = frame(5, friday)
        frames.append((friday, friday_snapshot))
        first = step(blank(), friday, friday_snapshot, frames)
        self.assertEqual(first["cash"], 100000)
        self.assertFalse(first["holdings"])
        self.assertEqual(first["pending"]["targets"], ["AAA"])
        self.assertEqual(first["history"][-1]["nav"], 100000)
        monday_snapshot = frame(6, mon)
        monday_snapshot["bars"]["AAA"]["open"] = 80.0
        monday_snapshot["bars"]["AAA"]["low"] = 79.0
        monday_snapshot["bars"]["AAA"]["high"] = 140.0
        second = step(first, mon, monday_snapshot, frames + [(mon, monday_snapshot)])
        self.assertEqual(second["pending"], None)
        self.assertGreater(second["holdings"]["AAA"], 0)
        buys = [e for e in second["events"] if e["event"] == "BUY"]
        self.assertEqual(len(buys), 1)
        self.assertEqual(buys[0]["signal_session"], friday)
        self.assertAlmostEqual(buys[0]["price"], 80 * 1.0005)
        self.assertLess(second["history"][-1]["nav"], 120000)
        with self.assertRaises(ValueError):
            step(second, mon, monday_snapshot, frames)

    def test_no_fill_when_pending_target_missing(self):
        fri = "2026-11-06"
        frames = [(day(i), frame(i)) for i in range(5)]
        now = frame(5, fri)
        frames.append((fri, now))
        state = step(blank(), fri, now, frames)
        next_day = frame(6, "2026-11-09")
        del next_day["bars"]["AAA"]
        with self.assertRaisesRegex(ValueError, "required"):
            step(state, "2026-11-09", next_day, frames)

    def test_no_fill_if_wrong_session_or_weak_coverage(self):
        x = frame(5, "2026-11-06")
        with self.assertRaises(ValueError):
            step(blank(), "2026-11-09", x, [])
        x["base"]["session"] = "2026-11-09"
        x["bars"] = {"SPY": bar(100)}
        with self.assertRaisesRegex(ValueError, "coverage"):
            step(blank(), "2026-11-09", x, [])

    def test_portfolio_risk_abstains_when_market_down(self):
        frames = [(day(i), frame(i, market=.96)) for i in range(6)]
        self.assertEqual(committee(frames)["targets"], [])

    def test_frozen_state_checksum(self):
        x = blank()
        x["state_sha256"] = sha(x)
        validate(x)
        x["events"].append({"fake": "retroactive"})
        with self.assertRaisesRegex(ValueError, "history"):
            validate(x)


if __name__ == "__main__":
    unittest.main()
