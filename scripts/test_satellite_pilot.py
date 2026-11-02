"""Synthetic fixtures test temporal validation; they are not satellite observations."""
import unittest
from copy import deepcopy
from satellite_pilot import audit_batch, SCHEMA

def observation(date, available, cars, mask="a"*64, hashval="b"*64):
    return {
        "ticker": "WMT", "store_ref": "STORE_0001",
        "source_sha256": hashval, "parking_mask_sha256": mask,
        "detector_version": "cv-research-v0",
        "captured_at_utc": date, "available_at_utc": available,
        "cars_detected": cars, "parking_capacity": 200,
        "cloud_cover_pct": 0, "local_capture_hour": 13,
    }

class SatellitePilotTests(unittest.TestCase):
    def setUp(self):
        self.doc = {
            "schema": SCHEMA, "strategy": "IL-R001",
            "data_class": "satellite_observations_research_unverified",
            "rights_attestation": "not_confirmed",
            "decision_at_utc": "2026-11-02T00:00:00Z",
            "observations": [],
        }

    def test_empty_batch_cannot_start_competition(self):
        r=audit_batch(self.doc)
        self.assertEqual(r["image_count"],0)
        self.assertEqual(r["comparable_store_pairs"],0)
        self.assertIsNone(r["trading_signal"])
        self.assertIsNone(r["return_pct"])
        self.assertFalse(r["paper_ready"])

    def test_metadata_test_pair_is_not_a_trading_signal(self):
        self.doc["observations"]=[
            observation("2025-10-20T13:00:00Z","2025-10-21T15:00:00Z",100),
            observation("2026-10-20T13:00:00Z","2026-10-22T15:00:00Z",140,hashval="c"*64),
        ]
        r=audit_batch(self.doc)
        self.assertEqual(r["comparable_store_pairs"],1)
        self.assertEqual(r["pairs_by_ticker"]["WMT"],1)
        self.assertFalse(r["paper_ready"])
        self.assertIsNone(r["nav"])

    def test_reject_future_data_delivery_even_if_image_older(self):
        self.doc["observations"]=[
            observation("2026-10-20T13:00:00Z","2026-11-03T12:00:00Z",130)]
        with self.assertRaisesRegex(ValueError,"Lookahead"):
            audit_batch(self.doc)

    def test_cloud_occlusion_different_mask_and_hour_prevent_comparability(self):
        original=observation("2025-10-20T13:00:00Z","2025-10-21T15:00:00Z",120)
        newer=observation("2026-10-20T13:00:00Z","2026-10-21T15:00:00Z",150,hashval="c"*64)
        for key,value in [("cloud_cover_pct",30),("parking_mask_sha256","d"*64),("local_capture_hour",20)]:
            changed=deepcopy(newer)
            changed[key]=value
            self.doc["observations"]=[original,changed]
            self.assertEqual(audit_batch(self.doc)["comparable_store_pairs"],0)

    def test_reject_duplicates_corrupted_hash_and_impossible_capacity(self):
        item=observation("2026-10-20T13:00:00Z","2026-10-21T15:00:00Z",120)
        for pair in [[item,item], [{**item,"source_sha256":"bad"}],
                     [{**item,"cars_detected":250}]]:
            self.doc["observations"]=pair
            with self.assertRaises(ValueError):
                audit_batch(self.doc)

    def test_no_economic_activity_even_with_declared_internal_rights(self):
        self.doc["rights_attestation"]="documented_internal_research"
        self.doc["observations"]=[observation("2026-10-20T13:00:00Z",
                            "2026-10-21T15:00:00Z",150)]
        r=audit_batch(self.doc)
        self.assertFalse(r["paper_ready"])
        self.assertIsNone(r["trading_signal"])
        self.assertIsNone(r["return_pct"])

if __name__=="__main__":
    unittest.main()
