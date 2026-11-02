#!/usr/bin/env python3
"""Standalone, genuinely fitted research MLP and ARIMA(1,0,0) baselines.

Synthetic test data only; never equivalent to original MIDAS model artifacts.
No market fetch, source-rights assertion, trained parameters publication or fills.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import timedelta

from weekly_baselines import (
    FEATURES, _day, _fields, _finite, _history, _trainable
)

MODEL_IDS = ("mlp_regression_research", "arima_1_0_0_research")
HIDDEN = 5
EPOCHS = 75
SCHEMA = "idealab_weekly_research_models_v1"


def _fingerprint(rows, model_kind):
    canonical = [
        (r["ticker"], r["feature_date"], r["feature_available_at"],
         r["label_end"], r["label_available_at"], r["source_sha256"],
         r["features"], r["forward_return"])
        for r in sorted(rows, key=lambda x:(x["feature_date"],x["ticker"]))
    ]
    return hashlib.sha256(json.dumps(
        {"method":model_kind, "rows":canonical, "hidden":HIDDEN,
         "epochs":EPOCHS, "schema":SCHEMA},
        sort_keys=True, separators=(",",":"), allow_nan=False
    ).encode()).hexdigest()


def fit_mlp(rows, *, minimum=30):
    """Fit actual one-hidden-layer tanh regression with deterministic full batch SGD."""
    if type(minimum) is not int or minimum < 30 or len(rows) < minimum:
        raise ValueError("Insufficient matured training observations")
    for row in rows:
        _fields(row, True)
    means = [sum(r["features"][f] for r in rows)/len(rows) for f in FEATURES]
    scales = [max((sum((r["features"][f]-means[i])**2 for r in rows)/len(rows))**.5,1e-8)
              for i,f in enumerate(FEATURES)]
    X = [[(r["features"][f]-means[i])/scales[i] for i,f in enumerate(FEATURES)]
         for r in rows]
    ymean = sum(r["forward_return"] for r in rows)/len(rows)
    yscale = max((sum((r["forward_return"]-ymean)**2 for r in rows)/len(rows))**.5,1e-6)
    Y = [(r["forward_return"]-ymean)/yscale for r in rows]
    W = [[.14*math.sin(1.1*(k+1)*(j+2)) for j in range(3)] for k in range(HIDDEN)]
    B = [0.0]*HIDDEN
    V = [.14*math.cos(.7*(k+1)) for k in range(HIDDEN)]
    c = 0.0
    lr,reg = .055,.002
    for _ in range(EPOCHS):
        gw = [[0.0]*3 for k in range(HIDDEN)]
        gb = [0.0]*HIDDEN
        gv = [0.0]*HIDDEN
        gc = 0.0
        for x,t in zip(X,Y):
            hidden = [math.tanh(B[k]+sum(W[k][j]*x[j] for j in range(3)))
                      for k in range(HIDDEN)]
            pred = c + sum(V[k]*hidden[k] for k in range(HIDDEN))
            delta = max(-5.0,min(5.0,pred-t))
            gc += delta
            for k in range(HIDDEN):
                gv[k] += delta*hidden[k]
                g = delta*V[k]*(1-hidden[k]**2)
                gb[k] += g
                for j in range(3):
                    gw[k][j] += g*x[j]
        n = len(X)
        for k in range(HIDDEN):
            V[k] -= lr*(gv[k]/n+reg*V[k])
            B[k] -= lr*gb[k]/n
            for j in range(3):
                W[k][j] -= lr*(gw[k][j]/n+reg*W[k][j])
        c -= lr*gc/n
    params = [c]+V+B+[v for row in W for v in row]
    if not all(math.isfinite(v) for v in params):
        raise ValueError("Nonfinite neural training result")
    return {"kind":"mlp_regression_research", "W":W,"B":B,"V":V,"c":c,
            "means":means,"scales":scales,"ymean":ymean,"yscale":yscale,
            "trained_rows":len(rows),
            "last_label_available":max(r["label_available_at"] for r in rows),
            "training_fingerprint":_fingerprint(rows,"mlp_regression_research")}


def predict_mlp(model, features):
    if not isinstance(features, dict) or set(features)!=set(FEATURES) or not all(
            _finite(features[f]) for f in FEATURES):
        raise ValueError("Invalid current feature observation")
    x = [(features[f]-model["means"][i])/model["scales"][i]
         for i,f in enumerate(FEATURES)]
    hidden = [math.tanh(model["B"][k]+sum(model["W"][k][j]*x[j] for j in range(3)))
              for k in range(HIDDEN)]
    return model["ymean"] + model["yscale"] * (model["c"]+
        sum(model["V"][k]*hidden[k] for k in range(HIDDEN)))


def fit_arima_100(rows, ticker, *, minimum=30):
    """Conditional least-squares ARIMA(1,0,0), no MA term and no differencing.

    Only consecutive weekly *already available* realized labels form pairs.
    A bounded stationary AR(1) coefficient avoids explosive naive forecasts.
    """
    if not isinstance(ticker,str) or type(minimum) is not int or minimum<30:
        raise ValueError("Invalid issuer or ARIMA training minimum")
    issuer = sorted((r for r in rows if r["ticker"]==ticker),
                    key=lambda r:r["feature_date"])
    if len(issuer)<minimum:
        raise ValueError("Insufficient ticker weekly labels")
    for r in issuer:
        _fields(r,True)
    pairs = []
    for previous, current in zip(issuer,issuer[1:]):
        gap = (_day(current["feature_date"])-_day(previous["feature_date"])).days
        if not 5<=gap<=9:
            raise ValueError("Nonconsecutive weekly ARIMA history")
        pairs.append((previous["forward_return"],current["forward_return"]))
    if len(pairs)<minimum-1:
        raise ValueError("Too few valid ARIMA training pairs")
    prior_mean = sum(x for x,_ in pairs)/len(pairs)
    next_mean = sum(y for _,y in pairs)/len(pairs)
    variance = sum((x-prior_mean)**2 for x,_ in pairs)
    phi = (sum((x-prior_mean)*(y-next_mean) for x,y in pairs)/variance
           if variance>1e-12 else 0.0)
    phi = max(-.98,min(.98,phi))
    intercept = next_mean-phi*prior_mean
    if not all(math.isfinite(v) for v in (phi,intercept)):
        raise ValueError("Unstable fitted autoregression")
    return {"kind":"arima_1_0_0_research","ticker":ticker,
            "phi":phi,"intercept":intercept,"trained_rows":len(issuer),
            "last_label_available":max(r["label_available_at"] for r in issuer),
            "training_fingerprint":_fingerprint(issuer,"arima_1_0_0_research")}


def predict_arima_100(model, previous_return):
    if not _finite(previous_return):
        raise ValueError("Last known return missing")
    return model["intercept"]+model["phi"]*previous_return


def _fit_predict(training, row, kind, *, minimum):
    if kind=="mlp_regression_research":
        model=fit_mlp(training,minimum=minimum)
        prediction=predict_mlp(model,row["features"])
        null = sum(r["forward_return"] for r in training)/len(training)
    elif kind=="arima_1_0_0_research":
        subset=sorted((r for r in training if r["ticker"]==row["ticker"]),
                      key=lambda r:r["feature_date"])
        model=fit_arima_100(subset,row["ticker"],minimum=minimum)
        prediction=predict_arima_100(model,subset[-1]["forward_return"])
        null=sum(r["forward_return"] for r in subset)/len(subset)
    else:
        raise ValueError("Unknown research estimator")
    return prediction,null,model


def walk_forward_models(rows, asof, kind, *, minimum=30, embargo_days=1):
    """Chronologically refit using labels available strictly before test week."""
    end=_day(asof)
    if kind not in MODEL_IDS or type(embargo_days) is not int or embargo_days<1:
        raise ValueError("Unknown research estimator or invalid embargo")
    data=_history(rows)
    test_dates=sorted({r["feature_date"] for r in data
                       if _day(r["feature_date"])<=end and
                          _day(r["label_available_at"])<=end})
    scored=[]
    for d in test_dates:
        training=_trainable(data,_day(d),embargo_days)
        candidates=[r for r in data if r["feature_date"]==d and
                    _day(r["label_available_at"])<=end]
        for r in candidates:
            try:
                score,baseline,model=_fit_predict(training,r,kind,minimum=minimum)
            except ValueError as exc:
                if str(exc) in ("Insufficient matured training observations",
                                "Insufficient ticker weekly labels",
                                "Too few valid ARIMA training pairs"):
                    continue
                raise
            if _day(model["last_label_available"]) >= _day(d):
                raise ValueError("Lookahead detected before OOS inference")
            scored.append({"date":d,"ticker":r["ticker"],
                           "prediction":score,"baseline":baseline,
                           "actual":r["forward_return"],
                           "train_labels_through":model["last_label_available"],
                           "training_fingerprint":model["training_fingerprint"]})
    if not scored:
        return {"schema":SCHEMA,"kind":kind,"status":"INSUFFICIENT_OOS_OBSERVATIONS",
                "n":0,"metrics":None}
    mse=sum((x["prediction"]-x["actual"])**2 for x in scored)/len(scored)
    mse0=sum((x["baseline"]-x["actual"])**2 for x in scored)/len(scored)
    return {"schema":SCHEMA,"kind":kind,
            "status":"SYNTHETIC_OOS_EVALUATED_NOT_MARKET_CERTIFIED",
            "n":len(scored),"first":scored[0]["date"],"last":scored[-1]["date"],
            "metrics":{"rmse":math.sqrt(mse),"null_rmse":math.sqrt(mse0),
                       "relative_mse_change":(mse0-mse)/mse0 if mse0>0 else None},
            "scored":scored}


def research_inference(rows, request, kind, *, minimum=30, embargo_days=1):
    """Produce a research-only, nonexecuting forecast at a specific dated close."""
    _fields(request,False)
    decision=_day(request["feature_date"])
    if type(embargo_days) is not int or embargo_days<1:
        raise ValueError("Invalid embargo")
    training=_trainable(_history(rows),decision,embargo_days)
    value,_,model=_fit_predict(training,request,kind,minimum=minimum)
    return {"status":"RESEARCH_ONLY_NOT_CERTIFIED_NOT_EXECUTED",
            "kind":kind,"ticker":request["ticker"],"asof":request["feature_date"],
            "prediction":value,"trained_rows":model["trained_rows"],
            "train_labels_through":model["last_label_available"],
            "training_fingerprint":model["training_fingerprint"],
            "original_model_equivalence":False}


if __name__=="__main__":
    print(json.dumps({"schema":SCHEMA,"status":"NOT_RUN_NO_DATASET",
                      "research_estimators":MODEL_IDS,
                      "market_performance_available":False},sort_keys=True))
