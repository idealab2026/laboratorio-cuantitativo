#!/usr/bin/env python3
"""Private-to-public MIDAS paper summary: signed, redacted, no raw Yahoo bars.

A private, independently operated institutional core may prepare summary input.
This module never reads personal accounts or imports historical private ledgers.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import math
import os
import re
import statistics
from datetime import date, datetime, timezone
from pathlib import Path

SCHEMA = "idealab_institutional_paper_feed_v1"
PRODUCER = "idealab_institutional_core"
DATA_SOURCE = {"vendor": "Yahoo Finance", "client": "yfinance", "market": "XNYS",
               "auto_adjust": False, "actions": True}
HEX = re.compile(r"^[a-f0-9]{64}$")
DAY = re.compile(r"^\d{4}-\d\d-\d\d$")
UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
SLOT = re.compile(r"^IL-\d{3}$")


def fail(message: str):
    raise ValueError("Untrusted institutional paper feed: " + message)


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        fail(label + " contains unknown or missing properties")


def is_number(value, minimum=None):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and (
        minimum is None or value >= minimum)


def as_day(value):
    if not isinstance(value, str) or not DAY.fullmatch(value):
        fail("invalid session date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value or parsed.weekday() >= 5:
        fail("noncanonical weekday session")
    return parsed


def canonical(doc):
    return json.dumps({k: v for k, v in doc.items() if k != "signature"},
                      sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")


def mac(doc, secret):
    if not isinstance(secret, str) or len(secret) < 32:
        fail("long institutional authentication secret missing")
    return hmac.new(secret.encode("utf8"), canonical(doc), hashlib.sha256).hexdigest()


def validate(doc, *, secret=None, roster=None):
    keys(doc, ("schema", "status", "producer", "generated_at_utc", "source", "tracks", "signature"), "feed")
    if doc["schema"] != SCHEMA:
        fail("wrong feed schema")
    if doc["status"] == "not_connected":
        if (doc["producer"] != "institutional_core_pending" or doc["generated_at_utc"] is not None or
                doc["source"] is not None or doc["tracks"] != [] or doc["signature"] is not None):
            fail("unconnected feed may not claim any observations")
        return {"status": "not_connected", "observed": 0}
    if doc["status"] != "source_verified" or doc["producer"] != PRODUCER:
        fail("unapproved source state")
    if not isinstance(secret, str) or len(secret) < 32:
        fail("source-verified feed requires independent private HMAC key")
    if not isinstance(doc["signature"], str) or not HEX.fullmatch(doc["signature"]):
        fail("signed digest is missing")
    if not hmac.compare_digest(doc["signature"], mac(doc, secret)):
        fail("source attestation mismatch")
    stamp = doc["generated_at_utc"]
    if not isinstance(stamp, str) or not UTC.fullmatch(stamp):
        fail("missing UTC generation timestamp")
    asof = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if asof > datetime.now(timezone.utc):
        fail("future generated_at timestamp")
    source = doc["source"]
    keys(source, ("identity", "session", "sha256", "requested", "observed", "constituents_observed",
                  "missing", "rights_attested"), "source")
    if source["identity"] != DATA_SOURCE or source["rights_attested"] is not True:
        fail("source identity and rights attestation incomplete")
    last_day = as_day(source["session"])
    if last_day > asof.date() or not isinstance(source["sha256"], str) or not HEX.fullmatch(source["sha256"]):
        fail("invalid SHA256 or future session")
    if any(type(source[x]) is not int for x in ("requested", "observed", "constituents_observed", "missing")):
        fail("noninteger market coverage")
    if (source["requested"] != 504 or source["observed"] + source["missing"] != 504 or
            source["constituents_observed"] < 453 or source["constituents_observed"] > 503 or
            source["observed"] != source["constituents_observed"] + 1):
        fail("wrong full-market source coverage")
    if not isinstance(doc["tracks"], list) or not 1 <= len(doc["tracks"]) <= 64:
        fail("missing verified strategy summaries")
    known = set()
    if roster is not None:
        if not isinstance(roster, dict) or not isinstance(roster.get("entries"), list):
            fail("invalid institutional roster")
        known = {row["slot"] for row in roster["entries"]}
        if len(known) != 64:
            fail("incomplete institutional roster")
    seen = set()
    for row in doc["tracks"]:
        fields = ("slot", "activity", "currency", "first_session", "last_session",
                  "initial_capital", "last_equity", "return_pct", "day_return_pct",
                  "risk", "positions", "pending_orders", "comparison", "history",
                  "source_snapshot_sha256", "config_sha256")
        keys(row, fields, "strategy")
        slot = row["slot"]
        if (not isinstance(slot, str) or not SLOT.fullmatch(slot) or slot in seen or
                (known and slot not in known)):
            fail("duplicate, unexpected or invalid strategy slot")
        seen.add(slot)
        if row["activity"] not in ("active", "pending", "cash", "paused", "error"):
            fail("unexpected strategy activity")
        if row["currency"] not in ("USD", "EUR"):
            fail("unknown risk currency")
        first, last = as_day(row["first_session"]), as_day(row["last_session"])
        if last < first or last > last_day:
            fail("strategy session outside verifiable market interval")
        if (not is_number(row["initial_capital"], 1) or not is_number(row["last_equity"], 0) or
                not is_number(row["return_pct"]) or
                (row["day_return_pct"] is not None and not is_number(row["day_return_pct"]))):
            fail("invalid NAV or percentage")
        if any(type(row[k]) is not int or row[k] < 0 for k in ("positions", "pending_orders")):
            fail("invalid portfolio exposure count")
        if (row["source_snapshot_sha256"] != source["sha256"] or
                not isinstance(row["config_sha256"], str) or not HEX.fullmatch(row["config_sha256"])):
            fail("incorrect source hash or unversioned configuration")
        risk = row["risk"]
        keys(risk, ("volatility_pct", "max_drawdown_pct", "sharpe_0rf"), "risk")
        if not all(v is None or is_number(v) for v in risk.values()):
            fail("non-finite risk")
        if risk["max_drawdown_pct"] is not None and not -100 <= risk["max_drawdown_pct"] <= 0:
            fail("impossible drawdown")
        comparison = row["comparison"]
        keys(comparison, ("eligible", "universe_id"), "comparison")
        if type(comparison["eligible"]) is not bool or (
            comparison["universe_id"] is not None and (
                not isinstance(comparison["universe_id"], str) or
                not re.fullmatch(r"[a-z0-9_-]{3,48}", comparison["universe_id"]))):
            fail("invalid comparison group")
        if comparison["eligible"] and comparison["universe_id"] is None:
            fail("comparison without common denominator")
        history = row["history"]
        if not isinstance(history, list) or len(history) < 1 or len(history) > 520:
            fail("missing or oversize NAV evidence")
        prior = None
        for point in history:
            keys(point, ("date", "nav"), "NAV point")
            day = as_day(point["date"])
            if day < first or day > last or prior is not None and day <= prior or not is_number(point["nav"], 0):
                fail("invalid or unordered NAV history")
            prior = day
        if history[-1]["date"] != row["last_session"] or abs(history[-1]["nav"]-row["last_equity"]) > .000001:
            fail("NAV not traced to last session")
        derived = 100 * (row["last_equity"] / row["initial_capital"] - 1)
        if abs(derived - row["return_pct"]) > .00001:
            fail("cumulative return inconsistent with NAV")
        if len(history) >= 2:
            prev = history[-2]["nav"]
            expected = 100 * (row["last_equity"]/prev - 1) if prev > 0 else None
            if expected is None:
                if row["day_return_pct"] is not None:
                    fail("invalid daily return on zero previous NAV")
            elif row["day_return_pct"] is None or abs(expected-row["day_return_pct"]) > .00001:
                fail("daily return inconsistent with two dated NAV observations")
        elif row["day_return_pct"] is not None:
            fail("single observation cannot claim daily P/L")
        # Risk must be derived from the same NAV series, not arbitrary values.
        if len(history) >= 2:
            peak = row["initial_capital"]
            worst = 0.0
            for point in history:
                peak = max(peak, point["nav"])
                worst = min(worst, 100 * (point["nav"] / peak - 1) if peak else 0.0)
            if risk["max_drawdown_pct"] is None or abs(risk["max_drawdown_pct"]-worst) > .0001:
                fail("drawdown is not reproducible from NAV")
    return {"status": "source_verified", "observed": len(seen),
            "session": source["session"], "sha256": source["sha256"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", type=Path)
    parser.add_argument("--sign", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.sign) == bool(args.validate):
        parser.error("Choose --validate or --sign")
    secret = os.environ.get("IDEALAB_PAPER_FEED_KEY")
    roster = json.loads((Path(__file__).resolve().parents[1]/"data/competition-roster.json").read_text())
    if args.validate:
        result = validate(json.loads(args.validate.read_text(encoding="utf8")), secret=secret, roster=roster)
        print(json.dumps(result, sort_keys=True))
        return
    if not args.output:
        parser.error("--sign requires --output")
    if not secret or len(secret) < 32:
        fail("cannot sign without private institutional secret")
    doc = json.loads(args.sign.read_text(encoding="utf8"))
    if doc.get("status") != "source_verified":
        fail("only source-verified candidate may be signed")
    doc["signature"] = mac(doc, secret)
    validate(doc, secret=secret, roster=roster)
    args.output.write_text(json.dumps(doc, indent=2, ensure_ascii=False)+"\n", encoding="utf8")
    print(json.dumps({"status":"signed", "tracked":len(doc["tracks"])}))


if __name__ == "__main__":
    main()
