"""Offline regression for the audited operations evidence exporter."""
import unittest
from build_operations_audit import build, normalize_ledger, rule_reason, price_history

class OperationsAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=build()

    def test_manifest_has_all_64_ids_and_no_fabricated_orders(self):
        tracks=self.doc["tracks"]
        self.assertEqual(len(tracks),64)
        self.assertEqual(set(tracks),{"IL-%03d"%n for n in range(1,65)})
        self.assertEqual(self.doc["schema"],"midas_operations_audit_v1")
        for slot,track in tracks.items():
            self.assertIn(track["status"],{"partial_executions_documented",
                    "nav_only_or_no_actions","no_executed_actions_documented"})
            seen=set()
            for session in track["sessions"]:
                self.assertNotIn(session["date"],seen)
                seen.add(session["date"])
                for event in session["actions"]:
                    self.assertIn(event["side"],{"buy","sell","hold"})
                    self.assertIn(event["reason_basis"],{"recorded","not_recorded",
                                                       "inferred_position_continuity"})
                    if event["side"]=="hold":
                        self.assertIsNone(event["price"])
                        self.assertEqual(event["reason_basis"],"inferred_position_continuity")
                    if event["price"] is not None:
                        self.assertGreater(event["price"],0)

    def test_real_monthly_books_preserve_fills_and_not_confuse_signals(self):
        for slot,expected in [("IL-038",24),("IL-039",20)]:
            rows=self.doc["tracks"][slot]["sessions"]
            fills=[event for r in rows for event in r["actions"]
                   if event["side"] in ("buy","sell")]
            self.assertEqual(len(fills),expected)
            self.assertTrue(all(e["ticker"] and e["reason"] for e in fills))
            self.assertTrue(any("mensual" in e["reason"].lower() for e in fills))
            self.assertGreater(len(rows),10)
            self.assertGreater(len(self.doc["tracks"][slot]["prices"]),0)
            self.assertEqual(self.doc["tracks"][slot]["currency"],"USD")

    def test_no_invention_if_book_has_no_execution_events(self):
        fixture={"events":[{"date":"2026-11-02","type":"signal",
                            "ticker":"AAPL","side":"buy"}]}
        self.assertEqual(normalize_ledger(fixture,"fixture"),{})
        note,basis=rule_reason({})
        self.assertIn("no documentado",note)
        self.assertEqual(basis,"not_recorded")

    def test_missing_engine_books_are_explicit(self):
        track=self.doc["tracks"]["IL-064"]
        self.assertEqual(track["status"],"no_executed_actions_documented")
        self.assertFalse(any(x["actions"] for x in track["sessions"]))

    def test_close_quotes_are_dated_and_currency_safe(self):
        quotes=price_history()
        self.assertTrue(quotes.get("AAPL"))
        for ticker,points in list(quotes.items())[:10]:
            self.assertTrue(all(x["source"]=="dated_market_close" for x in points))
        for track in self.doc["tracks"].values():
            if track["currency"]=="EUR":
                self.assertTrue(all(not points for points in track["prices"].values()))

if __name__=="__main__":
    unittest.main()
