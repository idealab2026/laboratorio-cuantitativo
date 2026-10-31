#!/usr/bin/env python3
"""Public issuer filing register from SEC EDGAR, never a stock quote or valuation."""
import argparse
import hashlib
import json
import re
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROSTER = {
    "ADBE": "0000796343", "AMZN": "0001018724", "CAT": "0000018230",
    "META": "0001326801", "MSFT": "0000789019", "NET": "0001477333",
    "NFLX": "0001065280", "PLTR": "0001321655",
}
SOURCE = "U.S. Securities and Exchange Commission (EDGAR submissions)"
ROOT = "https://data.sec.gov/submissions/"
NOTICE = "Official filing metadata only. NOT audited financial calculations, a stock price, or an approved investment thesis."
UA = "IDEA LAB Research 350414243+idealab2026@users.noreply.github.com (https://github.com/idealab2026/laboratorio-cuantitativo/issues)"
FORMATS = ("10-K", "10-Q", "8-K")
PATTERN = re.compile(r"^\d{10}$")
ACC = re.compile(r"^\d{10}-\d{2}-\d{6}$")
FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
HEX = re.compile(r"^[0-9a-f]{64}$")


def source_url(cik):
    if cik not in ROSTER.values():
        raise ValueError("CIK not in the independently selected public roster")
    return ROOT + "CIK" + cik + ".json"


def empty():
    return {"schema": "sec_filing_catalog_v1", "data_class": "official_sec_filings_only",
            "status": "not_collected", "generated_at_utc": None, "source": SOURCE,
            "notice": NOTICE, "issuers": []}


def parse_submission(ticker, raw, received, current_day=None):
    current_day = current_day or datetime.now(timezone.utc).date()
    cik = ROSTER[ticker]
    if not isinstance(raw, bytes) or not (1000 < len(raw) < 8_000_000):
        raise ValueError("Empty or unbounded official response")
    if not STAMP.fullmatch(received):
        raise ValueError("Invalid UTC collection time")
    obj = json.loads(raw)
    if int(obj.get("cik", -1)) != int(cik) or ticker not in obj.get("tickers", []):
        raise ValueError("SEC company identity disagrees with ticker/CIK roster")
    recent = obj.get("filings", {}).get("recent", {})
    fields = ("form", "accessionNumber", "filingDate", "reportDate", "primaryDocument")
    if any(not isinstance(recent.get(f), list) for f in fields):
        raise ValueError("Missing official filing field")
    size = len(recent["form"])
    if size < 4 or any(len(recent[f]) != size for f in fields):
        raise ValueError("Misaligned SEC filing arrays")
    selected = []
    seen = set()
    for i, form in enumerate(recent["form"]):
        if form not in FORMATS:
            continue
        accession, filed, reported, document = (
            recent["accessionNumber"][i], recent["filingDate"][i],
            recent["reportDate"][i], recent["primaryDocument"][i]
        )
        if not ACC.fullmatch(str(accession)) or not DAY.fullmatch(str(filed)):
            raise ValueError("Invalid accession or filing date")
        if not isinstance(document, str) or not FILE.fullmatch(document) or ".." in document:
            raise ValueError("Unsafe or absent primary document")
        filing_date = date.fromisoformat(filed)
        if filing_date > current_day:
            raise ValueError("SEC return contains a future-dated filing")
        if reported and (not DAY.fullmatch(str(reported)) or date.fromisoformat(reported) > current_day):
            raise ValueError("Invalid reported period")
        if accession in seen:
            raise ValueError("Duplicate accession number")
        seen.add(accession)
        selected.append({
            "form": form, "accession": accession, "filed": filed,
            "report_date": reported or None, "primary_document": document,
            "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"
        })
        if len(selected) >= 12:
            break
    if not selected or any(x not in {f["form"] for f in selected} for x in ("10-K", "10-Q")):
        raise ValueError("Insufficient 10-K and 10-Q coverage")
    if any(selected[i]["filed"] < selected[i + 1]["filed"] for i in range(len(selected) - 1)):
        raise ValueError("Unexpected SEC submissions ordering")
    name = obj.get("name")
    if not isinstance(name, str) or not (2 <= len(name) <= 150):
        raise ValueError("SEC company legal name unavailable")
    return {
        "ticker": ticker, "cik": cik, "sec_name": name,
        "source_url": source_url(cik), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at_utc": received, "filings": selected,
    }


