import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from refresh_sec import ROSTER, SOURCE, NOTICE, empty, parse_submission, source_url, validate_document, declared_user_agent

STAMP = "2026-10-31T16:00:00Z"


def sample_raw(ticker="MSFT"):
    cik = int(ROSTER[ticker])
    forms = ["8-K", "10-Q", "8-K", "10-K"]
    dates = ["2026-10-29", "2026-10-28", "2026-08-02", "2026-07-30"]
    return json.dumps({
        "cik": cik, "name": ticker + " INC.", "tickers": [ticker],
        "filings": {"recent": {
            "form": forms,
            "accessionNumber": [f"{cik:010d}-26-{i:06d}" for i in range(1, 5)],
            "filingDate": dates, "reportDate": ["2026-10-28", "2026-09-30", "", "2026-06-30"],
            "primaryDocument": ["entry.htm", "quarter10q.htm", "news.htm", "annual10k.htm"]
        }}
    }).encode()


class FilingSourceTests(unittest.TestCase):
    def test_placeholder_never_asserts_filing_coverage(self):
        self.assertTrue(validate_document(empty()))
        self.assertEqual(empty()["issuers"], [])
        self.assertEqual(empty()["status"], "not_collected")

    def test_institutional_roster_and_safe_edgar_primary_links(self):
        self.assertEqual(len(ROSTER), 8)
        rec = parse_submission("MSFT", sample_raw(), STAMP)
        self.assertEqual(rec["source_url"], source_url(ROSTER["MSFT"]))
        self.assertEqual(rec["source_sha256"], hashlib.sha256(sample_raw()).hexdigest())
        self.assertEqual(rec["filings"][0]["form"], "8-K")
        self.assertEqual(rec["filings"][1]["form"], "10-Q")
        self.assertEqual(rec["filings"][-1]["form"], "10-K")
        self.assertTrue(rec["filings"][0]["url"].startswith("https://www.sec.gov/Archives/edgar/data/"))
        self.assertTrue(rec["filings"][0]["url"].endswith("/entry.htm"))

    def test_rejects_wrong_company_future_filing_or_html_path_injection(self):
        original = json.loads(sample_raw())
        for mutate in [
            lambda obj: obj.update(cik=42),
            lambda obj: obj.update(tickers=["OTHER"]),
            lambda obj: obj["filings"]["recent"]["filingDate"].__setitem__(0, "2031-01-01"),
            lambda obj: obj["filings"]["recent"]["primaryDocument"].__setitem__(0, "../secret.json"),
            lambda obj: obj["filings"]["recent"]["accessionNumber"].__setitem__(0, "hacked"),
            lambda obj: obj["filings"]["recent"]["form"].__setitem__(3, "S-1"),
        ]:
            o = copy.deepcopy(original)
            mutate(o)
            with self.assertRaises((ValueError, KeyError)):
                parse_submission("MSFT", json.dumps(o).encode(), STAMP)

    def test_rejects_partial_and_changed_public_release_provenance(self):
        docs = [parse_submission(ticker, sample_raw(ticker), STAMP) for ticker in sorted(ROSTER)]
        doc = {"schema": "sec_filing_catalog_v1", "data_class": "official_sec_filings_only",
               "status": "verified_filings", "generated_at_utc": STAMP,
               "source": SOURCE, "notice": NOTICE, "issuers": docs}
        self.assertTrue(validate_document(doc))
        for mutate in [
            lambda obj: obj["issuers"].pop(),
            lambda obj: obj["issuers"][0].update(source_sha256="abcdef"),
            lambda obj: obj["issuers"][0]["filings"][0].update(url="https://example.org/untrusted"),
            lambda obj: obj["issuers"][0].update(cik="0000000000"),
            lambda obj: obj.update(status="approved_theses"),
        ]:
            o = copy.deepcopy(doc)
            mutate(o)
            with self.assertRaises((ValueError, TypeError, KeyError)):
                validate_document(o)

    def test_canonical_placeholder_and_public_issuer_mapping_are_consistent(self):
        root = Path(__file__).resolve().parents[1]
        canonical = json.loads((root / "data/sec-filings.json").read_text(encoding="utf8"))
        self.assertTrue(validate_document(canonical))
        demo = json.loads((root / "data/demo.json").read_text(encoding="utf8"))
        mapping = {x["ticker"]: x.get("secCik") for x in demo["issuerCatalog"]["issuers"] if x.get("secCik")}
        self.assertEqual(mapping, ROSTER)


    def test_sec_contact_must_be_monitored_institutional_email_and_never_written_to_source(self):
        for contact in ("", "350414243+idealab2026@users.noreply.github.com", "plain-text", "tester@example"):
            with patch.dict("os.environ", {"SEC_CONTACT_EMAIL": contact}):
                with self.assertRaisesRegex(RuntimeError, "monitored institutional"):
                    declared_user_agent()
        with patch.dict("os.environ", {"SEC_CONTACT_EMAIL": "research@institution.example"}):
            self.assertIn("IDEA LAB Research research@institution.example", declared_user_agent())


if __name__ == "__main__":
    unittest.main()
