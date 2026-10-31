import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json

from paper_feed import SCHEMA, DATA_SOURCE, mac, validate

SECRET = "institutional-test-auth-only-not-a-real-key-0123456789012345"
ROOT = Path(__file__).resolve().parents[1]
ROSTER = json.loads((ROOT / "data" / "competition-roster.json").read_text(encoding="utf8"))


def example():
    document = {
        "schema": SCHEMA, "status": "source_verified",
        "producer": "idealab_institutional_core",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "identity": DATA_SOURCE.copy(), "session": "2026-10-30",
            "sha256": "a"*64, "requested": 504, "observed": 504,
            "constituents_observed": 503, "missing": 0, "rights_attested": True
        },
        "tracks": [{
            "slot": "IL-010", "activity": "active", "currency": "USD",
            "first_session": "2026-10-29", "last_session": "2026-10-30",
            "initial_capital": 100000, "last_equity": 110000,
            "return_pct": 10, "day_return_pct": 10,
            "risk": {"volatility_pct": None, "max_drawdown_pct": 0,
                     "sharpe_0rf": None},
            "positions": 1, "pending_orders": 0,
            "comparison": {"eligible": True, "universe_id": "us_503_frozen"},
            "history": [{"date": "2026-10-29", "nav": 100000},
                        {"date": "2026-10-30", "nav": 110000}],
            "source_snapshot_sha256": "a"*64,
            "config_sha256": "b"*64
        }],
        "signature": None
    }
    document["signature"] = mac(document, SECRET)
    return document


class InstitutionalPaperFeedTest(unittest.TestCase):
    def test_disconnected_public_placeholder_is_truthful_without_secrets(self):
        doc = json.loads((ROOT/"data/institutional-paper-feed.json").read_text(encoding="utf8"))
        self.assertEqual(validate(doc, roster=ROSTER),
                         {"status": "not_connected", "observed": 0})

    def test_signed_source_verified_feed_accepts_only_reconciled_portfolios(self):
        doc = example()
        result = validate(doc, secret=SECRET, roster=ROSTER)
        self.assertEqual(result["status"], "source_verified")
        self.assertEqual(result["observed"], 1)
        self.assertEqual(result["session"], "2026-10-30")

    def test_unsigned_or_wrong_key_cannot_expose_fake_portfolios(self):
        doc = example()
        with self.assertRaisesRegex(ValueError, "private HMAC key"):
            validate(doc, roster=ROSTER)
        with self.assertRaisesRegex(ValueError, "attestation mismatch"):
            validate(doc, roster=ROSTER, secret="some-other-institutional-key-that-is-long-enough")
        doc["tracks"][0]["last_equity"] = 120000
        with self.assertRaisesRegex(ValueError, "attestation mismatch"):
            validate(doc, roster=ROSTER, secret=SECRET)

    def test_correctly_resigned_fraudulent_metadata_rejected_by_reconciliation(self):
        changes = [
            lambda d: d["tracks"][0].update(last_equity=120000),
            lambda d: d["tracks"][0].update(return_pct=12),
            lambda d: d["tracks"][0].update(day_return_pct=12),
            lambda d: d["tracks"][0]["risk"].update(max_drawdown_pct=-2),
            lambda d: d["tracks"][0].update(source_snapshot_sha256="c"*64),
            lambda d: d["tracks"][0].update(slot="IL-999"),
            lambda d: d["source"].update(rights_attested=False),
            lambda d: d["source"].update(vendor="other"),
            lambda d: d["source"].update(constituents_observed=452),
            lambda d: d["tracks"][0]["history"][0].update(date="2026-10-30"),
            lambda d: d["tracks"][0].update(positions=-2),
        ]
        for action in changes:
            with self.subTest(action=str(action)):
                doc = example()
                action(doc)
                doc["signature"] = mac(doc, SECRET)
                with self.assertRaises(ValueError):
                    validate(doc, secret=SECRET, roster=ROSTER)

    def test_unknown_fields_and_account_metadata_rejected(self):
        doc = example()
        doc["tracks"][0]["broker_account"] = "internal-test-should-not-leak"
        doc["signature"] = mac(doc, SECRET)
        with self.assertRaisesRegex(ValueError, "unknown or missing"):
            validate(doc, secret=SECRET, roster=ROSTER)
        disconnected = {
            "schema": SCHEMA, "status": "not_connected",
            "producer": "institutional_core_pending", "generated_at_utc": None,
            "source": None, "tracks": [], "signature": None,
        }
        disconnected["tracks"].append({"bogus":True})
        with self.assertRaisesRegex(ValueError, "may not claim"):
            validate(disconnected, roster=ROSTER)


if __name__ == "__main__":
    unittest.main()
