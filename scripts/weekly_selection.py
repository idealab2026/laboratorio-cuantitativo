#!/usr/bin/env python3
"""Independent, offline Weekly ML signal acceptance boundary for IDEA LAB.

Seven prediction-producing strategies and two independent benchmarks. This
module does NOT train LightGBM/MLP/LSTM/ARIMA, fetch Yahoo, place orders, replay
old weeks, assert source rights, or issue authenticated economic book entries.
"""
from __future__ import annotations

from datetime import date
import hashlib
import json
import math
import re

from classic_503 import ordered_history
from yahoo_source import DEFAULT_UNIVERSE

BENCHMARKS = {"IL-019": "SPY", "IL-020": "RSP"}
PREDICTORS = {
    "IL-021": "boosted_return",
    "IL-022": "boosted_direction",
    "IL-023": "boosted_rank",
    "IL-024": "mlp",
    "IL-025": "lstm",
    "IL-026": "arima",
    "IL-027": "consensus",
}
ALL_SLOTS = tuple(BENCHMARKS) + tuple(PREDICTORS)
MIN_COVERAGE = 453
MIN_SESSIONS = 130
MAX_HOLDINGS = 10
MAX_NAME_WEIGHT = .12
MAX_INVESTED = .95
COMMISSION = .001
SLIPPAGE = .0005
SHA = re.compile(r"^[a-f0-9]{64}$")


def iso_day(value):
    if not isinstance(value, str):
        raise ValueError("Missing canonical ISO market session")
    try:
        if date.fromisoformat(value).isoformat() == value:
            return value
    except ValueError:
        pass
    raise ValueError("Invalid canonical market session")


def numeric(value):
    return type(value) in (float, int) and math.isfinite(value)


def universe_symbols():
    manifest = json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
    return set(manifest["symbols"])


def validate_panel(panel, session, source_sha256):
    """Require 90%-plus individually dated closes and independent benchmarks.

    Supplied histories must have already been lawfully sourced by the caller.
    No missing final close may be filled from yesterday, and the function
    refuses any history from after the proposed close.
    """
    iso_day(session)
    if not isinstance(source_sha256, str) or not SHA.fullmatch(source_sha256):
        raise ValueError("Missing 64-hex market source snapshot")
    if not isinstance(panel, dict):
        raise ValueError("No independently sourced market panel")
    universe = universe_symbols()
    if set(panel) - universe - {"SPY", "RSP"}:
        raise ValueError("Foreign instrument in frozen 503 universe")
    for benchmark in ("SPY", "RSP"):
        if benchmark not in panel:
            raise ValueError("Missing independent weekly benchmark: " + benchmark)
        rows = ordered_history(panel[benchmark], session, benchmark)
        if len(rows) < MIN_SESSIONS:
            raise ValueError("Insufficient benchmark history")
    eligible = set()
    for ticker in sorted(universe):
        if ticker not in panel:
            continue
        # Invalid or inconsistent dates cannot silently count as eligible.
        rows = ordered_history(panel[ticker], session, ticker)
        if len(rows) >= MIN_SESSIONS:
            eligible.add(ticker)
    if len(eligible) < MIN_COVERAGE:
        raise ValueError("Weekly equity source coverage below 90 percent")
    return eligible


