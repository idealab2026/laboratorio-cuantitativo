import unittest
from datetime import date, timedelta
from hashlib import sha256

from refresh_ecb import parse_ecb_csv, validate_document, SERIES, URL

AT = "2026-10-31T15:00:00Z"
TODAY = date(2026, 10, 31)
FIELDS = "FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"


def sample():
    days = []
    day = date(2026, 9, 30)
    while day <= date(2026, 10, 30):
        if day.weekday() < 5:
            days.append(f"D,USD,EUR,SP00,A,{day.isoformat()},1.{1200+len(days):04d}\n")
        day += timedelta(days=1)
    return (FIELDS + "".join(days)).encode()


class OfficialECBTests(unittest.TestCase):
    def test_reproducible_source_and_verifiable_reference_fixings(self):
        raw = sample()
        doc = parse_ecb_csv(raw, AT, today=TODAY)
        self.assertEqual(doc["series"], SERIES)
        self.assertEqual(doc["source_url"], URL)
        self.assertEqual(doc["source_sha256"], sha256(raw).hexdigest())
        self.assertEqual(doc["latest_observation"], "2026-10-30")
        self.assertEqual(doc["count"], 23)
        self.assertTrue(doc["not_tradable"])
        self.assertTrue(validate_document(doc, today=TODAY))

    def test_missing_or_misaligned_rates_cannot_be_published(self):
        body = sample().decode()
        for bad in [
            body.replace("1.1203", ""),
            body.replace("D,USD,EUR", "D,GBP,EUR", 1),
            body.replace("2026-10-30", "2026-11-02"),
            body.replace("2026-10-30", "2026-10-29"),
            body.replace("1.1203", "0.0001"),
            "something other than official CSV",
        ]:
            with self.subTest(case=bad[:70]):
                with self.assertRaises((ValueError, KeyError)):
                    parse_ecb_csv(bad.encode(), AT, today=TODAY)

    def test_refuses_stale_or_false_provenance(self):
        doc = parse_ecb_csv(sample(), AT, today=TODAY)
        altered = dict(doc)
        altered["source_url"] = "https://untrusted.test/quotes"
        with self.assertRaises(ValueError):
            validate_document(altered, today=TODAY)
        altered = dict(doc)
        altered["not_tradable"] = False
        with self.assertRaises(ValueError):
            validate_document(altered, today=TODAY)
        with self.assertRaises(ValueError):
            parse_ecb_csv(sample(), AT, today=date(2026, 11, 25))

    def test_excludes_thin_history_and_speculative_market_data(self):
        thin = FIELDS + "D,USD,EUR,SP00,A,2026-10-30,1.1200\n"
        with self.assertRaises(ValueError):
            parse_ecb_csv(thin.encode(), AT, today=TODAY)
        self.assertNotIn("broker", URL.lower())
        self.assertNotIn("yahoo", URL.lower())


if __name__ == "__main__":
    unittest.main()
