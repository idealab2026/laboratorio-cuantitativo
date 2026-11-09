"""Run the Buy The Dip corpus v0 demo after a fully closed XNYS session."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_data.consume import canonical

from engine import STRATEGY_ID, advance, benchmark_return_pct
from factors import choose_portfolio, score_universe
from market import (
    calendar_context,
    close_series,
    current_bar,
    download_panel,
    eligible_session,
    fundamentals_snapshot,
    load_universe,
)


def _daily_marks(panel, asof, requested):
    """Recover exact-session RAW marks without manufacturing adjusted history."""
    bars, diagnostic = canonical(asof, requested, ROOT / "market_data/snapshots")
    bars = {ticker: bars[ticker] for ticker in requested if ticker in bars}
    missing = sorted(set(requested) - set(bars))
    if missing:
        raise ValueError("No se pueden valorar posiciones/órdenes: " + ",".join(missing))
    return bars, diagnostic


def _read(path, optional=False):
    path = Path(path)
    if optional and not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _month_index(day):
    year, month, _ = map(int, day.split("-"))
    return year * 12 + month


def _decision_due(state, asof, is_month_end):
    if not state or not state.get("last_signal_session"):
        return True
    if is_month_end:
        return state.get("last_signal_session") != asof
    return _month_index(asof) - _month_index(state["last_signal_session"]) >= 2


def _universe_review(asof, sectors, panel, fundamentals, scored, target_weights, config):
    """Persist derived point-in-time ranking outcomes for all frozen symbols.

    No provider raw financials, OHLC bars or post-decision features are emitted.
    This is a diagnostic of the existing decision, not a second decision engine.
    """
    import math
    if len(sectors) != 503 or len(set(sectors)) != len(sectors):
        raise ValueError("Review needs the exact frozen 503-symbol universe")
    scored_map = {row["ticker"]: row for row in scored}
    model = config["model"]

    def score(value):
        return round(float(value), 4) if (
            isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 100) else None

    output = []
    for ticker, sector in sorted(sectors.items()):
        row = scored_map.get(ticker)
        reasons = []
        if row is None:
            status = ("missing_price" if ticker not in panel else
                      "missing_fundamentals" if ticker not in fundamentals else "missing_features")
        elif ticker in target_weights:
            status = "selected"
        elif row.get("entry_eligible"):
            status = "eligible_not_selected"
        else:
            status = "rules_rejected"
            if not row.get("survival_gate"):
                reasons.append("survival")
            if score(row.get("valuation_score")) is None or row["valuation_score"] < model["minimum_valuation_score"]:
                reasons.append("valuation")
            if score(row.get("quality_score")) is None or row["quality_score"] < model["minimum_quality_score"]:
                reasons.append("quality")
            if row.get("catalyst_votes", 0) < model["minimum_catalyst_votes"]:
                reasons.append("catalysts")
            if not ((score(row.get("dislocation_score")) is not None and
                     row["dislocation_score"] >= model["minimum_dislocation_score"]) or
                    (score(row.get("valuation_score")) is not None and row["valuation_score"] >= 70.0)):
                reasons.append("opportunity")
            if score(row.get("composite_score")) is None or row["composite_score"] < model["entry_score"]:
                reasons.append("composite")
            if not reasons:
                reasons.append("other_entry_rule")

        output.append({
            "ticker": ticker, "sector": sector, "status": status,
            "score": score(row.get("composite_score")) if row else None,
            "valuation": score(row.get("valuation_score")) if row else None,
            "quality": score(row.get("quality_score")) if row else None,
            "allocation": score(row.get("capital_allocation_score")) if row else None,
            "dislocation": score(row.get("dislocation_score")) if row else None,
            "catalysts": int(row["catalyst_votes"]) if row else None,
            "eligible": bool(row["entry_eligible"]) if row else None,
            "weight": round(float(target_weights[ticker]), 8) if ticker in target_weights else None,
            "reasons": reasons,
        })
    if (len(output) != len(sectors)
            or sum(row["status"] in ("selected", "eligible_not_selected", "rules_rejected") for row in output) != len(scored)
            or sum(row["eligible"] is True for row in output) != sum(bool(x["entry_eligible"]) for x in scored)
            or sum(row["status"] == "selected" for row in output) != len(target_weights)):
        raise ValueError("Buy The Dip universe audit does not reconcile")
    return {
        "schema_version": 1, "decision_session": asof,
        "universe_count": len(sectors),
        "scored_count": len(scored),
        "eligible_count": sum(bool(row["entry_eligible"]) for row in scored),
        "selected_count": len(target_weights),
        "rows": output,
        "note": "Only derived frozen-decision scores; no raw market or fundamental feed.",
    }


def _build_decision(config, state, asof, context, panel, sectors, fundamentals,
                    price_failures, fundamental_failures):
    benchmark = config["benchmark_ticker"]
    benchmark_close = close_series(panel[benchmark])
    raw = []
    for ticker, fundamental in fundamentals.items():
        frame = panel.get(ticker)
        if frame is None:
            continue
        raw.append({
            "ticker": ticker,
            "sector": sectors[ticker],
            "close": close_series(frame),
            "benchmark_close": benchmark_close,
            "fundamental": fundamental,
        })

    scored = score_universe(raw, config)
    if len(scored) < int(config["minimum_valid_candidates"]):
        raise ValueError(f"Cobertura fundamental insuficiente: {len(scored)} candidatos puntuables")

    positions = {} if state is None else state.get("positions", {})
    target_weights, exit_reasons, invest_fraction = choose_portfolio(
        scored, positions, asof, config
    )
    lookup = {row["ticker"]: row for row in scored}
    selected = []
    for ticker, weight in target_weights.items():
        row = lookup[ticker]
        selected.append({
            "ticker": ticker,
            "sector": row["sector"],
            "weight": round(weight, 8),
            "composite_score": round(row["composite_score"], 4),
            "valuation_score": round(row["valuation_score"], 4) if row["valuation_score"] is not None else None,
            "quality_score": round(row["quality_score"], 4) if row["quality_score"] is not None else None,
            "capital_allocation_score": round(row["capital_allocation_score"], 4) if row["capital_allocation_score"] is not None else None,
            "dislocation_score": round(row["dislocation_score"], 4) if row["dislocation_score"] is not None else None,
            "catalyst_votes": int(row["catalyst_votes"]),
            "volatility_1y": round(row["volatility_1y"], 6) if row["volatility_1y"] is not None else None,
            "latest_statement_period": row["latest_statement_period"],
        })
    selected.sort(key=lambda x: (-x["composite_score"], x["ticker"]))

    decision = {
        "signal_date": asof,
        "expected_fill_session": context["next_session"],
        "target_weights": target_weights,
        "sectors": {ticker: sectors[ticker] for ticker in target_weights},
        "selected": selected,
        "invest_fraction": invest_fraction,
        "exit_reasons": exit_reasons,
        "excluded_count": len(set(sectors) - set(fundamentals)),
        "coverage": {
            "frozen_universe": len(sectors),
            "price_usable": len([ticker for ticker in sectors if ticker in panel]),
            "fundamental_usable": len(fundamentals),
            "scored": len(scored),
            "entry_eligible": sum(bool(row["entry_eligible"]) for row in scored),
            "financials_scored": sum(bool(row["financial_sector"]) for row in scored),
            "price_failures": len(price_failures),
            "fundamental_failures": len(fundamental_failures),
        },
    }
    review = _universe_review(asof, sectors, panel, fundamentals, scored, target_weights, config)
    return decision, review


def run(config_path, output_dir, now=None):
    config_path = Path(config_path)
    config = _read(config_path)
    if config.get("schema_version") != 1 or config.get("name") != "MIDAS_buy_the_dip_corpus_v0_2026":
        raise ValueError("Configuración Buy The Dip no reconocida")
    if config.get("currency") != "USD":
        raise ValueError("La campaña Buy The Dip requiere USD")

    asof = eligible_session(config.get("calendar", "XNYS"), now=now)
    if asof is None:
        return {"status": "market_closed", "changed": False}
    context = calendar_context(asof, config.get("calendar", "XNYS"))
    output = Path(output_dir)
    state_path = output / "ledger.json"
    state = _read(state_path, optional=True)

    universe_path = Path(config["universe_file"])
    universe_hash = _file_hash(universe_path)
    if state is not None and state.get("universe_hash") not in (None, universe_hash):
        raise ValueError("El universo congelado cambió: iniciar otra campaña")

    symbols, sectors, _ = load_universe(universe_path)
    benchmark = config["benchmark_ticker"]
    due = _decision_due(state, asof, context["is_month_end"])
    # Replay of a monthly signal must hash the same frozen universe as
    # its original run, rather than just today's held positions.
    replay_signal = bool(
        state and state.get("last_session") == asof
        and state.get("last_signal_session") == asof
    )

    active = set()
    if state:
        active |= set(state.get("positions", {}))
        pending = state.get("pending")
        if pending:
            active |= set(pending.get("target_weights", {}))

    if due:
        requested = symbols + ([benchmark] if benchmark not in symbols else [])
        panel, price_failures = download_panel(
            requested, period=config["history_period"], asof=asof,
            min_history=int(config["price_min_history_days"]),
            required=active | {benchmark},
        )
        common, _ = canonical(asof, requested, ROOT / "market_data/snapshots")
        panel = {ticker: frame for ticker, frame in panel.items() if ticker in common}
        if benchmark not in panel:
            raise ValueError("Benchmark sin historial completo")
        fundamentals, fundamental_failures = fundamentals_snapshot(
            [ticker for ticker in symbols if ticker in panel], sectors,
            asof=asof, workers=int(config.get("fundamental_workers", 8)),
        )
        decision, universe_review = _build_decision(
            config, state, asof, context, panel, sectors, fundamentals,
            price_failures, fundamental_failures,
        )
        universe_review["universe_hash"] = universe_hash
        universe_review["config_hash"] = _file_hash(config_path)
    else:
        requested = (symbols + ([benchmark] if benchmark not in symbols else [])
                     if replay_signal else sorted(active | {benchmark}))
        # Daily passive marks need no independent RAW provider download.
        panel, price_failures = {}, {}
        decision = None
        universe_review = None
        fundamental_failures = {}

    if due or replay_signal:
        # Original signal and its idempotent replay use identical RAW scope;
        # missing non-held constituents are still excluded from the hash.
        bars, quote_source = canonical(asof, requested, ROOT / "market_data/snapshots")
        if not (active | {benchmark}) <= set(bars):
            raise ValueError("Mandatory exposure missing from common RAW source")
    else:
        bars, quote_source = _daily_marks(panel, asof, requested)
    updated, changed = advance(
        config, bars, asof, bars[benchmark]["close"], decision=decision, state=state,
    )
    updated["universe_hash"] = universe_hash
    if changed:
        _atomic_json(state_path, updated)
        if decision is not None:
            _atomic_json(output / "signals" / f"{asof}.json", decision)
            # Diagnostic attached to this original signal, not recomputed later.
            _atomic_json(output / "universe_reviews" / f"{asof}.json", universe_review)

    return {
        "status": "ok",
        "strategy_id": STRATEGY_ID,
        "session": asof,
        "quote_source": quote_source,
        "month_end": context["is_month_end"],
        "decision_recorded": decision is not None,
        "changed": changed,
        "nav": updated["nav"],
        "positions": len(updated["positions"]),
        "cash": updated["cash"],
        "pending_targets": 0 if not updated.get("pending") else len(updated["pending"]["target_weights"]),
        "benchmark_return_pct": benchmark_return_pct(updated),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Buy The Dip corpus v0 demo; nunca envía órdenes reales")
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.config, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Error Buy The Dip demo: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
