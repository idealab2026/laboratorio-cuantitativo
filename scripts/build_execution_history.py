#!/usr/bin/env python3
"""Build a read-only day-by-day execution-status ledger from GitHub Actions.

One row per TARGET XNYS session; overnight UTC retries belong to the prior
US business day. Workflow outcomes attest to scheduled automation runs, NOT
to the individual paper trades, profitability or all shared child ledgers.
Unconfigured/historical algorithm slots must never be called failed.
"""
import argparse
import datetime as dt
import json
import hashlib
import math
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = "idealab2026/laboratorio-cuantitativo"
SCHEMA = "midas_daily_execution_health_v1"
# Include the entire historical competition window in the calendar, rather
# than limiting it to the date on which this UI was first implemented.
START = dt.date(2026, 10, 1)
HISTORY_DAYS = 500
GRACE = dt.timedelta(minutes=150)
UTC = dt.timezone.utc

# Only workflows with a genuine scheduled paper engine and a documented slot
# mapping are counted; synthetic demonstrations and unported strategies are not.
WORKFLOWS = {
    "classic_sp500.yml": list(range(10, 19)),
    "weekly_ml_daily.yml": list(range(19, 28)),
    "weekly_ml.yml": list(range(19, 28)),  # Additional weekly signal when due.
    "tfg_ahp.yml": [37],
    "capital_cycle.yml": [38],
    "buy_the_dip_strategy.yml": [39],
    "timesfm_daily.yml": [40, 41],
    "timesfm_weekly.yml": [40, 41],  # Additional weekly signal when due.
    "timesfm_one_day.yml": [42, 43],
    "genetic_sp500.yml": [44],
}
# Explicit evidence, where a job can succeed although an individual book was
# quarantined by the engine. This is a book-level override, not a guessed trade.
CLASSIC_BOOKS = {
    10: "buy_hold_equal_weight",
    11: "ema_rsi_fixed",
    12: "genetic_frozen",
    13: "macd_12_26_9",
    14: "rsi_reversion_14",
    15: "bollinger_breakout_20",
    16: "turtle_20_10_long",
    17: "turtle_55_20_long",
    18: "benchmark_spy",
}
GITHUB_API = "https://api.github.com/repos/" + REPO + "/actions/runs"


def slot(number):
    return f"IL-{number:03d}"


def cron_values(expression, upper):
    result = set()
    for item in expression.split(","):
        if item == "*":
            result.update(range(upper + 1))
        elif re.fullmatch(r"\d+", item):
            result.add(int(item))
        elif re.fullmatch(r"\d+-\d+", item):
            low, high = map(int, item.split("-"))
            if low > high:
                raise ValueError("Invalid cron range")
            result.update(range(low, high + 1))
        else:
            raise ValueError("Unsupported workflow cron field: " + item)
    if not result or min(result) < 0 or max(result) > upper:
        raise ValueError("Invalid cron field: " + expression)
    return result


def workflow_schedule(root=ROOT, workflows=WORKFLOWS):
    result = {}
    for filename in workflows:
        path = root / ".github" / "workflows" / filename
        data = path.read_text(encoding="utf-8")
        crons = re.findall(r"(?m)^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]\s*$", data)
        if not crons:
            raise ValueError("No scheduled cron for " + filename)
        parsed = []
        for cron in crons:
            fields = cron.split()
            if len(fields) != 5:
                raise ValueError("Expected five cron fields: " + cron)
            minute, hour, monthday, month, weekday = fields
            if monthday != "*" or month != "*":
                raise ValueError("Cron calendar requires explicit support: " + cron)
            parsed.append((cron_values(minute, 59), cron_values(hour, 23),
                           cron_values(weekday, 7)))
        result[filename] = parsed
    return result


def due_times_for_session(session, specs):
    """Compute UTC due times; 00:00–11:59 UTC is the preceding US session."""
    result = []
    for day in (session, session + dt.timedelta(days=1)):
        github_weekday = (day.weekday() + 1) % 7
        for minutes, hours, weekdays in specs:
            if github_weekday not in weekdays and not (
                github_weekday == 0 and 7 in weekdays
            ):
                continue
            for hour in sorted(hours):
                target = day - dt.timedelta(days=1) if hour < 12 else day
                if target != session:
                    continue
                for minute in sorted(minutes):
                    result.append(dt.datetime(day.year, day.month, day.day,
                                              hour, minute, tzinfo=UTC))
    return sorted(result)


