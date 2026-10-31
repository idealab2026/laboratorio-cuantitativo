#!/usr/bin/env python3
"""A genuinely trained, small LSTM via NumPy/BPTT for source-neutral research.

This is NOT an archived MIDAS recurrent model, executable trade, or real-data
forecast. Dated weekly feature windows, maturation embargo, no retrospective
signals, no market feed, and no publication of learned parameters.
"""
from __future__ import annotations

from datetime import timedelta
import hashlib
import json
import math
from collections import defaultdict

import numpy as np

from weekly_baselines import FEATURES, _day, _fields, _history, _trainable

SCHEMA = "idealab_research_lstm_v1"
WINDOW = 3
HIDDEN = 3
EPOCHS = 24
LR = .035
MINIMUM = 30


def _sequence(panel, row):
    ticker, end = row["ticker"], row["feature_date"]
    eligible = [r for r in panel if r["ticker"] == ticker
                and r["feature_date"] <= end]
    eligible.sort(key=lambda r: r["feature_date"])
    if len(eligible) < WINDOW or eligible[-1]["feature_date"] != end:
        return None
    last = eligible[-WINDOW:]
    for a,b in zip(last,last[1:]):
        gap = (_day(b["feature_date"])-_day(a["feature_date"])).days
        if not 5 <= gap <= 9:
            raise ValueError("Nonconsecutive weekly LSTM feature observations")
    if any(r["feature_available_at"] > end for r in last):
        raise ValueError("Unobserved feature in recurrent window")
    return np.asarray([[r["features"][f] for f in FEATURES] for r in last],
                      dtype=float)


def _sig(x):
    return 1/(1+np.exp(-np.clip(x,-35,35)))


def _forward(W,U,b,V,bo,sequence):
    h = np.zeros(HIDDEN)
    c = np.zeros(HIDDEN)
    cache = []
    for x in sequence:
        hp,cp = h,c
        z = W@x + U@hp + b
        i,f,o = (_sig(z[k*HIDDEN:(k+1)*HIDDEN]) for k in range(3))
        g = np.tanh(z[3*HIDDEN:4*HIDDEN])
        c = f*cp + i*g
        h = o*np.tanh(c)
        cache.append((x,hp,cp,i,f,o,g,c))
    return float(V@h+bo),h,cache


def _grad(W,U,V,cache,dy):
    gW = np.zeros_like(W)
    gU = np.zeros_like(U)
    gb = np.zeros(4*HIDDEN)
    gV = dy*(cache[-1][5]*np.tanh(cache[-1][7]))
    gbo = dy
    dh = dy*V.copy()
    dc = np.zeros(HIDDEN)
    for x,hprev,cprev,i,f,o,g,c in reversed(cache):
        tc = np.tanh(c)
        do = dh*tc
        newdc = dc + dh*o*(1-tc*tc)
        di = newdc*g
        df = newdc*cprev
        dg = newdc*i
        dz = np.concatenate((di*i*(1-i),df*f*(1-f),
                             do*o*(1-o),dg*(1-g*g)))
        gW += np.outer(dz,x)
        gU += np.outer(dz,hprev)
        gb += dz
        dh = U.T@dz
        dc = newdc*f
    return gW,gU,gb,gV,gbo


