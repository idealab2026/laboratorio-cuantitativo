"""Causal mark-only TimesFM recovery after missed observed paper sessions.

Historical OHLC + EURUSD daily closes can mark *held* shares, but cannot
prove a historical opening or close auction execution. Pending orders expire;
held positions remain held for a future observed settlement. Never invent a
daily exit for a trade which has no contemporaneous close observation.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_data.revisions import load_effective
from market_data.snapshot import normalize_bar
from strategy_comparison.inactive_recovery import window, identity_check
from timesfm_strategy import run as weekly_engine
from timesfm_strategy import daily_run as daily_engine

COHORTS = {
    "weekly": ("timesfm_state/ledger.json", "timesfm_strategy/config.json"),
    "one_day": ("timesfm_daily_state/ledger.json", "timesfm_strategy/config-daily.json"),
}
UTC = timezone.utc


def _stamp(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() != timedelta(0):
        raise ValueError("Unverified capture timezone")
    return t


def verified_fx_closes(days, *, now):
    """Retrieve real *historical mark* FX; this is NOT a tradable entry/exit."""
    if not days:
        return {}
    import yfinance as yf
    start = days[0]
    end = (datetime.fromisoformat(days[-1]) + timedelta(days=1)).date().isoformat()
    frame = yf.Ticker("EURUSD=X").history(
        start=start, end=end, interval="1d", auto_adjust=False, actions=False)
    if frame is None or frame.empty or frame.index.tz is None:
        raise ValueError("EURUSD actual daily bar missing; no synthetic EUR NAV")
    fx = {}
    for day in days:
        matches = frame.loc[frame.index.strftime("%Y-%m-%d") == day]
        if len(matches) != 1:
            raise ValueError("EURUSD close is missing/ambiguous for " + day)
        rate = float(matches.iloc[0]["Close"])
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Invalid EURUSD close: " + day)
        fx[day] = rate
    return fx


def validated_bars(root, day, required, now):
    """Read immutable, exact-session stock closes with revision provenance."""
    effective = load_effective(root / "market_data/snapshots", day)
    base = effective["base"]
    identity = {
        "snapshot_sha256": base["sha256"],
        "effective_sha256": effective["effective_sha256"],
    }
    identity_check(identity)
    if base["session"] != day or _stamp(effective["last_captured_at_utc"]) > now:
        raise ValueError("Historical stock data is future-dated")
    if not set(required) <= set(base["requested_symbols"]):
        raise ValueError("Unreviewed ticker outside the canonical frozen universe")
    if not set(required) <= set(effective["bars"]):
        raise ValueError("Missing observed held close: " +
                         ",".join(sorted(set(required) - set(effective["bars"]))))
    quotes = {ticker: normalize_bar(effective["bars"][ticker], day, ticker)
              for ticker in required}
    return quotes, identity


def reconcile(state, config, family, days, rows, rates, *, now, first_future):
    """Pure recovery; no past buy/sell/stop, no forecast, no revised history."""
    if family == "weekly":
        weekly_engine._check(state, config)
    elif family == "one_day":
        daily_engine.verify(config)
        daily_engine.check(state, config)
    else:
        raise ValueError("Unrecognized TimesFM campaign")
    original = copy.deepcopy(state)
    if not days:
        return original
    if days != sorted(set(days)) or days[0] <= state["last_session"]:
        raise ValueError("Invalid chronological inactive recovery window")
    result = copy.deepcopy(state)
    previous_session = result["last_session"]
    for day in days:
        if day not in rows or day not in rates:
            raise ValueError("Missing canonical daily OHLC or observed FX for " + day)
        rate = float(rates[day])
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Invalid historical FX mark")
        stock, identity = rows[day]
        identity_check(identity)
        for name, book in result["books"].items():
            if book["equity"][-1]["date"] != previous_session:
                raise ValueError("Independent TimesFM book missing its previous close")
            expired = copy.deepcopy(book["pending"])
            if expired:
                book["pending"] = []
                book["events"].append({
                    "date": day, "type": "inactive_expired_open_no_fill",
                    "orders": expired, "recorded_at_utc": now.isoformat(),
                })
            marks = {}
            for ticker, pos in book["positions"].items():
                if pos["entry_date"] > day:
                    raise ValueError("Future-dated held position: " + ticker)
                if ticker not in stock:
                    raise ValueError("No verified historical held mark for " + ticker)
                row = stock[ticker]
                # Economic entitlements cannot be silently reconstructed by
                # applying a later-adjusted vendor series to frozen shares.
                if float(row.get("split", 0)) or float(row.get("dividend", 0)):
                    raise ValueError("Corporate action demands separate entitlement review: " + ticker)
                close = float(row["close"])
                if not math.isfinite(close) or close <= 0:
                    raise ValueError("Invalid raw close: " + ticker)
                marks[ticker] = close / rate
            book["nav"] = float(book["cash"]) + sum(
                float(pos["shares"]) * marks[t] for t, pos in book["positions"].items())
            if not math.isfinite(book["nav"]) or book["nav"] < 0:
                raise ValueError("Invalid inactive EUR NAV")
            book["equity"].append({
                "date": day, "nav": book["nav"],
                "inactive_no_new_fills": True,
                "missing_exits_remain_open": bool(book["positions"]),
                "quote_identity": identity,
                "eurusd_daily_close": rate,
                "recorded_at_utc": now.isoformat(),
            })
            book["events"].append({
                "date": day, "type": "inactive_mark_only_no_execution",
                "held_tickers": sorted(book["positions"]),
                "recorded_at_utc": now.isoformat(),
            })
        result["last_session"] = day
        result["equity"].append({
            "date": day, "nav": result["books"]["timesfm" if family == "weekly" else "timesfm_daily"]["nav"],
            "inactive_no_new_fills": True,
        })
        previous_session = day
    result["outage_control"] = {
        "kind": "missed_forward_session_mark_only",
        "missing_sessions": days,
        "first_future_trading_session": first_future,
        "recorded_at_utc": now.isoformat(),
        "historical_fills_created": 0,
        "held_exits_require_future_observed_quote": True,
    }
    if family == "one_day":
        result["missing_signals"] = sorted(set(result.get("missing_signals", [])) | set(days))
    else:
        if days[-1] < result["last_signal_session"]:
            raise ValueError("Recovery cannot move behind frozen weekly decision")
        result["missed_weekly_signal_sessions"] = sorted(set(
            result.get("missed_weekly_signal_sessions", [])) | {
                d for d in days if datetime.fromisoformat(d).weekday() == 4
            })
    # Paper fills and orders already recorded inside the original ledger are
    # immutable. Recovery may only expire *unexecuted* pending orders.
    if result.get("forward_executions") != original.get("forward_executions"):
        raise ValueError("Recovered forward execution keys were mutated")
    for name, before in original["books"].items():
        after = result["books"][name]
        if (after["trades"] != before["trades"] or
                after["events"][:len(before["events"])] != before["events"] or
                after["equity"][:len(before["equity"])] != before["equity"] or
                after["cash"] != before["cash"] or
                after["positions"] != before["positions"]):
            raise ValueError("Inactive recovery changed trades, cash or actual shares")
    if family == "weekly":
        weekly_engine._check(result, config)
    else:
        daily_engine.check(result, config)
    return result


def recover(root=ROOT, *, write=False, now=None):
    root = Path(root)
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Recovery requires an aware time")
    configs, states, days_by_family, futures = {}, {}, {}, {}
    all_days = set()
    for family, (state_path, config_path) in COHORTS.items():
        state = json.loads((root / state_path).read_text())
        config = json.loads((root / config_path).read_text())
        if family == "weekly":
            weekly_engine._config(config)
            weekly_engine._check(state, config)
        else:
            daily_engine.verify(config)
            daily_engine.check(state, config)
        _, future, days = window(state["last_session"], now)
        configs[family], states[family] = config, state
        days_by_family[family], futures[family] = days, future
        all_days.update(days)
    quotes_by_day = {}
    for day in sorted(all_days):
        required = {ticker for family, state in states.items()
                    if day in days_by_family[family]
                    for book in state["books"].values()
                    for ticker in book["positions"]}
        quotes_by_day[day] = validated_bars(root, day, required, now)
    fx = verified_fx_closes(sorted(all_days), now=now)
    results = {}
    for family in COHORTS:
        results[family] = reconcile(
            states[family], configs[family], family, days_by_family[family],
            quotes_by_day, fx, now=now, first_future=futures[family])
    if write:
        # Fully validate *both* cohorts before writing either one.
        for family, (state_path, _) in COHORTS.items():
            if results[family] != states[family]:
                weekly_engine.atomic_write(root / state_path, results[family])
    return {
        "status": "mark_only_recovery" if all_days else "already_current",
        "written": bool(write and all_days),
        "sessions": days_by_family,
        "first_future": futures,
        "last_sessions": {family: s["last_session"] for family, s in results.items()},
        "historical_fills_created": 0,
        "held_exits_pending_real_observation": {
            family: sorted(results[family]["books"]["timesfm" if family == "weekly" else "timesfm_daily"]["positions"])
            for family in COHORTS
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("check", "recover"), default="check")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(recover(write=args.phase == "recover"), ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        print("TimesFM inactive recovery refused: " + repr(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
