import unittest
from unittest.mock import patch

import web_app
from analysis.overnight import apply_overnight_catalysts, score_market_catalyst
from data.price_fetcher import normalize_ticker


SNAPSHOT = {
    "generated_at": "2026-07-30T08:00:00+07:00",
    "instruments": {
        "sp500": {"change_pct": 1.0},
        "nikkei": {"change_pct": 1.0},
        "hang_seng": {"change_pct": 1.0},
        "shanghai": {"change_pct": 1.0},
        "oil": {"change_pct": 2.0},
        "usd_idr": {"change_pct": -0.5},
    },
}


class FakeAnalyzer:
    def ambil_berita_google(self, ticker, max=6, days=1):
        return [f"{ticker} umumkan buyback, prospek positif - Media Uji"]


class OvernightCatalystTestCase(unittest.TestCase):
    def test_preopen_catalyst_scores_market_news_and_corporate_action(self):
        rows = [{
            "ticker": "TEST",
            "sector": "Energy",
            "momentum": {
                "score": 60.0,
                "signals": {},
            },
        }]

        covered = apply_overnight_catalysts(rows, FakeAnalyzer(), SNAPSHOT)

        self.assertEqual(covered, 1)
        self.assertGreater(rows[0]["overnight_bonus"], 0)
        self.assertGreater(rows[0]["momentum"]["score"], 60)
        self.assertTrue(rows[0]["overnight"]["corporate_actions"])
        self.assertIn("overnight", rows[0]["momentum"]["signals"])

    def test_market_catalyst_is_sector_sensitive(self):
        energy = score_market_catalyst(SNAPSHOT, "Energy")
        transport = score_market_catalyst(SNAPSHOT, "Transportation & Logistic")

        self.assertGreater(energy["bonus"], transport["bonus"])
        self.assertEqual(normalize_ticker("CL=F"), "CL=F")
        self.assertEqual(normalize_ticker("000001.SS"), "000001.SS")

    def test_preopen_endpoint_accepts_overnight_option(self):
        with patch.object(web_app, "load_screener_universe", return_value=[]):
            result = web_app.momentum_for_web(mode="preopen", use_overnight=True)

        self.assertEqual(result["overnight_covered"], 0)


if __name__ == "__main__":
    unittest.main()
