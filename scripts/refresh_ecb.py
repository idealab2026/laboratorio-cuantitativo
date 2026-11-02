#!/usr/bin/env python3
"""Fetch source-attributed ECB observations; never infer executable market quotes."""
import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

SERIES = "D.USD.EUR.SP00.A"
URL = "https://data-api.ecb.europa.eu/service/data/EXR/" + SERIES + "?lastNObservations=80&format=csvdata"
SOURCE = "European Central Bank (ECB statistics)"
NOTICE = "ECB reference rate: US dollars per one euro, NOT a transaction, bid/ask, open or close."
USER_AGENT = "IDEA-LAB-public-research/1.0 (+https://idealab2026.github.io/laboratorio-cuantitativo/)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/csv"}


def parse_ecb_csv(raw, received_at, today=None):
    today = today or datetime.now(timezone.utc).date()
    if not isinstance(raw, bytes) or not (30 < len(raw) <= 2_000_000):
        raise ValueError("ECB body absent or outside size cap")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", received_at):
        raise ValueError("Invalid UTC reception timestamp")
    text = raw.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text))
    needed = {"TIME_PERIOD", "OBS_VALUE", "FREQ", "CURRENCY", "CURRENCY_DENOM", "EXR_TYPE", "EXR_SUFFIX"}
    if reader.fieldnames is None or not needed.issubset(reader.fieldnames):
        raise ValueError("Unknown official CSV schema")
    rows = list(reader)
    if not (15 <= len(rows) <= 100):
        raise ValueError("Unexpected observation coverage")
    observations = []
    previous = None
    for item in rows:
        if [item["FREQ"], item["CURRENCY"], item["CURRENCY_DENOM"], item["EXR_TYPE"], item["EXR_SUFFIX"]] != [
            "D", "USD", "EUR", "SP00", "A"
        ]:
            raise ValueError("Unexpected ECB series dimensions")
        observed = date.fromisoformat(item["TIME_PERIOD"])
        raw_rate = str(item["OBS_VALUE"] or "").strip()
        if not re.fullmatch(r"\d+\.\d{1,8}", raw_rate):
            raise ValueError("Missing/nonliteral reference rate")
        rate = float(raw_rate)
        if not (0.6 <= rate <= 2.0):
            raise ValueError("Invalid EUR/USD reference magnitude")
        if observed > today or observed.weekday() >= 5:
            raise ValueError("Future or weekend fixing")
        if previous is not None and not (0 < (observed - previous).days <= 8):
            raise ValueError("Duplicate, unsorted or unexpectedly missing fixing dates")
        observations.append({"date": observed.isoformat(), "usd_per_eur": raw_rate})
        previous = observed
    if (today - previous).days > 8:
        raise ValueError("ECB feed stale")
    return {
        "status": "verified_observations",
        "data_class": "official_fx_reference_only",
        "series": SERIES,
        "quote_currency": "USD",
        "base_currency": "EUR",
        "source": SOURCE,
        "source_url": URL,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "received_at_utc": received_at,
        "latest_observation": previous.isoformat(),
        "count": len(observations),
        "not_tradable": True,
        "notice": NOTICE,
        "observations": observations,
    }


def validate_document(obj, today=None):
    if not isinstance(obj, dict) or set(obj) != {
        "status", "data_class", "series", "quote_currency", "base_currency", "source",
        "source_url", "source_sha256", "received_at_utc", "latest_observation",
        "count", "not_tradable", "notice", "observations",
    }:
        raise ValueError("Unknown publication document schema")
    fixed = {"status": "verified_observations", "data_class": "official_fx_reference_only",
             "series": SERIES, "quote_currency": "USD", "base_currency": "EUR",
             "source": SOURCE, "source_url": URL, "not_tradable": True, "notice": NOTICE}
    if any(obj.get(k) != v for k, v in fixed.items()):
        raise ValueError("False evidence or incorrect source attribution")
    if not re.fullmatch("[a-f0-9]{64}", str(obj["source_sha256"])):
        raise ValueError("Invalid source hash")
    if obj["count"] != len(obj["observations"]) or not (15 <= obj["count"] <= 100):
        raise ValueError("Invalid observation count")
    if obj["latest_observation"] != obj["observations"][-1].get("date"):
        raise ValueError("Inconsistent latest observation")
    if len(json.dumps(obj, ensure_ascii=False)) > 30000:
        raise ValueError("Oversized public data")
    header = "FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
    # Validate the same observation rules through canonical fixture values.
    synthesized = header + "".join(
        f'D,USD,EUR,SP00,A,{r["date"]},{r["usd_per_eur"]}\n' for r in obj["observations"]
    )
    parse_ecb_csv(synthesized.encode(), obj["received_at_utc"], today=today)
    return True


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path)
    cli.add_argument("--validate", type=Path)
    args = cli.parse_args()
    if (args.output is None) == (args.validate is None):
        cli.error("Exactly one of --output/--validate required")
    if args.validate:
        obj = json.loads(args.validate.read_text(encoding="utf-8"))
        validate_document(obj)
        print("ECB public release validated: " + obj["latest_observation"])
        return
    request = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=22) as response:
        if response.status != 200 or response.geturl() != URL:
            raise RuntimeError("Unverified ECB response or redirect")
        raw = response.read(2_000_001)
    when = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = parse_ecb_csv(raw, when)
    validate_document(doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Source: ECB statistics | reference only | "
          + doc["latest_observation"] + " | " + str(doc["count"]) + " verified records")


if __name__ == "__main__":
    main()
