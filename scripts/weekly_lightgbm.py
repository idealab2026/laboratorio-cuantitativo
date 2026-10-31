#!/usr/bin/env python3
"""Independent REAL LightGBM training; research only, no institutional paper execution.

Three distinct objectives: regression, binary direction, cross-sectional LambdaRank.
All inputs must be prevalidated, dated and lawfully supplied. Tests use SYNTHETIC
data. These estimators are not certified copies of earlier investment models.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import hashlib
import json
import math

import lightgbm as lgb
import numpy as np

from weekly_baselines import FEATURES, _day, _fields, _history, _trainable

SCHEMA = "idealab_lightgbm_research_v1"
METHODS = ("return", "direction", "rank")
MINIMUM = 30
MIN_DATES = 8
ROUNDS = 18
PARAMS = {
    "learning_rate": 0.08, "num_leaves": 7, "max_depth": 3,
    "min_data_in_leaf": 3, "min_data_in_bin": 1,
    "feature_fraction": 1.0, "bagging_fraction": 1.0,
    "lambda_l2": 0.25, "seed": 17, "data_random_seed": 17,
    "feature_fraction_seed": 17, "bagging_seed": 17,
    "num_threads": 1, "deterministic": True,
    "force_col_wise": True, "verbosity": -1,
}


def _groups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["feature_date"]].append(row)
    return [sorted(groups[d], key=lambda r: r["ticker"]) for d in sorted(groups)]


def _rank_labels(rows):
    """Only rank already matured, same-date cross-sectional label packets."""
    valid = []
    labels = []
    counts = []
    for group in _groups(rows):
        if len(group) < 3:
            continue
        order = sorted(group, key=lambda r: (r["forward_return"],r["ticker"]))
        buckets = {r["ticker"]:min(2, 3*i//len(group))
                   for i,r in enumerate(order)}
        valid.extend(group)
        labels.extend(buckets[r["ticker"]] for r in group)
        counts.append(len(group))
    if len(counts) < MIN_DATES:
        raise ValueError("Insufficient matured cross-sectional training dates")
    return valid,labels,counts


def _fingerprint(rows, mode):
    payload = {
        "schema":SCHEMA, "mode":mode,"params":PARAMS,
        "rounds":ROUNDS,"lightgbm_version":lgb.__version__,
        "rows":[{k:r[k] for k in sorted(r)} for r in sorted(
            rows,key=lambda r:(r["feature_date"],r["ticker"]))]
    }
    return hashlib.sha256(json.dumps(payload,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode()).hexdigest()


def fit(rows, mode, *, minimum=MINIMUM):
    """Fit using nothing except matured input rows (no hyperparameter search)."""
    if mode not in METHODS:
        raise ValueError("Unknown LightGBM research objective")
    if type(minimum) is not int or minimum < MINIMUM or len(rows) < minimum:
        raise ValueError("Insufficient matured LightGBM observations")
    for row in rows:
        _fields(row,True)
    rows = _history(rows)
    if len({r["feature_date"] for r in rows}) < MIN_DATES:
        raise ValueError("Insufficient distinct training dates")
    if mode == "rank":
        train,y,counts = _rank_labels(rows)
        if len(train) < minimum:
            raise ValueError("Insufficient ranked issuer observations")
        params = {**PARAMS, "objective":"lambdarank",
                  "metric":"ndcg","label_gain":[0,1,3]}
    elif mode == "direction":
        train = rows
        y = [int(r["forward_return"]>0) for r in train]
        if set(y) != {0,1}:
            raise ValueError("Binary direction requires positive and negative examples")
        counts = None
        params = {**PARAMS,"objective":"binary","metric":"binary_logloss"}
    else:
        train = rows
        y = [r["forward_return"] for r in train]
        counts = None
        params = {**PARAMS,"objective":"regression","metric":"l2"}
    features = np.asarray([[r["features"][f] for f in FEATURES] for r in train],
                          dtype=np.float64)
    ds = lgb.Dataset(features, label=np.asarray(y,dtype=np.float64),
                     group=counts, feature_name=list(FEATURES),
                     free_raw_data=True)
    model = lgb.train(params,ds,num_boost_round=ROUNDS)
    return {
        "booster":model,"mode":mode,
        "trained_rows":len(train),"trained_dates":len({r["feature_date"] for r in train}),
        "last_label_available":max(r["label_available_at"] for r in train),
        "fingerprint":_fingerprint(train,mode),
        "library":"lightgbm","version":lgb.__version__,
    }


def predict(model, request):
    if not isinstance(request,dict):
        raise ValueError("Invalid prediction input")
    _fields(request,False)
    X=np.asarray([[request["features"][f] for f in FEATURES]],dtype=np.float64)
    score=float(model["booster"].predict(X,num_threads=1)[0])
    if not math.isfinite(score):
        raise ValueError("Nonfinite LightGBM prediction")
    if model["mode"]=="direction" and not 0 <= score <= 1:
        raise ValueError("Invalid probability")
    return score


def _metrics(scored, mode):
    if mode=="rank":
        pairs=0
        correct=0.0
        for group in _groups(scored):
            for i,a in enumerate(group):
                for b in group[i+1:]:
                    if a["actual"]==b["actual"]:
                        continue
                    pairs+=1
                    x=(a["prediction"]-b["prediction"])*(a["actual"]-b["actual"])
                    correct+=1 if x>0 else .5 if x==0 else 0
        return {"pairwise_accuracy":correct/pairs if pairs else None,
                "baseline_pairwise_accuracy":.5,"pairs":pairs}
    error=sum((r["prediction"]-r["actual"])**2 for r in scored)/len(scored)
    base=sum((r["baseline"]-r["actual"])**2 for r in scored)/len(scored)
    label="brier" if mode=="direction" else "rmse"
    return {label: error if mode=="direction" else math.sqrt(error),
            "baseline_"+label: base if mode=="direction" else math.sqrt(base),
            "mean_squared_error":error,"baseline_mse":base}


def walk_forward(rows, evaluation_asof, mode, *, minimum=MINIMUM, embargo_days=1):
    """Fit at every test close using only labels matured strictly before embargo."""
    end=_day(evaluation_asof)
    if mode not in METHODS or type(embargo_days) is not int or embargo_days<1:
        raise ValueError("Unsupported LightGBM method or embargo")
    evidence=_history(rows)
    test_days=sorted({r["feature_date"] for r in evidence
                      if _day(r["label_available_at"])<=end and
                         _day(r["feature_date"])<=end})
    scored=[]
    for day in test_days:
        training=_trainable(evidence,_day(day),embargo_days)
        try:
            fitted=fit(training,mode,minimum=minimum)
        except ValueError as exc:
            if str(exc) in (
                "Insufficient matured LightGBM observations",
                "Insufficient distinct training dates",
                "Insufficient matured cross-sectional training dates",
                "Insufficient ranked issuer observations",
                "Binary direction requires positive and negative examples",
            ):
                continue
            raise
        if not _day(fitted["last_label_available"]) < _day(day)-timedelta(days=embargo_days):
            raise ValueError("Lookahead detected in training availability")
        candidates=[r for r in evidence if r["feature_date"]==day
                    and _day(r["label_available_at"])<=end]
        if mode=="rank" and len(candidates)<3:
            continue
        base=(sum(int(x["forward_return"]>0) for x in training)/len(training)
              if mode=="direction" else
              sum(x["forward_return"] for x in training)/len(training))
        for row in candidates:
            pred=predict(fitted,{k:row[k] for k in (
                "ticker","feature_date","feature_available_at","features","source_sha256")})
            scored.append({
                "feature_date":day,"ticker":row["ticker"],
                "prediction":pred,
                "actual":(int(row["forward_return"]>0) if mode=="direction"
                          else row["forward_return"]),
                "baseline":base if mode!="rank" else None,
                "train_labels_through":fitted["last_label_available"],
                "model_fingerprint":fitted["fingerprint"],
            })
    if not scored:
        return {"schema":SCHEMA,"mode":mode,"status":"INSUFFICIENT_OOS_OBSERVATIONS",
                "observations":0,"metrics":None}
    return {
        "schema":SCHEMA,"mode":mode,
        "status":"SYNTHETIC_OOS_NOT_MARKET_CERTIFIED",
        "observations":len(scored),
        "first":scored[0]["feature_date"],"last":scored[-1]["feature_date"],
        "metrics":_metrics(scored,mode),
        "scored":scored,
    }


def research_predict(rows, request, mode, *, minimum=MINIMUM, embargo_days=1):
    """One research-only fitted forecast; no orders, portfolio or historical fill."""
    _fields(request,False)
    decision=_day(request["feature_date"])
    if type(embargo_days) is not int or embargo_days<1:
        raise ValueError("Invalid availability embargo")
    evidence=_history(rows)
    training=_trainable(evidence,decision,embargo_days)
    model=fit(training,mode,minimum=minimum)
    if not _day(model["last_label_available"])<decision-timedelta(days=embargo_days):
        raise ValueError("Lookahead in current decision")
    return {
        "status":"RESEARCH_ONLY_NOT_CERTIFIED_OR_EXECUTED",
        "mode":mode,"asof":request["feature_date"],"ticker":request["ticker"],
        "prediction":predict(model,request),
        "model_fingerprint":model["fingerprint"],
        "train_labels_through":model["last_label_available"],
        "trained_rows":model["trained_rows"],
        "original_model_parity":False,
        "source_rights_attested":False,
    }


if __name__=="__main__":
    print(json.dumps({"status":"RESEARCH_ONLY_NOT_RUN",
                      "methods":list(METHODS),
                      "lightgbm_version":lgb.__version__,
                      "stock_performance_available":False},sort_keys=True))
