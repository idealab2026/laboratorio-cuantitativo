"""Regression contracts for the published read-only MIDAS execution ledger."""
import datetime as dt
import unittest
from unittest import mock

import build_execution_history as h

U = dt.timezone.utc


def event(workflow, started, conclusion, uid=100):
    return {
        "workflow": workflow,
        "id": uid,
        "created_at": started,
        "status": "completed" if conclusion else "in_progress",
        "conclusion": conclusion,
        "url": "https://github.com/idealab2026/laboratorio-cuantitativo/actions/runs/" + str(uid),
    }


class ExecutionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.schedules = h.workflow_schedule()
        self.now = dt.datetime(2026, 11, 5, 10, 0, tzinfo=U)

    def test_explicit_26_tracked_slots_and_original_64_inventory(self):
        actual = {h.slot(x) for slots in h.WORKFLOWS.values() for x in slots}
        self.assertEqual(len(actual), 26)
        self.assertNotIn("IL-001", actual)
        self.assertNotIn("IL-064", actual)
        self.assertIn("IL-039", actual)
        self.assertIn("IL-044", actual)

    def test_overnight_backup_belongs_to_prior_nyse_session(self):
        date = dt.date(2026, 11, 4)
        expected = h.due_times_for_session(date, self.schedules["buy_the_dip_strategy.yml"])
        self.assertEqual([x.isoformat() for x in expected],
                         ["2026-11-04T23:27:00+00:00", "2026-11-05T04:17:00+00:00"])
        self.assertEqual(h.session_of_run(event("buy_the_dip_strategy.yml", "2026-11-05T04:17:30Z", "success")), date)
        self.assertEqual(h.session_of_run(event("weekly_ml_daily.yml", "2026-11-04T22:20:30Z", "success")), date)

    def test_shared_failed_workflow_counts_nine_algorithms_without_inventing_schedules(self):
        runs = [
            event("weekly_ml_daily.yml", "2026-11-05T01:28:00Z", "failure", 10),
            event("classic_sp500.yml", "2026-11-05T02:20:00Z", "success", 11),
            event("buy_the_dip_strategy.yml", "2026-11-05T04:20:00Z", "success", 12),
        ]
        doc = h.build(self.now, runs, self.schedules, {("IL-010", "2026-11-04"): "Quarantined"})
        h.verify(doc)
        row = next(x for x in doc["days"] if x["date"] == "2026-11-04")
        self.assertEqual(row["expected"], 25)
        self.assertEqual(row["not_scheduled"], 39)
        by_slot = {x["slot"]: x for x in row["details"]}
        self.assertEqual(by_slot["IL-019"]["status"], "failure")
        self.assertEqual(by_slot["IL-027"]["status"], "failure")
        self.assertEqual(by_slot["IL-010"]["status"], "failure")
        self.assertEqual(by_slot["IL-011"]["status"], "success")
        self.assertEqual(by_slot["IL-039"]["status"], "success")
        self.assertEqual(by_slot["IL-038"]["status"], "unverified")
        self.assertNotIn("IL-037", by_slot)  # Weekly-only algorithm on Wednesday.
        self.assertEqual(row["failure"], 10)
        self.assertEqual(row["success"], 9)  # Classic 8 + BTD 1.
        self.assertEqual(row["not_run"], 0)
        self.assertEqual(row["unverified"], 6)
        self.assertEqual(row["pending"], 0)
        self.assertEqual(sum(row[k] for k in ("success", "failure", "not_run", "pending", "unverified")), row["expected"])

    def test_pre_grace_missing_is_pending_not_automatically_failed(self):
        early = dt.datetime(2026, 11, 4, 22, 30, tzinfo=U)
        runs = [event("classic_sp500.yml", "2026-11-03T00:20:00Z", "success")]
        doc = h.build(early, runs, self.schedules)
        row = doc["days"][0]
        self.assertEqual(row["date"], "2026-11-04")
        self.assertGreater(row["pending"], 0)
        self.assertEqual(row["failure"], 0)
        self.assertEqual(row["not_run"], 0)
        self.assertFalse(row["complete"])

    def test_backup_success_overrides_prior_failure(self):
        due = h.due_times_for_session(dt.date(2026, 11, 4),
                                      self.schedules["buy_the_dip_strategy.yml"])
        status, last = h.one_workflow_status(due, [
            event("buy_the_dip_strategy.yml", "2026-11-04T23:30:00Z", "failure", 11),
            event("buy_the_dip_strategy.yml", "2026-11-05T04:20:00Z", "success", 12),
        ], self.now)
        self.assertEqual(status, "success")
        self.assertEqual(last["id"], 12)

    def test_weekly_slots_are_scheduled_on_friday_session_only(self):
        date = dt.date(2026, 11, 6)
        self.assertTrue(h.due_times_for_session(date, self.schedules["tfg_ahp.yml"]))
        self.assertTrue(h.due_times_for_session(date, self.schedules["weekly_ml.yml"]))
        self.assertTrue(h.due_times_for_session(date, self.schedules["timesfm_weekly.yml"]))
        runs = [event("classic_sp500.yml", "2026-11-03T00:20:00Z", "success")]
        doc = h.build(dt.datetime(2026, 11, 7, 9, tzinfo=U), runs, self.schedules)
        friday = next(x for x in doc["days"] if x["date"] == "2026-11-06")
        self.assertEqual(friday["expected"], 26)
        self.assertEqual(friday["not_scheduled"], 38)

    def test_rejects_unbalanced_and_duplicate_execution_reports(self):
        runs = [event("classic_sp500.yml", "2026-11-05T02:20:00Z", "success")]
        doc = h.build(self.now, runs, self.schedules)
        h.verify(doc)
        doc["days"][0]["success"] = 1
        with self.assertRaises(ValueError):
            h.verify(doc)
        doc["days"][0]["success"] = 0
        doc["days"][0]["details"].append(dict(doc["days"][0]["details"][0]))
        with self.assertRaises(ValueError):
            h.verify(doc)

    def test_october_is_visible_but_missing_actions_archive_is_not_false_failure(self):
        runs = [
            event("classic_sp500.yml", "2026-11-03T00:20:00Z", "success"),
            event("weekly_ml_daily.yml", "2026-11-02T22:53:00Z", "success"),
        ]
        doc = h.build(self.now, runs, self.schedules)
        h.verify(doc)
        self.assertEqual(doc["first_tracked_session"], "2026-10-01")
        self.assertEqual(doc["oldest_retained_run_session"], "2026-11-02")
        self.assertGreaterEqual(len(doc["days"]), 25)
        older = next(x for x in doc["days"] if x["date"] == "2026-10-01")
        self.assertEqual(older["data_status"], "not_verifiable")
        self.assertIsNone(older["expected"])
        self.assertIsNone(older["failure"])
        self.assertIsNone(older["not_run"])
        self.assertIsNone(older["success"])
        self.assertEqual(older["details"], [])

    def test_unverified_workflow_must_not_be_counted_as_missed(self):
        runs = [event("classic_sp500.yml", "2026-11-03T00:20:00Z", "success")]
        doc = h.build(self.now, runs, self.schedules)
        row = next(x for x in doc["days"] if x["date"] == "2026-11-04")
        per_slot = {x["slot"]: x for x in row["details"]}
        self.assertEqual(per_slot["IL-038"]["status"], "unverified")
        self.assertIsNone(per_slot["IL-038"]["workflows"][0]["run_url"])
        self.assertEqual(per_slot["IL-010"]["status"], "not_run")
        self.assertEqual(row["data_status"], "partially_verified")

    def test_unverifiable_date_rejects_fake_zero_and_false_success(self):
        runs = [event("classic_sp500.yml", "2026-11-03T00:20:00Z", "success")]
        doc = h.build(self.now, runs, self.schedules)
        old = next(x for x in doc["days"] if x["date"] == "2026-10-01")
        old["failure"] = 0
        with self.assertRaises(ValueError):
            h.verify(doc)

    def test_unavailable_cannot_publish_made_up_no_run_counts(self):
        h.verify({"schema": h.SCHEMA, "status": "unavailable", "days": []})
        with self.assertRaises(ValueError):
            h.verify({"schema": h.SCHEMA, "status": "unavailable",
                      "days": [{"date": "2026-11-04", "not_run": 64}]})


if __name__ == "__main__":
    unittest.main()
