import unittest
from datetime import date, timedelta
from hashlib import sha256

from refresh_ecb import parse_ecb_csv, validate_document, fetch_official_csv, SERIES, URL

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




class OfficialTransportTests(unittest.TestCase):
    def test_transient_gateway_failures_retry_same_source_and_preserve_bytes(self):
        from unittest.mock import Mock, MagicMock
        from urllib.error import HTTPError
        raw = sample()
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = URL
        response.read.return_value = raw
        opener = Mock(side_effect=[HTTPError(URL, 504, "gateway", {}, None),
                                   HTTPError(URL, 503, "busy", {}, None), response])
        sleeper = Mock()
        self.assertEqual(fetch_official_csv(URL, {}, 22, opener=opener, sleeper=sleeper), raw)
        self.assertEqual([c.args[0].full_url for c in opener.call_args_list], [URL] * 3)
        self.assertEqual([c.args[0] for c in sleeper.call_args_list], [2, 5])
        response.read.assert_called_once_with(2_000_001)

    def test_persistent_failure_is_bounded_and_never_returns_old_data(self):
        from unittest.mock import Mock
        from urllib.error import HTTPError
        opener = Mock(side_effect=HTTPError(URL, 504, "gateway", {}, None))
        sleeper = Mock()
        with self.assertRaises(HTTPError):
            fetch_official_csv(URL, {}, 22, opener=opener, sleeper=sleeper)
        self.assertEqual(opener.call_count, 3)
        self.assertEqual(sleeper.call_count, 2)

    def test_denials_redirects_and_certificate_failures_are_not_retried(self):
        from unittest.mock import Mock, MagicMock
        from urllib.error import HTTPError, URLError
        import ssl
        for error in (HTTPError(URL, 403, "denied", {}, None),
                      URLError(ssl.SSLCertVerificationError("certificate"))):
            opener, sleeper = Mock(side_effect=error), Mock()
            with self.assertRaises(type(error)):
                fetch_official_csv(URL, {}, 22, opener=opener, sleeper=sleeper)
            self.assertEqual(opener.call_count, 1)
            sleeper.assert_not_called()
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = "https://untrusted.test/redirect"
        opener, sleeper = Mock(return_value=response), Mock()
        with self.assertRaisesRegex(RuntimeError, "redirect"):
            fetch_official_csv(URL, {}, 22, opener=opener, sleeper=sleeper)
        response.read.assert_not_called()
        sleeper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
