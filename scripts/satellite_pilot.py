#!/usr/bin/env python3
"""Satellite research preflight: catalogue and observation metadata, no orders or P&L.

Source-derived counts must be supplied by a separately audited provider pipeline.
The existence of internally consistent metadata is NOT evidence of genuine imagery.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

SCHEMA = "idealab_satellite_observations_v1"
HEX = re.compile(r"^[a-f0-9]{64}$")
STORE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{3,63}$")
TICKERS = {"WMT", "TGT", "COST"}
VERSION = re.compile(r"^[A-Za-z0-9._-]{3,80}$")


def utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Timestamp must be ISO 8601 UTC with trailing Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError("Timestamp not UTC")
    return parsed


def audit_batch(doc):
    """Check temporal data lineage; output NEVER represents trading activity."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or doc.get("strategy") != "IL-R001":
        raise ValueError("Unexpected satellite observation contract")
    if doc.get("data_class") != "satellite_observations_research_unverified":
        raise ValueError("Research observations must remain unverified")
    rights = doc.get("rights_attestation")
    if rights not in ("not_confirmed", "documented_internal_research"):
        raise ValueError("Missing or unrecognized rights declaration")
    cutoff = utc(doc.get("decision_at_utc"))
    observations = doc.get("observations")
    if not isinstance(observations, list) or len(observations) > 10000:
        raise ValueError("Bad observation list")
    observations_by_store = {}
    seen = set()
    for o in observations:
        if not isinstance(o, dict):
            raise ValueError("Malformed record")
        ticker = o.get("ticker")
        store = o.get("store_ref")
        if ticker not in TICKERS or not isinstance(store, str) or not STORE.fullmatch(store):
            raise ValueError("Unknown retailer/store")
        if any(not isinstance(o.get(k), str) or not HEX.fullmatch(o[k])
               for k in ("source_sha256", "parking_mask_sha256")):
            raise ValueError("Missing immutable source/mask hash")
        if not isinstance(o.get("detector_version"), str) or not VERSION.fullmatch(o["detector_version"]):
            raise ValueError("Unknown detector version")
        captured = utc(o.get("captured_at_utc"))
        available = utc(o.get("available_at_utc"))
        if captured > available or available > cutoff:
            raise ValueError("Lookahead: acquisition or availability after decision time")
        count, capacity = o.get("cars_detected"), o.get("parking_capacity")
        if not isinstance(count, int) or isinstance(count, bool) or not isinstance(capacity, int) or isinstance(capacity, bool):
            raise ValueError("Invalid parking counts")
        if capacity <= 0 or capacity > 20000 or count < 0 or count > capacity:
            raise ValueError("Parking count outside physical capacity")
        cloud = o.get("cloud_cover_pct")
        if not isinstance(cloud, (float, int)) or isinstance(cloud, bool) or not 0 <= cloud <= 100:
            raise ValueError("Invalid cloud cover")
        hour = o.get("local_capture_hour")
        if not isinstance(hour, int) or isinstance(hour, bool) or not 0 <= hour <= 23:
            raise ValueError("Missing local capture hour")
        key = ticker, store, captured.isoformat()
        if key in seen:
            raise ValueError("Duplicate observation for same store and acquisition time")
        seen.add(key)
        record = (captured, o)
        observations_by_store.setdefault((ticker, store), []).append(record)
    pairs = []
    for (ticker, store), items in observations_by_store.items():
        ordered = sorted(items, key=lambda p: p[0])
        for current_time, current in ordered:
            if current["cloud_cover_pct"] > 10:
                continue
            eligible = [(t, prior) for t, prior in ordered
                        if 350 <= (current_time - t).days <= 380
                        and prior["cloud_cover_pct"] <= 10
                        and abs(prior["local_capture_hour"] - current["local_capture_hour"]) <= 1
                        and prior["parking_mask_sha256"] == current["parking_mask_sha256"]
                        and prior["parking_capacity"] == current["parking_capacity"]]
            if not eligible:
                continue
            _, previous = min(eligible, key=lambda entry: abs((current_time - entry[0]).days - 365))
            pairs.append({"ticker": ticker, "store_ref": store, "date": current_time.date().isoformat(),
                          "year_on_year_occupancy_change_pp": round(
                              100 * (current["cars_detected"] - previous["cars_detected"])
                              / current["parking_capacity"], 4)})
    return {
        "strategy": "IL-R001",
        "status": "metadata_only_no_usable_imagery" if not observations else "observations_contract_checked",
        "source_rights": rights,
        "image_count": len(observations),
        "comparable_store_pairs": len(pairs),
        "pairs_by_ticker": {t: sum(p["ticker"] == t for p in pairs) for t in sorted(TICKERS)},
        "trading_signal": None, "nav": None, "return_pct": None,
        "paper_ready": False,
        "warning": "Unverified source metadata only. No out-of-sample alpha validation or signed prospective paper ledger.",
    }


