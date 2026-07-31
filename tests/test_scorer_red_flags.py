import unittest

from analysis.fundamental import evaluate_fundamental
from analysis.scorer import compute_composite


class ScorerRedFlagsTestCase(unittest.TestCase):
    def test_bad_fundamental_forces_avoid_and_caps_composite(self):
        technical = {"technical_score": 90.0, "rsi": 55.0}
        fundamental = evaluate_fundamental(
            {"per": 84.3, "pbv": 2.0, "roe": 0.007, "der": 0.5, "dividend_yield": 0.01, "last_price": 150}
        )

        result = compute_composite(technical, fundamental)

        self.assertEqual(result["recommendation"], "AVOID/SELL")
        self.assertLessEqual(result["composite_score"], 40.0)
        self.assertIn("ROE terlalu rendah (0.7%)", result["red_flags"])
        self.assertIn("PER overvalued (84.3x)", result["red_flags"])

    def test_missing_primary_metrics_penalize_fundamental_score(self):
        complete = evaluate_fundamental(
            {"per": 12.0, "pbv": 2.0, "roe": 0.12, "der": 0.5, "dividend_yield": 0.03}
        )
        missing = evaluate_fundamental(
            {"per": None, "pbv": 2.0, "roe": None, "der": None, "dividend_yield": 0.03}
        )

        self.assertLess(missing["fundamental_score"], complete["fundamental_score"])
        self.assertIn("PER", missing["missing_data"])
        self.assertIn("ROE", missing["missing_data"])
        self.assertIn("DER", missing["missing_data"])

    def test_dividend_yield_accepts_percent_value(self):
        result = evaluate_fundamental(
            {"per": 12.0, "pbv": 2.0, "roe": 0.12, "der": 0.5, "dividend_yield": 5.67}
        )

        self.assertIn("5.7%", result["signals"]["dividend_yield"])

    def test_rsi_overbought_forces_avoid_without_red_flag(self):
        technical = {"technical_score": 90.0, "rsi": 72.0}
        fundamental = evaluate_fundamental(
            {"per": 12.0, "pbv": 2.0, "roe": 0.12, "der": 0.5, "dividend_yield": 0.03, "last_price": 500}
        )

        result = compute_composite(technical, fundamental)

        self.assertEqual(result["recommendation"], "AVOID/SELL")
        self.assertEqual(result["red_flags"], [])

    def test_sentiment_uses_ten_percent_and_no_data_keeps_original_score(self):
        technical = {"technical_score": 80.0, "rsi": 55.0}
        fundamental = {
            "fundamental_score": 60.0,
            "raw": {},
        }

        bullish = compute_composite(
            technical,
            fundamental,
            {"skor": 100, "status": "BULLISH", "total": 5},
        )
        no_data = compute_composite(
            technical,
            fundamental,
            {"skor": 50, "status": "NO_DATA", "total": 0},
        )
        with_bandarmology = compute_composite(
            technical,
            fundamental,
            {"skor": 100, "status": "BULLISH", "total": 5},
            {"skor": 100, "fase": "AKUMULASI"},
        )

        self.assertEqual(bullish["composite_score"], 73.0)
        self.assertEqual(no_data["composite_score"], 70.0)
        self.assertEqual(with_bandarmology["composite_score"], 77.5)

    def test_liquidity_score_affects_composite(self):
        result = compute_composite(
            {"technical_score": 80.0, "rsi": 55.0},
            {"fundamental_score": 60.0, "raw": {}},
            liquidity_result={"score": 100},
        )

        self.assertEqual(result["liquidity_score"], 100.0)
        self.assertEqual(result["composite_score"], 74.5)

    def test_ready_ml_score_uses_fifteen_percent(self):
        technical = {"technical_score": 80.0, "rsi": 55.0}
        fundamental = {"fundamental_score": 60.0, "raw": {}}

        with_ml = compute_composite(
            technical,
            fundamental,
            ml_result={"skor": 100, "arah": "NAIK", "status": "READY"},
        )
        failed_ml = compute_composite(
            technical,
            fundamental,
            ml_result={"skor": 50, "arah": "UNKNOWN", "status": "ERROR"},
        )

        self.assertEqual(with_ml["ml_score"], 100.0)
        self.assertEqual(with_ml["composite_score"], 74.5)
        self.assertEqual(failed_ml["composite_score"], 70.0)


if __name__ == "__main__":
    unittest.main()
