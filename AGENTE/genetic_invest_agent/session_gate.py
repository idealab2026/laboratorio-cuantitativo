"""Cheap, fail-closed preflight; do not spend time evolving an existing session."""
import argparse
import os
import json
import sys
from datetime import timedelta
from datetime import datetime, timezone
from pathlib import Path

from forward_portfolio import FILE_NAME, ensure_before_next_open, latest_completed_session, load, save, mark_inactive_sessions


def session_due(path, session, check_open=ensure_before_next_open):
    if not Path(path).is_file():
        raise RuntimeError("Canonical forward diary missing; refusing to restart")
    state = load(path)
    if state["last_session"] == session:
        return False
    if not state["last_session"] or state["last_session"] > session:
        raise RuntimeError("Canonical diary does not precede the requested session")
    check_open(session)
    return True


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def common_quotes(root, session):
    from market_data.revisions import load_effective
    record = load_effective(Path(root) / "market_data/snapshots", session)
    if datetime.fromisoformat(record["last_captured_at_utc"].replace("Z", "+00:00")) > datetime.now(timezone.utc):
        raise ValueError("Common capture is from the future")
    bars = {ticker: {"Open": row["open"], "High": row["high"], "Low": row["low"],
                     "Close": row["close"], "Dividends": row["dividend"],
                     "Stock Splits": row["split"]} for ticker, row in record["bars"].items()}
    return bars, {"session": session, "snapshot_sha256": record["base"]["sha256"],
                  "effective_sha256": record["effective_sha256"]}


def outage_window(last_session, now):
    import pandas_market_calendars as calendars
    schedule = calendars.get_calendar("XNYS").schedule(
        start_date=last_session, end_date=(now + timedelta(days=12)).date())
    closed = [str(day.date()) for day, row in schedule.iterrows()
              if row["market_close"].to_pydatetime() + timedelta(minutes=90) <= now
              and str(day.date()) > last_session]
    future = [str(day.date()) for day, row in schedule.iterrows()
              if row["market_open"].to_pydatetime() > now]
    if not future:
        raise ValueError("Future XNYS opening not verified")
    return closed, future[0]


def resume_outage(path=None, *, root=ROOT, write=False, now=None):
    root = Path(root)
    path = Path(path) if path else root / "AGENTE/genetic_invest_agent/registro_historico" / FILE_NAME
    if not path.is_file():
        raise ValueError("Canonical diary missing; recovery cannot restart capital")
    original = load(path)
    clock = now or datetime.now(timezone.utc)
    sessions, first_trading = outage_window(original["last_session"], clock)
    if not sessions:
        return {"status": "already_valued", "written": False,
                "session": original["last_session"]}
    reviews = json.loads((root / "market_data/corporate_action_reviews.json").read_text())
    updated = mark_inactive_sessions(original, sessions, lambda day: common_quotes(root, day),
        recorded_at=clock.isoformat(timespec="seconds"), reviews=reviews)
    updated["outage_control"] = {"previous_last_session": original["last_session"],
        "registered_at_utc": clock.isoformat(timespec="seconds"),
        "first_trading_session": first_trading,
        "policy": "retain_holdings_no_outage_fills_resume_at_future_open"}
    if (updated["trades"] != original["trades"] or updated["initial_capital"] != original["initial_capital"]
            or any(updated["equity_history"][d] != v for d, v in original["equity_history"].items())
            or updated["positions"] != original["positions"]):
        raise ValueError("Inactive recovery changed original portfolio economics or history")
    if write:
        save(path, updated)
    return {"status": "outage_reconciled_no_trades" if write else "verified_outage_recoverable",
            "sessions": sessions, "first_trading_session": first_trading,
            "positions": len(updated["positions"]), "trades_unchanged": True,
            "capital_preserved": True, "written": write,
            "last_nav": updated["equity_history"][updated["last_session"]]}


def check_resume_publication(path=None, *, now=None):
    import pandas_market_calendars as calendars
    path = Path(path) if path else ROOT / "AGENTE/genetic_invest_agent/registro_historico" / FILE_NAME
    state = load(path)
    first = state["outage_control"]["first_trading_session"]
    schedule = calendars.get_calendar("XNYS").schedule(start_date=first, end_date=first)
    clock = now or datetime.now(timezone.utc)
    if len(schedule) != 1 or clock >= schedule.iloc[0]["market_open"].to_pydatetime():
        raise ValueError("Resume publication missed its first prospective opening")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--resume-check", action="store_true")
    parser.add_argument("--resume-outage", action="store_true")
    parser.add_argument("--check-resume-window", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        return
    if args.check_resume_window:
        check_resume_publication()
        return
    if args.resume_check or args.resume_outage:
        print(json.dumps(resume_outage(write=args.resume_outage), sort_keys=True))
        return
    session = latest_completed_session(datetime.now(timezone.utc).date().isoformat())
    due = session_due(Path(__file__).parent / "registro_historico" / FILE_NAME, session)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"due={str(due).lower()}\nsession={session}\n")
    print(f"Simulated session {session}: {'due' if due else 'already recorded'}")


if __name__ == "__main__":
    main()
