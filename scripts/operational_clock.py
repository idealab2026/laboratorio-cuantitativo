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
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from forward_open_il039 import digest, market_window, quotes_yahoo, timestamp

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "midas.operational_clock.v1"
UTC = timezone.utc
ACTIVE = tuple(f"IL-{n:03d}" for n in (*range(10, 28), *range(37, 45)))
MAX_SECONDS = 180
LIMIT = 250


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


def clock_plan(now, market, tracks, commit):
    if now.tzinfo is None or not market or not (
            market["open"] - timedelta(minutes=90) <= now < market["open"]):
        raise ValueError("A new opening may only be locked before that opening")
    if not len(commit) == 40 or not all(c in "0123456789abcdef" for c in commit):
        raise ValueError("Source Git commit SHA required")
    slots = {}
    for slot in ACTIVE:
        record = tracks.get(slot)
        status = record.get("status") if isinstance(record, dict) else "unavailable"
        source_session = record.get("session") if isinstance(record, dict) else None
        eligible = status == "recorded" and source_session == market["previous"]
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
            "execution_ready": eligible,
            "orders": sorted(orders, key=lambda row: row["ticker"]) if eligible else [],
            "orders_count": len(orders) if eligible else 0,
            "holdings_count": len(record.get("holdings", [])) if isinstance(record, dict) else 0,
            # Only tactical classic portfolios monitor real observed stops.
            # Passive 503-position buy-and-hold is excluded from free quote reads.
            "monitor_tickers": (sorted(set(record.get("holdings", [])))
                                if eligible and slot in {f"IL-{n:03d}" for n in range(11, 18)}
                                and isinstance(record, dict) else []),
        }
    lock = {"schema": SCHEMA, "session": market["session"],
            "previous_session": market["previous"], "source_commit": commit,
            "open_at_utc": timestamp(market["open"]),
            "prepared_at_utc": timestamp(now), "slots": slots}
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


def quote_batch(tickers, now, market):
    """Best-effort free quotes; no fabricated values for unavailable symbols."""
    symbols = sorted(set(tickers))
    if len(symbols) > LIMIT:
        symbols = symbols[:LIMIT]
    if not symbols:
        return {}
    result = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = [pool.submit(quotes_yahoo, [symbol], now, market) for symbol in symbols]
        for future in as_completed(jobs):
            try:
                result.update(future.result())
            except (ValueError, OSError, TypeError):
                pass
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("prepare", "observe"), required=True)
    parser.add_argument("--lock", type=Path, default=ROOT / "forward_open_state/global-lock.json")
    parser.add_argument("--public", type=Path, default=ROOT / "data/operational-clock.json")
    args = parser.parse_args(argv)
    now = datetime.now(UTC)
    market = market_window(now)
    if not market:
        print('{"status":"exchange_closed"}')
        return 0
    if args.stage == "prepare":
        from build_opening_plan import plan_at
        sha = _repo_commit()
        sources = plan_at(sha, market["session"], market["previous"])
        lock = clock_plan(now, market, sources, sha)
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
        if not args.lock.exists():
            print('{"status":"no_preopen_lock","fills":0}')
            return 2
        lock = _read(args.lock)
        verify_lock(lock, market, now)
        prior = _read(args.public) if args.public.is_file() else None
        already = {r["ticker"] for entry in (prior or {}).get("slots", {}).values()
                   for r in entry.get("orders", []) if r.get("status") == "price_observed"}
        needed = {o["ticker"] for p in lock["slots"].values() for o in p["orders"]}
        monitored = {t for p in lock["slots"].values() for t in p.get("monitor_tickers", [])}
        # A new quote is mandatory on each stop check, not the previous
        # order observation.
        quotes = quote_batch((needed - already) | monitored, now, market)
        now = datetime.now(UTC)  # actual observation completion, not nominal scheduler time
        if now > market["close"]:
            print('{"status":"observation_too_late"}')
            return 2
        report = status_report(lock, now, market, quotes, prior,
                               run_id=os.environ.get("GITHUB_RUN_ID"))
        from native_forward_settlement import settle_native
        from forward_weekly_ml_settlement import settle_weekly
        updated, evidence = settle_native(lock, now, market, quotes)
        ml_updated, ml_evidence = settle_weekly(lock, now, market, quotes)
        from classic_forward_settlement import settle_classic
        classic_updated, classic_evidence = settle_classic(lock, now, market, quotes)
        if (set(updated) & set(ml_updated) or set(updated) & set(classic_updated)
                or set(ml_updated) & set(classic_updated)):
            raise ValueError("Two native settlers attempted to own the same canonical book")
        for ledger_path, book in {**updated, **ml_updated, **classic_updated}.items():
            _write(ROOT / ledger_path, book)
        report["settlement"] = "native_forward_010_through_027_038_039_other_engines_batch"
        for slot, result in {**evidence, **ml_evidence, **classic_evidence}.items():
            lane = report["slots"][slot]
            lane["native_settlement"] = result["status"]
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
    _write(args.public, report)
    print(json.dumps({"status": args.stage, "session": report["session"],
                      "slots": len(report["slots"]),
                      "plans": sum(r["planned"] for r in report["slots"].values()),
                      "observed": sum(r["observed"] for r in report["slots"].values())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
