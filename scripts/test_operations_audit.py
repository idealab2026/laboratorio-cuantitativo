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
                    self.assertIn(event["side"],{"buy","sell","hold","corporate_action"})
                    self.assertIn(event["reason_basis"],{"recorded","not_recorded",
                                                       "inferred_position_continuity","engine_rule"})
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


class AllStrategyOperationReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=build()

    def test_all_64_slots_have_consistent_executable_price_coverage(self):
        self.assertEqual(len(self.audit["tracks"]),64)
        count_with_events=0
        unpriced=[]
        for slot,track in self.audit["tracks"].items():
            rows=track["sessions"]
            executions=[a for row in rows for a in row["actions"]
                        if a["side"] in {"buy","sell"}]
            if executions:count_with_events+=1
            coverage=track.get("coverage")
            if coverage is None:
                self.assertFalse(executions,"Every executed order must have a coverage record")
                continue
            self.assertEqual(coverage["executions"],len(executions),slot)
            self.assertEqual(coverage["priced_executions"]+
                             coverage["unpriced_executions"],len(executions),slot)
            actual=sum(a["price"] is None for a in executions)
            self.assertEqual(coverage["unpriced_executions"],actual,slot)
            self.assertEqual(coverage["corporate_conversions"],
                sum(a["side"]=="corporate_action" for r in rows for a in r["actions"]),slot)
            for row in rows:
                for a in row["actions"]:
                    if a["side"]=="corporate_action":
                        self.assertEqual(a["price_basis"],"not_applicable")
                        self.assertIsNone(a["price"])
                    elif a["side"] in {"buy","sell"}:
                        self.assertIn(a["price_basis"],
                           {"book_fill","position_entry","corporate_original_entry",
                            "trade_entry_cost_derived","trade_net_proceeds_derived","not_recorded"})
                        if a["price"] is None:
                            unpriced.append((slot,row["date"],a["ticker"],a["side"]))
        self.assertGreaterEqual(count_with_events,30)
        print("Operation coverage:",sum(t.get("coverage",{}).get("executions",0) for t in self.audit["tracks"].values()),
              "executions;",
              sum(t.get("coverage",{}).get("priced_executions",0) for t in self.audit["tracks"].values()),
              "priced;",
              len(unpriced),"without recovered price")
        print("Unpriced audit events, first 35:",unpriced[:35])

    def test_trade_fees_are_preserved_only_when_supported_by_source(self):
        # Buy The Dip contains directly recorded fees on every fill.
        btd = self.audit["tracks"]["IL-039"]
        executed = [a for day in btd["sessions"] for a in day["actions"]
                    if a["side"] in {"buy","sell"}]
        self.assertEqual(len(executed),20)
        self.assertTrue(all(isinstance(a.get("fee"),(int,float))
                            and a["fee"] >= 0 for a in executed))
        # Classic purchase records have no explicit commission amount per fill.
        classic = self.audit["tracks"]["IL-012"]
        purchase = next(a for day in classic["sessions"] for a in day["actions"]
                        if a["side"]=="buy" and a["ticker"]=="ABT")
        self.assertIsNone(purchase.get("fee"))
        self.assertIsInstance(classic["splits"],list)

    def test_kvue_original_buy_and_conversion_are_visible_and_not_a_sale(self):
        for slot,shares,successor in [("IL-012",645.114733,94),
                                       ("IL-010",10.260274,1)]:
            book=self.audit["tracks"][slot]
            first=next(r for r in book["sessions"] if r["date"]=="2026-10-15")
            buy=next(a for a in first["actions"] if a["side"]=="buy" and a["ticker"]=="KVUE")
            self.assertAlmostEqual(buy["price"],18.389189160346984,places=7)
            self.assertAlmostEqual(buy["quantity"],shares,places=6)
            self.assertEqual(buy["price_basis"],"corporate_original_entry")
            self.assertFalse(any(a["side"]=="sell" and a["ticker"]=="KVUE"
                                 for r in book["sessions"] for a in r["actions"]))
            final=next(r for r in book["sessions"] if r["date"]=="2026-11-02")
            self.assertFalse(any(a["side"]=="hold" and a["ticker"]=="KVUE"
                                 for a in final["actions"]),
                             "KVUE was converted to KMB and cannot remain held")
            converted=next(a for a in final["actions"] if a["side"]=="corporate_action"
                           and a["ticker"]=="KVUE")
            self.assertEqual(converted["successor_ticker"],"KMB")
            self.assertEqual(converted["successor_quantity"],successor)
            self.assertIn("No es una venta",converted["reason"])
            self.assertEqual(converted["recorded_at_utc"],"2026-11-03T16:28:14+00:00")
            hold=next(a for a in final["actions"] if a["side"]=="hold" and a["ticker"]=="KMB")
            if slot=="IL-012":self.assertEqual(hold["quantity"],94)
            self.assertGreater(hold["quantity"],0)
            self.assertEqual(book["coverage"]["corporate_conversions"],1)
            self.assertEqual(book["coverage"]["unpriced_executions"],0)
            self.assertIn("KVUE",book["prices"],"Keep predecessor ticker chart available")

    def test_every_classic_filled_trade_has_original_or_fee_backsolved_price(self):
        classic=[t for t in self.audit["tracks"].values()
                 if t.get("source_path")=="classic_sp500_state/ledger.json"]
        self.assertEqual(len(classic),9)
        for book in classic:
            for session in book["sessions"]:
                for op in session["actions"]:
                    if op["side"] in {"buy","sell"}:
                        self.assertIsNotNone(op["price"],
                          (book["source_id"],session["date"],op["ticker"],op["side"]))
                        self.assertGreater(op["price"],0)
        self.assertEqual(sum(x["coverage"]["unpriced_executions"] for x in classic),0)
