#!/usr/bin/env python3
"""Forward-only IL-039 opening test. Never mutates the competition book or broker."""
import argparse
import copy
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
SCHEMA = "midas.il039.forward_open.v1"
MAX_AGE = timedelta(seconds=180)


def timestamp(t):
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z")


def digest(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def market_window(now):
    if now.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    import pandas_market_calendars as calendars
    local = now.astimezone(ZoneInfo("America/New_York"))
    dates = calendars.get_calendar("XNYS").schedule(
        start_date=local.date() - timedelta(days=14),
        end_date=local.date() + timedelta(days=1))
    current = dates.loc[dates.index.date == local.date()]
    older = dates.loc[dates.index.date < local.date()]
    if current.empty:
        return None
    return {"session": local.date().isoformat(),
            "previous": older.index[-1].date().isoformat(),
            "open": current.iloc[0]["market_open"].to_pydatetime(),
            "close": current.iloc[0]["market_close"].to_pydatetime()}


def prepare(ledger, now, market):
    if not market:
        return None
    if not market["open"] - timedelta(minutes=90) <= now < market["open"]:
        raise ValueError("A signal may only be committed before opening")
    if ledger.get("last_session") != market["previous"]:
        raise ValueError("Ledger not current through preceding session")
    pending = ledger.get("pending")
    if pending is not None and pending.get("expected_fill_session") != market["session"]:
        raise ValueError("Pending order is not for this opening")
    positions = copy.deepcopy(ledger.get("positions"))
    cash = ledger.get("cash")
    if not isinstance(positions, dict) or type(cash) not in (float, int) or not math.isfinite(cash):
        raise ValueError("Invalid paper portfolio")
    if pending and (not isinstance(pending.get("target_weights"), dict) or
                    not all(type(w) in (int, float) and math.isfinite(w) and 0 <= w <= 1
                            for w in pending["target_weights"].values())):
        raise ValueError("Invalid target weights")
    plan = {"schema": SCHEMA, "session": market["session"],
            "source_session": market["previous"],
            "open_at_utc": timestamp(market["open"]),
            "prepared_at_utc": timestamp(now), "positions": positions,
            "cash": cash, "pending": copy.deepcopy(pending)}
    plan["sha256"] = digest(plan)
    return plan


def verify_plan(plan, now, market):
    if not market or not isinstance(plan, dict):
        raise ValueError("No open session or pre-open plan")
    original = {k: v for k, v in plan.items() if k != "sha256"}
    prepared = datetime.fromisoformat(plan["prepared_at_utc"].replace("Z", "+00:00"))
    if (digest(original) != plan.get("sha256") or plan["session"] != market["session"] or
        plan["open_at_utc"] != timestamp(market["open"]) or not prepared < market["open"] <= now or
            now > market["open"] + timedelta(minutes=30)):
        raise ValueError("Missing, changed, late or mismatched pre-open plan")
    return True


def quotes_yahoo(tickers, now, market):
    """Read dated one-minute bars, never daily close or stale data."""
    import yfinance as yf
    from market_data.snapshot import provider_symbol
    quotes = {}
    for symbol in sorted(tickers):
        try:
            ticker = yf.Ticker(provider_symbol(symbol, market["session"]))
            frame = ticker.history(period="1d", interval="1m",
                                   auto_adjust=False, prepost=False, actions=False)
            observed = datetime.now(UTC)  # receipt time, not the scheduler's nominal time
            if frame is None or frame.empty or frame.index.tz is None:
                continue
            candidates = []
            for index, row in frame.iterrows():
                start = index.to_pydatetime()
                end = start + timedelta(minutes=1)
                price = float(row["Close"])
                if (market["open"] <= start < market["close"] and
                    end <= observed and timedelta(0) <= observed - end <= MAX_AGE and
                        math.isfinite(price) and price > 0):
                    candidates.append((end, price))
            if candidates:
                end, price = max(candidates)
                quotes[symbol] = {"price": price, "quote_at_utc": timestamp(end),
                                  "observed_at_utc": timestamp(observed),
                                  "age_seconds": int((observed - end).total_seconds())}
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return quotes


def observe(plan, now, market, quotes, config, prior=None):
    verify_plan(plan, now, market)
    if prior and prior.get("session") == plan["session"] and prior.get("status") == "indicative_fill":
        return prior
    targets = (plan.get("pending") or {}).get("target_weights", {})
    required = set(plan["positions"]) | set(targets)
    valid = {}
    for ticker in required:
        quote = quotes.get(ticker, {})
        try:
            stamped = datetime.fromisoformat(quote["quote_at_utc"].replace("Z", "+00:00"))
            observed = datetime.fromisoformat(quote["observed_at_utc"].replace("Z", "+00:00"))
            price = quote["price"]
            if (market["open"] <= stamped <= observed <= now and
                now - stamped <= MAX_AGE and type(price) in (float, int) and
                    math.isfinite(price) and price > 0):
                valid[ticker] = quote
        except (KeyError, ValueError, TypeError):
            pass
    missing = sorted(required - set(valid))
    status = ("waiting_quotes" if missing else
              "monitoring_no_orders" if not plan.get("pending") else "indicative_fill")
    report = {"schema": SCHEMA, "campaign": "IL-039_FORWARD_TRIAL",
              "status": status, "session": plan["session"],
              "open_at_utc": plan["open_at_utc"],
              "prepared_at_utc": plan["prepared_at_utc"],
              "checked_at_utc": timestamp(now), "source_session": plan["source_session"],
              "pending_targets": len(targets), "positions_count": len(plan["positions"]),
              "quotes_count": len(valid), "missing_quotes": missing,
              "quotes": {t: valid[t] for t in sorted(valid)},
              "indicative_fills": [], "indicative_nav": None,
              "mode": "observed_paper_not_broker"}
    if missing:
        return report
    shadow = {"cash": plan["cash"], "positions": copy.deepcopy(plan["positions"]),
              "pending": copy.deepcopy(plan.get("pending")), "events": []}
    if shadow["pending"]:
        from buy_the_dip_strategy.engine import _settle_pending
        # Observed minute-close substitutes for the execution proxy price.
        # Neither a historical auction fill nor a real broker execution.
        bars = {t: {"open": q["price"]} for t, q in valid.items()}
        _settle_pending(shadow, bars, plan["session"], config["paper_policy"])
        report["indicative_fills"] = [
            {"ticker": e["ticker"], "side": e["side"], "quantity": e["quantity"],
             "price": e["price"], "fee": e["fee"], "observed_at_utc": timestamp(now)}
            for e in shadow["events"] if e.get("type") == "fill"]
    report["indicative_nav"] = round(shadow["cash"] + sum(
        pos["quantity"] * valid[t]["price"] for t, pos in shadow["positions"].items()), 2)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=("prepare", "observe"))
    args = parser.parse_args(argv)
    now = datetime.now(UTC)
    market = market_window(now)
    if market is None:
        print('{"status":"market_closed"}')
        return 0
    plan_path = ROOT / "forward_open_state/il039-lock.json"
    public_path = ROOT / "data/forward-open-il039.json"
    if args.stage == "prepare":
        plan = prepare(json.loads((ROOT / "buy_the_dip_state/ledger.json").read_text()), now, market)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
        public = {"schema": SCHEMA, "campaign": "IL-039_FORWARD_TRIAL",
                  "status": "ready_for_open" if plan["pending"] else "ready_monitoring_no_orders",
                  "session": plan["session"], "source_session": plan["source_session"],
                  "open_at_utc": plan["open_at_utc"],
                  "prepared_at_utc": plan["prepared_at_utc"],
                  "pending_targets": len((plan["pending"] or {}).get("target_weights", {})),
                  "positions_count": len(plan["positions"]), "mode": "observed_paper_not_broker"}
    else:
        if not plan_path.is_file():
            raise ValueError("No pre-open plan: cannot backfill after the opening")
        plan = json.loads(plan_path.read_text())
        verify_plan(plan, now, market)
        tickers = set(plan["positions"]) | set((plan.get("pending") or {}).get("target_weights", {}))
        quotes = quotes_yahoo(tickers, now, market)
        now = datetime.now(UTC)
        previous = json.loads(public_path.read_text()) if public_path.is_file() else None
        config = json.loads((ROOT / "buy_the_dip_strategy/config.json").read_text())
        public = observe(plan, now, market, quotes, config, previous)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": public["status"], "session": public["session"],
                      "pending_targets": public["pending_targets"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