def live_session_plan(now, schedules):
    """Publish the next NYSE sessions and the actual workflow schedules."""
    from zoneinfo import ZoneInfo
    import pandas_market_calendars as calendars

    today = now.astimezone(ZoneInfo("America/New_York")).date()
    start = today - dt.timedelta(days=1)
    end = today + dt.timedelta(days=21)
    calendar = calendars.get_calendar("XNYS").schedule(start_date=start, end_date=end)
    source = "market_data_xnys.yml"
    schedule_map = {**schedules, **workflow_schedule(workflows=(source,))}
    days = {}
    for index, row in calendar.iterrows():
        day = index.date()
        lanes = []
        for name, spec in schedule_map.items():
            due = due_times_for_session(day, spec)
            if due:
                lanes.append({
                    "workflow": name,
                    "slots": [slot(number) for number in WORKFLOWS.get(name, [])],
                    "due": [time.isoformat() for time in due],
                    "accounting_step": COMMON_ACCOUNTING_STEPS.get(name),
                })
        days[day.isoformat()] = {
            "open": row["market_open"].isoformat(),
            "close": row["market_close"].isoformat(),
            "lanes": lanes,
        }
    return {"from": start.isoformat(), "through": end.isoformat(), "days": days}


def session_of_run(run):
    started = dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    return (started - dt.timedelta(days=1)).date() if started.hour < 12 else started.date()


COMMON_ACCOUNTING_STEPS = {
    "classic_sp500.yml": "Record next-open paper ledger",
    "weekly_ml_daily.yml": "Value one completed XNYS session",
    "capital_cycle.yml": "Record capital-cycle paper state",
    "buy_the_dip_strategy.yml": "Record Buy The Dip paper state",
    "timesfm_daily.yml": "Record latest closed daily XNYS session",
    "timesfm_one_day.yml": "Close paper session then freeze one-day forecast",
}


def common_consumer_runs(run, token, opener):
    """Read each called job, never infer six successes from a green capture."""
    result = []
    seen = set()
    for page in range(1, 11):
        req = urllib.request.Request(
            GITHUB_API + "/" + str(int(run["id"])) + "/jobs?per_page=100&page=" + str(page),
            headers={"Accept":"application/vnd.github+json",
                     "User-Agent":"MIDAS-daily-execution-health/1.0",
                     **({"Authorization":"Bearer " + token} if token else {})})
        with opener(req, timeout=20) as response:
            body = json.load(response)
        jobs = body.get("jobs")
        if not isinstance(jobs, list):
            raise ValueError("Incomplete common consumer job evidence")
        for job in jobs:
            prefix = job.get("name", "").split(" / ")[0]
            if not prefix.startswith("consume-"):
                continue
            workflow = prefix[len("consume-"):] + ".yml"
            if workflow not in COMMON_ACCOUNTING_STEPS:
                continue
            if workflow in seen:
                raise ValueError("Duplicate common consumer job")
            seen.add(workflow)
            conclusion = job.get("conclusion")
            # A green setup/test-only job is not an executed paper engine.
            if conclusion == "success" and not any(
                step.get("name") == COMMON_ACCOUNTING_STEPS[workflow] and
                step.get("conclusion") == "success" for step in job.get("steps", [])):
                conclusion = "unverified"
            if conclusion in ("skipped", "neutral"):
                conclusion = "unverified"
            result.append({"workflow":workflow,"id":run["id"],
                           "created_at":run["created_at"],"status":job.get("status", ""),
                           "conclusion":conclusion,"url":run["html_url"]})
        if len(jobs) < 100:
            return result
    raise ValueError("Common consumer job history truncated")


