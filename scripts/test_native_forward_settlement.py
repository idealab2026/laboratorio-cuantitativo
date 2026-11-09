"""Native forward paper settlement, source-lock and nightly non-duplication tests."""
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
from native_forward_settlement import NATIVE, settle_native

UTC = timezone.utc


class NativeForwardSettlementTests(unittest.TestCase):
    def setUp(self):
        self.open = datetime(2026, 11, 10, 14, 30, tzinfo=UTC)
        self.now = self.open + timedelta(minutes=2)
        self.market = {
            "session": "2026-11-10", "previous": "2026-11-09",
            "open": self.open, "close": self.open + timedelta(hours=6, minutes=30),
        }
        self.books, self.configs, self.tracks = {}, {}, {}
        for slot, (path, config, module) in NATIVE.items():
            book = json.loads((ROOT / path).read_text())
            book["last_session"] = "2026-11-09"
            # Native synthetic preopen plan: one new trade plus existing holdings,
            # without rewriting the actual archived 2026 campaign on disk.
            new_ticker = "AAPL"
            current = sorted(book["positions"])
            allocation = {ticker: .6 / len(current) for ticker in current}
            allocation[new_ticker] = .1
            book["pending"] = {
                "signal_date": "2026-11-09",
                "expected_fill_session": "2026-11-10",
                "target_weights": allocation,
                "sectors": {ticker: "Industrials" for ticker in allocation},
            }
            self.books[path] = book
            self.configs[config] = json.loads((ROOT / config).read_text())
            self.tracks[slot] = {
                "status": "recorded", "session": "2026-11-09",
                "holdings": current,
                "orders": [
                    {"ticker": ticker, "action": "buy" if ticker == new_ticker else "rebalance",
                     "decision_session": "2026-11-09", "target_session": "2026-11-10",
                     "target_weight": weight}
                    for ticker, weight in allocation.items()
                ],
            }
        self.lock = clock_plan(self.open-timedelta(minutes=9), self.market,
                               self.tracks, "b" * 40)
        self.quotes = {}
        all_tickers = {t for book in self.books.values()
                       for t in set(book["positions"]) | set(book["pending"]["target_weights"])}
        for t in all_tickers:
            self.quotes[t] = {
                "price": 100.0, "quote_at_utc": (self.open + timedelta(minutes=1)).isoformat(),
                "observed_at_utc": self.now.isoformat(),
            }
        self.snapshots = copy.deepcopy(self.books)

    def reader(self, path):
        return copy.deepcopy(self.books[path] if path in self.books else self.configs[path])

    def frozen(self, commit, path):
        self.assertEqual(commit, "b"*40)
        return copy.deepcopy(self.snapshots[path])

    def test_native_fills_update_original_books_and_nightly_only_marks(self):
        new_books, info = settle_native(self.lock, self.now, self.market, self.quotes,
                                        read=self.reader, original=self.frozen)
        self.assertEqual(set(new_books), set(self.books))
        for slot, (path, config, module) in NATIVE.items():
            before, after = self.books[path], new_books[path]
            self.assertIsNone(after["pending"])
            self.assertGreater(len(after["events"]), len(before["events"]))
            self.assertEqual(after["last_session"], "2026-11-09")
            self.assertEqual(after["nav"], before["nav"],
                             "Last official CLOSED NAV must not use an intraday proxy")
            self.assertEqual(info[slot]["status"], "settled_native_paper")
            self.assertGreaterEqual(info[slot]["fills"], 1)
            self.assertTrue(after["forward_executions"])
            self.assertTrue(all(e.get("observed_at_utc") and e.get("source_commit")
                                for e in after["events"][len(before["events"]):]
                                if e["type"] == "fill"))
            import importlib
            engine = importlib.import_module(module + ".engine")
            bars = {ticker: {"open": 100, "high": 102, "low": 99, "close": 101,
                             "split": 0, "dividend": 0}
                    for ticker in after["positions"]}
            n_fills = sum(e["type"] == "fill" for e in after["events"])
            close, changed = engine.advance(self.configs[config], bars, "2026-11-10",
                                            100, state=after)
            self.assertTrue(changed)
            self.assertEqual(sum(e["type"] == "fill" for e in close["events"]), n_fills,
                             "Nightly close must not re-execute the forward operation")
            self.assertEqual(close["last_session"], "2026-11-10")

    def test_no_trade_if_quote_stale_or_any_held_ticker_missing(self):
        missing = copy.deepcopy(self.quotes)
        missing.pop("AAPL")
        new_books, info = settle_native(self.lock, self.now, self.market, missing,
                                        read=self.reader, original=self.frozen)
        self.assertEqual(new_books, {})
        for slot in NATIVE:
            self.assertEqual(info[slot]["status"], "awaiting_fresh_quotes")
            self.assertIn("AAPL", info[slot]["missing"])

        stale = copy.deepcopy(self.quotes)
        for q in stale.values():
            q["quote_at_utc"] = (self.open-timedelta(minutes=10)).isoformat()
        changed, _ = settle_native(self.lock, self.now, self.market, stale,
                                   read=self.reader, original=self.frozen)
        self.assertEqual(changed, {})

    def test_cannot_use_postplan_modified_positions(self):
        changed = copy.deepcopy(self.books)
        for b in changed.values():
            b["cash"] += 500
        def reader(path):
            return changed[path] if path in changed else self.configs[path]
        books, info = settle_native(self.lock, self.now, self.market, self.quotes,
                                    read=reader, original=self.frozen)
        self.assertEqual(books, {})
        self.assertTrue(all(info[slot]["status"] == "source_changed" for slot in NATIVE))

    def test_second_run_cannot_duplicate_forward_fills(self):
        updated, info = settle_native(self.lock, self.now, self.market, self.quotes,
                                      read=self.reader, original=self.frozen)
        self.books.update(updated)
        again, info2 = settle_native(self.lock, self.now+timedelta(minutes=3),
                                     self.market, self.quotes,
                                     read=self.reader, original=self.frozen)
        self.assertEqual(again, {})
        self.assertTrue(all(info2[slot]["status"] != "settled_native_paper" for slot in NATIVE))

    def test_no_wrong_session_or_late_backfill(self):
        bad = copy.deepcopy(self.lock)
        bad["slots"]["IL-039"]["orders"][0]["signal_session"] = "2026-11-10"
        with self.assertRaisesRegex(ValueError, "modified"):
            settle_native(bad, self.now, self.market, self.quotes,
                          read=self.reader, original=self.frozen)
        books, _ = settle_native(self.lock, self.open+timedelta(minutes=40),
                                 self.market, self.quotes,
                                 read=self.reader, original=self.frozen)
        self.assertEqual(books, {})


if __name__ == "__main__":
    unittest.main()
