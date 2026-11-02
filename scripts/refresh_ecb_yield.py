#!/usr/bin/env python3
"""Official ECB euro area AAA 10Y spot yield; macro reference, not a price or DCF."""
import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request
from datetime import datetime, date, timezone
from pathlib import Path

KEY = "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
URL = "https://data-api.ecb.europa.eu/service/data/YC/" + KEY + "?lastNObservations=60&format=csvdata"
SOURCE = "European Central Bank (ECB statistics)"
NOTICE = "Euro area AAA government 10-year modelled spot yield, percent per annum, continuously compounded. Not a security quote, guaranteed risk-free rate, or automatic DCF assumption."
FIELDS = {"FREQ":"B","REF_AREA":"U2","CURRENCY":"EUR","PROVIDER_FM":"4F",
          "INSTRUMENT_FM":"G_N_A","PROVIDER_FM_ID":"SV_C_YM","DATA_TYPE_FM":"SR_10Y"}


def parse(raw,received,today=None):
    today=today or datetime.now(timezone.utc).date()
    if not isinstance(raw,bytes) or not 200<len(raw)<2_000_000:
        raise ValueError("ECB YC payload missing or oversize")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",received):
        raise ValueError("Missing UTC provenance")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames or not {"TIME_PERIOD","OBS_VALUE",*FIELDS}.issubset(reader.fieldnames):
        raise ValueError("ECB YC schema mismatch")
    rows=list(reader)
    if not 20<=len(rows)<=80: raise ValueError("Unexpected yield curve observation count")
    observations=[]
    previous=None
    for row in rows:
        if any(row.get(k)!=v for k,v in FIELDS.items()):
            raise ValueError("Not AAA euro area ten-year spot series")
        day=date.fromisoformat(row["TIME_PERIOD"])
        val=str(row.get("OBS_VALUE") or "").strip()
        if not re.fullmatch(r"-?\d+(?:\.\d{1,20})?",val):
            raise ValueError("Missing or invalid ECB spot yield: date="+repr(row.get("TIME_PERIOD"))+" literal="+repr(val[:45]))
        num=float(val)
        if not -5<=num<=15 or day>today or day.weekday()>=5:
            raise ValueError("Invalid fixing date or percentage range")
        if previous is not None and not 0<(day-previous).days<=8:
            raise ValueError("Duplicate, unordered or missing yield observations")
        observations.append({"date":day.isoformat(),"yield_pct":val})
        previous=day
    if (today-previous).days>8:
        raise ValueError("Stale ECB yield curve reference")
    return {"status":"verified_ecb_macro_observations","data_class":"official_aaa_euro_10y_spot_yield",
            "series":KEY,"source":SOURCE,"source_url":URL,
            "raw_sha256":hashlib.sha256(raw).hexdigest(),"received_at_utc":received,
            "latest_date":previous.isoformat(),"count":len(observations),
            "unit":"percent_per_annum","notice":NOTICE,"observations":observations}


def validate(doc,today=None):
    fields={"status":"verified_ecb_macro_observations","data_class":"official_aaa_euro_10y_spot_yield",
            "series":KEY,"source":SOURCE,"source_url":URL,"unit":"percent_per_annum","notice":NOTICE}
    if not isinstance(doc,dict) or set(doc)!=set(fields)|{"raw_sha256","received_at_utc","latest_date","count","observations"}:
        raise ValueError("Unapproved macro source structure")
    if any(doc[k]!=v for k,v in fields.items()) or not re.fullmatch("[a-f0-9]{64}",doc["raw_sha256"]):
        raise ValueError("Wrong ECB source identity")
    if doc["count"]!=len(doc["observations"]):
        raise ValueError("Source observation count differs")
    lines=[",".join([*FIELDS,"TIME_PERIOD","OBS_VALUE"])]
    for item in doc["observations"]:
        if set(item)!={"date","yield_pct"}:raise ValueError("Unknown ECB macro observation")
        lines.append(",".join([*FIELDS.values(),item["date"],item["yield_pct"]]))
    parse(("\n".join(lines)+"\n").encode(),doc["received_at_utc"],today=today)
    if doc["latest_date"]!=doc["observations"][-1]["date"]:
        raise ValueError("Latest spot date differs")
    return True


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path)
    parser.add_argument("--validate",type=Path)
    a=parser.parse_args()
    if (a.out is None)==(a.validate is None):parser.error("Specify out or validate")
    if a.validate:
        validate(json.loads(a.validate.read_text(encoding="utf8")))
        print("ECB AAA 10Y source verified")
        return
    req=urllib.request.Request(URL,headers={"User-Agent":"IDEA-LAB-public-research/1.0 (+https://idealab2026.github.io/laboratorio-cuantitativo/)","Accept":"text/csv"})
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.status!=200 or response.geturl()!=URL:raise RuntimeError("Unexpected ECB source response")
        raw=response.read(2_000_001)
    received=datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc=parse(raw,received)
    validate(doc)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("ECB AAA euro 10Y yield | "+doc["latest_date"]+" | "+str(doc["count"])+" values | official macro reference only")


if __name__=="__main__":
    main()
