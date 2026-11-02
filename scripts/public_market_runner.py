#!/usr/bin/env python3
"""Public-code institutional MIDAS paper runtime, no private repository required.

The source adapter uses the existing Yahoo/yfinance research contract only after
an explicit institutional data-rights gate. No raw OHLC gets written to Git.
Only two new prospective reference portfolios are initially enabled.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from paper_feed import DATA_SOURCE, SCHEMA as FEED_SCHEMA, mac as feed_mac, validate as validate_feed
from classic_503 import yahoo_historical_panel
from classic_503_book import (advance as advance_classic, summary_rows as classic_summary_rows,
                              verify_book as verify_classic_book)
from yahoo_source import (
    DEFAULT_UNIVERSE, prepare_snapshot, verify_universe,
    verify_closed_xnys_session, download_yahoo, verify_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "public-paper-book.json"
FEED_PATH = ROOT / "data" / "institutional-paper-feed.json"
ROSTER_PATH = ROOT / "data" / "competition-roster.json"
CLASSIC_PATH = ROOT / "data" / "classic-503-book.json"
VERSION = "idealab_public_paper_book_v1"
CAPITAL = 100000.0
SPREAD = .0005
FEE = .001
INVESTMENT = .95
EIGHT = ("AAPL", "AMZN", "JNJ", "JPM", "KO", "MSFT", "NVDA", "XOM")
PORTFOLIOS = {"IL-001": ("SPY",), "IL-002": EIGHT}
CONFIG = {"schema":VERSION, "starting_capital":CAPITAL,"commission":FEE,
          "slippage":SPREAD, "invest_fraction":INVESTMENT,
          "portfolios":{k:list(v) for k,v in PORTFOLIOS.items()},
          "signal_timing":"daily_close_next_market_open",
          "no_lookahead":True}
CONFIG_SHA = hashlib.sha256(json.dumps(CONFIG,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def canonical(value):
    return json.dumps({k:v for k,v in value.items() if k!="signature"},
                      sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def seal(value, key):
    if not key or len(key)<32:
        raise ValueError("Missing dedicated institutional secret for public paper book")
    return hmac.new(key.encode(),canonical(value),hashlib.sha256).hexdigest()


def empty_state():
    return {"schema":VERSION, "status":"not_started", "last_session":None,
            "last_source_sha256":None,"config_sha256":None,
            "portfolios":{}, "signature":None}


def validate_state(state,key=None):
    if not isinstance(state,dict) or set(state)!={
        "schema","status","last_session","last_source_sha256",
        "config_sha256","portfolios","signature"
    } or state["schema"]!=VERSION:
        raise ValueError("Unexpected public-book contract")
    if state["status"]=="not_started":
        if state!=empty_state():raise ValueError("Unsigned empty state altered")
        return True
    if state["status"]!="prospective_paper" or not key or len(key)<32:
        raise ValueError("Active paper ledger requires institutional key")
    if state["config_sha256"]!=CONFIG_SHA or not isinstance(state["signature"],str) or not hmac.compare_digest(state["signature"],seal(state,key)):
        raise ValueError("Incorrect configuration or paper ledger signature")
    if not isinstance(state["last_session"],str) or not isinstance(state["last_source_sha256"],str) or len(state["last_source_sha256"])!=64:
        raise ValueError("Invalid last-source trace")
    if set(state["portfolios"])!=set(PORTFOLIOS):
        raise ValueError("Expected two separate certified accounts")
    for slot,book in state["portfolios"].items():
        if set(book)!={"cash","holdings","pending","history","events"}:
            raise ValueError("Unknown account-book property")
        if not isinstance(book["cash"],(int,float)) or book["cash"]<-.000001 or not math.isfinite(book["cash"]):
            raise ValueError("Invalid cash")
        if not isinstance(book["holdings"],dict) or set(book["holdings"])-set(PORTFOLIOS[slot]):
            raise ValueError("Foreign equity position")
        for qty in book["holdings"].values():
            if not isinstance(qty,(float,int)) or qty<0 or not math.isfinite(qty):
                raise ValueError("Invalid share quantity")
        if not isinstance(book["pending"],list) or len(set(book["pending"]))!=len(book["pending"]) or set(book["pending"])-set(PORTFOLIOS[slot]):
            raise ValueError("Untrusted pending order")
        if not isinstance(book["events"],list) or len(book["events"])>3000:
            raise ValueError("Unbounded public event record")
        hist=book["history"]
        if not isinstance(hist,list) or not 1<=len(hist)<=520 or hist[-1]["date"]!=state["last_session"]:
            raise ValueError("Invalid prospective NAV history")
        if any(set(row)!={"date","nav"} or not isinstance(row["nav"],(int,float)) or not math.isfinite(row["nav"]) or row["nav"]<0 for row in hist):
            raise ValueError("Invalid NAV observation")
        if any(hist[i]["date"]>=hist[i+1]["date"] for i in range(len(hist)-1)):
            raise ValueError("Unordered paper market sessions")
    return True


def init_book():
    return {"cash":CAPITAL,"holdings":{},"pending":[],"history":[],"events":[]}


def advance(state, snapshot, *, key, roster, issued_at):
    """One source-verified daily transition. No retroactive order generation."""
    validate_state(state,key)
    if not isinstance(snapshot,dict):
        raise ValueError("No source-backed daily snapshot")
    manifest=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
    verify_snapshot(snapshot,manifest["symbols"])
    session=snapshot["session"]
    if snapshot["coverage"]["constituents_observed"]<453 or "SPY" not in snapshot["bars"]:
        raise ValueError("Unverified common XNYS source")
    required=set(EIGHT)|{"SPY"}
    if not required.issubset(snapshot["bars"]):
        raise ValueError("A required portfolio instrument has no authentic dated quote")
    if state["status"]=="prospective_paper":
        if session<=state["last_session"]:
            raise ValueError("Out-of-order or repeated paper session")
        # Without an archived RAW source for missing sessions, no replaying fills.
        import pandas_market_calendars as mcal
        market=mcal.get_calendar("NYSE")
        sessions=market.schedule(start_date=state["last_session"],end_date=session).index
        if len(sessions)!=2 or sessions[0].strftime("%Y-%m-%d")!=state["last_session"] or sessions[1].strftime("%Y-%m-%d")!=session:
            raise ValueError("Missed market session: pause, never invent previous next-open fills")
    else:
        state={**state,"status":"prospective_paper","portfolios":{x:init_book() for x in PORTFOLIOS},
               "config_sha256":CONFIG_SHA}
    for slot,universe in PORTFOLIOS.items():
        book=state["portfolios"][slot]
        bars=snapshot["bars"]
        # Older holdings receive corporate actions before today's opening.
        for symbol,quantity in list(book["holdings"].items()):
            bar=bars[symbol]
            if bar["split"]>0:
                book["holdings"][symbol]=quantity*bar["split"]
                book["events"].append({"type":"SPLIT","date":session,"symbol":symbol,"factor":bar["split"]})
            if bar["dividend"]>0:
                amount=book["holdings"][symbol]*bar["dividend"]
                book["cash"]+=amount
                book["events"].append({"type":"DIVIDEND","date":session,"symbol":symbol,"amount":amount})
        if book["pending"]:
            amount=book["cash"]*INVESTMENT/len(book["pending"])
            for symbol in sorted(book["pending"]):
                bar=bars[symbol]
                price=bar["open"]*(1+SPREAD)
                if price>bar["high"]+1e-6:
                    raise ValueError("Modeled next-open fill outside observed high")
                units=amount/(price*(1+FEE))
                fee=units*price*FEE
                book["cash"]-=units*price+fee
                if book["cash"]<-.00001:
                    raise ValueError("Paper account insufficient funds")
                book["holdings"][symbol]=units
                book["events"].append({"type":"FILL","side":"BUY","date":session,
                     "symbol":symbol,"quantity":units,"fill":price,"fee":fee})
            book["pending"]=[]
        nav=book["cash"]+sum(shares*bars[symbol]["close"] for symbol,shares in book["holdings"].items())
        if not math.isfinite(nav) or nav<=0:
            raise ValueError("Invalid independently computed portfolio NAV")
        if len(book["history"])>=520:
            raise ValueError("Reached public NAV archival limit: do not discard history silently")
        book["history"].append({"date":session,"nav":nav})
        if not book["holdings"]:
            # A decision becomes executable only in the following XNYS session.
            book["pending"]=list(universe)
            book["events"].append({"type":"SIGNAL","date":session,"side":"BUY",
                                   "count":len(universe),"execution":"next_market_open"})
    result={"schema":VERSION,"status":"prospective_paper",
            "last_session":session,"last_source_sha256":snapshot["sha256"],
            "config_sha256":CONFIG_SHA,"portfolios":state["portfolios"],"signature":None}
    result["signature"]=seal(result,key)
    validate_state(result,key)
    return result,make_feed(result,snapshot,key=key,roster=roster,issued_at=issued_at)


def make_feed(state,snapshot,*,key,roster,issued_at):
    validate_state(state,key)
    if not isinstance(roster,dict) or not isinstance(roster.get("entries"),list):
        raise ValueError("No institutional slot registry")
    permitted={x["slot"] for x in roster["entries"]}
    if not set(PORTFOLIOS).issubset(permitted):
        raise ValueError("Unregistered institutional reference")
    rows=[]
    for slot in PORTFOLIOS:
        book=state["portfolios"][slot]
        history=book["history"]
        end=history[-1]["nav"]
        peak=CAPITAL
        drawdown=0.0
        for point in history:
            peak=max(peak,point["nav"])
            drawdown=min(drawdown,100*(point["nav"]/peak-1))
        daily=100*(end/history[-2]["nav"]-1) if len(history)>1 and history[-2]["nav"]>0 else None
        row={"slot":slot,"activity":"active" if book["holdings"] else "pending",
             "currency":"USD","first_session":history[0]["date"],
             "last_session":history[-1]["date"],"initial_capital":CAPITAL,
             "last_equity":end,"return_pct":100*(end/CAPITAL-1),
             "day_return_pct":daily,
             "risk":{"volatility_pct":None,"max_drawdown_pct":drawdown,"sharpe_0rf":None},
             "positions":len(book["holdings"]),"pending_orders":len(book["pending"]),
             "comparison":{"eligible":False,"universe_id":None},
             "history":history,"source_snapshot_sha256":snapshot["sha256"],
             "config_sha256":CONFIG_SHA}
        rows.append(row)
    c=snapshot["coverage"]
    feed={"schema":FEED_SCHEMA,"status":"source_verified","producer":"idealab_institutional_core",
          "generated_at_utc":issued_at,
          "source":{"identity":DATA_SOURCE,"session":snapshot["session"],
                    "sha256":snapshot["sha256"],"requested":504,"observed":c["observed"],
                    "constituents_observed":c["constituents_observed"],
                    "missing":c["missing"],"rights_attested":True},
          "tracks":rows,"signature":None}
    feed["signature"]=feed_mac(feed,key)
    validate_feed(feed,secret=key,roster=roster)
    return feed


def preflight():
    manifest=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))
    symbols=verify_universe(manifest["symbols"])
    roster=json.loads(ROSTER_PATH.read_text(encoding="utf8"))
    book=json.loads(STATE_PATH.read_text(encoding="utf8"))
    if len(symbols)!=503 or not set(PORTFOLIOS).issubset({x["slot"] for x in roster["entries"]}):
        raise ValueError("Public MIDAS strategy/source identity mismatch")
    classic=json.loads(CLASSIC_PATH.read_text(encoding="utf8"))
    if classic["status"]=="not_started":
        verify_classic_book(classic)
    elif classic.get("status")!="prospective_paper":
        raise ValueError("Untrusted classical paper state")
    elif os.environ.get("IDEALAB_PAPER_FEED_KEY"):
        verify_classic_book(classic,os.environ["IDEALAB_PAPER_FEED_KEY"])
    if book["status"]=="not_started":
        validate_state(book)
    elif book["status"]!="prospective_paper" or book.get("config_sha256")!=CONFIG_SHA:
        raise ValueError("Untrusted or incompatible existing public book")
    elif os.environ.get("IDEALAB_PAPER_FEED_KEY"):
        validate_state(book,os.environ["IDEALAB_PAPER_FEED_KEY"])
    # Read-only CI without the signing secret cannot authenticate active state;
    # the source-writing job and Pages signed-summary gate perform that check.
    return {"status":"source_gate_required" if book["status"]=="not_started" else "prospective_existing",
            "source":"Yahoo/yfinance original", "capital_reference_books":2,
            "universe_constituents":len(symbols),"broker_orders":0,
            "public_raw_prices_written":False,
            "classic_503_reference_books":9}


def is_exchange_session(session, calendar=None):
    """NYSE calendar, not UTC weekdays, decides whether a source run is due."""
    if calendar is None:
        import pandas_market_calendars as calendars
        calendar=calendars.get_calendar("NYSE")
    return not calendar.schedule(start_date=session,end_date=session).empty


def run():
    if os.environ.get("MIDAS_YAHOO_RIGHTS_CONFIRMED")!="true":
        raise RuntimeError("Explicit institutional Yahoo data-use rights attestation required")
    key=os.environ.get("IDEALAB_PAPER_FEED_KEY")
    if not key or len(key)<32:
        raise RuntimeError("Missing institution-owned summary and book authentication secret")
    today=datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    if not is_exchange_session(today):
        return {"status":"exchange_closed","session":today,"changed":False}
    verify_closed_xnys_session(today)
    old=json.loads(STATE_PATH.read_text(encoding="utf8"))
    validate_state(old,key)
    if old["last_session"]==today:
        # A retry must not fetch a mutable quote or repeat an order.
        validate_feed(json.loads(FEED_PATH.read_text(encoding="utf8")),
                      secret=key,roster=json.loads(ROSTER_PATH.read_text(encoding="utf8")))
        verify_classic_book(json.loads(CLASSIC_PATH.read_text(encoding="utf8")),key)
        return {"status":"existing_session_unchanged","session":today,"changed":False}
    roster=json.loads(ROSTER_PATH.read_text(encoding="utf8"))
    universe=json.loads(DEFAULT_UNIVERSE.read_text(encoding="utf8"))["symbols"]
    readings=download_yahoo(universe,today)
    stamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot=prepare_snapshot(universe,today,readings,stamp)
    state,feed=advance(old,snapshot,key=key,roster=roster,issued_at=stamp)
    classic_previous=json.loads(CLASSIC_PATH.read_text(encoding="utf8"))
    # No original historical diary is ever reconstructed or backfilled.
    historic=yahoo_historical_panel(today,rights_attested=True)
    classic_new=advance_classic(classic_previous,snapshot,historic,key=key)
    feed["tracks"].extend(classic_summary_rows(classic_new,snapshot,key=key))
    feed["signature"]=feed_mac(feed,key)
    validate_feed(feed,secret=key,roster=roster)
    # All three candidates are checked before any file is persisted.
    # Only post-source-verified derived research bookkeeping is persisted.
    STATE_PATH.write_text(json.dumps(state,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    FEED_PATH.write_text(json.dumps(feed,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    CLASSIC_PATH.write_text(json.dumps(classic_new,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    return {"status":"new_source_verified_paper_session","session":today,"changed":True,
            "constituent_coverage":snapshot["coverage"]["constituents_observed"],
            "active_reference_books":2,"classic_503_books":9,"raw_ohlc_persisted":False}


def main():
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--preflight",action="store_true")
    g.add_argument("--execute",action="store_true")
    args=p.parse_args()
    print(json.dumps(preflight() if args.preflight else run(),sort_keys=True))


if __name__=="__main__":
    main()
