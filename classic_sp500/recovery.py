"""Recover only passive marks; never create a historical decision or fill."""
from __future__ import annotations

import copy
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def reviewed_dividend_action(reviews, ticker, day, amount):
    for item in reviews.get("reviews", []):
        if (item.get("ticker") == ticker and item.get("vendor_ex_session") == day
                and item.get("kind") == "cash_dividend" and item.get("currency") == "USD"
                and item.get("amount") == amount and item.get("source_url", "").startswith("https://")
                and item.get("verified_on")):
            # Preserve the immutable vendor observation, but value the newly
            # recovered entitlement at the issuer's exact declared amount.
            # A discrepancy is admitted only through an explicit, reproducible
            # decimal-rounding review, never a general numerical tolerance.
            issuer = item.get("issuer_amount", amount)
            try:
                exact = Decimal(str(issuer))
                observed = Decimal(str(amount))
                if not exact.is_finite() or exact <= 0:
                    continue
                if exact != observed:
                    places = item.get("vendor_rounding_decimals")
                    if (type(places) is not int or not 3 <= places <= 8
                            or item.get("amount_basis") != "issuer_exact_vendor_rounded"
                            or exact.quantize(Decimal(1).scaleb(-places),
                                              rounding=ROUND_HALF_UP) != observed):
                        continue
            except (InvalidOperation, TypeError, ValueError):
                continue
            return item
    return None


def reviewed_dividend(reviews, ticker, day, amount):
    action = reviewed_dividend_action(reviews, ticker, day, amount)
    return action["source_url"] if action else None


def recover_passive_books(config, state, sessions_after, quote_loader, *, recorded_at, reviews=None):
    from classic_sp500.corporate_actions import required_claim_quotes, portfolio_nav, valuation_metadata
    result = copy.deepcopy(state)
    recovered, blocked = [], {}
    for name, original in state["books"].items():
        if not original.get("paused_missing_quotes"):
            continue
        spec = config["strategies"].get(name, {})
        if (spec.get("kind") != "equal_weight_hold" and name != "benchmark_spy") or any(
            pos.get("stop") is not None or pos.get("target") is not None
            for pos in original["positions"].values()
        ) or any(order["side"] != "buy" for order in original["pending"].values()):
            blocked[name] = "historical_trading_rules_require_review"
            continue
        book = copy.deepcopy(original)
        days = sessions_after(book["equity"][-1]["date"], state["last_session"])
        if not days or days[-1] != state["last_session"]:
            blocked[name] = "incomplete_session_calendar"
            continue
        marks = []
        verified_book = copy.deepcopy(book)
        missing_tickers = []
        try:
            # Commit only complete consecutive daily marks in memory. A failed
            # day rolls back its dividends too; later days are never skipped.
            for day in days:
                bars, identity = quote_loader(day)
                missing_tickers = sorted((set(book["positions"]) | required_claim_quotes(book)) - set(bars))
                if missing_tickers:
                    raise ValueError("missing_historical_held_bar")
                for ticker, pos in book["positions"].items():
                    row = bars[ticker]
                    dividend = float(row.get("dividend", 0))
                    if row.get("split", 0):
                        raise ValueError("corporate_action_requires_review")
                    if dividend:
                        action = reviewed_dividend_action(reviews or {}, ticker, day, dividend)
                        if not action or not math.isfinite(dividend) or dividend < 0:
                            raise ValueError("corporate_action_requires_review")
                        issuer_dividend = float(action.get("issuer_amount", dividend))
                        amount = pos["shares"] * issuer_dividend
                        book["cash"] += amount
                        pos["dividends"] = pos.get("dividends", 0) + amount
                        book["events"].append({"date": day, "type": "dividend",
                            "ticker": ticker, "amount": amount, "source_url": action["source_url"],
                            "vendor_dividend_per_share": dividend,
                            "issuer_dividend_per_share": issuer_dividend,
                            "recorded_at_utc": recorded_at, "recognition": "existing_paper_ex_session_model"})
                    close = float(row["close"])
                    if not math.isfinite(close) or close <= 0:
                        raise ValueError("invalid_close")
                nav = portfolio_nav(book, bars)
                if not math.isfinite(nav) or nav < 0:
                    raise ValueError("invalid_nav")
                marks.append({"date": day, "nav": nav, "late_mark_only": True,
                              "recorded_at_utc": recorded_at,
                              "quote_identity": identity, **valuation_metadata(book)})
                verified_book = copy.deepcopy(book)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            blocked[name] = str(exc)
            if not marks:
                continue
            book = verified_book
        # These orders missed their intended open. Preserve their omission;
        # never execute them from a later historical or present-day quote.
        expired = sorted(book["pending"])
        book["pending"] = {}
        book["equity"].extend(marks)
        book["nav"] = marks[-1]["nav"]
        partial = name in blocked
        book["events"].append({"date": marks[-1]["date"],
            "type": "passive_prefix_recovered_still_paused" if partial else
                    "passive_marks_recovered_no_fills",
            "recorded_at_utc": recorded_at, "sessions": [m["date"] for m in marks],
            "expired_unfilled_buys": expired})
        if partial:
            book["paused_missing_quotes"] = {
                "since": day, "last_valued_session": marks[-1]["date"],
                "missing_tickers": missing_tickers or original["paused_missing_quotes"]["missing_tickers"],
                "reason": blocked[name]}
        else:
            del book["paused_missing_quotes"]
            recovered.append(name)
        result["books"][name] = book
    return result, recovered, blocked
