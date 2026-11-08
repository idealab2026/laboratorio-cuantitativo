#!/usr/bin/env python3
"""MIDAS Debate Alpha: no-cost, deterministic multi-agent *research baseline*.

NOT a LangGraph/LLM implementation of TauricResearch TradingAgents.
Consumes only the institution's already captured and verified XNYS snapshots.
Signals at close, settlements at the NEXT verified session's open. Never a broker.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from market_data.revisions import load_effective

SCHEMA = "idealab_debate_alpha_paper_v1"
CAPITAL = 100000.0
FEE = 0.001
SLIPPAGE = 0.0005
MAX_POSITIONS = 5
MAX_WEIGHT = 0.18
LOOKBACK = 6  # six dated closes = five observed close-to-close intervals
VERSION = "deterministic-debate-v1"
STATE_PATH = ROOT / "multi_agent_state" / "ledger.json"
SNAPSHOT_DIR = ROOT / "market_data" / "snapshots"
CONFIG = {"version": VERSION, "capital_usd": CAPITAL, "fee_per_side": FEE,
          "slippage_per_side": SLIPPAGE, "max_positions": MAX_POSITIONS,
          "max_weight": MAX_WEIGHT, "lookback_closes": LOOKBACK,
          "rebalance_weekday": 4, "universe": "sp500_frozen_2026-09-29",
          "exec": "signal_after_close_next_session_open", "llm": False}
CONFIG_SHA = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()


def sha(doc):
    clean = {k: v for k, v in doc.items() if k != "state_sha256"}
    payload = json.dumps(clean, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def blank():
    doc = {"schema": SCHEMA, "version": VERSION, "config_sha256": CONFIG_SHA,
           "status": "not_started", "last_session": None, "cash": CAPITAL,
           "holdings": {}, "pending": None, "history": [], "decisions": [],
           "events": [], "source_chain": [], "state_sha256": None}
    doc["state_sha256"] = sha(doc)
    return doc


def validate(doc):
    if not isinstance(doc, dict) or set(doc) != set(blank()):
        raise ValueError("Unexpected debate ledger schema")
    if (doc["schema"] != SCHEMA or doc["version"] != VERSION or
            doc["config_sha256"] != CONFIG_SHA or doc["state_sha256"] != sha(doc)):
        raise ValueError("Wrong version or changed paper history")
    if not isinstance(doc["cash"], (int, float)) or not math.isfinite(doc["cash"]) or doc["cash"] < -1e-6:
        raise ValueError("Bad paper cash")
    if not isinstance(doc["holdings"], dict) or len(doc["holdings"]) > MAX_POSITIONS:
        raise ValueError("Bad holdings")
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in doc["holdings"].values()):
        raise ValueError("Invalid shares")
    if not all(isinstance(doc[k], list) for k in ("history", "decisions", "events", "source_chain")):
        raise ValueError("Malformed paper event lists")
    if doc["status"] == "not_started":
        if doc != blank():
            raise ValueError("Noncanonical unstarted ledger")
        return
    if doc["status"] != "prospective_paper" or not doc["history"] or not doc["last_session"]:
        raise ValueError("Unverifiable paper state")
    if doc["history"][-1]["session"] != doc["last_session"]:
        raise ValueError("NAV and session disagree")
    if len(doc["history"]) != len(doc["source_chain"]):
        raise ValueError("Missing daily source provenance")
    days = [r["session"] for r in doc["history"]]
    if days != sorted(set(days)):
        raise ValueError("Nonmonotonic sessions")
    if any(not math.isfinite(float(x["nav"])) or x["nav"] < 0 for x in doc["history"]):
        raise ValueError("Invalid NAV")
    if doc["pending"] is not None:
        q = doc["pending"]
        if (set(q) != {"decided_at", "targets"} or q["decided_at"] != doc["last_session"]
                or len(q["targets"]) > MAX_POSITIONS or len(set(q["targets"])) != len(q["targets"])):
            raise ValueError("Invalid frozen pending target")


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _returns(closes):
    return [b / a - 1 for a, b in zip(closes, closes[1:])]


def _stdev(xs):
    avg = sum(xs) / len(xs)
    return math.sqrt(sum((x-avg)**2 for x in xs) / len(xs))


def committee(frames):
    """Three verifiable agents + bull/bear debate. Fundamental/sentiment ABSTAIN.

    frames: ordered (session, verified market-source result), latest last.
    No future vendor reads, no model inference, no imputed fundamental/news facts.
    """
    if len(frames) < LOOKBACK:
        return {"targets": [], "reason": "WARMUP", "debate": []}
    recent = frames[-LOOKBACK:]
    dates = [x[0] for x in recent]
    if dates != sorted(set(dates)):
        raise ValueError("Source dates nonmonotonic")
    if "SPY" not in recent[0][1]["bars"] or any("SPY" not in x[1]["bars"] for x in recent):
        raise ValueError("Missing SPY reference price")
    spy = [x[1]["bars"]["SPY"]["close"] for x in recent]
    market_return = spy[-1] / spy[0] - 1
    candidates = []
    common = set.intersection(*(set(x[1]["bars"]) for x in recent)) - {"SPY"}
    for ticker in sorted(common):
        rows = [x[1]["bars"][ticker] for x in recent]
        closes = [x["close"] for x in rows]
        if not all(_finite(c) and c > 0 for c in closes):
            continue
        if closes[-1] < 5 or rows[-1]["volume"] < 100000:
            continue
        mom = closes[-1] / closes[0] - 1
        rel = mom - market_return
        vol = _stdev(_returns(closes))
        # Simulated experts operating on verifiable, dated inputs only.
        technical = mom > .01
        relative = rel > .005
        risk = vol <= .045
        bull = int(technical) + int(relative)
        bearish = (not risk) or mom < 0 or market_return <= 0
        approved = bull == 2 and risk and not bearish
        score = 0.5 * mom + 0.4 * rel - 0.5 * vol
        if approved:
            candidates.append((score, ticker, {"ticker": ticker, "technical": technical,
                 "relative_strength": relative, "risk": risk, "bull_votes": bull,
                 "bear_objection": bearish, "fundamental": "ABSTAIN_NO_PIT_DATA",
                 "sentiment": "ABSTAIN_NO_PIT_NEWS",
                 "momentum_5": round(mom, 8), "relative_5": round(rel, 8),
                 "daily_volatility_5": round(vol, 8), "score": round(score, 8)}))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    chosen = candidates[:MAX_POSITIONS]
    return {"targets": [row[1] for row in chosen],
            "reason": "DEBATE_APPROVED" if chosen else "RISK_OR_SIGNAL_REJECTED",
            "benchmark_return_5": round(market_return, 8),
            "debate": [row[2] for row in chosen]}


def _price(bar, key):
    value = bar.get(key)
    if not _finite(value) or value <= 0:
        raise ValueError("Missing executable OHLC " + key)
    return float(value)


def step(prior, session, current, history_frames):
    """Pure, idempotence-rejecting daily settlement and after-close signal."""
    validate(prior)
    date.fromisoformat(session)
    if prior["last_session"] is not None and session <= prior["last_session"]:
        raise ValueError("Duplicate or retroactive paper session")
    if current["base"]["session"] != session or not current["effective_sha256"]:
        raise ValueError("Wrong verified market session")
    if len(current["bars"]) < 454 or "SPY" not in current["bars"]:
        raise ValueError("Insufficient verified common-source coverage")
    state = copy.deepcopy(prior)
    bars = current["bars"]
    # Missing held marks or pending targets block the ENTIRE next-open session.
    required = set(state["holdings"])
    if state["pending"]:
        required.update(state["pending"]["targets"])
    if not required.issubset(bars):
        raise ValueError("No paper fill or NAV without all required exact-session prices")
    if state["pending"]:
        pending = state["pending"]
        if pending["decided_at"] >= session:
            raise ValueError("Cannot execute same-session or future decisions")
        # Corporate actions credited on the ex-date before opening trades.
        for symbol, shares in list(state["holdings"].items()):
            split = float(bars[symbol]["split"])
            if split:
                state["holdings"][symbol] *= split
            dividend = float(bars[symbol]["dividend"])
            if dividend:
                state["cash"] += state["holdings"][symbol] * dividend
                state["events"].append({"session": session, "event": "DIVIDEND",
                                        "ticker": symbol, "cash": state["holdings"][symbol] * dividend})
        # Full reconstitution at the next opening, avoiding hidden intraday hindsight.
        for symbol, shares in sorted(state["holdings"].items()):
            fill = _price(bars[symbol], "open") * (1 - SLIPPAGE)
            proceeds = shares * fill * (1 - FEE)
            state["cash"] += proceeds
            state["events"].append({"session": session, "signal_session": pending["decided_at"],
                                   "event": "SELL", "ticker": symbol, "shares": shares,
                                   "price": fill, "fee": shares * fill * FEE})
        state["holdings"] = {}
        targets = pending["targets"]
        if targets:
            per_name = state["cash"] * MAX_WEIGHT
            for symbol in targets:
                fill = _price(bars[symbol], "open") * (1 + SLIPPAGE)
                amount = per_name
                shares = math.floor(amount / (fill * (1 + FEE)) * 1e6) / 1e6
                gross = shares * fill
                charge = gross * FEE
                if shares <= 0 or gross + charge > state["cash"] + 1e-7:
                    raise ValueError("Infeasible bounded paper purchase")
                state["cash"] -= gross + charge
                state["holdings"][symbol] = shares
                state["events"].append({"session": session, "signal_session": pending["decided_at"],
                                       "event": "BUY", "ticker": symbol, "shares": shares,
                                       "price": fill, "fee": charge})
        state["pending"] = None
    else:
        # Daily corporate actions even when no rebalance occurs.
        for symbol in sorted(state["holdings"]):
            bar = bars[symbol]
            factor = float(bar["split"])
            if factor:
                state["holdings"][symbol] *= factor
            if bar["dividend"]:
                amount = state["holdings"][symbol] * float(bar["dividend"])
                state["cash"] += amount
                state["events"].append({"session": session, "event": "DIVIDEND",
                                        "ticker": symbol, "cash": amount})
    nav = state["cash"] + sum(shares * _price(bars[sym], "close")
                              for sym, shares in state["holdings"].items())
    if not math.isfinite(nav) or nav < 0:
        raise ValueError("Invalid paper capital accounting")
    if date.fromisoformat(session).weekday() == 4:
        result = committee(history_frames)
        state["pending"] = {"decided_at": session, "targets": result["targets"]}
        state["decisions"].append({"session": session, "model": VERSION, "llm": False,
                                   "source_sha256": current["effective_sha256"], **result})
    state["history"].append({"session": session, "nav": round(nav, 8),
                             "cash": round(state["cash"], 8),
                             "positions": len(state["holdings"])})
    state["source_chain"].append({"session": session, "sha256": current["effective_sha256"]})
    state["last_session"] = session
    state["status"] = "prospective_paper"
    state["state_sha256"] = sha(state)
    validate(state)
    return state


def load_history(session, root=SNAPSHOT_DIR):
    """All reads come from existing hash-validated canonical + revision snapshots."""
    files = sorted((root / "XNYS").glob("????-??-??.json"))
    names = [p.stem for p in files if p.stem <= session]
    if session not in names:
        raise ValueError("No exact eligible captured session; never use a stale mark")
    names = names[-LOOKBACK:]
    return [(day, load_effective(root, day)) for day in names]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--daily", action="store_true")
    args = parser.parse_args()
    if args.check:
        validate(blank())
        if STATE_PATH.exists():
            validate(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        print(json.dumps({"status": "PASS", "model": VERSION, "llm": False,
                          "external_inference_cost": 0}))
        return
    # An eligible, completed XNYS session is decided by existing MIDAS calendar.
    from timesfm_strategy.run import calendar
    eligible = calendar()
    if not eligible:
        raise ValueError("No newly closed XNYS session")
    session = eligible[0]
    prior = (json.loads(STATE_PATH.read_text(encoding="utf-8"))
             if STATE_PATH.exists() else blank())
    # A delayed Action must never fill Monday intentions at Tuesday's open.
    # Existing XNYS calendar independently supplies the immediately previous
    # trading session, including exchange holidays. No retroactive catch-up.
    if prior["status"] == "prospective_paper" and prior["last_session"] != eligible[1]:
        raise ValueError("Missed XNYS session: halt; do not backfill paper fills")
    frames = load_history(session)
    state = step(prior, session, frames[-1][1], frames)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2,
                                     sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "prospective_paper", "session": session,
                      "nav": state["history"][-1]["nav"],
                      "positions": len(state["holdings"]),
                      "pending_targets": len(state["pending"]["targets"]) if state["pending"] else None,
                      "llm": False}))


if __name__ == "__main__":
    main()
