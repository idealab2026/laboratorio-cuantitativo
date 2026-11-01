#!/usr/bin/env python3
"""Read-only MIDAS operational check; no market calls or private source data."""
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "data"

def load(name):
    with (ROOT / name).open(encoding="utf-8") as f:
        return json.load(f)

def evaluate(roster, feed, reference, classic, monthly, *, rights=False, signed=False):
    slots = [r["slot"] for r in roster["entries"]]
    expected = {f"IL-{i:03d}" for i in range(1, 65)}
    if len(slots) != 64 or set(slots) != expected:
        raise ValueError("Invalid institutional registry")
    valid_book = {"not_started", "prospective_paper"}
    books = {"reference": reference["status"], "classic": classic["status"],
             "monthly": monthly["status"]}
    if any(v not in valid_book for v in books.values()):
        raise ValueError("Unrecognized paper book state")
    source = feed["status"]
    if source not in {"not_connected", "source_verified"}:
        raise ValueError("Unrecognized feed status")
    source_day = feed.get("source", {}).get("session") if isinstance(feed.get("source"), dict) else None
    try:
        last_age = (datetime.now(timezone.utc).date() - date.fromisoformat(source_day)).days
        fresh = 0 <= last_age <= 4
    except (ValueError, TypeError):
        fresh = False
    running = source == "source_verified" and rights and signed and fresh
    ready = running and books["reference"] == "prospective_paper" and books["classic"] == "prospective_paper"
    observed = len(feed["tracks"]) if ready else 0
    return {
        "schema": "idealab_paper_operational_audit_v1",
        "registered_strategies": len(slots),
        "market_feed": source,
        "last_source_session": source_day,
        "source_recent": fresh,
        "book_status": books,
        "market_data_rights": "confirmed" if rights else "unconfirmed",
        "signing_key": "configured" if signed else "missing",
        "operating": bool(ready),
        "active_reference_strategies": observed,
        "full_64_parity": ready and observed == 64 and books["monthly"] == "prospective_paper",
        "old_system_shutdown_safe": False,
    }

def main():
    key = os.environ.get("IDEALAB_PAPER_FEED_KEY", "")
    feed = load("institutional-paper-feed.json")
    reference = load("public-paper-book.json")
    classic = load("classic-503-book.json")
    monthly = load("monthly-paper-book.json")
    if feed["status"] == "source_verified":
        if len(key) < 32:
            raise ValueError("Active market feed requires institutional signing key")
        from paper_feed import validate
        from public_market_runner import validate_state
        from classic_503_book import verify_book
        validate(feed, secret=key, roster=load("competition-roster.json"))
        validate_state(reference, key)
        verify_book(classic, key)
    report = evaluate(
        load("competition-roster.json"),
        feed, reference, classic, monthly,
        rights=os.environ.get("MIDAS_YAHOO_RIGHTS_CONFIRMED") == "true",
        signed=len(key) >= 32)
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
