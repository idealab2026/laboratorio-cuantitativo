"""Read-only NYSE opening plans reconstructed from pre-opening Git trees."""
from datetime import timedelta
from functools import lru_cache
import json
import subprocess
from zoneinfo import ZoneInfo

from build_operations_audit import ROOT, date, pending_signals, signal_book, source_book, source_for

# These engines consume a pending order on the next XNYS session, even
# when its ledger only stores signal_date. Archived weekly engines are excluded.
NEXT_OPEN = {*range(10, 28), 40, 41, 42, 43}
LEGACY = set(range(28, 37))


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf8")


def plan_track(slot, book, target, previous):
    if not isinstance(book, dict):
        return {"status": "unavailable", "session": None, "orders": [], "holdings": [], "undated": 0}
    history = book.get("equity") or []
    last = date(history[-1].get("date")) if history else date(book.get("last_session"))
    code = int(slot[3:])
    if code == 37:
        # AHP closes its signal on Friday and enters the following XNYS
        # opening. During the week, its official incremental book supplies
        # the verified prior close for next-open portfolio stop orders.
        forward = book.get("forward_book")
        if isinstance(forward, dict):
            if forward.get("status") != "open":
                return {"status": "recorded" if forward.get("status") == "closed" else "paused",
                        "session": previous, "orders": [], "holdings": [], "undated": 0}
            holdings = sorted(forward.get("positions", {}))
            latest = forward.get("last_mark_session")
            eligible = latest == previous and not forward.get("unresolved_exit")
            orders = ([{"ticker": t, "action": "sell", "decision_session": previous,
                        "target_session": target, "target_weight": 0,
                        "limit_price": None}
                       for t in holdings] if eligible and forward.get("stop_due") else [])
            return {"status": "recorded" if eligible else "stale",
                    "session": latest, "orders": orders, "holdings": holdings,
                    "undated": 0}
        signal = book.get("pending_signal")
        decision = signal.get("asof") if isinstance(signal, dict) else None
        eligible = (decision == previous and decision >= "2026-11-13"
                    and book.get("last_signal_session") == decision)
        selections = signal.get("selections", []) if isinstance(signal, dict) else []
        orders = ([{"ticker": x["ticker"], "action": "buy",
                    "decision_session": decision, "target_session": target,
                    "target_weight": float(x["weight"]), "limit_price": None}
                   for x in selections] if eligible else [])
        return {"status": "recorded" if eligible else "stale",
                "session": decision, "orders": orders, "holdings": [], "undated": 0}
    rows = pending_signals(book)
    orders, holdings, undated = [], [], 0
    for row in rows:
        if row["action"] == "hold":
            holdings.append(row["ticker"])
            continue
        if code in LEGACY:
            continue
        decision, execution = row["decision_session"], row["target_session"]
        if decision and decision >= target:
            continue
        if execution is None and code in NEXT_OPEN and decision == previous:
            execution = target
        if execution == target and decision:
            orders.append({**row, "target_session": execution})
        elif execution is None:
            undated += 1
    status = ("archived" if code in LEGACY else "paused" if book.get("paused_missing_quotes")
              else "recorded" if last == previous else "stale")
    return {"status": status, "session": last, "orders": orders, "holdings": holdings, "undated": undated}


def plan_at(commit, target, previous):
    @lru_cache(maxsize=None)
    def read(path):
        result = git("show", f"{commit}:{path}")
        return (json.loads(result.stdout), None) if result.returncode == 0 else (None, None)

    registry, _ = read("data/original-track-map.json")
    dashboard, _ = read("strategy_state/dashboard.json")
    if not registry or not dashboard:
        return {}
    tracks = {}
    for original in dashboard["tracks"]:
        source_id = original["id"]
        slot = registry.get(source_id)
        if not slot or not 10 <= int(slot[3:]) <= 44:
            continue
        filename, key = source_for(source_id)
        doc, _ = read(filename) if filename else (None, None)
        book, _, _ = signal_book(source_id, source_book(doc, filename, key) if filename else None,
                                 filename, doc, read_source=read)
        tracks[slot] = plan_track(slot, book, target, previous)
    return tracks


def opening_plans(now):
    import pandas_market_calendars as calendars

    local = now.astimezone(ZoneInfo("America/New_York")).date()
    schedule = calendars.get_calendar("XNYS").schedule(
        start_date=local - timedelta(days=24), end_date=local + timedelta(days=10))
    days = [(index.date().isoformat(), row["market_open"].to_pydatetime())
            for index, row in schedule.iterrows()]
    pivot = next(i for i, (day, _) in enumerate(days) if day > local.isoformat())
    plans = {}
    for i in range(max(1, pivot - 5), pivot + 1):
        day, opens_at = days[i]
        previous = days[i - 1][0]
        cutoff = min(now, opens_at - timedelta(seconds=1))
        commit = git("rev-list", "-1", "--first-parent", f"--before={cutoff.isoformat()}", "HEAD")
        commit.check_returncode()
        sha = commit.stdout.strip()
        if not sha:
            continue
        plans[day] = {"opens_at": opens_at.isoformat(), "previous_session": previous,
                      "source_commit": sha, "tracks": plan_at(sha, day, previous)}
    return plans
