import unittest
from unittest.mock import patch

import pandas as pd

import web_app
from analysis.momentum import evaluate_daily_momentum, evaluate_session2_momentum


class MomentumScreenerTestCase(unittest.TestCase):
    def test_evaluate_daily_momentum_scores_breakout_volume_and_gain(self):
        df = pd.DataFrame(
            {
                "Open": [100] * 20 + [105],
                "High": [110] * 20 + [125],
                "Low": [95] * 20 + [104],
                "Close": [100] * 20 + [124],
                "Volume": [1_000_000] * 20 + [4_000_000],
            }
        )

        result = evaluate_daily_momentum(df)

        self.assertEqual(result["status"], "KUAT")
        self.assertTrue(result["breakout_20d"])
        self.assertGreaterEqual(result["volume_ratio"], 4)

    def test_preopen_mode_scores_next_day_setup(self):
        df = pd.DataFrame(
            {
                "Open": [100] * 20 + [102],
                "High": [110] * 20 + [116],
                "Low": [95] * 20 + [101],
                "Close": [100] * 20 + [115],
                "Volume": [1_000_000] * 20 + [3_500_000],
            }
        )

        result = evaluate_daily_momentum(df, mode="preopen")

        self.assertEqual(result["mode"], "preopen")
        self.assertEqual(result["status"], "KUAT")

    def test_preopen_relative_strength_and_accumulation(self):
        df = pd.DataFrame(
            {
                "Open": [100] * 20 + [101, 102, 103, 104, 105],
                "High": [101] * 20 + [102, 103, 104, 105, 112],
                "Low": [99] * 20 + [100, 101, 102, 103, 104],
                "Close": [100] * 20 + [101, 102, 103, 104, 111],
                "Volume": [1_000_000] * 20 + [1_100_000, 1_200_000, 1_300_000, 1_400_000, 1_500_000],
            }
        )
        ihsg = pd.DataFrame({"Close": [100] * 20 + [99, 98, 97, 96, 95]})

        result = evaluate_daily_momentum(
            df,
            mode="preopen",
            ihsg_df=ihsg,
            use_relative_strength=True,
            use_accumulation=True,
        )

        self.assertGreater(result["relative_strength"], 0)
        self.assertGreater(result["accumulation_score"], 0)
        self.assertIn("relative_strength", result["signals"])
        self.assertIn("accumulation", result["signals"])

    def test_session2_mode_scores_intraday_push(self):
        index = pd.date_range("2026-07-27 02:00", periods=60, freq="5min").append(
            pd.date_range("2026-07-28 02:00", periods=60, freq="5min")
        )
        df = pd.DataFrame(
            {
                "Open": [100] * 110 + [104] * 10,
                "High": [102] * 110 + [110] * 10,
                "Low": [99] * 110 + [103] * 10,
                "Close": [101] * 110 + [109] * 10,
                "Volume": [100_000] * 110 + [500_000] * 10,
            },
            index=index,
        )

        result = evaluate_session2_momentum(df)

        self.assertEqual(result["mode"], "session2")
        self.assertEqual(result["status"], "KUAT")
        self.assertLess(result["session1_pct"], 5)

    def test_session2_penalizes_already_top_gainer_from_session1(self):
        index = pd.date_range("2026-07-27 02:00", periods=60, freq="5min").append(
            pd.date_range("2026-07-28 02:00", periods=60, freq="5min")
        )
        df = pd.DataFrame(
            {
                "Open": [100] * 60 + [100] * 50 + [112] * 10,
                "High": [102] * 60 + [114] * 60,
                "Low": [99] * 60 + [100] * 50 + [111] * 10,
                "Close": [101] * 60 + [112] * 60,
                "Volume": [100_000] * 110 + [500_000] * 10,
            },
            index=index,
        )

        result = evaluate_session2_momentum(df)

        self.assertGreaterEqual(result["session1_pct"], 8)
        self.assertIn("sudah top gainer", result["signals"]["session1"])

    def test_momentum_endpoint_filters_and_sorts(self):
        def fake_history(ticker):
            close = 124 if ticker == "FAST" else 101
            volume = 4_000_000 if ticker == "FAST" else 100_000
            return pd.DataFrame(
                {
                    "Open": [100] * 20 + [100],
                    "High": [110] * 20 + [125],
                    "Low": [95] * 20 + [99],
                    "Close": [100] * 20 + [close],
                    "Volume": [1_000_000] * 20 + [volume],
                }
            )

        with patch.object(web_app, "load_screener_universe", return_value=["SLOW", "FAST"]):
            with patch("data.price_fetcher.fetch_price_history", side_effect=fake_history):
                result = web_app.momentum_for_web(limit=10, max_tickers=10, mode="intraday")

        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["mode"], "intraday")
        self.assertEqual([item["ticker"] for item in result["results"]], ["FAST"])


if __name__ == "__main__":
    unittest.main()
