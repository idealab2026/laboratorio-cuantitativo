"""Market recovery must be reproducible from exact provider receipts."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_data import verified_chart as v
from market_data.snapshot import _digest, make_snapshot, write_immutable
from market_data.revisions import append_missing, load_effective

DAY="2026-11-04"


def response(url, timestamps, rows, symbol="DECK", currency="USD", events=None):
    body={"chart":{"error":None,"result":[{"meta":{"symbol":symbol,"currency":currency,
          "exchangeTimezoneName":"America/New_York"},"timestamp":timestamps,
          "indicators":{"quote":[{k:[r[k] for r in rows] for k in ("open","high","low","close","volume")}]}}]}}
    if events: body["chart"]["result"][0]["events"]=events
    raw=json.dumps(body)
    return {"url":url,"raw":raw,"sha256":hashlib.sha256(raw.encode()).hexdigest()}


def receipt(day=DAY, invalid=True):
    opening,closing=v.session_bounds(day)
    daily_url,tape_url=v.urls("DECK",day)
    daily={"open":100.,"close":101.,"high":103.,"low":100.5 if invalid else 99.,"volume":12345.}
    times=list(range(opening,closing,300))
    bars=[{"open":100.,"close":101.,"high":103.,"low":99.,"volume":10.} for _ in times]
    doc={"schema":v.SCHEMA,"method":v.RANGE if invalid else v.RAW,"session":day,"provider_symbol":"DECK",
         "daily":response(daily_url,[opening],[daily]),
         "intraday":response(tape_url,times,bars) if invalid else None}
    doc["sha256"]=_digest(doc)
    return doc


def mutate_response(doc,which,change):
    data=json.loads(doc[which]["raw"]);change(data["chart"]["result"][0])
    doc[which]["raw"]=json.dumps(data)
    doc[which]["sha256"]=hashlib.sha256(doc[which]["raw"].encode()).hexdigest()
    doc["sha256"]=_digest(doc)


class VerifiedChartTests(unittest.TestCase):
    def test_valid_raw_daily_is_kept_verbatim_without_tape(self):
        r=receipt(invalid=False)
        bar=v.reconstruct(r)
        self.assertEqual((bar["open"],bar["high"],bar["low"],bar["close"],bar["volume"]),(100.,103.,99.,101.,12345.))
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            return io.BytesIO(r["daily"]["raw"].encode())
        result,evidence=v.fetch_verified_bar("DECK",DAY,opener)
        self.assertEqual(result,bar);self.assertEqual(evidence["method"],v.RAW);self.assertEqual(len(calls),1)

    def test_invalid_range_uses_observed_tape_extrema_not_clipped_open_or_close(self):
        r=receipt();bar=v.reconstruct(r)
        self.assertEqual(bar["low"],99.)  # Not the daily low 100.5 or clipped open 100.
        self.assertEqual(bar["volume"],12345.)  # RAW daily volume, not partial tape volume.
        payloads={r[k]["url"]:r[k]["raw"] for k in ("daily","intraday")}
        found,evidence=v.fetch_verified_bar("DECK",DAY,lambda req,timeout:io.BytesIO(payloads[req.full_url].encode()))
        self.assertEqual(found,bar);self.assertEqual(evidence["method"],v.RANGE)

    def test_rejects_a_single_missing_duplicate_extra_or_extended_session_bar(self):
        for mode in ("missing","duplicate","extended","outside"):
            r=receipt()
            def change(x):
                if mode=="missing":
                    x["timestamp"].pop(3)
                    for values in x["indicators"]["quote"][0].values(): values.pop(3)
                elif mode=="duplicate":x["timestamp"][3]=x["timestamp"][2]
                elif mode=="extended":x["timestamp"][0]-=300
                else:x["timestamp"][-1]+=600
            mutate_response(r,"intraday",change)
            with self.assertRaises(ValueError):v.reconstruct(r)

    def test_rejects_daily_anchor_disagreement_and_invalid_tape_fields(self):
        for field,value in (("open",100.1),("close",102.),("low",102.),("volume",None)):
            r=receipt()
            def change(x):
                i=0 if field=="open" else -1
                x["indicators"]["quote"][0][field][i]=value
            mutate_response(r,"intraday",change)
            with self.assertRaises(ValueError):v.reconstruct(r)

    def test_rejects_wrong_instrument_currency_day_and_corporate_action(self):
        changes=[lambda x:x["meta"].update(symbol="MSFT"),
                 lambda x:x["meta"].update(currency="EUR"),
                 lambda x:x["timestamp"].__setitem__(0,x["timestamp"][0]-86400),
                 lambda x:x.update(events={"splits":{"1":{"date":v.session_bounds(DAY)[0],"numerator":2}}})]
        for change in changes:
            r=receipt();mutate_response(r,"daily",change)
            with self.assertRaises(ValueError):v.reconstruct(r)

    def test_receipt_hash_or_unapproved_location_cannot_pass(self):
        r=receipt();r["intraday"]["raw"]+=" "
        r["sha256"]=_digest(r)
        with self.assertRaises(ValueError):v.reconstruct(r)
        r=receipt();r["daily"]["url"]="https://example.com/unreviewed";r["sha256"]=_digest(r)
        with self.assertRaises(ValueError):v.reconstruct(r)

    def test_early_close_calendar_requires_actual_short_session(self):
        r=receipt("2026-11-27")
        opening,closing=v.session_bounds(r["session"])
        self.assertEqual((closing-opening)//300,42)
        self.assertEqual(v.reconstruct(r)["close"],101.)

    def test_existing_valid_daily_cannot_be_rederived(self):
        r=receipt(invalid=False);r["method"]=v.RANGE;r["sha256"]=_digest(r)
        with self.assertRaises(ValueError):v.reconstruct(r)

    def test_full_receipts_revalidate_on_load_and_base_stays_byte_identical(self):
        r=receipt();bar=v.reconstruct(r)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);symbols=["DECK"]+["S%03d"%i for i in range(502)]
            source=make_snapshot(DAY,symbols,{"SPY":{**bar,"provider_symbol":"SPY"}},captured_at_utc="2026-11-04T23:30:00+00:00")
            path,_=write_immutable(root,source);before=path.read_bytes()
            revision,doc=append_missing(root,DAY,{"DECK":bar},captured_at_utc="2026-11-05T00:10:00+00:00",observation_evidence={"DECK":r})
            self.assertEqual(load_effective(root,DAY)["bars"]["DECK"],bar)
            self.assertEqual(path.read_bytes(),before)
            # Even recomputing both public hashes cannot conceal evidence/bar mismatch.
            doc["bars"]["DECK"]["low"]=98.;doc["sha256"]=_digest(doc)
            revision.unlink();(revision.parent/(doc["sha256"]+".json")).write_text(json.dumps(doc))
            with self.assertRaises(ValueError):load_effective(root,DAY)


if __name__=="__main__":unittest.main()