def fit(rows, panel, *, minimum=MINIMUM):
    """Fit *all four* LSTM gates and output projection on matured labels."""
    if type(minimum) is not int or minimum<MINIMUM or len(rows)<minimum:
        raise ValueError("Insufficient matured LSTM target observations")
    data=_history(panel)
    allowed={(r["ticker"],r["feature_date"]) for r in data}
    if len(rows) != len({(r["ticker"],r["feature_date"]) for r in rows}):
        raise ValueError("Duplicated LSTM target")
    for r in rows:
        _fields(r,True)
        if (r["ticker"],r["feature_date"]) not in allowed:
            raise ValueError("LSTM training target missing in dated panel")
    means=np.asarray([sum(r["features"][f] for r in rows)/len(rows)
                      for f in FEATURES])
    std=np.asarray([max((sum((r["features"][f]-means[k])**2
                             for r in rows)/len(rows))**.5,1e-6)
                    for k,f in enumerate(FEATURES)])
    xs=[];ys=[]
    for row in sorted(rows,key=lambda x:(x["feature_date"],x["ticker"])):
        seq=_sequence(data,row)
        if seq is not None:
            xs.append((seq-means)/std)
            ys.append(row["forward_return"])
    if len(xs)<minimum:
        raise ValueError("Insufficient consecutive LSTM training sequences")
    ym=float(np.mean(ys))
    yscl=max(float(np.std(ys)),1e-6)
    targets=(np.asarray(ys)-ym)/yscl
    rng=np.random.default_rng(17)
    W=rng.normal(0,.085,size=(4*HIDDEN,len(FEATURES)))
    U=rng.normal(0,.085,size=(4*HIDDEN,HIDDEN))
    b=np.zeros(4*HIDDEN)
    b[HIDDEN:2*HIDDEN]=.6
    V=rng.normal(0,.08,size=HIDDEN)
    bo=0.
    for _ in range(EPOCHS):
        wgrad=np.zeros_like(W);ugrad=np.zeros_like(U)
        bgrad=np.zeros_like(b);vgrad=np.zeros_like(V);obgrad=0.
        for x,y in zip(xs,targets):
            pred,_,cache=_forward(W,U,b,V,bo,x)
            dy=float(np.clip(pred-y,-4.,4.))
            a,bb,cc,dd,ee=_grad(W,U,V,cache,dy)
            wgrad+=a;ugrad+=bb;bgrad+=cc;vgrad+=dd;obgrad+=ee
        n=len(xs)
        grad=[wgrad/n,ugrad/n,bgrad/n,vgrad/n]
        norm=math.sqrt(sum(float(np.sum(g*g)) for g in grad)+(obgrad/n)**2)
        scale=min(1.,3./max(norm,1e-12))
        W-=LR*scale*grad[0]
        U-=LR*scale*grad[1]
        b-=LR*scale*grad[2]
        V-=LR*scale*grad[3]
        bo-=LR*scale*obgrad/n
    if not all(np.isfinite(a).all() for a in (W,U,b,V)) or not math.isfinite(bo):
        raise ValueError("Nonfinite trained recurrent state")
    training=[{k:r[k] for k in sorted(r)} for r in sorted(rows,key=lambda x:(x["feature_date"],x["ticker"]))]
    checksum=hashlib.sha256(json.dumps({
        "training":training,"epochs":EPOCHS,"hidden":HIDDEN,
        "window":WINDOW,"learning_rate":LR
    },sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {"status":"RESEARCH_LSTM_TRAINED_SYNTHETIC_ONLY",
            "W":W,"U":U,"b":b,"V":V,"bo":bo,
            "mean":means,"std":std,"ym":ym,"yscl":yscl,
            "trained_sequences":len(xs),"trained_labels_through":max(r["label_available_at"] for r in rows),
            "fingerprint":checksum}


def predict(model,panel,request):
    _fields(request,False)
    seq=_sequence(panel,request)
    if seq is None:
        raise ValueError("No dated recurrent window for prediction")
    pred,_,_=_forward(model["W"],model["U"],model["b"],model["V"],model["bo"],
                      (seq-model["mean"])/model["std"])
    result=float(model["ym"]+model["yscl"]*pred)
    if not math.isfinite(result):
        raise ValueError("Nonfinite recurrent prediction")
    return result


def research_predict(rows,request,*,minimum=MINIMUM,embargo_days=1):
    """Source-neutral experimental forecast, never a trade or prior-model claim."""
    _fields(request,False)
    if type(embargo_days) is not int or embargo_days<1:
        raise ValueError("LSTM embargo must be positive")
    date=_day(request["feature_date"])
    panel=_history(rows)
    eligible=_trainable(panel,date,embargo_days)
    model=fit(eligible,panel,minimum=minimum)
    if not _day(model["trained_labels_through"])<date-timedelta(days=embargo_days):
        raise ValueError("LSTM label leakage at decision close")
    current=[v for v in panel if (v["ticker"],v["feature_date"]) != (request["ticker"],request["feature_date"])]+[request]
    return {
        "status":"RESEARCH_LSTM_NOT_MARKET_CERTIFIED",
        "ticker":request["ticker"],"asof":request["feature_date"],
        "prediction":predict(model,current,request),
        "trained_sequences":model["trained_sequences"],
        "trained_labels_through":model["trained_labels_through"],
        "training_fingerprint":model["fingerprint"],
        "original_model_equivalence":False,
        "orders_executed":0,
    }


def preflight():
    return {"schema":SCHEMA,"status":"RESEARCH_ONLY_UNSTARTED",
            "real_recurrent_gate_training":True,"gates":4,
            "historical_market_performance":False,
            "portfolio_started":False,"window":WINDOW,
            "minimum_training_rows":MINIMUM}


if __name__=="__main__":
    print(json.dumps(preflight(),sort_keys=True))
