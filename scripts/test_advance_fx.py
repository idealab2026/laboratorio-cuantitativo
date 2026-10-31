import copy
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from advance_fx import advance, empty_ledger, event_hash, verify_ledger
from refresh_ecb import SERIES, SOURCE, URL, NOTICE, validate_document


def official_fixture(upto=None):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stop = now.date()
    days = []
    for ago in range(45, -1, -1):
        day = stop - timedelta(days=ago)
        if day.weekday() < 5:
            days.append(day)
    if upto is not None:
        days = days[:upto]
    observations = [{"date": d.isoformat(), "usd_per_eur":format(Decimal("1.1000")+Decimal(i)/10000, ".4f")}
                    for i,d in enumerate(days)]
    return {
        "status": "verified_observations", "data_class":"official_fx_reference_only",
        "series":SERIES,"quote_currency":"USD","base_currency":"EUR",
        "source":SOURCE,"source_url":URL, "source_sha256":hashlib.sha256(
            json.dumps(observations,sort_keys=True).encode()).hexdigest(),
        "received_at_utc":now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "latest_observation":observations[-1]["date"],"count":len(observations),
        "not_tradable":True,"notice":NOTICE,"observations":observations
    }


class ProspectiveFXTests(unittest.TestCase):
    def test_first_run_is_only_pending_future_forecast(self):
        data=official_fixture()
        ledger=empty_ledger()
        self.assertEqual(advance(ledger,data),1)
        self.assertTrue(verify_ledger(ledger))
        self.assertEqual(len(ledger["events"]),1)
        issued=ledger["events"][0]
        self.assertEqual(issued["event_type"],"issued")
        self.assertEqual(issued["fixing_date"],data["latest_observation"])
        self.assertEqual(issued["observed_rate"],data["observations"][-1]["usd_per_eur"])
        self.assertEqual(len(issued["predictions"]),3)
        self.assertFalse(any("return" in k or "pnl" in k or "profit" in k for k in issued))
        self.assertEqual(advance(ledger,data),0)

    def test_next_official_fixing_scores_only_prior_issued_signal(self):
        whole=official_fixture()
        first=copy.deepcopy(whole)
        first["observations"]=first["observations"][:-1]
        first["latest_observation"]=first["observations"][-1]["date"]
        first["count"]=len(first["observations"])
        ledger=empty_ledger()
        self.assertEqual(advance(ledger,first),1)
        pending=ledger["events"][0]
        self.assertEqual(advance(ledger,whole),2)
        issued,resolved,next_issue=ledger["events"]
        self.assertEqual(issued,pending)
        self.assertEqual(resolved["event_type"],"resolved")
        self.assertEqual(resolved["signal_hash"],pending["hash"])
        self.assertEqual(resolved["realized_fixing_date"],whole["latest_observation"])
        self.assertEqual(next_issue["event_type"],"issued")
        self.assertEqual(next_issue["fixing_date"],whole["latest_observation"])
        self.assertEqual(resolved["absolute_errors"]["unchanged"],"0.000100")
        self.assertTrue(verify_ledger(ledger))
        self.assertEqual(advance(ledger,whole),0)

    def test_delayed_feed_resolves_only_the_first_next_available_fixing(self):
        all_data=official_fixture()
        prior=copy.deepcopy(all_data)
        prior["observations"]=prior["observations"][:-3]
        prior["count"]=len(prior["observations"])
        prior["latest_observation"]=prior["observations"][-1]["date"]
        ledger=empty_ledger()
        advance(ledger,prior)
        self.assertEqual(advance(ledger,all_data),2)
        self.assertEqual(ledger["events"][1]["realized_fixing_date"],all_data["observations"][-3]["date"])
        self.assertEqual(ledger["events"][2]["fixing_date"],all_data["latest_observation"])
        self.assertFalse(any(x["event_type"]=="issued" and x["fixing_date"]==all_data["observations"][-2]["date"]
                             for x in ledger["events"]))
        self.assertTrue(verify_ledger(ledger))

    def test_hash_chain_detects_tampering_and_unapproved_methods(self):
        ledger=empty_ledger()
        advance(ledger,official_fixture())
        bad=copy.deepcopy(ledger)
        bad["events"][0]["observed_rate"]="1.9876"
        with self.assertRaisesRegex(ValueError,"digest"):
            verify_ledger(bad)
        bad=copy.deepcopy(ledger)
        bad["events"][0]["predictions"]["invented_model"]="1.234567"
        bad["events"][0]["hash"]=event_hash(bad["events"][0])
        with self.assertRaisesRegex(ValueError,"algorithm"):
            verify_ledger(bad)

    def test_expired_old_pending_signal_fails_closed(self):
        ledger=empty_ledger()
        advance(ledger,official_fixture())
        stale=official_fixture()
        stale["observations"]=stale["observations"][1:]
        stale["count"]=len(stale["observations"])
        # Force an unknown formerly outstanding source date, without mutating the ledger.
        out=copy.deepcopy(ledger)
        out["events"][0]["fixing_date"]="2026-01-02"
        out["events"][0]["hash"]=event_hash(out["events"][0])
        self.assertTrue(verify_ledger(out))
        with self.assertRaisesRegex(ValueError,"expired source window"):
            advance(out,stale)

    def test_user_history_is_not_backfilled_from_observations(self):
        data=official_fixture()
        ledger=empty_ledger()
        advance(ledger,data)
        self.assertEqual(sum(x["event_type"]=="issued" for x in ledger["events"]),1)
        self.assertGreater(len(data["observations"]),15)
        self.assertNotIn("positions",ledger)
        self.assertNotIn("brokers",ledger)


if __name__=="__main__":
    unittest.main()
