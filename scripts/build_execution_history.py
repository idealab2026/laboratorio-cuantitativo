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
START = dt.date(2026, 11, 3)
HISTORY_DAYS = 21
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


def workflow_schedule(root=ROOT):
    result = {}
    for filename in WORKFLOWS:
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


def session_of_run(run):
    started = dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    return (started - dt.timedelta(days=1)).date() if started.hour < 12 else started.date()


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


def one_workflow_status(due, runs, now):
    if not due:
        return "not_due", None
    linked = sorted(runs, key=lambda x: x["created_at"])
    succeeded = [r for r in linked if r["conclusion"] == "success"]
    if succeeded:
        return "success", succeeded[-1]
    if any(r["status"] in ("queued", "in_progress", "pending", "waiting") for r in linked):
        return "pending", linked[-1]
    if now < max(due) + GRACE:
        return "pending", linked[-1] if linked else None
    if linked and any(r["conclusion"] in ("failure", "timed_out", "cancelled", "action_required") for r in linked):
        return "failure", linked[-1]
    return "not_run", linked[-1] if linked else None


def build(now, runs, schedules, quarantines=None):
    now = now.astimezone(UTC)
    quarantines = quarantines or {}
    unique_slots = sorted({slot(x) for v in WORKFLOWS.values() for x in v})
    if len(unique_slots) >= 64 or len(unique_slots) != 26:
        raise ValueError("Unexpected scheduled-algorithm inventory")
    indexed = {}
    for run in runs:
        key = (run["workflow"], session_of_run(run))
        indexed.setdefault(key, []).append(run)
    end = now.date()
    days = []
    count = 0
    day = end
    while day >= START and count < HISTORY_DAYS:
        if day.weekday() < 5:
            records = []
            for sid in unique_slots:
                workflow_details = []
                for workflow, attached in WORKFLOWS.items():
                    if int(sid[-3:]) not in attached:
                        continue
                    due = due_times_for_session(day, schedules[workflow])
                    if not due:
                        continue
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
                          "not_run" if "not_run" in statuses else
                          "pending" if "pending" in statuses else "success")
                reason = quarantines.get((sid, day.isoformat()))
                if status == "success" and reason:
                    status = "failure"
                records.append({"slot": sid, "status": status,
                                "reason": reason, "workflows": workflow_details})
            totals = {name: sum(x["status"] == name for x in records)
                      for name in ("success", "failure", "not_run", "pending")}
            expected = len(records)
            if sum(totals.values()) != expected:
                raise ValueError("Execution totals do not reconcile")
            days.append({
                "date": day.isoformat(), "expected": expected, **totals,
                "not_scheduled": 64 - expected,
                "details": records,
                "complete": totals["pending"] == 0,
            })
            count += 1
        day -= dt.timedelta(days=1)
    return {
        "schema": SCHEMA,
        "status": "verified_github_actions",
        "source": "GitHub Actions schedule runs + explicit MIDAS slot mapping",
        "repository": REPO,
        "as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "first_tracked_session": START.isoformat(),
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
        count = sum(row[k] for k in ("success", "failure", "not_run", "pending"))
        if count != row["expected"] or row["expected"] + row["not_scheduled"] != 64:
            raise ValueError("Daily totals do not reconcile")
        details = row["details"]
        if len(details) != row["expected"] or len({x["slot"] for x in details}) != len(details):
            raise ValueError("Duplicated or missing algorithm statuses")
        for item in details:
            if item["status"] not in ("success", "failure", "not_run", "pending"):
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
    try:
        token = os.getenv("GH_TOKEN", "")
        runs = collect_runs(token, now)
        document = build(now, runs, workflow_schedule(), classic_quarantines())
    except (ValueError, OSError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
        # A source outage must not turn into a fabricated zero-execution day.
        document = {
            "schema": SCHEMA, "status": "unavailable", "repository": REPO,
            "as_of_utc": now.isoformat().replace("+00:00", "Z"),
            "reason": type(exc).__name__, "days": [],
        }
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