def collect_runs(token, now, opener=urllib.request.urlopen):
    """Query complete paginated Actions history, fail-closed if incomplete."""
    since = START - dt.timedelta(days=1)
    end = now.date() + dt.timedelta(days=2)
    output = []
    # GitHub Actions list pagination. Refuse truncated data, rather than claim
    # 0 missing workflows on days whose history was not fully retrieved.
    for page in range(1, 31):
        query = urllib.parse.urlencode({
            "per_page": 100, "page": page,
            "created": since.isoformat() + ".." + end.isoformat(),
        })
        req = urllib.request.Request(
            GITHUB_API + "?" + query,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "MIDAS-daily-execution-health/1.0",
                **({"Authorization": "Bearer " + token} if token else {}),
            },
        )
        with opener(req, timeout=20) as response:
            body = json.load(response)
        batch = body.get("workflow_runs")
        if not isinstance(batch, list):
            raise ValueError("GitHub returned no workflow_runs array")
        for run in batch:
            if run.get("event") != "schedule":
                continue
            path = run.get("path", "").split("/")[-1]
            if path == "market_data_xnys.yml":
                output.extend(common_consumer_runs(run, token, opener))
                continue
            if path not in WORKFLOWS:
                continue
            output.append({
                "workflow": path, "id": run["id"],
                "created_at": run["created_at"],
                "status": run.get("status", ""),
                "conclusion": run.get("conclusion"),
                "url": run["html_url"],
            })
        if len(batch) < 100:
            return output
    raise ValueError("Actions history is truncated at 3000 records")


def classic_quarantines(root=ROOT):
    path = root / "classic_sp500_state" / "ledger.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    books = doc.get("books", {})
    result = {}
    for number, name in CLASSIC_BOOKS.items():
        book = books.get(name) or {}
        if not isinstance(book, dict):
            continue
        for event in book.get("events", []):
            if (event.get("type") == "book_quarantined_missing_held_bar"
                and isinstance(event.get("date"), str)):
                result[(slot(number), event["date"])] = "Libro inmovilizado por dato OHLC ausente"
    return result



def journal_evidence(root=ROOT):
    """Read committed accounting observations, never infer an automation run.

    Archived cohorts retain their own identity and source hash. Their NAV is
    not spliced into an active campaign and never proves a historical fill.
    """
    from build_operations_audit import source_for, source_book
    root = Path(root)
    mapping = json.loads((root / "data/original-track-map.json").read_text())
    if len(mapping) != 64 or set(mapping.values()) != {slot(n) for n in range(1,65)}:
        raise ValueError("Invalid accounting slot map")
    cache, result = {}, {}
    ref = os.getenv("GITHUB_SHA", "main")
    if ref != "main" and not re.fullmatch(r"[a-f0-9]{40}", ref):
        raise ValueError("Invalid public accounting source ref")

    def read(path):
        if path not in cache:
            raw = (root / path).read_bytes()
            cache[path] = json.loads(raw), hashlib.sha256(raw).hexdigest()
        return cache[path]

    def add(sid, path, book, parent, cohort):
        _doc, digest = read(path)
        points = book.get("equity", [])
        if isinstance(book.get("equity_history"), dict):
            points = [{"date": d, "nav": n} for d,n in book["equity_history"].items()]
        if not isinstance(points, list):
            raise ValueError("Invalid accounting history")
        seen = set()
        for point in points:
            day, nav = point.get("date"), point.get("nav")
            dt.date.fromisoformat(day)
            if day in seen or isinstance(nav,bool) or not isinstance(nav,(int,float)) or not math.isfinite(nav) or nav < 0:
                raise ValueError("Duplicate or invalid accounting observation")
            seen.add(day)
            provenance = book.get("equity_provenance", {}).get(day, {})
            inactive = bool(point.get("inactive_no_fills") or day in book.get("inactive_sessions", []))
            recovered = bool(inactive or point.get("late_mark_only") or point.get("late_recorded_verified_date"))
            result.setdefault(day, []).append({
                "slot": sid, "cohort": cohort, "nav": nav,
                "currency": parent.get("currency", "USD"),
                "inactive": inactive, "recovered": recovered,
                "recorded_at_utc": point.get("recorded_at_utc", provenance.get("recorded_at_utc")),
                "first_trading_session": book.get("outage_control", parent.get("outage_control", {})).get("first_trading_session"),
                "source_path": path, "source_sha256": digest,
                "source_url": "https://github.com/" + REPO + "/blob/" + ref + "/" + path,
            })

    for source_id, sid in mapping.items():
        if sid == "IL-044":
            for name,cohort in (("diario_portfolio.json", "Histórico de cierre · archivado"),
                                ("diario_portfolio_forward.json", "Prospectivo archivado"),
                                ("diario_portfolio_forward_2026-10-12.json", "Prospectivo activo")):
                path = "AGENTE/genetic_invest_agent/registro_historico/" + name
                doc,_ = read(path)
                add(sid,path,doc,doc,cohort)
            continue
        if source_id in ("timesfm_2p5_daily_eur_paper", "timesfm_daily_spy_eur"):
            path = "timesfm_daily_state/ledger.json"
            key = "timesfm_daily" if source_id == "timesfm_2p5_daily_eur_paper" else "benchmark_spy"
        else:
            path,key = source_for(source_id)
        if path is None:
            continue
        doc,_ = read(path)
        book = (doc.get("books",{}).get(key) if path == "timesfm_daily_state/ledger.json"
                else source_book(doc,path,key))
        if not isinstance(book, dict):
            raise ValueError("Mapped accounting book absent: " + sid)
        cohort = ("Archivo de ocho activos" if path == "paper_state/state.json" else
                  "Archivo semanal" if path == "weekly_ml_state/ledger.json" else
                  "Archivo de modelos" if path == "tfm_state/ledger.json" else "Campaña actual")
        add(sid,path,book,doc,cohort)
    return result


