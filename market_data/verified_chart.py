"""Provenance-bearing Yahoo daily recovery with independently observed ranges.

Invalid daily OHLC is never clipped. A full regular-session five-minute tape
may supply H/L only when its opening and closing prices match RAW daily O/C.
Daily O/C/V remain verbatim. Receipts retain both original HTTP responses.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import urllib.request
from zoneinfo import ZoneInfo

from market_data.snapshot import normalize_bar, provider_symbol, _digest

SCHEMA = "midas.yahoo_chart_evidence.v1"
RAW = "yahoo_chart_daily_raw_v1"
RANGE = "yahoo_regular_range_daily_ocv_v1"
CLOSE = "yahoo_crosschecked_close_only_v1"
NY = ZoneInfo("America/New_York")


@lru_cache(maxsize=128)
def session_bounds(day):
    import pandas_market_calendars as calendars
    schedule = calendars.get_calendar("XNYS").schedule(start_date=day, end_date=day)
    if len(schedule) != 1:
        raise ValueError("Not an XNYS session")
    return tuple(int(schedule.iloc[0][key].timestamp()) for key in ("market_open", "market_close"))


def urls(symbol, day):
    if not symbol or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for c in symbol):
        raise ValueError("Invalid provider symbol")
    opening, closing = session_bounds(day)
    base = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol
    daily = base + "?interval=1d&period1=" + str(opening-6*86400) + "&period2=" + str(closing+86400) + "&events=div%2Csplits"
    tape = base + "?interval=5m&period1=" + str(opening) + "&period2=" + str(closing) + "&includePrePost=false&events=div%2Csplits"
    return daily, tape


def read_response(url, opener):
    req = urllib.request.Request(url, headers={"User-Agent":"MIDAS-verified-market-reader/1.0"})
    with opener(req, timeout=15) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Market response exceeds bounded receipt size")
    return {"url":url,"raw":raw.decode("utf-8"),"sha256":hashlib.sha256(raw).hexdigest()}


def parse(response, expected_url, symbol):
    if (set(response) != {"url","raw","sha256"} or response["url"] != expected_url or
        hashlib.sha256(response["raw"].encode("utf-8")).hexdigest() != response["sha256"]):
        raise ValueError("Market receipt identity mismatch")
    doc = json.loads(response["raw"])
    if doc.get("chart",{}).get("error"):
        raise ValueError("Provider rejected market request")
    results = doc.get("chart",{}).get("result")
    if not isinstance(results,list) or len(results) != 1:
        raise ValueError("Missing provider instrument")
    result = results[0]
    meta = result.get("meta",{})
    if (meta.get("symbol") != symbol or meta.get("currency") != "USD" or
        meta.get("exchangeTimezoneName") != "America/New_York"):
        raise ValueError("Wrong market instrument, currency or time zone")
    quotes = result.get("indicators",{}).get("quote")
    stamps = result.get("timestamp")
    if (not isinstance(stamps,list) or not stamps or not isinstance(quotes,list) or len(quotes)!=1 or
        len(set(stamps))!=len(stamps) or stamps!=sorted(stamps)):
        raise ValueError("Incomplete or duplicate market timestamps")
    quote = quotes[0]
    if any(not isinstance(quote.get(k),list) or len(quote[k])!=len(stamps)
           for k in ("open","high","low","close","volume")):
        raise ValueError("Incomplete market fields")
    return result, stamps, quote


def row_at(quote, index, day):
    return {"date":day, **{k:quote[k][index] for k in ("open","high","low","close","volume")},
            "dividend":0.,"split":0.}


def no_actions(result, day):
    for events in result.get("events",{}).values():
        for event in events.values():
            if datetime.fromtimestamp(event["date"],NY).date().isoformat()==day:
                raise ValueError("Corporate action requires separate review")


def reconstruct(receipt):
    if (set(receipt)!={"schema","method","session","provider_symbol","daily","intraday","sha256"} or
        receipt.get("schema")!=SCHEMA or receipt.get("method") not in (RAW,RANGE,CLOSE) or
        _digest(receipt)!=receipt["sha256"]):
        raise ValueError("Invalid chart recovery evidence")
    day,symbol=receipt["session"],receipt["provider_symbol"]
    daily_url,tape_url=urls(symbol,day)
    result,stamps,quote=parse(receipt["daily"],daily_url,symbol)
    no_actions(result,day)
    indices=[i for i,t in enumerate(stamps) if datetime.fromtimestamp(t,NY).date().isoformat()==day]
    if len(indices)!=1:
        raise ValueError("Missing exact daily anchor")
    daily=row_at(quote,indices[0],day)
    if receipt["method"]==CLOSE:
        close=daily["close"]
        if isinstance(close,bool) or not isinstance(close,(int,float)) or not math.isfinite(close) or close<=0:
            raise ValueError("Invalid exact closing mark")
        tape,times,prices=parse(receipt["intraday"],tape_url,symbol)
        no_actions(tape,day)
        opening,closing=session_bounds(day)
        if times[-1] not in (closing-300,closing) or any(t<opening or t>closing for t in times):
            raise ValueError("No regular-session terminal closing observation")
        terminal=prices["close"][-1]
        if (isinstance(terminal,bool) or not isinstance(terminal,(int,float)) or not math.isfinite(terminal) or
            terminal<=0 or not math.isclose(close,terminal,rel_tol=1e-7,abs_tol=1e-6)):
            raise ValueError("Closing observations disagree")
        return {"date":day,"provider_symbol":symbol,"close":float(close),
                "dividend":0.,"split":0.,"price_scope":"passive_close_only"}
    if receipt["method"]==RAW:
        if receipt["intraday"] is not None:
            raise ValueError("Unexpected tape for RAW daily recovery")
        return normalize_bar(daily,day,symbol)
    # All daily scalar fields must be finite, positive prices and nonnegative volume.
    for key in ("open","high","low","close","volume"):
        v=daily[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (v<0 if key=="volume" else v<=0):
            raise ValueError("Invalid daily anchor field")
    try:
        normalize_bar(daily,day,symbol)
    except ValueError:
        pass
    else:
        raise ValueError("Valid daily bar must not be re-derived")
    tape,times,prices=parse(receipt["intraday"],tape_url,symbol)
    no_actions(tape,day)
    opening,closing=session_bounds(day)
    required=list(range(opening,closing,300))
    # No holes, fills, extended-session observations, duplicates or guessed auctions.
    if times not in (required, required+[closing]):
        raise ValueError("Incomplete regular-session tape")
    bars=[normalize_bar(row_at(prices,i,day),day,symbol) for i in range(len(times))]
    if (not math.isclose(bars[0]["open"],daily["open"],rel_tol=1e-7,abs_tol=1e-6) or
        not math.isclose(bars[-1]["close"],daily["close"],rel_tol=1e-7,abs_tol=1e-6)):
        raise ValueError("Daily opening/closing anchors disagree with regular tape")
    # Only genuinely observed extrema are used, never min/max-clipping bad daily values.
    derived={**daily,"high":max(b["high"] for b in bars),"low":min(b["low"] for b in bars)}
    return normalize_bar(derived,day,symbol)


def fetch_verified_bar(symbol, day, opener=urllib.request.urlopen):
    source=provider_symbol(symbol,day)
    daily_url,tape_url=urls(source,day)
    receipt={"schema":SCHEMA,"method":RAW,"session":day,"provider_symbol":source,
             "daily":read_response(daily_url,opener),"intraday":None}
    receipt["sha256"]=_digest(receipt)
    try:
        bar=reconstruct(receipt)
    except ValueError as daily_error:
        # A tape is eligible only for an actually present daily range error.
        result,times,quote=parse(receipt["daily"],daily_url,source)
        no_actions(result,day)
        selected=[i for i,t in enumerate(times) if datetime.fromtimestamp(t,NY).date().isoformat()==day]
        if len(selected)!=1:
            raise daily_error
        try:
            normalize_bar(row_at(quote,selected[0],day),day,source)
        except ValueError as error:
            if str(error)!="Impossible OHLC range":
                raise daily_error
        else:
            raise daily_error
        receipt["method"]=RANGE
        receipt["intraday"]=read_response(tape_url,opener)
        receipt["sha256"]=_digest(receipt)
        bar=reconstruct(receipt)
    return bar,receipt


def fetch_verified_close(symbol, day, opener=urllib.request.urlopen):
    """A dated close is useful for passive NAV, never for simulated fills."""
    source=provider_symbol(symbol,day)
    daily_url,tape_url=urls(source,day)
    receipt={"schema":SCHEMA,"method":CLOSE,"session":day,"provider_symbol":source,
             "daily":read_response(daily_url,opener),"intraday":read_response(tape_url,opener)}
    receipt["sha256"]=_digest(receipt)
    return reconstruct(receipt),receipt
