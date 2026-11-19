#!/usr/bin/env python3
"""One exchange-clock execution-observation journal across eligible MIDAS paper slots.

Causal, fail-closed; original engines keep their separate historically audited ledgers.
An observed intraday *signal* is NOT a broker fill or a canonical paper fill.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from forward_open_il039 import digest, market_window, quotes_yahoo, timestamp

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "midas.operational_clock.v1"
UTC = timezone.utc
ACTIVE = tuple(f"IL-{n:03d}" for n in (*range(10, 28), *range(37, 45)))
MAX_SECONDS = 180
LIMIT = 250
PREOPEN_HORIZON = timedelta(hours=4)  # early redundant scheduler attempts, never post-open
# Bounded same-job close rendezvous: no new runner, ledger or retrospective fill.
WATCH_HORIZON = timedelta(minutes=35)
LATEST_ARM = timedelta(minutes=6)
TARGET_BEFORE_CLOSE = timedelta(minutes=4, seconds=30)
MAX_SLEEP_SECONDS = 35 * 60
# Cron starts were absent before the 2026-11-18 opening. A single preopen
# job may stay alive until a fresh first observation; no retroactive fill.
OPEN_WATCH_HORIZON = timedelta(minutes=80)
OPEN_WATCH_LATEST_ARM = timedelta(minutes=5)
OPEN_OBSERVE_OFFSET = timedelta(minutes=4)
OPEN_WATCH_LATEST_WAKE = timedelta(minutes=20)
OPEN_MAX_SLEEP_SECONDS = 85 * 60


def _repo_commit():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _write(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf8")
    os.replace(tmp, path)


def clock_plan(now, market, tracks, commit, *, fx_reference=None):
    if now.tzinfo is None or not market or not (
            market["open"] - PREOPEN_HORIZON <= now < market["open"]):
        raise ValueError("A new opening may only be locked before that opening")
    if not len(commit) == 40 or not all(c in "0123456789abcdef" for c in commit):
        raise ValueError("Source Git commit SHA required")
    slots = {}
    for slot in ACTIVE:
        record = tracks.get(slot)
        status = record.get("status") if isinstance(record, dict) else "unavailable"
        source_session = record.get("session") if isinstance(record, dict) else None
        eligible = status == "recorded" and source_session == market["previous"]
        weekly_slot = slot in {f"IL-{n:03d}" for n in range(19, 28)}
        # An independently paused portfolio may exit a frozen long position
        # at a future observed preclose, without reviving stale entry orders.
        exit_only_ready = (weekly_slot and isinstance(record, dict)
                           and status == "paused" and source_session == market["previous"]
                           and bool(record.get("holdings")) and not record.get("orders"))
        proposals = record.get("orders", []) if isinstance(record, dict) else []
        orders = []
        seen = set()
        for row in proposals:
            if not isinstance(row, dict):
                continue
            ticker = row.get("ticker")
            action = row.get("action")
            decision = row.get("decision_session")
            target = row.get("target_session")
            weight = row.get("target_weight")
            limit = row.get("limit_price")
            if not (isinstance(ticker, str) and 0 < len(ticker) <= 14 and
                    all(ch.isupper() or ch.isdigit() or ch in ".-" for ch in ticker) and
                    action in ("buy", "sell", "rebalance") and
                    isinstance(decision, str) and decision < market["session"] and
                    target == market["session"] and ticker not in seen):
                continue
            if weight is not None and not (type(weight) in (float, int) and math.isfinite(weight)
                                           and 0 <= weight <= 1):
                continue
            if limit is not None and not (type(limit) in (float, int) and math.isfinite(limit)
                                          and limit > 0):
                continue
            seen.add(ticker)
            orders.append({"ticker": ticker, "action": action, "signal_session": decision,
                           "target_session": target, "scheduled_at_utc": timestamp(market["open"]),
                           "target_weight": weight, "limit_price": limit})
        slots[slot] = {
            "source_status": status, "source_session": source_session,
            "exit_only_ready": exit_only_ready,
            "execution_ready": eligible,
            "orders": sorted(orders, key=lambda row: row["ticker"]) if eligible else [],
            "orders_count": len(orders) if eligible else 0,
            "holdings_count": len(record.get("holdings", [])) if isinstance(record, dict) else 0,
            # Only tactical classic portfolios monitor real observed stops.
            # Passive 503-position buy-and-hold is excluded from free quote reads.
            "monitor_tickers": (
                sorted(set(record.get("holdings", []))
                       | ({o["ticker"] for o in orders} if slot in ("IL-042", "IL-044") else set()))
                if (eligible or exit_only_ready) and (slot in {f"IL-{n:03d}" for n in range(11, 18)}
                                 or slot in {f"IL-{n:03d}" for n in range(19, 28)}
                                 or slot in ("IL-037", "IL-040", "IL-042", "IL-044"))
                and isinstance(record, dict) else []),
        }
    lock = {"schema": SCHEMA, "session": market["session"],
            "previous_session": market["previous"], "source_commit": commit,
            "open_at_utc": timestamp(market["open"]),
            "prepared_at_utc": timestamp(now), "slots": slots}
    if fx_reference is not None:
        if (not isinstance(fx_reference, dict) or
                fx_reference.get("source_session") != market["previous"] or
                fx_reference.get("pair") != "EURUSD=X" or
                not (datetime.fromisoformat(
                    fx_reference["captured_at_utc"].replace("Z","+00:00"))
                    <= now < market["open"]) or
                type(fx_reference.get("rate_usd_per_eur")) not in (int, float) or
                not math.isfinite(fx_reference["rate_usd_per_eur"]) or
                fx_reference["rate_usd_per_eur"] <= 0):
            raise ValueError("Invalid or mismatched pre-opening FX evidence")
        lock["fx_reference"] = copy.deepcopy(fx_reference)
    lock["lock_sha256"] = digest(lock)
    return lock


def verify_lock(lock, market, now):
    if not market or not isinstance(lock, dict) or lock.get("schema") != SCHEMA:
        raise ValueError("No verified opening plan")
    expected = {key: val for key, val in lock.items() if key != "lock_sha256"}
    if digest(expected) != lock.get("lock_sha256"):
        raise ValueError("Pre-opening plan modified")
    before = datetime.fromisoformat(lock["prepared_at_utc"].replace("Z", "+00:00"))
    if not (lock["session"] == market["session"] and lock["previous_session"] == market["previous"]
            and lock["open_at_utc"] == timestamp(market["open"])
            and before < market["open"] <= now <= market["close"]):
        raise ValueError("Opening plan belongs to another time or session")
    if not isinstance(lock["slots"], dict) or set(lock["slots"]) != set(ACTIVE):
        raise ValueError("Missing algorithm-specific operating lanes")


def verify_prepared_lock(lock, market):
    """Authenticate a pre-open lock without pretending the market has opened.

    Used on retry: an already-published valid plan is immutable until the
    session finishes, regardless of later ledger commits or cron delays.
    """
    if not isinstance(lock, dict) or not market or lock.get("schema") != SCHEMA:
        raise ValueError("Missing or invalid frozen pre-open lock")
    if digest({k: v for k, v in lock.items() if k != "lock_sha256"}) != lock.get("lock_sha256"):
        raise ValueError("Pre-open lock hash mismatch: refusing overwrite")
    prepared = datetime.fromisoformat(lock["prepared_at_utc"].replace("Z", "+00:00"))
    if not (lock.get("session") == market["session"] and
            lock.get("previous_session") == market["previous"] and
            lock.get("open_at_utc") == timestamp(market["open"]) and
            market["open"] - PREOPEN_HORIZON <= prepared < market["open"] and
            set(lock.get("slots", {})) == set(ACTIVE)):
        raise ValueError("Frozen pre-open lock does not match session or eligibility")
    fx = lock.get("fx_reference")
    if fx is not None:
        try:
            captured = datetime.fromisoformat(fx["captured_at_utc"].replace("Z", "+00:00"))
            if (fx.get("source_session") != market["previous"] or
                    fx.get("pair") != "EURUSD=X" or captured > prepared or
                    captured >= market["open"] or
                    not math.isfinite(float(fx["rate_usd_per_eur"])) or
                    float(fx["rate_usd_per_eur"]) <= 0):
                raise ValueError("Invalid frozen FX reference")
        except (TypeError, KeyError, OverflowError) as exc:
            raise ValueError("Malformed frozen FX reference") from exc
    return True


def stage_for_actual_time(requested, now, market):
    """A delayed scheduled *prepare* event becomes observe, NEVER late FX freeze."""
    if requested not in ("auto", "prepare", "observe"):
        raise ValueError("Unrecognized clock stage")
    if requested == "auto":
        return "prepare" if now < market["open"] else "observe"
    return requested


def verify_published_lock(path=ROOT / "forward_open_state/global-lock.json"):
    """Verify the commit actually published the original hash-locked plan."""
    path = Path(path)
    if not path.is_file():
        return {"status": "no_local_lock"}
    local = json.loads(path.read_text(encoding="utf8"))
    remote = subprocess.run(["git", "show", "origin/main:" + str(path.relative_to(ROOT))],
                            cwd=ROOT, capture_output=True, text=True)
    if remote.returncode != 0:
        raise ValueError("Pre-open lock absent from origin/main after publish")
    saved = json.loads(remote.stdout)
    if local != saved or digest({k: v for k, v in local.items() if k != "lock_sha256"}) != local.get("lock_sha256"):
        raise ValueError("Pre-open lock on origin/main differs from frozen local plan")
    return {"status": "published_and_hash_verified", "session": local["session"],
            "sha256": local["lock_sha256"]}


def _quote_valid(quote, now, market):
    if not isinstance(quote, dict):
        return False
    try:
        stamp = datetime.fromisoformat(quote["quote_at_utc"].replace("Z", "+00:00"))
        observed = datetime.fromisoformat(quote["observed_at_utc"].replace("Z", "+00:00"))
        value = quote["price"]
        return (type(value) in (float, int) and math.isfinite(value) and value > 0 and
                market["open"] <= stamp <= observed <= now and
                timedelta(0) <= observed - stamp <= timedelta(seconds=MAX_SECONDS) and
                now - stamp <= timedelta(seconds=MAX_SECONDS))
    except (ValueError, TypeError, KeyError):
        return False


def record_opening_quote_diagnostic(lane, previous_lane, frozen_lane, evidence, now, market):
    """Publish why an opening was not booked; never infer or alter any fill.

    The indicative order quote alone is insufficient: classical portfolios
    require contemporaneous quotes for every held position plus pending orders.
    Retain the first missing set through retries to diagnose provider gaps.
    """
    if (lane.get("planned", 0) == 0 or
            evidence.get("status") not in ("awaiting_fresh_open_quotes", "opening_window_missed")):
        return
    required = sorted(set(frozen_lane.get("monitor_tickers", [])) |
                      {r["ticker"] for r in frozen_lane.get("orders", [])})
    missing = sorted(set(evidence.get("missing", [])))
    if not set(missing).issubset(required):
        raise ValueError("Opening quote diagnostic contains an unexpected ticker")
    previous = previous_lane.get("opening_quote_diagnostic", {})
    if not isinstance(previous, dict):
        raise ValueError("Malformed previous opening quote diagnostic")
    first_missing = previous.get("first_missing_tickers", missing)
    first_at = previous.get("first_missing_at_utc",
                            timestamp(now) if missing else None)
    lane["opening_quote_diagnostic"] = {
        "settlement_status": evidence["status"],
        "required_tickers": required,
        "missing_tickers_at_last_attempt": missing,
        "first_missing_tickers": first_missing,
        "first_missing_at_utc": first_at,
        "last_checked_at_utc": timestamp(now),
        "opening_cutoff_at_utc": timestamp(market["open"] + timedelta(minutes=30)),
        "all_required_quotes_available_now": not bool(missing),
    }


def publish_missed_open(lane, evidence):
    """Show terminal opening misses; never turn an observed quote into a fill."""
    if (evidence.get("status") != "opening_window_missed" or
            lane.get("status") in ("native_forward_settled", "opening_window_missed")):
        return False
    lane["status"] = "opening_window_missed"
    lane["waiting"] = 0
    lane["opening_order_execution"] = "unfilled_expired"
    return True


def status_report(lock, now, market, quotes, prior=None, *, run_id=None):
    verify_lock(lock, market, now)
    if prior is not None and prior.get("session") != lock["session"]:
        prior = None
    slots = {}
    for slot, entry in lock["slots"].items():
        prev = (prior or {}).get("slots", {}).get(slot, {})
        if prev.get("status") == "native_forward_settled":
            slots[slot] = copy.deepcopy(prev)
            continue
        saved = {r["ticker"]: r for r in prev.get("orders", []) if r.get("status") == "price_observed"}
        rows = []
        for proposal in entry["orders"]:
            ticker = proposal["ticker"]
            prior_observation = saved.get(ticker)
            quote = quotes.get(ticker)
            if prior_observation:
                rows.append(prior_observation)
                continue
            if _quote_valid(quote, now, market):
                price = quote["price"]
                # Limit orders never fill merely because the last traded price crossed:
                # only a fresh indicative observation is recorded.
                limited = proposal["limit_price"] is not None
                crossed = (price <= proposal["limit_price"] if limited and proposal["action"] == "buy"
                           else price >= proposal["limit_price"] if limited and proposal["action"] == "sell"
                           else False)
                stage = "limit_observed" if limited and crossed else (
                    "limit_not_met" if limited else "price_observed")
                rows.append({**proposal, "status": stage, "observed_price": price,
                             "quote_at_utc": quote["quote_at_utc"],
                             "observed_at_utc": quote["observed_at_utc"],
                             "source": "yfinance_1m"})
            else:
                rows.append({**proposal, "status": "waiting_fresh_quote",
                             "observed_price": None, "quote_at_utc": None,
                             "observed_at_utc": None, "source": None})
        counts = {
            "planned": len(rows),
            "observed": sum(r["status"] in ("price_observed", "limit_observed", "limit_not_met") for r in rows),
            "waiting": sum(r["status"] == "waiting_fresh_quote" for r in rows),
        }
        if not entry["execution_ready"]:
            status = "source_stale_or_unavailable"
        elif not rows:
            status = "active_no_orders"
        elif counts["waiting"]:
            status = "partial_data"
        else:
            status = "prices_observed_not_settled"
        slots[slot] = {
            "status": status, "source_session": entry["source_session"],
            "planned": counts["planned"], "observed": counts["observed"],
            "waiting": counts["waiting"], "holdings_count": entry["holdings_count"],
            "orders": rows,
        }
    return {
        "schema": SCHEMA, "session": lock["session"],
        "previous_session": lock["previous_session"],
        "source_commit": lock["source_commit"], "lock_sha256": lock["lock_sha256"],
        "open_at_utc": lock["open_at_utc"], "prepared_at_utc": lock["prepared_at_utc"],
        "checked_at_utc": timestamp(now), "run_id": int(run_id) if run_id else None,
        "mode": "single_midas_operator_monitor_no_broker",
        "settlement": "native_engine_batch_until_migrated",
        "slots": slots,
        "note": "Observed quotes are not fills. A native engine must settle quantity/cash before a trade counts in P&L.",
    }


def freeze_timesfm_entry_fx(now, market):
    """Capture the previous XNYS session's EURUSD daily close BEFORE opening.

    This is explicitly a pre-observed paper FX proxy, not an executable
    broker quote. Missing/ambiguous/late data disables TimesFM entry fills.
    """
    if now.tzinfo is None or now >= market["open"]:
        raise ValueError("FX may only be frozen before the opening")
    import yfinance as yf
    prev = market["previous"]
    start = prev
    end = market["session"]
    try:
        frame = yf.Ticker("EURUSD=X").history(
            start=start, end=end, interval="1d",
            auto_adjust=False, actions=False)
        if frame is None or frame.empty:
            return None
        matches = frame.loc[frame.index.strftime("%Y-%m-%d") == prev]
        if len(matches) != 1:
            return None
        value = float(matches.iloc[0]["Close"])
        received = datetime.now(UTC)
        if not math.isfinite(value) or value <= 0 or received >= market["open"]:
            return None
        return {
            "pair": "EURUSD=X", "source": "yfinance_unadjusted_daily_close",
            "source_session": prev, "rate_usd_per_eur": value,
            "captured_at_utc": timestamp(received),
            "purpose": "paper_previous_XNYS_session_FX_proxy",
        }
    except (ValueError, TypeError, KeyError, OSError, IndexError):
        return None


def budgeted_quote_targets(lock, prior=None, *, limit=LIMIT, now=None, market=None):
    """Reserve whole algorithm-specific requests without silently truncating.

    Priority is given to scarce next-open cash flows (monthly and ML), then
    tactical classic stop orders; passive 503-constituent books are last.
    No dropped order can be misreported as executable or partial success.
    """
    if type(limit) is not int or limit < 1:
        raise ValueError("Positive hard quote budget required")
    settled = (prior or {}).get("slots", {})
    requested, omitted = set(), {}
    slots = lock["slots"]
    priority = (
        ["IL-038", "IL-039"] +
        [f"IL-{i:03d}" for i in range(19, 28)] +
        [f"IL-{i:03d}" for i in range(11, 18)] +
        ["IL-037", "IL-040", "IL-041", "IL-042", "IL-043", "IL-044"] +
        ["IL-010", "IL-018"]
    )
    priority += sorted(set(slots) - set(priority))
    for slot in priority:
        if slot not in slots:
            continue
        lane = slots[slot]
        # A settled lane only needs its monitoring stops, not replayed orders.
        remaining = (set() if settled.get(slot, {}).get("status") == "native_forward_settled"
                     else {r["ticker"] for r in lane["orders"]})
        monitored = set(lane.get("monitor_tickers", []))
        if slot in {f"IL-{n:03d}" for n in range(19, 28)}:
            # Freeze all held names; request them only in the LAST weekly
            # preclose window, never sacrifice the daily free quote quota.
            is_close = (now is not None and market is not None
                        and now >= market["close"] - timedelta(minutes=6))
            if is_close:
                from tfg_ahp.data import is_week_end_session
                is_close = is_week_end_session(market["session"])
            last_marker = settled.get(slot, {}).get("native_marker") or {}
            if (last_marker.get("mode") == "weekly_observed_exit"
                    and last_marker.get("session") == (market or {}).get("session")):
                is_close = False
            if not is_close:
                monitored = set()
        if slot in ("IL-037", "IL-040", "IL-042"):
            # Demand a fresh observed USD stock quote and contemporaneous FX
            # only near the actual closing window. Do not burn the daily
            # budget chasing weekly strategy holdings all day.
            is_close = (now is not None and market is not None
                        and now >= market["close"] - timedelta(minutes=6))
            if slot == "IL-040" and is_close:
                from tfg_ahp.data import is_week_end_session
                is_close = is_week_end_session(market["session"])
            last_marker = settled.get(slot, {}).get("native_marker") or {}
            if last_marker.get("mode") == "exit" and last_marker.get("session") == (market or {}).get("session"):
                is_close = False
            if not is_close:
                monitored = set()
            elif slot in ("IL-040", "IL-042") and monitored:
                monitored.add("EURUSD=X")
        remaining |= monitored
        if not remaining or not (lane.get("execution_ready") or lane.get("exit_only_ready")):
            continue
        if len(requested | remaining) > limit:
            omitted[slot] = {
                "reason": "quota_cap_fail_closed",
                "required": len(remaining),
                "additional": len(remaining - requested),
            }
            continue
        requested |= remaining
    return requested, omitted


def quote_batch(tickers, now, market):
    """Read minute quotes without concurrent access to yfinance's SQLite cache.

    yfinance's lazy timezone/cookie caches are shared across threads. The
    previous five-worker ThreadPoolExecutor could produce peewee.OperationalError
    'database is locked' and abort the entire clock before journal publication.
    One vendor call at a time is intentionally preferred over throughput:
    strict freshness checks after receipt still reject delayed quotes.
    """
    symbols = sorted(set(tickers))
    if len(symbols) > LIMIT:
        raise ValueError("Quote budget exceeded: never silently truncate a paper lane")
    result = {}
    for symbol in symbols:
        try:
            # Independent per-symbol failure isolation; never substitute an
            # older daily bar or fabricate an observation when a query fails.
            result.update(quotes_yahoo([symbol], now, market))
        except (ValueError, OSError, TypeError) as exc:
            print(f"midas_quote_unavailable symbol={symbol} error={type(exc).__name__}",
                  file=sys.stderr)
        except Exception as exc:
            # A second vendor-side SQLite contention must not erase the
            # successful quotes gathered for other symbols. This narrow
            # compatibility guard covers both sqlite3 and Peewee exceptions.
            if not ("database is locked" in str(exc).lower() and
                    (isinstance(exc, sqlite3.OperationalError) or
                     type(exc).__name__ == "OperationalError")):
                raise
            print(f"midas_yfinance_cache_lock symbol={symbol} skipped_no_fill",
                  file=sys.stderr)
    return result


def open_rendezvous_target(now, market, lock):
    """Real XNYS opening observation from an already-running preopen job.

    Returns a future time, never a trade price, signal, or revised lock.
    Shorter than GitHub's 90-minute job timeout including setup/publication.
    """
    if now.tzinfo is None or not market or not isinstance(lock, dict):
        return None
    opening = market["open"]
    if not (lock.get("session") == market["session"] and
            opening - OPEN_WATCH_HORIZON <= now <
            opening - OPEN_WATCH_LATEST_ARM):
        return None
    lanes = lock.get("slots", {})
    if not isinstance(lanes, dict) or not any(
            isinstance(lane, dict) and lane.get("execution_ready")
            and (lane.get("orders") or lane.get("monitor_tickers"))
            for lane in lanes.values()):
        return None
    return opening + OPEN_OBSERVE_OFFSET


def run_open_watch(lockpath, publicpath):
    """Observe using the ORIGINAL operator, after first lock publication.

    This bounded in-job wait is a fallback for delayed GitHub cron. It
    never creates an opening plan, never reuses quotes, and never publishes
    a retroactive order. The workflow handles the sole subsequent commit.
    """
    now = datetime.now(UTC)
    market = market_window(now)
    if not market:
        _preclose_report("open_watch_exchange_closed")
        return 0
    if not lockpath.is_file():
        _preclose_report("open_watch_no_frozen_lock", session=market["session"])
        return 0
    lock = _read(lockpath)
    if lock.get("session") != market["session"]:
        _preclose_report("open_watch_other_session", session=market["session"])
        return 0
    verify_prepared_lock(lock, market)
    target = open_rendezvous_target(now, market, lock)
    if target is None:
        _preclose_report("open_watch_outside_window_or_no_orders", session=market["session"])
        return 0
    seconds = (target - now).total_seconds()
    if not 0 < seconds <= OPEN_MAX_SLEEP_SECONDS:
        raise ValueError("Invalid bounded wait for NYSE opening")
    _preclose_report("open_watch_armed", session=market["session"],
                     wait_seconds=round(seconds), target_at_utc=target.isoformat())
    time.sleep(seconds)
    observed = datetime.now(UTC)
    market_at_wake = market_window(observed)
    if (not market_at_wake or market_at_wake["session"] != market["session"] or
            not target <= observed <= market["open"] + OPEN_WATCH_LATEST_WAKE or
            observed >= market["close"]):
        _preclose_report("open_watch_woke_too_late_no_fill", session=market["session"])
        return 2
    # Fresh quote batch; native settlers validate exact frozen plan,
    # <=180s quote age, cash/position match, and individual order cutoff.
    result = main(["--stage", "observe", "--lock", str(lockpath),
                   "--public", str(publicpath)])
    if result != 0:
        _preclose_report("open_watch_operator_refused", session=market["session"],
                         result=result)
        return result
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf8") as fh:
            fh.write("observed=true\n")
    _preclose_report("open_watch_observed_pending_native_publication",
                     session=market["session"], timestamp=timestamp(observed))
    return 0


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


def _preclose_report(status, **extra):
    data = {"mode": "same_shared_clock_preclose_rendezvous",
            "status": status, **extra}
    print(json.dumps(data, sort_keys=True), flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf8") as fh:
            fh.write(f"\nMIDAS preclose guard: **{status}** — "
                     f"session={extra.get('session', 'N/D')}\n")


def run_preclose_watch(lockpath, publicpath):
    now = datetime.now(UTC)
    market = market_window(now)
    if not market:
        _preclose_report("exchange_closed_no_watch")
        return 0
    if not lockpath.is_file():
        _preclose_report("no_preopen_lock_no_watch", session=market["session"])
        return 0
    lock = _read(lockpath)
    # Ignore a prior day's lock when a delayed job finally starts. No late
    # rebuilding, re-dating or reuse of somebody else's execution plan.
    if lock.get("session") != market["session"]:
        _preclose_report("stale_lock_no_watch", session=market["session"])
        return 0
    verify_prepared_lock(lock, market)
    target = preclose_target(now, market, lock)
    if target is None:
        _preclose_report("outside_watch_window_or_no_close_orders", session=market["session"])
        return 0
    seconds = (target - now).total_seconds()
    if not 0 < seconds <= MAX_SLEEP_SECONDS:
        raise ValueError("Invalid bounded wait duration for exchange close")
    _preclose_report("armed", session=market["session"], wait_seconds=round(seconds),
            target_at_utc=target.isoformat())
    # One sleeping GitHub job is more reliable than a 15:59 cron that may
    # not start until 16:30. Does not poll, consume market data, or trade.
    time.sleep(seconds)
    observed = datetime.now(UTC)
    new_market = market_window(observed)
    if (not new_market or new_market["session"] != market["session"]
            or not target <= observed < market["close"]):
        _preclose_report("wake_missed_market_close_no_fill", session=market["session"])
        return 2
    # The true quote timestamp is collected anew by the original operator.
    # Never reuse a price from the earlier 15:31 observation.
    result = main(["--stage", "observe", "--lock", str(lockpath),
                           "--public", str(publicpath)])
    if result != 0:
        _preclose_report("native_observation_refused", session=market["session"],
                operator_result=result)
        return result
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf8") as fh:
            fh.write("observed=true\n")
    _preclose_report("completed_operator_attempt", session=market["session"],
            sampled_at_utc=observed.isoformat())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("auto", "prepare", "observe"), required=True)
    parser.add_argument("--watch-preclose", action="store_true",
                        help="Reuse the same already-scheduled clock near real NYSE close")
    parser.add_argument("--watch-open", action="store_true",
                        help="Bounded opening observation inside an existing preopen job")
    parser.add_argument("--lock", type=Path, default=ROOT / "forward_open_state/global-lock.json")
    parser.add_argument("--public", type=Path, default=ROOT / "data/operational-clock.json")
    args = parser.parse_args(argv)
    if args.watch_open:
        if args.stage != "observe" or args.watch_preclose:
            raise ValueError("Opening watcher requires observe stage only")
        return run_open_watch(args.lock, args.public)
    if args.watch_preclose:
        if args.stage != "observe":
            raise ValueError("Preclose watcher must invoke an observed session only")
        return run_preclose_watch(args.lock, args.public)
    now = datetime.now(UTC)
    market = market_window(now)
    if not market:
        print('{"status":"exchange_closed"}')
        return 0
    stage = stage_for_actual_time(args.stage, now, market)
    if stage == "prepare":
        if now >= market["open"]:
            print(json.dumps({"status": "late_prepare_refused", "session": market["session"]}))
            return 2
        if now < market["open"] - PREOPEN_HORIZON:
            print(json.dumps({"status": "too_early_to_freeze", "session": market["session"]}))
            return 0
        if args.lock.exists():
            existing = _read(args.lock)
            if existing.get("session") == market["session"]:
                verify_prepared_lock(existing, market)
                print(json.dumps({"status": "preopen_lock_already_frozen",
                                  "session": market["session"],
                                  "lock_sha256": existing["lock_sha256"]}))
                return 0
        from build_opening_plan import plan_at
        sha = _repo_commit()
        sources = plan_at(sha, market["session"], market["previous"])
        fx_required = any(
            sources.get(slot, {}).get("status") == "recorded"
            and sources[slot].get("orders")
            for slot in ("IL-040", "IL-041", "IL-042", "IL-043")
        )
        # Freeze FX before opening, never fetch yesterday's FX after opening
        # for a trade that ought to have executed earlier.
        fx = freeze_timesfm_entry_fx(now, market) if fx_required else None
        # Never backdate FX capture to the scheduler's intended 09:20 call.
        now = datetime.now(UTC)
        lock = clock_plan(now, market, sources, sha, fx_reference=fx)
        _write(args.lock, lock)
        report = {"schema": SCHEMA, "session": lock["session"],
                  "previous_session": lock["previous_session"],
                  "source_commit": sha, "lock_sha256": lock["lock_sha256"],
                  "open_at_utc": lock["open_at_utc"], "prepared_at_utc": lock["prepared_at_utc"],
                  "checked_at_utc": timestamp(now), "run_id": None,
                  "mode": "single_midas_operator_monitor_no_broker",
                  "settlement": "native_engine_batch_until_migrated",
                  "slots": {
                      slot: {"status": "before_open" if p["execution_ready"] else "source_stale_or_unavailable",
                             "source_session": p["source_session"],
                             "planned": p["orders_count"], "observed": 0,
                             "waiting": p["orders_count"], "holdings_count": p["holdings_count"],
                             "orders": [{**o, "status": "pending_open", "observed_price": None,
                                         "quote_at_utc": None, "observed_at_utc": None, "source": None}
                                        for o in p["orders"]]}
                      for slot, p in lock["slots"].items()},
                  "note": "Pre-opening decisions only. Not a broker or a confirmed forward fill."}
    else:
        if now < market["open"]:
            print(json.dumps({"status": "observation_not_yet_due",
                              "session": market["session"]}))
            return 0
        if now >= market["close"]:
            # A queued GitHub run after a half-day close cannot create a
            # price observation or a backdated market event.
            print(json.dumps({"status": "observation_window_closed",
                              "session": market["session"]}))
            return 0
        if not args.lock.exists():
            print('{"status":"no_preopen_lock","fills":0}')
            return 2
        lock = _read(args.lock)
        verify_prepared_lock(lock, market)
        verify_lock(lock, market, now)
        prior = _read(args.public) if args.public.is_file() else None
        requested, quota_omissions = budgeted_quote_targets(lock, prior, now=now, market=market)
        quotes = quote_batch(requested, now, market)
        now = datetime.now(UTC)  # actual observation completion, not nominal scheduler time
        if now > market["close"]:
            print('{"status":"observation_too_late"}')
            return 2
        report = status_report(lock, now, market, quotes, prior,
                               run_id=os.environ.get("GITHUB_RUN_ID"))
        report["quote_budget"] = {
            "hard_symbol_limit": LIMIT,
            "requested_symbols": len(requested),
            "observed_symbols": len(quotes),
            "omitted_algorithm_lanes": quota_omissions,
        }
        for slot in quota_omissions:
            if report["slots"][slot]["status"] not in ("native_forward_settled",):
                report["slots"][slot]["quote_capacity_blocked"] = True
        from native_forward_settlement import settle_native
        from forward_weekly_ml_settlement import settle_weekly
        updated, evidence = settle_native(lock, now, market, quotes)
        ml_updated, ml_evidence = settle_weekly(lock, now, market, quotes)
        from classic_forward_settlement import settle_classic
        classic_updated, classic_evidence = settle_classic(lock, now, market, quotes)
        from forward_ahp_settlement import settle_ahp
        ahp_updated, ahp_evidence = settle_ahp(lock, now, market, quotes)
        from forward_timesfm_settlement import settle_timesfm
        timesfm_updated, timesfm_evidence = settle_timesfm(lock, now, market, quotes)
        from forward_genetic_settlement import settle_genetic
        genetic_updated, genetic_evidence = settle_genetic(lock, now, market, quotes)
        paths = [updated, ml_updated, classic_updated, ahp_updated, timesfm_updated, genetic_updated]
        if sum(len(z) for z in paths) != len(set().union(*(set(z) for z in paths))):
            raise ValueError("Two native settlers attempted to own the same canonical book")
        for ledger_path, book in {**updated, **ml_updated, **classic_updated, **ahp_updated, **timesfm_updated, **genetic_updated}.items():
            _write(ROOT / ledger_path, book)
        report["settlement"] = "native_forward_010_through_027_037_through_044"
        for slot, result in {**evidence, **ml_evidence, **classic_evidence, **ahp_evidence, **timesfm_evidence, **genetic_evidence}.items():
            lane = report["slots"][slot]
            lane["native_settlement"] = result["status"]
            if result.get("pending_open_unfilled"):
                # One independently observed protective stop is NOT proof
                # that the unrelated frozen opening BUY was executed.
                lane["pending_open_unfilled"] = result["pending_open_unfilled"]
                lane["opening_order_execution"] = "unfilled_not_a_native_trade"
            if (slot in {f"IL-{n:03d}" for n in range(19, 28)} and
                    result["status"] == "awaiting_verified_weekly_exit_quotes"):
                required = lock["slots"][slot].get("monitor_tickers", [])
                missing = result.get("missing", [])
                if (not isinstance(missing, list) or
                        not set(missing).issubset(set(required))):
                    raise ValueError("Unexpected weekly exit missing-quote diagnostic")
                lane["weekly_exit_diagnostic"] = {
                    "required_tickers": required,
                    "missing_tickers": missing,
                    "valid_count": result.get("valid_count", 0),
                    "required_count": result.get("required_count", len(required)),
                    "checked_at_utc": timestamp(now),
                    "closing_cutoff_at_utc": timestamp(market["close"]),
                    "price_scope": "observed_preclose_paper_only",
                }
            if ((slot in {f"IL-{n:03d}" for n in range(11, 18)}
                    and result.get("sizing_reference"))
                    or (slot in ({f"IL-{n:03d}" for n in range(19, 28)}
                              | {f"IL-{n:03d}" for n in range(40, 44)})
                        and result.get("unfilled_open_quotes"))
                    or (slot in ("IL-037", "IL-044") and
                        (result.get("unfilled_open_quotes") or
                         result.get("missing_held_quotes")))):
                missing_open = result.get("unfilled_open_quotes", [])
                locked_open = {order["ticker"] for order in lock["slots"][slot]["orders"]}
                if not set(missing_open) <= locked_open:
                    raise ValueError(f"{slot}: missing-quote diagnostic violates frozen orders")
                lane["opening_quote_isolation"] = {
                    "unfilled_tickers": missing_open,
                    "missing_held_quotes": result.get("missing_held_quotes", []),
                    "sizing_reference": result.get("sizing_reference", "frozen_order_budget"),
                    "scope": "paper_forward_open_only",
                    "checked_at_utc": timestamp(now)}
            if slot in {f"IL-{n:03d}" for n in range(11, 18)}:
                record_opening_quote_diagnostic(
                    lane, (prior or {}).get("slots", {}).get(slot, {}),
                    lock["slots"][slot], result, now, market)
            if result["status"] == "settled_native_paper":
                lane["status"] = "native_forward_settled"
                lane["fills"] = result["operations"]
                lane["fills_count"] = result["fills"]
                lane["native_marker"] = result["marker"]
            elif result["status"] == "already_settled" and not (
                    lane.get("status") == "native_forward_settled"):
                # Reconciliation evidence exists in the source book even if the
                # public status was lost. Do not fabricate any missing per-trade info.
                lane["status"] = "native_forward_settled"
                lane["fills_count"] = result["fills"]
                lane["native_marker"] = result["marker"]
                lane["fills"] = []
            else:
                publish_missed_open(lane, result)
        # Accumulate every verified weekly paper sale from this *session*,
        # even if separate polls saw different symbols. A missing-price retry
        # must not erase earlier closes from the published activity journal.
        from forward_weekly_ml_settlement import (
            LEDGER as WEEKLY_LEDGER, SLOTS as WEEKLY_SLOTS, _exit_key as weekly_exit_key)
        from native_forward_settlement import _source_at as read_original_weekly
        weekly_ledger = _read(ROOT / WEEKLY_LEDGER)
        frozen_weekly = read_original_weekly(lock["source_commit"], WEEKLY_LEDGER)
        for slot, book_name in WEEKLY_SLOTS.items():
            lane = report["slots"].get(slot)
            if not lane:
                continue
            book = weekly_ledger["strategies"][book_name]
            original = frozen_weekly["strategies"][book_name]
            prefix = weekly_exit_key(slot, market["session"]) + ":"
            closed_events = [
                e for e in book.get("events", [])
                if e.get("date") == market["session"]
                and e.get("execution") == "observed_preclose_paper"
                and e.get("idempotency_key", "").startswith(prefix)]
            if not closed_events:
                continue
            expected = set(lock["slots"][slot].get("monitor_tickers", []))
            if expected != set(original["positions"]):
                raise ValueError(f"{slot}: weekly sold names differ from locked holdings")
            by_symbol = {e["ticker"]: e for e in closed_events}
            if (len(by_symbol) != len(closed_events)
                    or set(by_symbol) | set(book["positions"]) != expected
                    or set(by_symbol) & set(book["positions"])):
                raise ValueError(f"{slot}: inconsistent partial weekly exits")
            fills = []
            for symbol, e in by_symbol.items():
                key = prefix + symbol
                marker = book.get("forward_executions", {}).get(key)
                if (not marker or marker.get("mode") != "weekly_observed_exit_symbol"
                        or marker.get("lock_sha256") != lock["lock_sha256"]
                        or marker.get("source_commit") != lock["source_commit"]
                        or marker.get("fill_tickers") != [symbol]
                        or e.get("lock_sha256") != lock["lock_sha256"]
                        or e.get("source_commit") != lock["source_commit"]
                        or e.get("idempotency_key") != key):
                    raise ValueError(f"{slot}: weekly sale lacks immutable native marker")
                fills.append({"ticker": symbol, "side": "sell",
                              "quantity": e["shares"], "price": e["price"],
                              "fee": e["fee"], "observed_at_utc": e["observed_at_utc"]})
            fills.sort(key=lambda v: (v["observed_at_utc"], v["ticker"]))
            final_key = weekly_exit_key(slot, market["session"])
            all_markers = book["forward_executions"]
            marker = all_markers.get(final_key) or all_markers[prefix + fills[-1]["ticker"]]
            lane["status"] = "native_forward_settled"
            lane["native_marker"] = marker
            lane["fills_count"] = len(fills)
            lane["fills"] = fills
            lane["weekly_exit_progress"] = {
                "closed_tickers": sorted(by_symbol),
                "remaining_tickers": sorted(book["positions"]),
                "complete": not bool(book["positions"]),
                "source": "observed_preclose_paper_symbol_isolated"}
            lane["session_fill_reconciled"] = True

        # A classic book can sell more than one frozen position during separate
        # intraday polls; its latest marker never represents the daily total.
        from classic_forward_settlement import (
            LEDGER as CLASSIC_LEDGER, CONFIG as CLASSIC_CONFIG,
            SLOTS as CLASSIC_SLOTS, summarize_session_fills as summarize_classic)
        from native_forward_settlement import _source_at as _read_frozen_classic
        classic_book = _read(ROOT / CLASSIC_LEDGER)
        frozen_classic = _read_frozen_classic(lock["source_commit"], CLASSIC_LEDGER)
        classic_policy = _read(ROOT / CLASSIC_CONFIG)["execution"]
        for slot, name in CLASSIC_SLOTS.items():
            lane = report["slots"].get(slot)
            if not lane or lane.get("status") != "native_forward_settled":
                continue
            summary = summarize_classic(
                classic_book["books"][name], frozen_classic["books"][name],
                report["session"], lock["lock_sha256"],
                lock["source_commit"], classic_policy["commission"])
            lane["fills_count"] = summary["fills_count"]
            lane["fills"] = summary["fills"]
            lane["native_markers"] = summary["native_markers"]
            lane["session_fill_reconciled"] = True
            if summary["latest_marker"] is not None:
                lane["native_marker"] = summary["latest_marker"]
        # IL-044 may have multiple distinct stop/target fills during one
        # session. The last native marker is not a daily trade count.
        genetic_lane = report["slots"].get("IL-044")
        if genetic_lane and genetic_lane.get("status") == "native_forward_settled":
            from forward_genetic_settlement import LEDGER, summarize_session_fills
            summary = summarize_session_fills(
                _read(ROOT / LEDGER), report["session"], lock["lock_sha256"])
            genetic_lane["fills_count"] = summary["fills_count"]
            genetic_lane["fills"] = summary["fills"]
            genetic_lane["native_markers"] = summary["native_markers"]
            genetic_lane["session_fill_reconciled"] = True
            if summary["latest_marker"] is not None:
                genetic_lane["native_marker"] = summary["latest_marker"]
    _write(args.public, report)
    print(json.dumps({"status": stage, "session": report["session"],
                      "slots": len(report["slots"]),
                      "plans": sum(r["planned"] for r in report["slots"].values()),
                      "observed": sum(r["observed"] for r in report["slots"].values())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
