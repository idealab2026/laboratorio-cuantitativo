"""Bounded rendezvous for the EXISTING MIDAS market clock near XNYS close.

This is not a second engine or ledger. When an already-running scheduled
GitHub job reached the session by ~15:31 ET, keep that same job available for
one LAST causal observed-quote attempt around 15:55:30 ET. This reduces
reliance on 15:56/15:58 cron arrivals (which can be delayed 30+ minutes).
If the original pre-open lock is absent, stale or changed, never create one.

The normal operational_clock.py performs the actual risk checks, native
settlement, and quote provenance. Publication remains in the same workflow.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from forward_open_il039 import market_window
from operational_clock import ROOT, _read, main as run_operator, verify_prepared_lock

UTC = timezone.utc
WATCH_HORIZON = timedelta(minutes=35)
LATEST_ARM = timedelta(minutes=6)
TARGET_BEFORE_CLOSE = timedelta(minutes=4, seconds=30)
MAX_SLEEP_SECONDS = 35 * 60


def preclose_target(now, market, lock):
    """Return exchange-local rendezvous datetime or None; NEVER derive a fill."""
    if now.tzinfo is None or not market or not isinstance(lock, dict):
        return None
    close = market["close"]
    if not (market["open"] < close - WATCH_HORIZON <= now
            < close - LATEST_ARM and lock.get("session") == market["session"]):
        return None

    from tfg_ahp.data import is_week_end_session
    friday = is_week_end_session(market["session"])
    lanes = lock.get("slots", {})
    watch = []
    for slot, lane in lanes.items():
        if not isinstance(lane, dict) or not lane.get("monitor_tickers"):
            continue
        if not (lane.get("execution_ready") or lane.get("exit_only_ready")):
            continue
        weekly = slot in {f"IL-{i:03d}" for i in range(19, 28)}
        if (weekly and friday or slot in ("IL-037", "IL-042")
                or slot == "IL-040" and friday):
            watch.append(slot)
    if not watch:
        return None
    return close - TARGET_BEFORE_CLOSE


def _report(status, **extra):
    data = {"mode": "same_shared_clock_preclose_rendezvous",
            "status": status, **extra}
    print(json.dumps(data, sort_keys=True), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf8") as fh:
            fh.write(f"\nMIDAS preclose guard: **{status}** — "
                     f"session={extra.get('session', 'N/D')}\n")


def main():
    now = datetime.now(UTC)
    market = market_window(now)
    if not market:
        _report("exchange_closed_no_watch")
        return 0
    lockpath = ROOT / "forward_open_state/global-lock.json"
    publicpath = ROOT / "data/operational-clock.json"
    if not lockpath.is_file():
        _report("no_preopen_lock_no_watch", session=market["session"])
        return 0
    lock = _read(lockpath)
    # Ignore a prior day's lock when a delayed job finally starts. No late
    # rebuilding, re-dating or reuse of somebody else's execution plan.
    if lock.get("session") != market["session"]:
        _report("stale_lock_no_watch", session=market["session"])
        return 0
    verify_prepared_lock(lock, market)
    target = preclose_target(now, market, lock)
    if target is None:
        _report("outside_watch_window_or_no_close_orders", session=market["session"])
        return 0
    seconds = (target - now).total_seconds()
    if not 0 < seconds <= MAX_SLEEP_SECONDS:
        raise ValueError("Invalid bounded wait duration for exchange close")
    _report("armed", session=market["session"], wait_seconds=round(seconds),
            target_at_utc=target.isoformat())
    # One sleeping GitHub job is more reliable than a 15:59 cron that may
    # not start until 16:30. Does not poll, consume market data, or trade.
    time.sleep(seconds)
    observed = datetime.now(UTC)
    new_market = market_window(observed)
    if (not new_market or new_market["session"] != market["session"]
            or not target <= observed < market["close"]):
        _report("wake_missed_market_close_no_fill", session=market["session"])
        return 2
    # The true quote timestamp is collected anew by the original operator.
    # Never reuse a price from the earlier 15:31 observation.
    result = run_operator(["--stage", "observe", "--lock", str(lockpath),
                           "--public", str(publicpath)])
    if result != 0:
        _report("native_observation_refused", session=market["session"],
                operator_result=result)
        return result
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf8") as fh:
            fh.write("observed=true\n")
    _report("completed_operator_attempt", session=market["session"],
            sampled_at_utc=observed.isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
