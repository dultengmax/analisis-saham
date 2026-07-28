import unittest
from unittest.mock import patch

import web_app


class WebScreenerTestCase(unittest.TestCase):
    def test_screen_filters_and_sorts_candidates(self):
        def fake_analyze(ticker, options):
            scores = {"BBCA": 80, "TLKM": 60, "GOTO": 30}
            return {
                "ticker": ticker,
                "recommendation": "AVOID/SELL" if ticker == "GOTO" else "HOLD/WATCH",
                "red_flags": [],
                "composite_score": scores[ticker],
            }

        with patch.object(web_app, "load_screener_universe", return_value=["TLKM", "GOTO", "BBCA"]):
            with patch.object(web_app, "analyze_for_web", side_effect=fake_analyze):
                result = web_app.screen_for_web(limit=10, max_tickers=10)

        self.assertEqual(result["checked"], 3)
        self.assertEqual(result["qualified"], 2)
        self.assertEqual([item["ticker"] for item in result["results"]], ["BBCA", "TLKM"])


if __name__ == "__main__":
    unittest.main()
