"""Explicit KVUE merger accounting; unsettled claims are never spendable cash.

The issuer establishes the entitlement. OCC memo 60113 supplies a temporary
pricing reference while fractional cash is unknown. Adopting that reference
for this paper ledger is a disclosed model assumption, not a settlement price.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ACTION = "KVUE_KMB_2026-11-02"
EFFECTIVE = "2026-11-02"
ISSUER = "https://www.sec.gov/Archives/edgar/data/55785/000110465926120990/tm2628636d1_8k.htm"
REFERENCE = "https://infomemo.theocc.com/infomemos?number=60113"
RATIO, CASH = Decimal("0.14625"), Decimal("3.50")


def positive(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("Invalid corporate-action value")
    return result


def required_claim_quotes(book):
    return {claim["symbol"] for claim in book.get("receivables", {}).values()
            if claim["status"] == "unsettled" and Decimal(claim["fractional_shares"]) > 0}


def receivable_value(book, bars, field="close"):
    value = 0.
    for claim in book.get("receivables", {}).values():
        if claim["status"] == "unsettled":
            fraction = float(claim["fractional_shares"])
            amount = float(claim["fixed_cash"])
            if not math.isfinite(fraction) or fraction < 0 or fraction >= 1 or not math.isfinite(amount) or amount < 0:
                raise ValueError("Invalid merger receivable")
            if fraction and bars[claim["symbol"]].get("split", 0):
                raise ValueError("Unsettled cash reference requires a split review")
            value += amount + (fraction * positive(bars[claim["symbol"]][field]) if fraction else 0.)
    return value


def portfolio_nav(book, bars, field="close"):
    value = (float(book["cash"]) + receivable_value(book, bars, field)
             + sum(positive(pos["shares"]) * positive(bars[ticker][field])
                   for ticker, pos in book["positions"].items()))
    if not math.isfinite(value) or value < 0 or not math.isfinite(book["cash"]) or book["cash"] < 0:
        raise ValueError("Invalid portfolio NAV or spendable cash")
    return value


def valuation_metadata(book):
    unsettled = [key for key, claim in book.get("receivables", {}).items()
                 if claim["status"] == "unsettled"]
    return ({"provisional_corporate_valuation": True, "unsettled_receivables": unsettled,
             "valuation_reference_url": REFERENCE} if unsettled else {})


def apply_merger(book, day, bars, *, recorded_at):
    if "KVUE" not in book["positions"] or day < EFFECTIVE:
        return False
    if day != EFFECTIVE or ACTION in book.get("receivables", {}):
        raise ValueError("Merger must be applied exactly once on its effective session")
    bar = bars["KMB"]
    price = positive(bar["open"])
    high, low, close = (positive(bar[k]) for k in ("high", "low", "close"))
    if low > min(price, close) or high < max(price, close) or bar.get("split", 0):
        raise ValueError("Merger successor bar invalid or split requires review")
    old = copy.deepcopy(book["positions"]["KVUE"])
    existing = copy.deepcopy(book["positions"].get("KMB"))
    if existing and any(p.get(k) is not None for p in (old, existing) for k in ("stop", "target")):
        raise ValueError("Protected successor lots require separate review before aggregation")
    shares = Decimal(str(positive(old["shares"])))
    entitlement = shares * RATIO
    whole = int(entitlement.to_integral_value(rounding=ROUND_FLOOR))
    fraction = entitlement - whole
    fixed = (shares * CASH).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Proportional model cost allocation preserves the total original cost.
    # It is accounting attribution, never a simulated purchase or tax claim.
    value = whole * price + float(fixed) + float(fraction) * price
    position_cost = float(old["cost"]) * whole * price / positive(value)
    claim_cost = float(old["cost"]) - position_cost
    successor = None
    if whole:
        successor = {"shares": float(whole), "cost": position_cost,
                     "entry_date": old["entry_date"], "entry_price": position_cost / whole,
                     "dividends": float(old.get("dividends", 0)),
                     "stop": None, "target": None,
                     "basis_origin": "corporate_conversion_no_purchase",
                     "acquired_by_merger_on": day}
        for key in ("stop", "target"):
            if old.get(key) is not None:
                successor[key] = positive((positive(old[key]) - float(CASH)) / float(RATIO))
        if existing:
            successor["shares"] += positive(existing["shares"])
            successor["cost"] += float(existing["cost"])
            successor["dividends"] += float(existing.get("dividends", 0))
            successor["entry_date"] = min(old["entry_date"], existing["entry_date"])
            successor["entry_price"] = successor["cost"] / successor["shares"]
    claim = {"action_id": ACTION, "status": "unsettled", "symbol": "KMB",
             "fixed_cash": str(fixed), "fractional_shares": str(fraction),
             "allocated_cost": claim_cost, "source_url": ISSUER,
             "valuation_reference_url": REFERENCE,
             "valuation_policy": "occ_temporary_reference_applied_to_paper_claim",
             "effective_session": day, "recorded_at_utc": recorded_at}
    del book["positions"]["KVUE"]
    if successor:
        book["positions"]["KMB"] = successor
    book.setdefault("receivables", {})[ACTION] = claim
    book["events"].append({"date": day, "type": "corporate_merger_entitlement",
        "action_id": ACTION, "original_position": old, "prior_successor_position": existing,
        "successor_whole_shares": whole, "fractional_shares": str(fraction),
        "fixed_cash_receivable": str(fixed), "source_url": ISSUER,
        "valuation_reference_url": REFERENCE, "recorded_at_utc": recorded_at,
        "cost_allocation": "pro_rata_temporary_reference_at_effective_open",
        "cash_credited": 0., "trades_executed": 0})
    return True


def settle_reviewed_claims(book, day, reviews, *, recorded_at):
    for review in reviews.get("merger_settlements", []):
        claim = book.get("receivables", {}).get(review.get("action_id"))
        if claim is None or claim["status"] != "unsettled":
            continue
        payment = review.get("payment_session", "")
        if not payment or payment > day:
            continue
        source = review.get("source_url", "")
        if (review.get("currency") != "USD" or review.get("payment_verified") is not True
                or not review.get("verified_on") or review["verified_on"] > day
                or not source.startswith(("https://www.sec.gov/Archives/", "https://www.investor.kimberly-clark.com/"))):
            raise ValueError("Merger cash payment requires issuer evidence")
        price = Decimal(str(positive(review["fractional_cash_price"])))
        cash = Decimal(claim["fixed_cash"]) + (Decimal(claim["fractional_shares"]) * price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        book["cash"] += float(cash)
        claim.update(status="settled", settled_cash=str(cash), payment_session=payment,
                     settlement_source_url=source)
        book["events"].append({"date": day, "type": "corporate_cash_settlement",
            "action_id": claim["action_id"], "amount": float(cash), "source_url": source,
            "allocated_cost": claim["allocated_cost"],
            "realized_pnl": float(cash) - claim["allocated_cost"],
            "recorded_at_utc": recorded_at})


def inactive_mark(book, day, bars, *, recorded_at, identity=None, reviews=None):
    from classic_sp500.recovery import reviewed_dividend_action
    if not (set(book["positions"]) | required_claim_quotes(book)) <= set(bars):
        raise ValueError("Missing exact held or receivable bar")
    for ticker, pos in book["positions"].items():
        row = bars[ticker]
        o, h, l, c = (positive(row[k]) for k in ("open", "high", "low", "close"))
        if l > min(o, c) or h < max(o, c) or row.get("split", 0):
            raise ValueError("Invalid bar or unreviewed split during inactive session")
        dividend = float(row.get("dividend", 0))
        if not math.isfinite(dividend) or dividend < 0:
            raise ValueError("Invalid dividend")
        if dividend:
            action = reviewed_dividend_action(reviews or {}, ticker, day, dividend)
            if not action:
                raise ValueError("Inactive dividend requires issuer review")
            amount = pos["shares"] * float(action.get("issuer_amount", dividend))
            book["cash"] += amount
            pos["dividends"] += amount
            book["events"].append({"date": day, "type": "dividend", "ticker": ticker,
                "amount": amount, "source_url": action["source_url"], "recorded_at_utc": recorded_at})
        crossed = "stop" if pos.get("stop") is not None and l <= pos["stop"] else (
            "target" if pos.get("target") is not None and h >= pos["target"] else None)
        if crossed:
            book["events"].append({"date": day, "type": "unexecuted_during_outage",
                "ticker": ticker, "trigger": crossed, "recorded_at_utc": recorded_at})
    expired = copy.deepcopy(book["pending"])
    book["pending"] = {}
    book["nav"] = portfolio_nav(book, bars)
    book["equity"].append({"date": day, "nav": book["nav"], "inactive_no_fills": True,
        "recorded_at_utc": recorded_at, "quote_identity": identity,
        **valuation_metadata(book)})
    book["events"].append({"date": day, "type": "inactive_mark_no_trades",
        "expired_unfilled_orders": expired, "recorded_at_utc": recorded_at})


def recover_books(state, loader, *, recorded_at, first_trading, reviews=None):
    import pandas_market_calendars as calendars
    result = copy.deepcopy(state)
    completed = []
    for name, book in result["books"].items():
        if "KVUE" not in book["positions"] or not book.get("paused_missing_quotes"):
            continue
        if book["paused_missing_quotes"]["missing_tickers"] != ["KVUE"]:
            raise ValueError("Merger recovery cannot conceal other missing exposures")
        dates = calendars.get_calendar("XNYS").valid_days(
            start_date=book["equity"][-1]["date"], end_date=state["last_session"])
        days = [str(value.date()) for value in dates][1:]
        if not days or days[0] != EFFECTIVE or days[-1] != state["last_session"]:
            raise ValueError("Merger recovery requires complete consecutive sessions from effective date")
        for day in days:
            bars, identity = loader(day)
            if any(not isinstance(identity.get(k), str) or len(identity[k]) != 64
                   or any(c not in "0123456789abcdef" for c in identity[k])
                   for k in ("snapshot_sha256", "effective_sha256")):
                raise ValueError("Merger recovery lacks immutable common source identity")
            apply_merger(book, day, bars, recorded_at=recorded_at)
            settle_reviewed_claims(book, day, reviews or {}, recorded_at=recorded_at)
            inactive_mark(book, day, bars, recorded_at=recorded_at, identity=identity, reviews=reviews)
        del book["paused_missing_quotes"]
        book["outage_control"] = {"first_trading_session": first_trading,
                                  "registered_at_utc": recorded_at}
        completed.append(name)
    for name in completed:
        old, new = state["books"][name], result["books"][name]
        if old["trades"] != new["trades"] or new["equity"][:len(old["equity"])] != old["equity"]:
            raise ValueError("Merger recovery changed original fills or NAV")
        old_cost = sum(float(p["cost"]) for p in old["positions"].values())
        new_cost = sum(float(p["cost"]) for p in new["positions"].values()) + sum(
            r["allocated_cost"] for r in new.get("receivables", {}).values())
        if not math.isclose(old_cost, new_cost, rel_tol=0, abs_tol=1e-7):
            raise ValueError("Merger recovery lost original cost basis")
    return result, completed


def recovery_window(last_session, now):
    import pandas_market_calendars as calendars
    schedule = calendars.get_calendar("XNYS").schedule(
        start_date=last_session, end_date=(now + timedelta(days=12)).date())
    closed = [str(day.date()) for day, row in schedule.iterrows()
              if row["market_close"].to_pydatetime() + timedelta(minutes=90) <= now]
    future = [str(day.date()) for day, row in schedule.iterrows()
              if row["market_open"].to_pydatetime() > now]
    if not closed or closed[-1] != last_session or not future:
        raise ValueError("Reconcile the latest common closed session before merger recovery")
    return future[0]


def recover(*, root=ROOT, write=False, now=None):
    from classic_sp500 import run as classic
    from market_data.revisions import load_effective
    root = Path(root)
    path = root / "classic_sp500_state/ledger.json"
    original = classic.market.read(path)
    config = classic.market.read(root / "classic_sp500/config.json")
    classic.verify_config(config)
    classic.validate_state(original, config)
    clock = now or datetime.now(timezone.utc)
    first = recovery_window(original["last_session"], clock)
    def loader(day):
        effective = load_effective(root / "market_data/snapshots", day)
        stamp = datetime.fromisoformat(effective["last_captured_at_utc"].replace("Z", "+00:00"))
        if stamp > clock:
            raise ValueError("Common capture is from the future")
        return effective["bars"], {"snapshot_sha256": effective["base"]["sha256"],
                                    "effective_sha256": effective["effective_sha256"]}
    updated, names = recover_books(original, loader, recorded_at=clock.isoformat(timespec="seconds"),
        first_trading=first, reviews=classic.market.read(root / "market_data/corporate_action_reviews.json"))
    classic.validate_state(updated, config)
    if write and names:
        classic.market.atomic_write(path, updated)
    return {"status": "merger_reconciled_provisional_receivables" if names else "already_reconciled",
            "recovered_books": names, "written": bool(write and names),
            "session": original["last_session"], "first_trading_session": first,
            "trades_unchanged": True, "cash_receivables_not_spendable": True,
            "valuations_provisional": bool(names)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("check", "recover", "publication-check"), default="check")
    args = parser.parse_args()
    if args.phase == "publication-check":
        import pandas_market_calendars as calendars
        state = json.loads((ROOT / "classic_sp500_state/ledger.json").read_text())
        now = datetime.now(timezone.utc)
        for book in state["books"].values():
            first = book.get("outage_control", {}).get("first_trading_session")
            if first:
                schedule = calendars.get_calendar("XNYS").schedule(start_date=first, end_date=first)
                if len(schedule) != 1 or now >= schedule.iloc[0]["market_open"].to_pydatetime():
                    raise ValueError("Recovery publication missed its first prospective opening")
        return
    print(json.dumps(recover(write=args.phase == "recover"), sort_keys=True))


if __name__ == "__main__":
    main()
