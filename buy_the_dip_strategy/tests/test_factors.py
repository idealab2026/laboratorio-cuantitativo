import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factors import choose_portfolio, months_between
from run import _universe_review


class FactorPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

    def row(self, ticker, score, sector="Industrials", eligible=True, hard=False,
            rerated=False, vol=0.30):
        return {
            "ticker": ticker,
            "sector": sector,
            "composite_score": score,
            "entry_eligible": eligible,
            "hard_exit": hard,
            "rerated": rerated,
            "volatility_1y": vol,
        }

    def test_months_between(self):
        self.assertEqual(months_between("2026-01-10", "2026-04-02"), 3)

    def test_sparse_opportunities_leave_cash(self):
        scored = [
            self.row("AAA", 80, "Industrials"),
            self.row("BBB", 75, "Energy"),
            self.row("CCC", 70, "Materials"),
        ]
        targets, exits, invest_fraction = choose_portfolio(
            scored, {}, "2026-10-01", self.config
        )
        self.assertEqual(invest_fraction, 0.50)
        self.assertLessEqual(sum(targets.values()), 0.50 + 1e-9)
        self.assertEqual(exits, {})

    def test_rotation_can_replace_old_position(self):
        positions = {"OLD": {"entry_date": "2026-01-02", "sector": "Industrials"}}
        sectors = ["Energy", "Materials", "Information Technology", "Healthcare", "Consumer Staples"]
        scored = [self.row("NEW", 95, "Energy")]
        scored += [self.row(f"X{i}", 90 - i, sectors[i % len(sectors)]) for i in range(11)]
        scored += [self.row("OLD", 46, "Industrials", eligible=False)]
        targets, exits, _ = choose_portfolio(scored, positions, "2026-10-01", self.config)
        self.assertNotIn("OLD", targets)
        self.assertEqual(exits["OLD"], "rank_replaced")

    def test_hard_exit_ignores_minimum_hold(self):
        positions = {"BAD": {"entry_date": "2026-09-15", "sector": "Energy"}}
        scored = [self.row("BAD", 70, "Energy", eligible=False, hard=True)]
        targets, exits, _ = choose_portfolio(scored, positions, "2026-10-01", self.config)
        self.assertEqual(targets, {})
        self.assertEqual(exits["BAD"], "hard_quality_or_value_exit")

    def test_minimum_hold_position_is_not_rotated_or_forced_to_cash(self):
        positions = {"YOUNG": {"entry_date": "2026-09-15", "sector": "Industrials"}}
        scored = [self.row("YOUNG", 46, "Industrials", eligible=False)]
        targets, exits, invest_fraction = choose_portfolio(
            scored, positions, "2026-10-01", self.config
        )
        self.assertIn("YOUNG", targets)
        self.assertNotIn("YOUNG", exits)
        self.assertEqual(invest_fraction, 0.50)


    def test_full_frozen_universe_captures_every_outcome_without_market_data(self):
        sectors = {f"X{n:03d}": "Industrials" for n in range(503)}
        scored = [{
            "ticker": "X000", "sector": "Industrials", "entry_eligible": True,
            "survival_gate": True, "valuation_score": 86.0,
            "quality_score": 70.0, "capital_allocation_score": 62.0,
            "dislocation_score": 90.0, "composite_score": 79.0,
            "catalyst_votes": 4,
        }, {
            "ticker": "X001", "sector": "Industrials", "entry_eligible": False,
            "survival_gate": True, "valuation_score": 30.0,
            "quality_score": 30.0, "capital_allocation_score": 44.0,
            "dislocation_score": 8.0, "composite_score": 28.0,
            "catalyst_votes": 0,
        }]
        market = {"X000": object(), "X001": object(), "X002": object()}
        fundamentals = {"X000": object(), "X001": object()}
        review = _universe_review("2026-11-30", sectors, market,
                                  fundamentals, scored, {"X000": 0.10}, self.config)
        by = {row["ticker"]: row for row in review["rows"]}
        self.assertEqual(review["universe_count"], 503)
        self.assertEqual(review["scored_count"], 2)
        self.assertEqual(review["eligible_count"], 1)
        self.assertEqual(by["X000"]["status"], "selected")
        self.assertEqual(by["X000"]["weight"], 0.1)
        self.assertEqual(by["X001"]["status"], "rules_rejected")
        self.assertIn("valuation", by["X001"]["reasons"])
        self.assertIn("quality", by["X001"]["reasons"])
        self.assertEqual(by["X002"]["status"], "missing_fundamentals")
        self.assertEqual(by["X003"]["status"], "missing_price")
        self.assertIsNone(by["X003"]["score"])
        self.assertNotIn("price", by["X001"])
        self.assertNotIn("market_cap", by["X000"])

    def test_caps_are_respected(self):
        scored = [self.row(f"E{i}", 90-i, "Energy", vol=0.15) for i in range(6)]
        scored += [self.row(f"I{i}", 80-i, "Industrials", vol=0.30) for i in range(6)]
        targets, _, _ = choose_portfolio(scored, {}, "2026-10-01", self.config)
        self.assertLessEqual(len(targets), 10)
        self.assertTrue(all(w <= 0.15 + 1e-9 for w in targets.values()))
        energy = sum(w for t, w in targets.items() if t.startswith("E"))
        self.assertLessEqual(energy, 0.30 + 1e-9)


if __name__ == "__main__":
    unittest.main()
