#!/usr/bin/env python3
"""Bounded, synthetic-only, actual LSTM chronological out-of-sample assessment.

This is a research audit and not a market backtest, a legacy model replica,
a public forecast or a basis for creating financial paper trades.
"""
from __future__ import annotations

from datetime import timedelta
import math

from weekly_baselines import _day, _history, _trainable
from weekly_lstm import fit, predict, MINIMUM, SCHEMA

INPUT_FIELDS = ("ticker", "feature_date", "feature_available_at",
                "features", "source_sha256")


def walk_forward(rows, evaluation_asof, *, minimum=MINIMUM,
                 embargo_days=1, stride_weeks=3, max_decisions=4):
    """Refit at historical closes using labels matured BEFORE each close.

    Parameters bound CI cost: sampled decisions represent explicitly disclosed
    observation dates, never an annualized backtest or a complete portfolio.
    """
    evaluation = _day(evaluation_asof)
    if type(embargo_days) is not int or embargo_days < 1:
        raise ValueError("Embargo must be positive")
    if type(minimum) is not int or minimum < MINIMUM:
        raise ValueError("Insufficient requested training minimum")
    if type(stride_weeks) is not int or not 1 <= stride_weeks <= 52:
        raise ValueError("Invalid weekly evaluation stride")
    if type(max_decisions) is not int or not 1 <= max_decisions <= 12:
        raise ValueError("Invalid bounded evaluation count")
    panel = _history(rows)
    dates = sorted({
        row["feature_date"] for row in panel
        if _day(row["feature_date"]) <= evaluation
        and _day(row["label_available_at"]) <= evaluation
    })
    # Consume only a bounded tail of chronological dates, with stated sampling.
    # Keep immutable test-date selection independent from the actual labels.
    selected = dates[-(stride_weeks * max_decisions)::stride_weeks]
    results = []
    decisions = []
    for day in selected:
        candidates = [r for r in panel if r["feature_date"] == day
                      and _day(r["label_available_at"]) <= evaluation]
        training = _trainable(panel, _day(day), embargo_days)
        if len(training) < minimum or not candidates:
            continue
        try:
            model = fit(training, panel, minimum=minimum)
        except ValueError as exc:
            if str(exc) in ("Insufficient matured LSTM target observations",
                            "Insufficient consecutive LSTM training sequences"):
                continue
            raise
        # The model has no exposure to future labels or later feature windows.
        if not _day(model["trained_labels_through"]) < _day(day)-timedelta(days=embargo_days):
            raise ValueError("Out-of-sample LSTM label lookahead")
        reference = sum(r["forward_return"] for r in training)/len(training)
        evaluated = 0
        for row in candidates:
            request = {k:row[k] for k in INPUT_FIELDS}
            forecast = predict(model, panel, request)
            if not math.isfinite(forecast):
                raise ValueError("Nonfinite chronological model output")
            results.append({
                "date":day,"ticker":row["ticker"],
                "prediction":forecast,"null_prediction":reference,
                "realized_label":row["forward_return"],
                "label_available_at":row["label_available_at"],
                "training_labels_through":model["trained_labels_through"],
                "training_fingerprint":model["fingerprint"],
            })
            evaluated += 1
        if evaluated:
            decisions.append(day)
    if not results:
        return {
            "schema":SCHEMA,"status":"INSUFFICIENT_SYNTHETIC_OOS_OBSERVATIONS",
            "decisions":0,"observations":0,"metrics":None,
            "equivalent_to_original_model":False,
            "market_performance":False,
        }
    mse = sum((r["prediction"]-r["realized_label"])**2 for r in results)/len(results)
    null_mse = sum((r["null_prediction"]-r["realized_label"])**2 for r in results)/len(results)
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_SYNTHETIC_OOS_VALIDATED_NOT_MARKET_CERTIFIED",
        "decisions":len(decisions),"observations":len(results),
        "decision_dates":decisions,
        "evaluation_label_cutoff":evaluation.isoformat(),
        "embargo_days":embargo_days,
        "stride_weeks":stride_weeks,
        "metrics":{"lstm_rmse":math.sqrt(mse),
                   "training_mean_rmse":math.sqrt(null_mse),
                   "relative_mse_improvement":(null_mse-mse)/null_mse
                     if null_mse > 0 else None},
        "scored":results,
        "equivalent_to_original_model":False,
        "market_performance":False,
        "paper_ledger_activated":False,
    }
