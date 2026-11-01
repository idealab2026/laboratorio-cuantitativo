import unittest
from copy import deepcopy
from datetime import datetime, timezone
from operational_status import evaluate, load

ROSTER = load("competition-roster.json")
FEED = load("institutional-paper-feed.json")
REFERENCE = load("public-paper-book.json")
CLASSIC = load("classic-503-book.json")
MONTHLY = load("monthly-paper-book.json")

class OperationalStatusTests(unittest.TestCase):
    def report(self, **changes):
        return evaluate(ROSTER, FEED, REFERENCE, CLASSIC, MONTHLY, **changes)

    def test_original_archive_does_not_count_as_live_paper(self):
        r = self.report()
        self.assertEqual(r["registered_strategies"], 64)
        self.assertEqual(r["market_feed"], "not_connected")
        self.assertEqual(r["active_reference_strategies"], 0)
        self.assertFalse(r["operating"])
        self.assertFalse(r["old_system_shutdown_safe"])

    def test_declaring_rights_does_not_fabricate_source(self):
        r = self.report(rights=True, signed=True)
        self.assertFalse(r["operating"])
        self.assertFalse(r["full_64_parity"])

    def test_foreign_slot_cannot_enter_registry(self):
        bad = deepcopy(ROSTER)
        bad["entries"][0]["slot"] = "IL-999"
        with self.assertRaisesRegex(ValueError, "registry"):
            evaluate(bad, FEED, REFERENCE, CLASSIC, MONTHLY)

    def test_fake_source_status_is_rejected(self):
        bad = deepcopy(FEED)
        bad["status"] = "pretend_live"
        with self.assertRaisesRegex(ValueError, "feed status"):
            evaluate(ROSTER, bad, REFERENCE, CLASSIC, MONTHLY)

    def test_partial_engine_is_never_full_parity(self):
        fresh = deepcopy(FEED)
        fresh["status"] = "source_verified"
        fresh["source"] = {"session": datetime.now(timezone.utc).date().isoformat()}
        fresh["tracks"] = [{"slot": "IL-001"}]
        ref = deepcopy(REFERENCE)
        classic = deepcopy(CLASSIC)
        ref["status"] = "prospective_paper"
        classic["status"] = "prospective_paper"
        r = evaluate(ROSTER, fresh, ref, classic, MONTHLY, rights=True, signed=True)
        self.assertTrue(r["operating"])
        self.assertEqual(r["active_reference_strategies"], 1)
        self.assertFalse(r["full_64_parity"])
        self.assertFalse(r["old_system_shutdown_safe"])

if __name__ == "__main__":
    unittest.main()
