import json
import unittest
from copy import deepcopy
from datetime import date,timedelta
from classic_503 import MODELS
from classic_503_book import (
    SCHEMA, CONFIG_SHA, blank_state, verify_book, advance, summary_rows,
)
from yahoo_source import DEFAULT_UNIVERSE, prepare_snapshot

KEY="test-only-institutional-source-ledger-key-not-deployed-9876"
UNIVERSE=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"]
DAYS=[]
day=date(2026,1,5)
while len(DAYS)<82:
    if day.weekday()<5:DAYS.append(day.isoformat())
    day+=timedelta(days=1)


def panel(n,*,missing=None,split=False):
    history={}
    for ticker in UNIVERSE+["SPY"]:
        rows=[]
        for idx,day in enumerate(DAYS[:n]):
            close=(200 if ticker=="SPY" else 80)+idx*.1
            if split and idx==n-1 and ticker=="AAPL":close/=2
            rows.append({"date":day,"open":close,"high":close*1.015,
                "low":close*.985,"close":close,"volume":100000,
                "dividend":.5 if split and idx==n-1 and ticker=="AAPL" else 0,
                "split":2 if split and idx==n-1 and ticker=="AAPL" else 0})
        if ticker!=missing:history[ticker]=rows
        else:history[ticker]=rows[:-1]
    latest={k:v[-1] for k,v in history.items() if v and v[-1]["date"]==DAYS[n-1]}
    snap=prepare_snapshot(UNIVERSE,DAYS[n-1],latest,DAYS[n-1]+"T23:20:00Z")
    return history,snap


class OriginalSizedClassicBooks(unittest.TestCase):
    def test_new_campaign_only_frozen_closing_signals_with_503_distinct_equity_intents(self):
        history,snap=panel(80)
        book=advance(blank_state(),snap,history,key=KEY)
        self.assertTrue(verify_book(book,KEY))
        self.assertEqual(book["config_sha256"],CONFIG_SHA)
        self.assertEqual(book["session"],DAYS[79])
        self.assertEqual(set(book["books"]),set(MODELS))
        equal=book["books"]["IL-010"]
        self.assertEqual(len(equal["pending"]),503)
        self.assertEqual(equal["cash"],100000)
        self.assertEqual(equal["holdings"],{})
        self.assertEqual(equal["history"],[{"date":DAYS[79],"nav":100000}])
        self.assertEqual(len(book["books"]["IL-018"]["pending"]),1)
        self.assertEqual(book["books"]["IL-018"]["pending"][0]["ticker"],"SPY")
        rows=summary_rows(book,snap,key=KEY)
        self.assertEqual(len(rows),9)
        self.assertTrue(all(x["positions"]==0 and x["day_return_pct"] is None for x in rows))

    def test_next_market_open_makes_503_equal_weight_fills_and_separate_spy_notional(self):
        history,first=panel(80)
        book=advance(blank_state(),first,history,key=KEY)
        next_history,next_bar=panel(81)
        result=advance(book,next_bar,next_history,key=KEY)
        self.assertTrue(verify_book(result,KEY))
        eq=result["books"]["IL-010"]
        index=result["books"]["IL-018"]
        self.assertEqual(len(eq["holdings"]),503)
        self.assertEqual(len(index["holdings"]),1)
        self.assertAlmostEqual(eq["cash"],5000,delta=.15)
        self.assertAlmostEqual(index["cash"],5000,delta=.15)
        self.assertEqual(len([x for x in eq["events"] if x["type"]=="BUY"]),503)
        self.assertEqual(len(eq["history"]),2)
        self.assertEqual(len(index["history"]),2)
        self.assertNotEqual(eq["history"][-1]["nav"],index["history"][-1]["nav"])
        self.assertTrue(all(q["signalAt"]==DAYS[80] for q in eq["pending"]))

    def test_unpriced_holding_quarantined_without_marking_other_books(self):
        old,first=panel(80)
        a=advance(blank_state(),first,old,key=KEY)
        history,second=panel(81)
        b=advance(a,second,history,key=KEY)
        third_history,third=panel(82,missing="AAPL")
        c=advance(b,third,third_history,key=KEY)
        eq=c["books"]["IL-010"]
        index=c["books"]["IL-018"]
        self.assertEqual(eq["paused"]["since"],DAYS[81])
        self.assertEqual(eq["paused"]["missing"],["AAPL"])
        self.assertEqual(eq["history"][-1]["date"],DAYS[80])
        self.assertEqual(index["history"][-1]["date"],DAYS[81])
        summary=summary_rows(c,third,key=KEY)
        self.assertEqual(summary[0]["activity"],"paused")
        self.assertEqual(summary[0]["last_session"],DAYS[80])
        self.assertEqual(summary[-1]["last_session"],DAYS[81])

    def test_reject_revision_missing_spy_and_state_tampering(self):
        history,source=panel(80)
        book=advance(blank_state(),source,history,key=KEY)
        altered=deepcopy(book);altered["books"]["IL-010"]["cash"]+=3
        with self.assertRaisesRegex(ValueError,"signature"):
            verify_book(altered,KEY)
        with self.assertRaisesRegex(ValueError,"Duplicate or reversed"):
            advance(book,source,history,key=KEY)
        wrong=deepcopy(history);wrong["AAPL"][-1]["close"]*=1.02
        with self.assertRaisesRegex(ValueError,"capture disagree"):
            advance(blank_state(),source,wrong,key=KEY)
        without=deepcopy(history);without.pop("SPY")
        with self.assertRaisesRegex(ValueError,"benchmark absent"):
            advance(blank_state(),source,without,key=KEY)

    def test_dividend_and_split_corporate_actions_update_existing_share_counts(self):
        first_history,first=panel(80)
        a=advance(blank_state(),first,first_history,key=KEY)
        second_history,second=panel(81)
        b=advance(a,second,second_history,key=KEY)
        before=b["books"]["IL-010"]["holdings"]["AAPL"]["shares"]
        third_history,third=panel(82,split=True)
        c=advance(b,third,third_history,key=KEY)
        updated=c["books"]["IL-010"]
        self.assertAlmostEqual(updated["holdings"]["AAPL"]["shares"],2*before,places=5)
        self.assertGreater(updated["holdings"]["AAPL"]["dividends"],0)
        self.assertTrue(any(x["type"]=="SPLIT" and x["symbol"]=="AAPL" for x in updated["events"]))


if __name__=="__main__":unittest.main()
