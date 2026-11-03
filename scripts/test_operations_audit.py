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


class ClassicDecisionTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=build()

    def test_genetic_abt_holds_recover_shares_entry_price_market_close_and_rule(self):
        sessions=self.data["tracks"]["IL-012"]["sessions"]
        day15=next(x for x in sessions if x["date"]=="2026-10-15")
        purchase=next(x for x in day15["actions"] if x["ticker"]=="ABT" and x["side"]=="buy")
        self.assertAlmostEqual(purchase["quantity"],112.925792)
        self.assertAlmostEqual(purchase["price"],105.0525)
        self.assertEqual(purchase["reason_basis"],"engine_rule")
        self.assertIn("no conserva la lectura exacta",purchase["reason"])
        self.assertEqual(purchase["rule_source"],"classic_sp500/run.py")
        latest=next(x for x in sessions if x["date"]=="2026-11-02")
        hold=next(x for x in latest["actions"] if x["ticker"]=="ABT" and x["side"]=="hold")
        self.assertAlmostEqual(hold["quantity"],112.925792)
        self.assertAlmostEqual(hold["entry_price"],105.0525)
        self.assertAlmostEqual(hold["reference_close"],110.16000366210938,places=5)
        self.assertIsNone(hold["price"],"Market closing price is NOT a trade execution")
        self.assertEqual(hold["reason_basis"],"inferred_position_continuity")
        self.assertIn("Reglas genéticas congeladas",hold["reason"])
        self.assertIn("stop vigente",hold["reason"])
        self.assertIn("objetivo vigente",hold["reason"])
        self.assertIn("no cruzó",hold["reason"])
        self.assertEqual(hold["rule_source"],"classic_sp500/run.py")
        older=next(x for x in sessions if x["date"]=="2026-10-16")
        old_hold=next(x for x in older["actions"] if x["ticker"]=="ABT" and x["side"]=="hold")
        self.assertAlmostEqual(old_hold["quantity"],112.925792)
        self.assertNotIn("reference_close",old_hold,"Cannot synthesize an absent market close")
        self.assertNotIn("stop vigente",old_hold["reason"],"Do not project final thresholds backwards")

    def test_final_position_shares_replay_and_buy_hold_policy(self):
        track=self.data["tracks"]["IL-010"]
        self.assertEqual(track["status"],"partial_executions_documented")
        abt=next(x for x in track["sessions"][-1]["actions"] if x["ticker"]=="ABT" and x["side"]=="hold")
        self.assertAlmostEqual(abt["quantity"],1.796036)
        self.assertAlmostEqual(abt["entry_price"],105.0525)
        self.assertIn("Equiponderación",abt["reason"])
        self.assertEqual(abt["reason_basis"],"inferred_position_continuity")
