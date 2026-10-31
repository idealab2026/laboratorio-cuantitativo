#!/usr/bin/env python3
"""Independent walk-forward *baseline* models, never legacy ML strategy replicas.

No data vendor, brokerage, network, filesystem writes or public market results.
Only fully matured point-in-time labels can train a model at a later session.
"""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
import math
import re

FEATURES = ("momentum20", "volatility20", "reversal5")
METHODS = ("ridge_baseline", "logistic_baseline")
HASH = re.compile(r"^[a-f0-9]{64}$")
SCHEMA = "idealab_weekly_oos_baseline_v1"


def _day(s):
    if not isinstance(s, str):
        raise ValueError("Missing date")
    try:
        if date.fromisoformat(s).isoformat() == s:
            return date.fromisoformat(s)
    except ValueError:
        pass
    raise ValueError("Noncanonical ISO date")


def _finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def _fields(row, labeled):
    required = {"ticker", "feature_date", "feature_available_at",
                "features", "source_sha256"}
    if labeled:
        required |= {"label_end", "label_available_at", "forward_return"}
    if not isinstance(row, dict) or set(row) != required:
        raise ValueError("Unexpected evidence row fields")
    if not isinstance(row["ticker"], str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", row["ticker"]):
        raise ValueError("Invalid ticker identity")
    feature_date = _day(row["feature_date"])
    if _day(row["feature_available_at"]) > feature_date:
        raise ValueError("Feature unavailable at claimed close")
    if not isinstance(row["source_sha256"], str) or not HASH.fullmatch(row["source_sha256"]):
        raise ValueError("Missing source content fingerprint")
    values = row["features"]
    if not isinstance(values, dict) or set(values) != set(FEATURES) or not all(_finite(values[x]) for x in FEATURES):
        raise ValueError("Missing or invalid source-dated features")
    if labeled:
        if not feature_date < _day(row["label_end"]) <= _day(row["label_available_at"]):
            raise ValueError("Invalid future label maturity")
        if not _finite(row["forward_return"]) or not -1.0 <= row["forward_return"] <= 10.0:
            raise ValueError("Invalid realized label")
    return row


def _history(rows):
    if not isinstance(rows, list):
        raise ValueError("Historical source rows required")
    seen = set()
    for row in rows:
        _fields(row, True)
        key = (row["ticker"], row["feature_date"])
        if key in seen:
            raise ValueError("Duplicate evidence row")
        seen.add(key)
    return sorted(rows, key=lambda r: (r["feature_date"], r["ticker"]))


def _trainable(rows, day, embargo_days):
    cutoff = day - timedelta(days=embargo_days)
    return [r for r in rows if _day(r["feature_date"]) < day
            and _day(r["label_available_at"]) < cutoff]


def _solve(a, b):
    n = len(b)
    matrix = [list(a[i]) + [b[i]] for i in range(n)]
    for pivot in range(n):
        idx = max(range(pivot, n), key=lambda i: abs(matrix[i][pivot]))
        matrix[pivot], matrix[idx] = matrix[idx], matrix[pivot]
        if abs(matrix[pivot][pivot]) < 1e-12:
            raise ValueError("Singular training system")
        scale = matrix[pivot][pivot]
        matrix[pivot] = [x / scale for x in matrix[pivot]]
        for row in range(n):
            if row != pivot:
                factor = matrix[row][pivot]
                matrix[row] = [x - factor*y for x,y in zip(matrix[row], matrix[pivot])]
    return [matrix[i][-1] for i in range(n)]


def fit(rows, kind, *, minimum=30):
    """Real fitting on supplied labels, without asserting financial validity."""
    if kind not in METHODS:
        raise ValueError("Unknown explicitly scoped baseline")
    if type(minimum) is not int or minimum < 30 or len(rows) < minimum:
        raise ValueError("Insufficient matured training observations")
    for row in rows:
        _fields(row, True)
    means = [sum(r["features"][f] for r in rows) / len(rows) for f in FEATURES]
    scales = [max(math.sqrt(sum((r["features"][f]-means[i])**2 for r in rows)/len(rows)),1e-8)
              for i,f in enumerate(FEATURES)]
    x = [[1.0]+[(r["features"][f]-means[i])/scales[i] for i,f in enumerate(FEATURES)]
         for r in rows]
    y = [float(r["forward_return"]) for r in rows]
    if kind == "ridge_baseline":
        penalty = .5
        a = [[sum(v[i]*v[j] for v in x)+(penalty if i==j else 0.0)
              for j in range(4)] for i in range(4)]
        b = [sum(v[i]*z for v,z in zip(x,y)) for i in range(4)]
        weights = _solve(a,b)
    else:
        targets = [int(v > 0) for v in y]
        if min(targets) == max(targets):
            raise ValueError("Both outcome classes required for logistic fit")
        weights = [0.0]*4
        for _ in range(320):
            grad = [0.0]*4
            for row, target in zip(x, targets):
                raw = max(-30.0,min(30.0,sum(w*v for w,v in zip(weights,row))))
                residual = 1.0/(1.0+math.exp(-raw)) - target
                for j in range(4):
                    grad[j] += residual*row[j]
            for j in range(4):
                grad[j] = grad[j]/len(x)+(.02*weights[j] if j else 0.0)
                weights[j] -= .15*grad[j]
    if not all(_finite(w) for w in weights):
        raise ValueError("Nonfinite fitted baseline")
    return {"method":kind,"means":means,"scales":scales,"weights":weights,
            "training_rows":len(rows),
            "last_label_available":max(r["label_available_at"] for r in rows),
            "training_fingerprint":hashlib.sha256(json.dumps(
                [(r["ticker"],r["feature_date"],r["label_available_at"],r["source_sha256"])
                 for r in rows],sort_keys=True).encode()).hexdigest()}


def infer(model, features):
    if not isinstance(features,dict) or set(features)!=set(FEATURES) or not all(_finite(features[k]) for k in FEATURES):
        raise ValueError("Malformed inference features")
    x = [1.0]+[(features[k]-model["means"][i])/model["scales"][i]
               for i,k in enumerate(FEATURES)]
    raw = sum(a*b for a,b in zip(x,model["weights"]))
    if model["method"]=="logistic_baseline":
        return 1.0/(1.0+math.exp(-max(-30.0,min(30.0,raw))))
    return raw


def walk_forward(rows, evaluation_asof, kind, *, minimum=30, embargo_days=1):
    """Re-fit at each out-of-sample *feature date*, score matured labels only."""
    end = _day(evaluation_asof)
    if kind not in METHODS or type(embargo_days) is not int or embargo_days < 1:
        raise ValueError("Unknown baseline or invalid embargo")
    rows = _history(rows)
    test_days = sorted({r["feature_date"] for r in rows
                        if _day(r["feature_date"])<=end
                        and _day(r["label_available_at"])<=end})
    scored = []
    for tested in test_days:
        training = _trainable(rows,_day(tested),embargo_days)
        if len(training) < minimum:
            continue
        if kind=="logistic_baseline" and len({r["forward_return"]>0 for r in training})<2:
            continue
        model = fit(training,kind,minimum=minimum)
        test = [r for r in rows if r["feature_date"]==tested
                and _day(r["label_available_at"])<=end]
        for row in test:
            score = infer(model,row["features"])
            baseline = (sum(int(r["forward_return"]>0) for r in training)/len(training)
                        if kind=="logistic_baseline"
                        else sum(r["forward_return"] for r in training)/len(training))
            actual = int(row["forward_return"]>0) if kind=="logistic_baseline" else row["forward_return"]
            scored.append({"feature_date":tested,"ticker":row["ticker"],
                           "prediction":score,"baseline":baseline,
                           "actual":actual,"label_available_at":row["label_available_at"],
                           "training_labels_through":model["last_label_available"]})
    if not scored:
        return {"schema":SCHEMA,"status":"INSUFFICIENT_OOS_OBSERVATIONS",
                "method":kind,"oos_count":0,"metrics":None}
    sq = sum((r["prediction"]-r["actual"])**2 for r in scored)/len(scored)
    sq_ref = sum((r["baseline"]-r["actual"])**2 for r in scored)/len(scored)
    metrics = {"model_error":sq,"baseline_error":sq_ref,
               "relative_improvement":(sq_ref-sq)/sq_ref if sq_ref>0 else None}
    if kind=="ridge_baseline":
        metrics["model_rmse"] = math.sqrt(sq)
        metrics["baseline_rmse"] = math.sqrt(sq_ref)
    else:
        metrics["model_brier"] = sq
        metrics["baseline_brier"] = sq_ref
    return {"schema":SCHEMA,"status":"OFFLINE_OOS_EVALUATED_NOT_MARKET_CERTIFIED",
            "method":kind,"oos_count":len(scored),"metrics":metrics,
            "first_test_date":scored[0]["feature_date"],
            "last_test_date":scored[-1]["feature_date"],
            "last_scored_label_at":max(x["label_available_at"] for x in scored),
            "scored":scored}


def research_prediction(rows, request, kind, *, minimum=30, embargo_days=1):
    """Current unlabelled point-in-time inference; NOT an original MIDAS model."""
    _fields(request,False)
    training = _history(rows)
    decision = _day(request["feature_date"])
    if type(embargo_days) is not int or embargo_days < 1:
        raise ValueError("Invalid embargo")
    chosen = _trainable(training,decision,embargo_days)
    model = fit(chosen,kind,minimum=minimum)
    return {"status":"RESEARCH_BASELINE_PREDICTION_NOT_EXECUTABLE",
            "ticker":request["ticker"],"asof":request["feature_date"],
            "source_sha256":request["source_sha256"],"method":kind,
            "prediction":infer(model,request["features"]),
            "train_rows":model["training_rows"],
            "train_labels_through":model["last_label_available"],
            "training_fingerprint":model["training_fingerprint"],
            "legacy_model_replicated":False}


if __name__=="__main__":
    print(json.dumps({"schema":SCHEMA,"status":"NOT_RUN_NO_DATASET",
                      "fitted_baselines":list(METHODS),
                      "market_results":False},sort_keys=True))
