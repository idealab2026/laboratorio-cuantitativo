#!/usr/bin/env python3
"""IDEA LAB: independent Yahoo/yfinance XNYS RAW OHLC source contract.

Sources and outputs are deliberately independent of personal GitHub accounts.
Only a locally authorised collector may retain raw provider data. A public
institutional Pages deployment must never redistribute this RAW dataset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCHEMA = "idealab.xnys_ohlc.v1"
UNIVERSE_SIZE = 503
BENCHMARK = "SPY"
MIN_COVERAGE = math.ceil(UNIVERSE_SIZE * 0.90)
SOURCE = {"vendor": "Yahoo Finance", "client": "yfinance",
          "interval": "1d", "auto_adjust": False, "actions": True}
FIELDS = ("open", "high", "low", "close", "volume", "dividend", "split")
REPO_ROOT = Path(__file__).resolve().parents[1]


def canonical_symbol(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", value):
        raise ValueError("Unrecognized canonical Yahoo symbol")
    return value


def yahoo_symbol(value: str) -> str:
    return canonical_symbol(value).replace(".", "-")


def verify_universe(symbols: list[str]) -> list[str]:
    if not isinstance(symbols, list) or len(symbols) != UNIVERSE_SIZE:
        raise ValueError("Frozen institutional universe requires exactly 503 symbols")
    clean = [canonical_symbol(x) for x in symbols]
    if len(set(clean)) != UNIVERSE_SIZE or BENCHMARK in clean:
        raise ValueError("Universe contains duplicates or the separate benchmark")
    return sorted(clean)


def date_literal(text: str) -> date:
    if not isinstance(text, str):
        raise ValueError("Missing XNYS ISO session")
    d = date.fromisoformat(text)
    if d.isoformat() != text or d.weekday() >= 5:
        raise ValueError("Invalid XNYS ISO session")
    return d


def normalize(symbol: str, session: str, row: dict) -> dict:
    date_literal(session)
    if not isinstance(row, dict) or row.get("date") != session:
        raise ValueError("Wrong-date or missing Yahoo daily bar")
    record = {"date": session, "provider_symbol": yahoo_symbol(symbol)}
    for key in FIELDS:
        value = row.get(key, 0 if key in ("dividend", "split") else None)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Absent or nonfinite raw OHLC field")
        if key in ("open", "high", "low", "close") and value <= 0:
            raise ValueError("Invalid nonpositive market price")
        if key in ("volume", "dividend", "split") and value < 0:
            raise ValueError("Invalid corporate action or volume")
        record[key] = float(value)
    if not (record["low"] <= min(record["open"], record["close"]) <=
            max(record["open"], record["close"]) <= record["high"]):
        raise ValueError("Impossible raw OHLC range")
    return record


def digest(document: dict) -> str:
    data = {k: v for k, v in document.items() if k != "sha256"}
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def prepare_snapshot(universe: list[str], session: str, readings: dict,
                     stamp: str) -> dict:
    companies = verify_universe(universe)
    date_literal(session)
    when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if not when.tzinfo or when.utcoffset() != timedelta(0) or when.date() < date_literal(session):
        raise ValueError("Capture requires an authentic UTC observation timestamp")
    if not isinstance(readings, dict) or set(readings) - (set(companies) | {BENCHMARK}):
        raise ValueError("Unrecognized or foreign Yahoo price symbol")
    observed, missing = {}, {}
    for symbol in sorted(companies + [BENCHMARK]):
        try:
            observed[symbol] = normalize(symbol, session, readings.get(symbol))
        except (ValueError, TypeError):
            missing[symbol] = "no_complete_dated_raw_bar"
    if sum(x in observed for x in companies) < MIN_COVERAGE or BENCHMARK not in observed:
        raise ValueError("Yahoo coverage under 90% or benchmark SPY missing; no snapshot")
    doc = {"schema": SCHEMA, "market": "XNYS", "session": session,
           "captured_at_utc": stamp, "source": SOURCE,
           "universe_size": UNIVERSE_SIZE, "benchmark": BENCHMARK,
           "requested_symbols": sorted(companies + [BENCHMARK]),
           "coverage": {"requested": UNIVERSE_SIZE + 1,
                        "observed": len(observed), "missing": len(missing),
                        "constituents_observed": sum(x in observed for x in companies)},
           "bars": observed, "missing": missing}
    doc["sha256"] = digest(doc)
    return doc


def verify_snapshot(doc: dict, universe: list[str]) -> bool:
    if not isinstance(doc, dict) or set(doc) != {
        "schema", "market", "session", "captured_at_utc", "source", "universe_size",
        "benchmark", "requested_symbols", "coverage", "bars", "missing", "sha256"
    }:
        raise ValueError("Unknown Yahoo institutional snapshot schema")
    if doc["schema"] != SCHEMA or doc["market"] != "XNYS" or doc["source"] != SOURCE or (
            doc["universe_size"], doc["benchmark"]) != (UNIVERSE_SIZE, BENCHMARK):
        raise ValueError("Wrong price source or market")
    if doc["requested_symbols"] != sorted(verify_universe(universe) + [BENCHMARK]):
        raise ValueError("Frozen constituent identities differ")
    if set(doc["bars"]) & set(doc["missing"]) or set(doc["bars"]) | set(doc["missing"]) != set(doc["requested_symbols"]):
        raise ValueError("Invalid Yahoo coverage/missing set")
    recomputed = prepare_snapshot(universe, doc["session"],
                                  {k: {x: v for x, v in b.items() if x != "provider_symbol"}
                                   for k, b in doc["bars"].items()},
                                  doc["captured_at_utc"])
    if recomputed != doc or digest(doc) != doc["sha256"]:
        raise ValueError("Provider snapshot checksum or bar contract changed")
    return True


def download_yahoo(universe: list[str], session: str) -> dict:
    """Batch Yahoo via yfinance, exact-session raw OHLC/actions. No stale fallback."""
    import yfinance as yf  # Optional dependency; offline CI never queries Yahoo.
    companies = verify_universe(universe)
    target = date_literal(session)
    begin = (target - timedelta(days=6)).isoformat()
    end = (target + timedelta(days=1)).isoformat()
    output = {}
    for start in range(0, len(companies) + 1, 40):
        canonical = sorted(companies + [BENCHMARK])[start:start + 40]
        provider = [yahoo_symbol(s) for s in canonical]
        frame = yf.download(provider, start=begin, end=end, interval="1d",
                            auto_adjust=False, actions=True, group_by="ticker",
                            threads=False, progress=False)
        for ticker, vendor in zip(canonical, provider):
            try:
                part = frame[vendor] if hasattr(frame.columns, "levels") else frame
                selected = part.loc[part.index.strftime("%Y-%m-%d") == session]
                if len(selected) != 1:
                    continue
                row = selected.iloc[0]
                entry = {"date": session, **{
                    field: row.get(name, 0 if field in ("dividend", "split") else None)
                    for field, name in zip(FIELDS, ("Open", "High", "Low", "Close",
                                                   "Volume", "Dividends", "Stock Splits"))}}
                output[ticker] = normalize(ticker, session, entry)
            except (KeyError, TypeError, ValueError):
                continue
    return {ticker: {k: v for k, v in row.items() if k != "provider_symbol"}
            for ticker, row in output.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-contract", action="store_true")
    ap.add_argument("--capture-internal", action="store_true")
    ap.add_argument("--session")
    ap.add_argument("--universe-json", type=Path)
    ap.add_argument("--output-dir", type=Path)
    args = ap.parse_args()
    if args.check_contract and not args.capture_internal:
        print(json.dumps({"status": "source_contract_verified_offline",
                          "vendor": SOURCE["vendor"], "client": SOURCE["client"],
                          "universe_size": UNIVERSE_SIZE, "benchmark": BENCHMARK,
                          "minimum_constituents": MIN_COVERAGE,
                          "data_publication": "disabled"}, sort_keys=True))
        return
    if not args.capture_internal or not (args.session and args.universe_json and args.output_dir):
        ap.error("Use --check-contract or a fully specified internal capture")
    if os.environ.get("INSTITUTIONAL_YAHOO_INTERNAL_RIGHTS") != "confirmed":
        raise RuntimeError("Yahoo personal-use rights not confirmed for institutional capture")
    target = args.output_dir.resolve()
    if target.is_relative_to(REPO_ROOT) or not target.exists():
        raise ValueError("Internal-only storage must already exist outside the public repository")
    universe = json.loads(args.universe_json.read_text(encoding="utf8"))
    readings = download_yahoo(universe, args.session)
    doc = prepare_snapshot(universe, args.session, readings,
                           datetime.now(timezone.utc).isoformat())
    verify_snapshot(doc, universe)
    filename = target / (doc["session"] + ".json")
    if filename.exists():
        if json.loads(filename.read_text(encoding="utf8")) != doc:
            raise ValueError("Existing session is immutable; refuse silent overwrite")
        return
    filename.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": "internal_snapshot_written", "session": doc["session"],
                      "sha256": doc["sha256"], "coverage": doc["coverage"]}))


if __name__ == "__main__":
    main()