def validate_document(doc, expected_roster=ROSTER):
    fixed = {"schema": "sec_filing_catalog_v1", "data_class": "official_sec_filings_only",
             "source": SOURCE, "notice": NOTICE}
    if not isinstance(doc, dict) or set(doc) != set(fixed) | {"status", "generated_at_utc", "issuers"}:
        raise ValueError("Unexpected SEC publication structure")
    if any(doc.get(k) != v for k, v in fixed.items()):
        raise ValueError("Wrong source or security class")
    status = doc["status"]
    if status == "not_collected":
        if doc["generated_at_utc"] is not None or doc["issuers"] != []:
            raise ValueError("A placeholder must not contain purported filings")
        return True
    if status != "verified_filings" or not STAMP.fullmatch(str(doc["generated_at_utc"])):
        raise ValueError("No verified collection timestamp")
    issuers = doc.get("issuers")
    if not isinstance(issuers, list) or len(issuers) != len(expected_roster):
        raise ValueError("Partial or mixed issuer release")
    if set(x.get("ticker") for x in issuers) != set(expected_roster):
        raise ValueError("Issuer roster mismatch")
    for record in issuers:
        ticker = record["ticker"]
        if set(record) != {"ticker", "cik", "sec_name", "source_url",
                           "source_sha256", "retrieved_at_utc", "filings"}:
            raise ValueError("Unexpected company record field")
        cik = record["cik"]
        if cik != expected_roster[ticker] or record["source_url"] != source_url(cik):
            raise ValueError("Unverified CIK/source pairing")
        if not HEX.fullmatch(str(record["source_sha256"])) or not STAMP.fullmatch(str(record["retrieved_at_utc"])):
            raise ValueError("Missing raw SEC provenance")
        if not isinstance(record["sec_name"], str) or len(record["sec_name"]) > 150:
            raise ValueError("Company identity invalid")
        items = record["filings"]
        if not isinstance(items, list) or not (2 <= len(items) <= 12):
            raise ValueError("Missing filing evidence")
        seen = set()
        for item in items:
            if set(item) != {"form", "accession", "filed", "report_date", "primary_document", "url"}:
                raise ValueError("Unknown SEC filing schema")
            if item["form"] not in FORMATS or not ACC.fullmatch(item["accession"]) or item["accession"] in seen:
                raise ValueError("Invalid filing identifier")
            seen.add(item["accession"])
            if not DAY.fullmatch(item["filed"]) or (item["report_date"] is not None
                 and not DAY.fullmatch(item["report_date"])):
                raise ValueError("Invalid SEC date")
            if date.fromisoformat(item["filed"]) > date.fromisoformat(record["retrieved_at_utc"][:10]):
                raise ValueError("Future filing relative to source retrieval")
            document = item["primary_document"]
            if not FILE.fullmatch(document) or ".." in document:
                raise ValueError("Untrusted filing document path")
            expected = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{item['accession'].replace('-', '')}/{document}"
            if item["url"] != expected:
                raise ValueError("Untrusted filing URL")
        if not {"10-K", "10-Q"}.issubset(x["form"] for x in items):
            raise ValueError("Required annual/quarterly source absent")
    if len(json.dumps(doc)) > 100_000:
        raise ValueError("Oversized SEC public release")
    return True


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--out", type=Path)
    cli.add_argument("--validate", type=Path)
    args = cli.parse_args()
    if (args.out is None) == (args.validate is None):
        cli.error("Choose exactly one of --out or --validate")
    if args.validate:
        validate_document(json.loads(args.validate.read_text(encoding="utf-8")))
        print("SEC issuer archive structure validated")
        return
    received = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    issuers = []
    for ticker in sorted(ROSTER):
        url = source_url(ROSTER[ticker])
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=24) as response:
            if response.status != 200 or response.geturl() != url:
                raise RuntimeError(f"{ticker}: SEC source request did not return the expected endpoint")
            raw = response.read(8_000_000)
        issuers.append(parse_submission(ticker, raw, received))
        time.sleep(0.4)
    doc = {"schema": "sec_filing_catalog_v1", "data_class": "official_sec_filings_only",
           "status": "verified_filings", "generated_at_utc": received,
           "source": SOURCE, "notice": NOTICE, "issuers": issuers}
    validate_document(doc)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SEC filings verified: {len(issuers)} institutional issuers, "
          f"{sum(len(x['filings']) for x in issuers)} SEC filings; no prices or private documents")


if __name__ == "__main__":
    main()
