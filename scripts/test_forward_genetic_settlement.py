"""Original genetic IL-044: exact frozen signal, causal fills, mark only."""
import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "AGENTE/genetic_invest_agent"))

from operational_clock import clock_plan, budgeted_quote_targets
from build_opening_plan import plan_track
from forward_genetic_settlement import LEDGER, settle_genetic
import forward_portfolio as original

UTC = timezone.utc


class NativeGeneticProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.day = "2026-11-10"
        self.previous = "2026-11-09"
        opened = datetime(2026,11,10,14,30,tzinfo=UTC)
        self.market = {"session":self.day,"previous":self.previous,
                       "open":opened,"close":opened+timedelta(hours=6,minutes=30)}
        self.now = opened+timedelta(minutes=2)
        self.state = original._new_state()
        self.state.update(last_session=self.previous,
            equity_history={self.previous:100000.},cash=99000.,
            positions={"MSFT":{"shares":10.0,"entry":100.,"sl":95.,"tp":120.}},
            pending={"buys":{"AAPL":{"weight":.15,"stop_pct":.05,
                                    "target_pct":.10}},"sells":[]},
            trades=[],outage_events=[])
        self.before=copy.deepcopy(self.state)
        self.lock=self.build_lock()
        self.quotes=self.quote_rows({"MSFT":100.,"AAPL":110.},self.now)

    def quote_rows(self,prices,now):
        return {ticker:{"price":price,
            "quote_at_utc":(now-timedelta(minutes=1)).isoformat(),
            "observed_at_utc":now.isoformat()} for ticker,price in prices.items()}

    def build_lock(self,book=None):
        book=book or self.state
        plan=plan_track("IL-044",book,self.day,self.previous)
        return clock_plan(self.market["open"]-timedelta(minutes=10),
                          self.market,{"IL-044":plan},"a"*40)

    def settle(self,quotes=None,now=None):
        return settle_genetic(self.lock,now or self.now,self.market,
                              self.quotes if quotes is None else quotes,
                              reader=lambda path:copy.deepcopy(self.state),
                              frozen=lambda sha,path:copy.deepcopy(self.before))

    def test_genetic_frozen_orders_exactly_next_session_and_monitors_stops(self):
        lane=self.lock["slots"]["IL-044"]
        self.assertEqual(lane["source_session"],self.previous)
        self.assertEqual(lane["orders_count"],1)
        self.assertEqual(lane["orders"][0]["ticker"],"AAPL")
        self.assertEqual(lane["monitor_tickers"],["AAPL","MSFT"])
        self.assertEqual(lane["orders"][0]["target_session"],self.day)
        needed,omitted=budgeted_quote_targets(self.lock,limit=10,
            now=self.now,market=self.market)
        self.assertEqual(needed,{"AAPL","MSFT"})
        self.assertEqual(omitted,{})
        old=copy.deepcopy(self.state);old["last_session"]="2026-11-06"
        lane=plan_track("IL-044",old,self.day,self.previous)
        self.assertNotEqual(lane["status"],"recorded")
        self.assertEqual(lane["orders"],[])

    def test_verified_next_open_buy_uses_original_cash_and_lots_once(self):
        updated,status=self.settle()
        self.assertEqual(set(updated),{LEDGER})
        self.assertEqual(status["IL-044"]["status"],"settled_native_paper")
        self.assertEqual(status["IL-044"]["fills"],1)
        after=updated[LEDGER]
        self.assertEqual(after["last_session"],self.previous)
        self.assertEqual(after["equity_history"],self.before["equity_history"])
        self.assertFalse(after["pending"]["buys"])
        self.assertIn("AAPL",after["positions"])
        buy=after["trades"][-1]
        self.assertEqual(buy["side"],"BUY")
        self.assertEqual(buy["execution"],"forward_observed_paper")
        self.assertAlmostEqual(buy["fill"],110*(1+original.SLIPPAGE))
        self.assertAlmostEqual(after["cash"],
                99000-buy["shares"]*buy["fill"]-buy["fee"],places=4)
        self.assertIn(self.day,after["preopen_inventory"])
        self.assertEqual(after["preopen_inventory"][self.day]["MSFT"],10.)
        self.state=copy.deepcopy(after)
        again,evidence=self.settle()
        self.assertEqual(again,{})
        self.assertEqual(evidence["IL-044"]["status"],"already_settled")

    def test_missing_quote_prevents_any_open_trade_and_stale_data_is_rejected(self):
        out,evidence=self.settle(quotes={"AAPL":self.quotes["AAPL"]})
        self.assertEqual(out,{})
        self.assertEqual(evidence["IL-044"]["status"],"awaiting_fresh_open_quotes")
        rows=copy.deepcopy(self.quotes)
        rows["MSFT"]["quote_at_utc"]=(self.market["open"]-timedelta(minutes=1)).isoformat()
        out,_=self.settle(quotes=rows)
        self.assertEqual(out,{})
        out,evidence=self.settle(now=self.market["open"]+timedelta(minutes=45))
        self.assertEqual(out,{})
        self.assertEqual(evidence["IL-044"]["status"],"opening_window_missed")
        self.assertEqual(self.state,self.before)

    def test_observed_stop_uses_fresh_quote_and_cannot_be_repeated(self):
        bought,_=self.settle()
        self.state=copy.deepcopy(bought[LEDGER])
        now=self.market["open"]+timedelta(minutes=31)
        q=self.quote_rows({"MSFT":94.},now)
        out,evidence=self.settle(quotes=q,now=now)
        self.assertEqual(evidence["IL-044"]["fills"],1)
        after=out[LEDGER]
        self.assertNotIn("MSFT",after["positions"])
        self.assertIn("AAPL",after["positions"])
        self.assertEqual(after["trades"][-1]["reason"],"STOP_OBSERVED")
        self.assertEqual(after["trades"][-1]["shares"],10.0)
        self.state=copy.deepcopy(after)
        rerun,status=self.settle(quotes=q,now=now)
        self.assertEqual(rerun,{})
        self.assertEqual(status["IL-044"]["status"],"already_settled")
        self.assertEqual(status["IL-044"]["marker"]["mode"],"STOP_OBSERVED")

    def test_daily_mark_retains_dividend_entitlement_after_intraday_sale(self):
        bought,_=self.settle()
        self.state=copy.deepcopy(bought[LEDGER])
        now=self.market["open"]+timedelta(minutes=31)
        sold,_=self.settle(quotes=self.quote_rows({"MSFT":94},now),now=now)
        snapshot=copy.deepcopy(sold[LEDGER])
        bars={"AAPL":{"Open":110.,"High":120.,"Low":105.,"Close":113.,
                      "Stock Splits":0,"Dividends":0},
              "MSFT":{"Open":95.,"High":100.,"Low":90.,"Close":94.,
                      "Stock Splits":0,"Dividends":1.}}
        changed=original.settle(snapshot,self.day,bars,{"TSLA":.12},[],.04,.15)
        self.assertEqual(changed["last_session"],self.day)
        self.assertIn("TSLA",changed["pending"]["buys"])
        self.assertEqual(len(changed["trades"]),2)
        self.assertEqual(changed["equity_history"].keys(),{self.previous,self.day})
        self.assertTrue(any(e["type"]=="observed_dividend_after_sale"
                            for e in changed["outage_events"]))
        self.assertAlmostEqual(
            changed["cash"], snapshot["cash"]+10.0, places=5)

    def test_full_daily_high_low_cannot_invent_genetic_fills(self):
        bars={"MSFT":{"Open":100.,"High":150.,"Low":50.,"Close":101.,
                      "Stock Splits":0,"Dividends":0}}
        result=original.settle(self.state,self.day,bars,{},[])
        self.assertEqual(result["positions"],self.state["positions"])
        self.assertEqual(result["trades"],[])
        self.assertEqual(result["pending"],{"buys":{},"sells":[]})
        self.assertEqual(result["last_session"],self.day)
        self.assertTrue(any(e["type"]=="missed_forward_open" for e in result["outage_events"]))
        self.assertTrue(any(e["type"]=="unexecuted_intraday_level"
                            for e in result["outage_events"]))

    def test_entry_day_corporate_action_requires_review(self):
        bought,_=self.settle()
        state=bought[LEDGER]
        bars={"AAPL":{"Open":110.,"High":120.,"Low":105.,"Close":112.,
                      "Stock Splits":2.,"Dividends":0.},
              "MSFT":{"Open":100.,"High":105.,"Low":98.,"Close":102.,
                      "Stock Splits":0.,"Dividends":0.}}
        with self.assertRaisesRegex(ValueError,"corporate action needs review"):
            original.settle(state,self.day,bars,{},[])


if __name__=="__main__":
    unittest.main()
