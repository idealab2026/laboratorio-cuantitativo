#!/usr/bin/env python3
"""Institutional append-only prospective research; ECB fixings are NOT trade fills."""
import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from refresh_ecb import SERIES, SOURCE, validate_document

SCHEMA = "idea_lab_fx_forecast_events_v1"
CLASS = "prospective_reference_forecasts_not_trades"
NOTICE = "Prospective forecasts of ECB reference fixings only. No executable fills, investment P&L or broker positions."
ZERO = "0" * 64
MODELS = ("unchanged", "momentum_1", "reversal_1")
RATE = re.compile(r"^\d+\.\d{1,8}$")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def empty_ledger():
    return {"schema": SCHEMA, "data_class": CLASS, "series": SERIES,
            "source": SOURCE, "notice": NOTICE, "events": []}


def event_hash(event):
    body = {key: value for key, value in event.items() if key != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def rate_literal(value):
    if not isinstance(value, str) or not RATE.fullmatch(value):
        raise ValueError("Invalid decimal rate literal")
    number = Decimal(value)
    if not Decimal("0.6") <= number <= Decimal("2"):
        raise ValueError("Reference fixing outside permitted bounds")
    return number


def rounded(value):
    return format(value.quantize(Decimal(".000001"), rounding=ROUND_HALF_UP), ".6f")


def forecasts(observations):
    if len(observations) < 3:
        raise ValueError("Insufficient chronologically known history")
    previous, current = [rate_literal(r["usd_per_eur"]) for r in observations[-2:]]
    change = current - previous
    return {MODELS[0]: rounded(current),
            MODELS[1]: rounded(current + change),
            MODELS[2]: rounded(current - change)}


def check_time(value):
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise ValueError("Unknown UTC event time")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt


def verify_ledger(ledger):
    if not isinstance(ledger, dict) or set(ledger) != {"schema", "data_class", "series", "source", "notice", "events"}:
        raise ValueError("Unknown forecast-ledger document")
    if {key: ledger[key] for key in ("schema", "data_class", "series", "source", "notice")} != {
        "schema": SCHEMA, "data_class": CLASS, "series": SERIES, "source": SOURCE, "notice": NOTICE
    }:
        raise ValueError("Ledger cannot be attributed to another source")
    events = ledger["events"]
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("Invalid prospective event sequence")
    issued, resolved, invalidated, inconsistent = {}, set(), set(), set()
    prev = ZERO
    last_time = None
    for event in events:
        kind = event.get("event_type")
        required = {"event_type", "fixing_date", "recorded_at_utc", "source_sha256", "previous_hash", "hash"}
        if kind == "issued":
            required |= {"observed_rate", "predictions"}
        elif kind == "resolved":
            required |= {"signal_hash", "realized_rate", "realized_fixing_date", "absolute_errors"}
        elif kind == "invalidated":
            required |= {"signal_hash", "reason"}
        else:
            raise ValueError("Unknown event class")
        if set(event) != required or event["previous_hash"] != prev:
            raise ValueError("Invalid event structure or hash chain")
        if not isinstance(event["hash"], str) or not SHA.fullmatch(event["hash"]) or event_hash(event) != event["hash"]:
            raise ValueError("Event integrity digest mismatch")
        if not isinstance(event["source_sha256"], str) or not SHA.fullmatch(event["source_sha256"]):
            raise ValueError("Missing immutable source reference")
        dt = check_time(event["recorded_at_utc"])
        if last_time and dt < last_time:
            raise ValueError("Event issued out of chronological order")
        last_time = dt
        fixing = date.fromisoformat(event["fixing_date"])
        if fixing.weekday() >= 5 or fixing > dt.date():
            raise ValueError("Forecast retrodated or future-fixing")
        if kind == "issued":
            if event["fixing_date"] in issued:
                raise ValueError("Duplicate prospective issue")
            rate_literal(event["observed_rate"])
            pred = event["predictions"]
            if not isinstance(pred, dict) or set(pred) != set(MODELS):
                raise ValueError("Unexpected forecast algorithm")
            for value in pred.values():
                rate_literal(value)
            baseline = rounded(rate_literal(event["observed_rate"]))
            symmetric = abs(Decimal(pred["momentum_1"]) + Decimal(pred["reversal_1"]) - 2 * Decimal(baseline)) <= Decimal(".000002")
            if pred["unchanged"] != baseline or not symmetric:
                inconsistent.add(event["hash"])
            issued[event["fixing_date"]] = event
        elif kind == "invalidated":
            prior = issued.get(event["fixing_date"])
            if (not prior or prior["hash"] != event["signal_hash"] or
                    event["signal_hash"] in resolved or event["signal_hash"] in invalidated or
                    event["signal_hash"] not in inconsistent or
                    event["reason"] != "prediction_input_order_bug_v1"):
                raise ValueError("Unknown or unsupported forecast invalidation")
            invalidated.add(event["signal_hash"])
        else:
            prior = issued.get(event["fixing_date"])
            if not prior or event["signal_hash"] != prior["hash"] or event["signal_hash"] in resolved or event["signal_hash"] in invalidated:
                raise ValueError("Unknown or duplicate resolved signal")
            settled_on = date.fromisoformat(event["realized_fixing_date"])
            if settled_on <= fixing or settled_on > dt.date() or settled_on.weekday() >= 5:
                raise ValueError("Outcome must be from a later official fixing")
            realized = rate_literal(event["realized_rate"])
            errors = event["absolute_errors"]
            if not isinstance(errors, dict) or set(errors) != set(MODELS):
                raise ValueError("Invalid model score coverage")
            for name in MODELS:
                if errors[name] != rounded(abs(Decimal(prior["predictions"][name]) - realized)):
                    raise ValueError("Score does not reconcile with observed fixing")
            resolved.add(event["signal_hash"])
        prev = event["hash"]
    if inconsistent != invalidated:
        raise ValueError("Forecast input-order error must be explicitly invalidated")
    return True


def append_event(ledger, event):
    event["previous_hash"] = ledger["events"][-1]["hash"] if ledger["events"] else ZERO
    event["hash"] = event_hash(event)
    ledger["events"].append(event)


def advance(ledger, official):
    validate_document(official)
    verify_ledger(ledger)
    observations = official["observations"]
    date_to_index = {r["date"]: index for index, r in enumerate(observations)}
    existing = {event["fixing_date"]: event for event in ledger["events"] if event["event_type"] == "issued"}
    resolved = {event["signal_hash"] for event in ledger["events"] if event["event_type"] in ("resolved", "invalidated")}
    stamp, source_hash = official["received_at_utc"], official["source_sha256"]
    added = 0
    for fixing_date, issue in existing.items():
        if issue["hash"] in resolved:
            continue
        if fixing_date not in date_to_index:
            raise ValueError("Lost next fixing due to expired source window: refusing silent reset")
        index = date_to_index[fixing_date]
        if index == len(observations) - 1:
            continue
        next_rate = observations[index + 1]
        actual = rate_literal(next_rate["usd_per_eur"])
        append_event(ledger, {"event_type": "resolved", "fixing_date": fixing_date,
                            "realized_fixing_date": next_rate["date"],
                            "signal_hash": issue["hash"], "realized_rate": next_rate["usd_per_eur"],
                            "absolute_errors": {model: rounded(abs(Decimal(issue["predictions"][model])-actual))
                                                for model in MODELS},
                            "source_sha256": source_hash, "recorded_at_utc": stamp})
        added += 1
    current = official["latest_observation"]
    if current not in existing:
        append_event(ledger, {"event_type": "issued", "fixing_date": current,
                            "recorded_at_utc": stamp, "source_sha256": source_hash,
                            "observed_rate": observations[-1]["usd_per_eur"],
                            "predictions": forecasts(observations)})
        added += 1
    verify_ledger(ledger)
    return added


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--official", type=Path, required=True)
    cli.add_argument("--ledger", type=Path, required=True)
    args = cli.parse_args()
    official = json.loads(args.official.read_text(encoding="utf-8"))
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    count = advance(ledger, official)
    if count:
        args.ledger.write_text(json.dumps(ledger, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Source: ECB statistics | {count} new prospective journal events | "
          f"{len(ledger['events'])} total | no trades")


if __name__ == "__main__":
    main()