NAIP_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
# Public store surroundings. A tile intersecting the box does not prove the
# parking area is visible, and multiple tiles can come from a single flight.
NAIP_SAMPLES = {
    "WMT": ("Bentonville, AR", "-94.226,36.367,-94.223,36.370"),
    "TGT": ("Richfield, MN", "-93.2495,44.8845,-93.2472,44.8868"),
    "COST": ("Issaquah, WA", "-122.0545,47.5483,-122.0521,47.5506"),
}
CATALOG_LIMIT = 2_000_000


def catalog_dates(doc, as_of: date):
    """Report distinct submeter acquisition dates, not counts or delivery dates."""
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        raise ValueError("Invalid NAIP catalogue response")
    links, features = doc.get("links"), doc.get("features")
    if not isinstance(links, list) or any(link.get("rel") == "next" for link in links):
        raise ValueError("Incomplete NAIP catalogue response")
    if not isinstance(features, list) or len(features) >= 100:
        raise ValueError("Incomplete NAIP feature list")
    by_day = {}
    for feature in features:
        if feature.get("collection") != "naip":
            raise ValueError("Unexpected catalogue collection")
        props = feature["properties"]
        gsd = props.get("gsd")
        if type(gsd) not in (int, float) or not 0 < gsd <= 10:
            raise ValueError("Missing or invalid ground resolution")
        captured = utc(props.get("datetime")).date()
        if captured > as_of:
            raise ValueError("Catalogue acquisition after cutoff")
        if gsd < 1:
            by_day[captured] = min(gsd, by_day.get(captured, gsd))
    days = sorted(by_day)
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    quarters = {(day.year, (day.month - 1) // 3 + 1) for day in days}
    return {"submeter_dates": [{"date": day.isoformat(), "best_gsd_m": by_day[day]} for day in days],
            "distinct_submeter_quarters": len(quarters),
            "largest_gap_days": max(gaps, default=None),
            "days_since_latest": (as_of - days[-1]).days if days else None}


def audit_naip_coverage(as_of: date, opener=urlopen):
    evidence = {}
    for ticker, (location, bbox) in NAIP_SAMPLES.items():
        query = NAIP_SEARCH + "?" + urlencode({"collections": "naip", "bbox": bbox, "limit": 100})
        with opener(query, timeout=20) as response:
            raw = response.read(CATALOG_LIMIT + 1)
        if len(raw) > CATALOG_LIMIT:
            raise ValueError("NAIP response exceeds size limit")
        evidence[ticker] = {"sample": location, "query": query,
                            "catalog_sha256": hashlib.sha256(raw).hexdigest(),
                            **catalog_dates(json.loads(raw), as_of)}
    return {"strategy": "IL-R001", "source": "USDA NAIP via Microsoft Planetary Computer",
            "as_of": as_of.isoformat(), "data_class": "catalogue_coverage_only",
            "samples": evidence, "paper_ready": False, "trading_signal": None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--input", type=Path)
    mode.add_argument("--naip-coverage", action="store_true", help="Check live NAIP catalogue coverage at three public stores")
    args = parser.parse_args()
    if args.naip_coverage:
        print(json.dumps(audit_naip_coverage(datetime.now(timezone.utc).date()),
                         ensure_ascii=False, sort_keys=True, indent=2))
        return
    # Default preflight cannot manufacture imagery: empty observation batch.
    doc = json.loads(args.input.read_text(encoding="utf8")) if args.input else {
        "schema": SCHEMA, "strategy": "IL-R001",
        "data_class": "satellite_observations_research_unverified",
        "rights_attestation": "not_confirmed",
        "decision_at_utc": "2026-11-02T00:00:00Z",
        "observations": [],
    }
    print(json.dumps(audit_batch(doc), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
