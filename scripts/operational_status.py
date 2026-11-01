#!/usr/bin/env python3
"""Read-only MIDAS operational check; no market calls or private source data."""
import json
import os
from datetime import date
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
    running = source == "source_verified" and rights and signed
    ready = running and books["reference"] == "prospective_paper" and books["classic"] == "prospective_paper"
    observed = len(feed["tracks"]) if ready else 0
    return {
        "schema": "idealab_paper_operational_audit_v1",
        "registered_strategies": len(slots),
        "market_feed": source,
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
    report = evaluate(
        load("competition-roster.json"),
        load("institutional-paper-feed.json"),
        load("public-paper-book.json"),
        load("classic-503-book.json"),
        load("monthly-paper-book.json"),
        rights=os.environ.get("MIDAS_YAHOO_RIGHTS_CONFIRMED") == "true",
        signed=len(key) >= 32)
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