def _accept_predictions(slot, packet, eligible, session):
    if not isinstance(packet, dict) or set(packet) != {
        "prediction_asof", "train_last_label_end",
        "model_sha256", "scores", "trained_rows"
    }:
        raise ValueError("Missing source-neutral model prediction packet")
    prediction_asof = iso_day(packet["prediction_asof"])
    target_end = iso_day(packet["train_last_label_end"])
    if prediction_asof != session or target_end > prediction_asof:
        raise ValueError("Model prediction uses future or stale label cutoff")
    if not isinstance(packet["model_sha256"], str) or not SHA.fullmatch(packet["model_sha256"]):
        raise ValueError("Untraceable prediction model configuration")
    if type(packet["trained_rows"]) is not int or packet["trained_rows"] < 130:
        raise ValueError("No sufficient reported historical training sample")
    scores = packet["scores"]
    if not isinstance(scores, dict) or len(scores) < MIN_COVERAGE:
        raise ValueError("Insufficient dated model predictions")
    if not set(scores).issubset(eligible):
        raise ValueError("Predictions include undated or foreign equities")
    if not all(numeric(score) for score in scores.values()):
        raise ValueError("Nonfinite weekly model score")
    # An external model's name or 64-hex fingerprint is NOT evidence of
    # successful fitting or an independently verified OOS backtest.
    winners = sorted(scores, key=lambda ticker: (-scores[ticker], ticker))[:MAX_HOLDINGS]
    weight = MAX_INVESTED / MAX_HOLDINGS
    if weight > MAX_NAME_WEIGHT:
        raise ValueError("Weekly per-name exposure exceeded")
    return {
        "slot": slot,
        "target_weights": {ticker: weight for ticker in winners},
        "model_sha256": packet["model_sha256"],
        "train_last_label_end": target_end,
        "trained_rows_reported": packet["trained_rows"],
        "research_status": "MODEL_OUTPUT_ONLY_NOT_INDEPENDENTLY_TRAINED_OR_VERIFIED",
    }


def freeze_weekly_targets(panel, packets, session, next_open, source_sha256,
                          *, week_close, previous_signal=None):
    """Freeze paper research targets at the weekly close, never same-day fills."""
    session, next_open = iso_day(session), iso_day(next_open)
    if not isinstance(week_close, bool) or not week_close:
        raise ValueError("Weekly close must be confirmed by exchange calendar")
    if next_open <= session:
        raise ValueError("Orders may only settle on a later verified XNYS open")
    if previous_signal is not None:
        previous_signal = iso_day(previous_signal)
        gap = (date.fromisoformat(session) - date.fromisoformat(previous_signal)).days
        if gap <= 0 or gap > 9:
            raise ValueError("Repeated or missed weekly decision: no retroactive signal")
    eligible = validate_panel(panel, session, source_sha256)
    if not isinstance(packets, dict) or set(packets) != set(PREDICTORS):
        raise ValueError("Seven independent model forecast packets required")
    targets = {}
    for slot, ticker in BENCHMARKS.items():
        targets[slot] = {
            "slot": slot, "target_weights": {ticker: MAX_INVESTED},
            "research_status": "BENCHMARK_TARGET_ONLY_NOT_EXECUTED",
        }
    for slot in PREDICTORS:
        targets[slot] = _accept_predictions(slot, packets[slot], eligible, session)
    return {
        "status": "RESEARCH_WEEKLY_TARGETS_PENDING_NEXT_OPEN_NOT_EXECUTED",
        "session": session,
        "next_open": next_open,
        "source_sha256": source_sha256,
        "eligible": len(eligible),
        "expected": 503,
        "commission_fraction_per_side": COMMISSION,
        "slippage_fraction_per_side": SLIPPAGE,
        "model_validation": "FORECAST_PROVENANCE_REQUIRES_INDEPENDENT_TRAINING_AUDIT",
        "strategies": targets,
    }


def preflight():
    return {
        "status": "WEEKLY_ML_SOURCE_NEUTRAL_CONTRACT_ONLY",
        "slots": list(ALL_SLOTS), "benchmarks": list(BENCHMARKS),
        "predictions": list(PREDICTORS), "minimum_observed": MIN_COVERAGE,
        "lookback_sessions": MIN_SESSIONS, "max_names": MAX_HOLDINGS,
        "single_name_ceiling": MAX_NAME_WEIGHT,
        "target_invested": MAX_INVESTED,
        "trained_models": False, "financial_ledger_started": False,
    }


if __name__ == "__main__":
    print(json.dumps(preflight(), sort_keys=True))
