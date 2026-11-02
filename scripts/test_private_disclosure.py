"""Fictitious identifiers only; no actual private terms belong in these tests."""
import unittest
from private_disclosure import configured_terms, contains_private_term


class PrivatePublicationGuardTests(unittest.TestCase):
    def test_required_unconfigured_or_invalid_guard_fails_closed(self):
        for raw in ("", "not json", "[]", '["tiny"]', '["example-name",42]'):
            with self.assertRaisesRegex(ValueError, "not configured"):
                configured_terms({"IDEALAB_REQUIRE_PRIVATE_DENY_TERMS": "true",
                                  "IDEALAB_PUBLIC_DENY_TERMS_JSON": raw})

    def test_identifier_can_be_detected_without_exposing_its_value(self):
        terms = configured_terms({"IDEALAB_PUBLIC_DENY_TERMS_JSON":
                                  '["example-name","retired-account"]'})
        for text in ("EXAMPLE-NAME", "%65xample-name", "%2565xample-name",
                     "&#101;xample-name", "&amp;#101;xample-name"):
            self.assertTrue(contains_private_term(text, terms))
        self.assertFalse(contains_private_term("Independent research", terms))

    def test_local_generic_audit_does_not_need_the_secret(self):
        self.assertEqual(configured_terms({}), ())


if __name__ == "__main__":
    unittest.main()
