"""Regression contracts for the published read-only MIDAS execution ledger."""
import datetime as dt
import copy
import json
import hashlib
import tempfile
import io
from pathlib import Path
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

    def test_scheduled_common_consumer_jobs_are_attributed_individually(self):
        parent={"id":200,"event":"schedule","path":".github/workflows/market_data_xnys.yml",
                "created_at":"2026-11-04T23:40:00Z","status":"completed","conclusion":"failure",
                "html_url":"https://github.com/idealab2026/laboratorio-cuantitativo/actions/runs/200"}
        jobs=[{"name":"capture","status":"completed","conclusion":"success"}]
        for filename in h.COMMON_ACCOUNTING_STEPS:
            outcome="failure" if filename=="weekly_ml_daily.yml" else "success"
            jobs.append({"name":"consume-"+filename[:-4]+" / runner","status":"completed","conclusion":outcome,
                         "steps":[{"name":h.COMMON_ACCOUNTING_STEPS[filename],"conclusion":outcome}]})
        def opener(req, timeout):
            payload={"jobs":jobs} if "/200/jobs?" in req.full_url else {"workflow_runs":[parent]}
            return io.StringIO(json.dumps(payload))
        now=dt.datetime(2026,11,4,23,50,tzinfo=U)
        runs=h.collect_runs("",now,opener=opener)
        self.assertEqual(len(runs),6)
        doc=h.build(now,runs,self.schedules)
        h.verify(doc)
        row=next(d for d in doc["days"] if d["date"]=="2026-11-04")
        by_slot={d["slot"]:d for d in row["details"]}
        self.assertEqual(by_slot["IL-019"]["status"],"failure")
        self.assertEqual(by_slot["IL-010"]["status"],"success")
        self.assertEqual(by_slot["IL-039"]["status"],"success")
        self.assertEqual(by_slot["IL-044"]["status"],"unverified")  # Not a called consumer.
        self.assertEqual(row["failure"],9)
        self.assertEqual(row["success"],15)
        self.assertTrue(all(w["run_id"]==200 for d in row["details"] for w in d["workflows"] if w["run_id"]))

    def test_green_capture_cannot_certify_missing_or_skipped_consumer_accounting(self):
        parent={"id":200,"created_at":"2026-11-04T23:40:00Z",
                "html_url":"https://github.com/idealab2026/laboratorio-cuantitativo/actions/runs/200"}
        jobs=[{"name":"capture","conclusion":"success"},
              {"name":"consume-classic_sp500 / classic","status":"completed","conclusion":"success",
               "steps":[{"name":"Record next-open paper ledger","conclusion":"skipped"}]}]
        runs=h.common_consumer_runs(parent,"",lambda req,timeout:io.StringIO(json.dumps({"jobs":jobs})))
        self.assertEqual(len(runs),1)
        self.assertEqual(runs[0]["conclusion"],"unverified")
        jobs=[]
        self.assertEqual(h.common_consumer_runs(parent,"",lambda req,timeout:io.StringIO(json.dumps({"jobs":jobs}))),[])
        with self.assertRaises(ValueError):
            h.common_consumer_runs(parent,"",lambda req,timeout:io.StringIO('{}'))

    def test_observed_failure_is_visible_before_future_backup_but_missing_run_stays_pending(self):
        due=h.due_times_for_session(dt.date(2026,11,4),self.schedules["weekly_ml_daily.yml"])
        now=dt.datetime(2026,11,4,23,50,tzinfo=U)
        status,_=h.one_workflow_status(due,[event("weekly_ml_daily.yml","2026-11-04T23:40:00Z","failure")],now)
        self.assertEqual(status,"failure")
        self.assertEqual(h.one_workflow_status(due,[],now)[0],"pending")

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

    def journal(self, sid="IL-010", recovered=False):
        return {"slot":sid,"cohort":"Campaña actual","nav":100000.,"currency":"USD",
                "source_path":"classic_sp500_state/ledger.json","source_sha256":"a"*64,
                "source_url":"https://github.com/idealab2026/laboratorio-cuantitativo/blob/main/classic_sp500_state/ledger.json",
                "inactive":recovered,"recovered":recovered,"recorded_at_utc":None,
                "first_trading_session":None}

    def test_october_journals_survive_absent_actions_without_inventing_successes(self):
        evidence={"2026-10-30":[self.journal()]}
        runs=[event("classic_sp500.yml","2026-11-03T00:20:00Z","success")]
        doc=h.build(self.now,runs,self.schedules,journals=evidence)
        h.verify(doc)
        old=next(d for d in doc["days"] if d["date"]=="2026-10-30")
        self.assertEqual(old["journal_count"],1)
        self.assertEqual(old["journals"][0]["nav"],100000.)
        self.assertIsNone(old["success"])
        self.assertIsNone(old["not_run"])
        self.assertEqual(old["data_status"],"not_verifiable")

    def test_recovery_does_not_erase_original_automation_failure(self):
        runs=[event("classic_sp500.yml","2026-11-04T00:20:00Z","success",1),
              event("weekly_ml_daily.yml","2026-11-04T02:20:00Z","failure",2)]
        journals={"2026-11-03":[self.journal("IL-010",True),self.journal("IL-019",True)]}
        doc=h.build(self.now,runs,self.schedules,{("IL-010","2026-11-03"):"Missing OHLC"},journals)
        h.verify(doc)
        day=next(d for d in doc["days"] if d["date"]=="2026-11-03")
        self.assertEqual(day["journal_count"],2)
        self.assertEqual(day["recovered_count"],2)
        self.assertEqual(day["recovered_failures"],2)
        self.assertEqual(next(d for d in day["details"] if d["slot"]=="IL-010")["status"],"failure")
        self.assertEqual(next(d for d in day["details"] if d["slot"]=="IL-019")["status"],"failure")

    def test_actions_outage_does_not_hide_accounting_history(self):
        doc=h.build(self.now,[],self.schedules,journals={"2026-10-30":[self.journal()]},actions_available=False)
        h.verify(doc)
        self.assertFalse(doc["actions_available"])
        day=next(d for d in doc["days"] if d["date"]=="2026-10-30")
        self.assertEqual(day["journal_count"],1)
        self.assertIsNone(day["failure"])

    def test_all_three_genetic_cohorts_are_read_separately_from_original_files(self):
        evidence=h.journal_evidence()
        records=[(d,x) for d,rows in evidence.items() for x in rows if x["slot"]=="IL-044"]
        historical=[x for d,x in records if x["cohort"]=="Histórico de cierre · archivado"]
        archived=[x for d,x in records if x["cohort"]=="Prospectivo archivado"]
        active=[x for d,x in records if x["cohort"]=="Prospectivo activo"]
        self.assertEqual(len(historical),149)
        self.assertEqual(len(archived),7)
        self.assertGreaterEqual(len(active),17)
        self.assertEqual(len({x["source_sha256"] for x in historical+archived+active}),3)
        doc=h.build(self.now,[],self.schedules,journals=evidence)
        h.verify(doc)
        self.assertEqual(doc["first_tracked_session"],"2026-02-27")
        self.assertTrue(any(d["date"]=="2026-10-30" and d["journal_count"]>0 for d in doc["days"]))

    def test_rejects_recovery_count_tampering_and_duplicate_cohort_records(self):
        j=self.journal(recovered=True)
        with self.assertRaisesRegex(ValueError,"Duplicate cohort"):
            h.build(self.now,[],self.schedules,journals={"2026-10-30":[j,j]})
        doc=h.build(self.now,[],self.schedules,journals={"2026-10-30":[j]})
        day=next(d for d in doc["days"] if d["date"]=="2026-10-30")
        day["recovered_count"]=0
        with self.assertRaisesRegex(ValueError,"recovery counts"):
            h.verify(doc)

    def test_reviewed_october_archive_fills_observed_outcomes_without_inventing_schedule(self):
        archive=h.reviewed_archive()
        self.assertEqual(len(archive["records"]),141)
        self.assertEqual(sum(x["attempts"] for x in archive["records"]),245)
        runs=[event("classic_sp500.yml","2026-11-04T00:20:00Z","failure")]
        doc=h.build(self.now,runs,self.schedules,h.classic_quarantines(),h.journal_evidence(),archive=archive)
        h.verify(doc)
        old=next(d for d in doc["days"] if d["date"]=="2026-10-30")
        self.assertEqual((old["success"],old["failure"],old["journal_count"]),(24,2,35))
        self.assertEqual(old["data_status"],"archived_observations")
        for key in ("not_run","pending","not_scheduled","complete"):
            self.assertIsNone(old[key])
        # The archive cannot turn a later institutional failure into success.
        current=next(d for d in doc["days"] if d["date"]=="2026-11-03")
        self.assertEqual(next(d for d in current["details"] if d["slot"]=="IL-010")["status"],"failure")
        # Journals before the archive survive without invented automation outcomes.
        earlier=next(d for d in doc["days"] if d["date"]=="2026-09-30")
        self.assertGreater(earlier["journal_count"],0)
        self.assertIsNone(earlier["success"])

    def test_reviewed_archive_retains_original_failure_alongside_recovered_journal(self):
        archive=h.reviewed_archive()
        doc=h.build(self.now,[],self.schedules,journals={"2026-10-30":[self.journal("IL-044",True)]},archive=archive)
        h.verify(doc)
        old=next(d for d in doc["days"] if d["date"]=="2026-10-30")
        self.assertEqual(old["recovered_failures"],1)
        self.assertEqual(next(d for d in old["details"] if d["slot"]=="IL-044")["status"],"failure")
        self.assertIsNone(old["not_run"])

    def test_archive_checksum_and_original_identifier_fields_fail_closed(self):
        original=json.loads((h.ROOT/"data/execution-history-archive.json").read_text())
        for field in (None,"original_location","original_record_id"):
            doc=copy.deepcopy(original)
            if field is None:
                doc["records"][0]["attempts"]+=1  # checksum mismatch
            elif field=="original_location":
                doc[field]="must remain private"
            else:
                doc["records"][0][field]="must remain private"
            if field:
                core={k:v for k,v in doc.items() if k!="sha256"}
                doc["sha256"]=hashlib.sha256(json.dumps(core,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/"data").mkdir()
                (root/"data/execution-history-archive.json").write_text(json.dumps(doc))
                with self.assertRaises(ValueError):
                    h.reviewed_archive(root)

    def test_published_archive_rejects_identifying_links_and_false_missed_runs(self):
        doc=h.build(self.now,[],self.schedules,archive=h.reviewed_archive())
        day=next(d for d in doc["days"] if d["date"]=="2026-10-30")
        w=day["details"][0]["workflows"][0]
        self.assertTrue(w["evidence_url"].endswith("/data/execution-history-archive.json"))
        self.assertIsNone(w["run_url"])
        self.assertIsNone(w["run_id"])
        day["not_run"]=0
        with self.assertRaises(ValueError): h.verify(doc)
        day["not_run"]=None
        w["run_id"]=123
        with self.assertRaises(ValueError): h.verify(doc)
        w["run_id"]=None; w["evidence_url"]="https://example.com/original"
        with self.assertRaises(ValueError): h.verify(doc)

    def test_unavailable_cannot_publish_made_up_no_run_counts(self):
        h.verify({"schema": h.SCHEMA, "status": "unavailable", "days": []})
        with self.assertRaises(ValueError):
            h.verify({"schema": h.SCHEMA, "status": "unavailable",
                      "days": [{"date": "2026-11-04", "not_run": 64}]})


if __name__ == "__main__":
    unittest.main()