def attach_journals(row, evidence):
    records = evidence.get(row["date"], [])
    if len({(x["slot"],x["cohort"]) for x in records}) != len(records):
        raise ValueError("Duplicate cohort accounting evidence")
    row["journals"] = records
    row["journal_count"] = len({x["slot"] for x in records})
    row["recovered_count"] = len({x["slot"] for x in records if x["recovered"]})
    recovered = {x["slot"] for x in records if x["recovered"]}
    row["recovered_failures"] = sum(x["status"] == "failure" and x["slot"] in recovered
                                     for x in row["details"])
    return row

def reviewed_archive(root=ROOT):
    """Verify the privacy-reviewed projection, never expose original identifiers."""
    path = Path(root) / "data/execution-history-archive.json"
    raw = path.read_bytes()
    doc = json.loads(raw)
    core = {k:v for k,v in doc.items() if k != "sha256"}
    digest = hashlib.sha256(json.dumps(core,sort_keys=True,separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()
    allowed_top={"schema","period_start","period_end","evidence_class","date_basis",
                 "privacy","count_semantics","records","sha256"}
    if (set(doc) != allowed_top or doc.get("schema") != "midas_reviewed_execution_archive_v1" or
        doc.get("evidence_class") != "reviewed_migration_schedule_metadata" or
        doc.get("sha256") != digest or
        doc.get("period_start") != "2026-10-01" or doc.get("period_end") != "2026-11-01"):
        raise ValueError("Unreviewed automation archive")
    seen=set()
    allowed={"evidence_id","date","workflow","slots","outcome","attempts",
             "successful_attempts","failed_attempts"}
    for record in doc.get("records",[]):
        key=(record.get("date"),record.get("workflow"))
        if (set(record) != allowed or key in seen or
            not doc["period_start"] <= record["date"] <= doc["period_end"] or
            record["workflow"] not in WORKFLOWS or
            record["slots"] != [slot(i) for i in WORKFLOWS[record["workflow"]]] or
            record["outcome"] not in ("success","failure","unverified") or
            not re.fullmatch(r"ARCH-\d{4}",record["evidence_id"]) or
            any(type(record[k]) is not int or record[k]<0 for k in
                ("attempts","successful_attempts","failed_attempts")) or
            record["attempts"] < 1 or
            record["successful_attempts"] + record["failed_attempts"] > record["attempts"] or
            (record["outcome"]=="success") != (record["successful_attempts"]>0) or
            (record["outcome"]=="failure") != (record["successful_attempts"]==0 and record["failed_attempts"]>0)):
            raise ValueError("Invalid or identifying automation archive record")
        dt.date.fromisoformat(record["date"])
        seen.add(key)
    if not seen:
        raise ValueError("Empty automation archive")
    doc["source_sha256"] = hashlib.sha256(raw).hexdigest()
    return doc


def archived_day(day, archive, quarantines):
    """Only observed outcomes; no fabricated historical schedule inventory."""
    mapped={}
    ref=os.getenv("GITHUB_SHA","main")
    if ref != "main" and not re.fullmatch(r"[a-f0-9]{40}",ref):
        raise ValueError("Invalid public evidence ref")
    for record in archive["records"]:
        if record["date"] != day:
            continue
        for sid in record["slots"]:
            mapped.setdefault(sid,[]).append({
                "workflow":record["workflow"],"status":record["outcome"],
                "run_url":None,"run_id":None,"source_kind":"reviewed_archive",
                "evidence_id":record["evidence_id"],"attempts":record["attempts"],
                "evidence_sha256":archive["source_sha256"],
                "evidence_url":"https://github.com/"+REPO+"/blob/"+ref+"/data/execution-history-archive.json"})
    details=[]
    for sid,workflows in sorted(mapped.items()):
        values=[w["status"] for w in workflows]
        status="failure" if "failure" in values else "unverified" if "unverified" in values else "success"
        reason=quarantines.get((sid,day))
        if status=="success" and reason:
            status="failure"
        details.append({"slot":sid,"status":status,"reason":reason,"workflows":workflows})
    return {"date":day,"data_status":"archived_observations","expected":len(details),
            **{k:sum(d["status"]==k for d in details) for k in ("success","failure","unverified")},
            "not_run":None,"pending":None,"not_scheduled":None,"complete":None,"details":details}


def one_workflow_status(due, runs, now):
    if not due:
        return "not_due", None
    linked = sorted(runs, key=lambda x: x["created_at"])
    succeeded = [r for r in linked if r["conclusion"] == "success"]
    if succeeded:
        return "success", succeeded[-1]
    if any(r["status"] in ("queued", "in_progress", "pending", "waiting") for r in linked):
        return "pending", linked[-1]
    # Report an observed failed attempt immediately. A future backup is not
    # evidence that the failure did not happen; an actual success can recover it.
    if linked and any(r["conclusion"] in ("failure", "timed_out", "cancelled", "action_required") for r in linked):
        return "failure", linked[-1]
    if any(r["conclusion"] == "unverified" for r in linked):
        return "unverified", linked[-1]
    if now < max(due) + GRACE:
        return "pending", linked[-1] if linked else None
    return "not_run", linked[-1] if linked else None


def build(now, runs, schedules, quarantines=None, journals=None, *, actions_available=True, archive=None):
    now = now.astimezone(UTC)
    quarantines = quarantines or {}
    journals = journals or {}
    first_day = min([START] + [dt.date.fromisoformat(d) for d in journals if d <= now.date().isoformat()])
    unique_slots = sorted({slot(x) for v in WORKFLOWS.values() for x in v})
    if len(unique_slots) >= 64 or len(unique_slots) != 26:
        raise ValueError("Unexpected scheduled-algorithm inventory")

    indexed = {}
    first_observed = {}
    for run in runs:
        when = session_of_run(run)
        key = (run["workflow"], when)
        indexed.setdefault(key, []).append(run)
        earlier = first_observed.get(run["workflow"])
        if earlier is None or when < earlier:
            first_observed[run["workflow"]] = when
    archive_first = min(first_observed.values(), default=None)
    end = now.date()
    days = []
    count = 0
    day = end
    while day >= first_day and count < HISTORY_DAYS:
        if day.weekday() < 5 or day.isoformat() in journals:
            if archive and any(r["date"] == day.isoformat() for r in archive["records"]):
                days.append(attach_journals(archived_day(day.isoformat(),archive,quarantines),journals))
                count += 1
                day -= dt.timedelta(days=1)
                continue
            # Historical NAV dates must remain visible, but the GitHub Actions
            # API currently has no corresponding retained scheduled-run logs.
            # We cannot retrospectively claim either zero runs or 64 failures.
            if not actions_available or archive_first is None or day < archive_first:
                days.append(attach_journals({
                    "date": day.isoformat(),
                    "data_status": "not_verifiable",
                    "expected": None,
                    "success": None, "failure": None, "not_run": None,
                    "pending": None, "unverified": None,
                    "not_scheduled": None, "details": [], "complete": None,
                }, journals))
                count += 1
                day -= dt.timedelta(days=1)
                continue
            records = []
            for sid in unique_slots:
                workflow_details = []
                for workflow, attached in WORKFLOWS.items():
                    if int(sid[-3:]) not in attached:
                        continue
                    due = due_times_for_session(day, schedules[workflow])
                    if not due:
                        continue

                    if workflow not in first_observed or day < first_observed[workflow]:
                        # The absence of a workflow from the retained Actions
                        # history is not evidence that an algorithm failed.
                        status, matched = "unverified", None
                    else:
                        status, matched = one_workflow_status(
                            due, indexed.get((workflow, day), []), now)
                    workflow_details.append({
                        "workflow": workflow, "status": status,
                        "run_url": matched["url"] if matched else None,
                        "run_id": matched["id"] if matched else None,
                        "due_last_utc": max(due).isoformat().replace("+00:00", "Z"),
                    })
                if not workflow_details:
                    continue
                statuses = [w["status"] for w in workflow_details]
                status = ("failure" if "failure" in statuses else
                          "unverified" if "unverified" in statuses else
                          "not_run" if "not_run" in statuses else
                          "pending" if "pending" in statuses else "success")
                reason = quarantines.get((sid, day.isoformat()))
                if status == "success" and reason:
                    status = "failure"
                records.append({"slot": sid, "status": status,
                                "reason": reason, "workflows": workflow_details})
            totals = {name: sum(x["status"] == name for x in records)
                      for name in ("success", "failure", "not_run", "pending", "unverified")}
            expected = len(records)
            if sum(totals.values()) != expected:
                raise ValueError("Execution totals do not reconcile")
            days.append(attach_journals({
                "date": day.isoformat(), "expected": expected, **totals,
                "data_status": "partially_verified" if totals["unverified"] else "verified",
                "not_scheduled": 64 - expected,
                "details": records,
                "complete": totals["pending"] == 0 and totals["unverified"] == 0,
            }, journals))
            count += 1
        day -= dt.timedelta(days=1)
    return {
        "schema": SCHEMA,
        "status": "verified_github_actions",
        "source": "Committed paper journals + scheduled GitHub Actions; independent evidence",
        "actions_available": actions_available,
        "reviewed_archive": None if not archive else {
            "first_session": min(r["date"] for r in archive["records"]),
            "last_session": max(r["date"] for r in archive["records"]),
            "records": len(archive["records"]), "source_sha256": archive["source_sha256"]},
        "repository": REPO,
        "as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "first_tracked_session": first_day.isoformat(),
        "oldest_retained_run_session": archive_first.isoformat() if archive_first else None,
        "slot_count": 64,
        "automated_slots": len(unique_slots),
        "unconfigured_slots": 64 - len(unique_slots),
        "count_semantics": "Outcome of scheduled workflow associated with each slot; shared workflow is not proof of independent strategy accounting",
        "days": days,
    }


def verify(document):
    if document.get("schema") != SCHEMA:
        raise ValueError("Invalid execution-health schema")
    if document.get("status") == "unavailable":
        if document.get("days") != []:
            raise ValueError("Unavailable data cannot contain invented days")
        return
    if document.get("status") != "verified_github_actions":
        raise ValueError("Unexpected data status")
    if document.get("slot_count") != 64 or document.get("automated_slots") != 26:
        raise ValueError("Algorithm count mismatch")
    days = document.get("days", [])
    if not isinstance(days, list) or len(days) > HISTORY_DAYS:
        raise ValueError("Invalid execution history size")
    prev = None
    for row in days:
        date = dt.date.fromisoformat(row["date"])
        if prev is not None and date >= prev:
            raise ValueError("Daily history not descending")
        prev = date
        journals = row.get("journals", [])
        keys = {(x.get("slot"),x.get("cohort")) for x in journals}
        if len(keys) != len(journals) or any(
            x.get("slot") not in {slot(i) for i in range(1,65)} or
            not re.fullmatch(r"[a-f0-9]{64}", x.get("source_sha256", "")) or
            not x.get("source_url", "").startswith("https://github.com/" + REPO + "/blob/") or
            type(x.get("inactive")) is not bool or type(x.get("recovered")) is not bool
            for x in journals):
            raise ValueError("Unverifiable accounting evidence")
        if (row.get("journal_count") != len({x["slot"] for x in journals}) or
            row.get("recovered_count") != len({x["slot"] for x in journals if x["recovered"]}) or
            row.get("recovered_failures") != sum(x["status"] == "failure" and x["slot"] in {
                j["slot"] for j in journals if j["recovered"]} for x in row["details"])):
            raise ValueError("Accounting and recovery counts do not reconcile")
        if row.get("data_status") == "archived_observations":
            if (any(row.get(k) is not None for k in ("not_run","pending","not_scheduled","complete")) or
                sum(row[k] for k in ("success","failure","unverified")) != row["expected"] or
                len(row["details"]) != row["expected"] or
                len({d["slot"] for d in row["details"]}) != row["expected"] or
                any(row[k] != sum(d["status"] == k for d in row["details"])
                    for k in ("success","failure","unverified"))):
                raise ValueError("Archive invented schedule inventory or invalid outcome counts")
            for detail in row["details"]:
                if detail["status"] not in ("success","failure","unverified") or not detail["workflows"]:
                    raise ValueError("Invalid archived workflow outcome")
                for w in detail["workflows"]:
                    if (w.get("source_kind") != "reviewed_archive" or w.get("run_url") is not None or
                        w.get("run_id") is not None or
                        w.get("status") not in ("success","failure","unverified") or
                        not re.fullmatch(r"ARCH-\d{4}", w.get("evidence_id", "")) or
                        type(w.get("attempts")) is not int or w["attempts"] < 1 or
                        w.get("workflow") not in WORKFLOWS or
                        detail["slot"] not in [slot(n) for n in WORKFLOWS[w["workflow"]]] or
                        not re.fullmatch(r"[a-f0-9]{64}", w.get("evidence_sha256", "")) or
                        not re.fullmatch(r"https://github.com/idealab2026/laboratorio-cuantitativo/blob/(?:main|[a-f0-9]{40})/data/execution-history-archive\.json",w.get("evidence_url", ""))):
                        raise ValueError("Unreviewed archived evidence or identifying original link")
            continue
        if row.get("data_status") == "not_verifiable":
            if row["details"] != [] or row.get("complete") is not None or any(
                row.get(k) is not None for k in
                ("expected", "success", "failure", "not_run", "pending",
                 "unverified", "not_scheduled")
            ):
                raise ValueError("Unverifiable date must not invent execution counts")
            continue
        if row.get("data_status") not in ("verified", "partially_verified"):
            raise ValueError("Unexpected coverage status")
        count = sum(row[k] for k in
                    ("success", "failure", "not_run", "pending", "unverified"))
        if count != row["expected"] or row["expected"] + row["not_scheduled"] != 64:
            raise ValueError("Daily totals do not reconcile")
        details = row["details"]
        if len(details) != row["expected"] or len({x["slot"] for x in details}) != len(details):
            raise ValueError("Duplicated or missing algorithm statuses")
        for item in details:
            if item["status"] not in ("success", "failure", "not_run", "pending", "unverified"):
                raise ValueError("Invalid workflow status")
            if item["slot"] not in {slot(x) for v in WORKFLOWS.values() for x in v}:
                raise ValueError("Unmapped algorithm")
            if not item["workflows"]:
                raise ValueError("Algorithm lacks scheduled workflow evidence")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--validate")
    args = parser.parse_args()
    if args.validate:
        verify(json.loads(Path(args.validate).read_text(encoding="utf-8")))
        print("Execution history validated")
        return
    if not args.output:
        parser.error("Specify --output or --validate")
    now = dt.datetime.now(UTC)
    schedules = workflow_schedule()
    try:
        token = os.getenv("GH_TOKEN", "")
        journals = journal_evidence()
        try:
            runs = collect_runs(token, now)
            available = True
        except (ValueError, OSError, urllib.error.URLError, KeyError, json.JSONDecodeError):
            runs, available = [], False
        document = build(now, runs, schedules, classic_quarantines(),
                         journals, actions_available=available, archive=reviewed_archive())
    except (ValueError, OSError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
        # A source outage must not turn into a fabricated zero-execution day.
        document = {
            "schema": SCHEMA, "status": "unavailable", "repository": REPO,
            "as_of_utc": now.isoformat().replace("+00:00", "Z"),
            "reason": type(exc).__name__, "days": [],
        }
    document["live_plan"] = live_session_plan(now, schedules)
    verify(document)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(path), "status": document["status"],
                      "rows": len(document["days"]), "algorithms": document.get("automated_slots")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
