import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

import pandas as pd

import web_app
from analysis.momentum import (
    evaluate_daily_momentum,
    evaluate_morning_momentum,
    evaluate_session2_momentum,
)


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
        self.assertGreater(result["acceleration"], 0)
        self.assertGreater(result["session2_value"], 0)
        self.assertGreater(result["price_vs_vwap_pct"], 0)
        self.assertIn("vwap", result["signals"])

    def test_morning_rvol_opening_range_and_vwap(self):
        prior_dates = pd.date_range("2026-06-01", periods=20, freq="B")
        prior_index = pd.DatetimeIndex([
            date + pd.Timedelta(hours=2, minutes=offset)
            for date in prior_dates
            for offset in (0, 5, 10)
        ])
        current_index = pd.date_range("2026-07-01 02:00", periods=12, freq="5min")
        index = prior_index.append(current_index)
        df = pd.DataFrame({
            "Open": 100.0,
            "High": 102.0,
            "Low": 99.0,
            "Close": 101.0,
            "Volume": 100_000.0,
        }, index=index)
        df.loc[current_index[:3], "Volume"] = 300_000
        df.loc[current_index[3:], ["High", "Close", "Volume"]] = [107, 106, 250_000]

        result = evaluate_morning_momentum(df)

        self.assertEqual(result["mode"], "morning")
        self.assertEqual(result["time_volume_days"], 20)
        self.assertEqual(result["time_volume_ratio"], 3.0)
        self.assertTrue(result["opening_range_breakout"])
        self.assertGreater(result["price_vs_vwap_pct"], 0)
        self.assertIn("RVOL 09:00-09:15 3.0x", result["signals"]["time_rvol"])
        self.assertIn("fibonacci", result)
        self.assertLessEqual(abs(result["fibonacci_bonus"]), 8)

    def test_morning_filter_requires_rvol_vwap_and_opening_range(self):
        momentum = {
            "score": 80,
            "time_volume_ratio": 1.5,
            "price_vs_vwap_pct": 0.5,
            "value_today": 500_000_000,
            "opening_range_breakout": True,
        }

        self.assertTrue(web_app.passes_momentum_filter(momentum, "morning"))
        momentum["price_vs_vwap_pct"] = -0.1
        self.assertFalse(web_app.passes_momentum_filter(momentum, "morning"))

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

    def test_session2_uses_same_time_relative_volume_from_20_days(self):
        prior_dates = [
            date for date in pd.date_range("2026-05-01", "2026-06-30", freq="B")
            if date.weekday() < 4
        ][-20:]
        prior_index = pd.DatetimeIndex([
            date + pd.Timedelta(hours=6, minutes=30 + offset)
            for date in prior_dates
            for offset in (0, 5, 10, 15)
        ])
        current_index = pd.date_range("2026-07-02 02:00", periods=60, freq="5min")
        index = prior_index.append(current_index)
        volume = pd.Series(100_000, index=index)
        volume.loc[current_index[(current_index.hour == 6) & (current_index.minute <= 45)]] = 300_000
        df = pd.DataFrame({
            "Open": 100,
            "High": 103,
            "Low": 99,
            "Close": 102,
            "Volume": volume,
        }, index=index)

        result = evaluate_session2_momentum(df)

        self.assertEqual(result["time_volume_days"], 20)
        self.assertEqual(result["time_volume_ratio"], 3.0)
        self.assertIn("RVOL slot awal sesi 2 3.0x", result["signals"]["time_rvol"])

    def test_session2_filter_rejects_old_top_gainer_without_new_push(self):
        self.assertFalse(web_app.passes_momentum_filter({
            "score": 80,
            "change_pct": 9,
            "session1_pct": 8,
            "session2_pct": 0.7,
            "session2_value": 1_000_000_000,
            "acceleration": -7.3,
        }, "session2"))

    def test_session2_filter_accepts_fresh_afternoon_acceleration(self):
        self.assertTrue(web_app.passes_momentum_filter({
            "score": 70,
            "change_pct": 4,
            "session1_pct": 2,
            "session2_pct": 1.5,
            "session2_value": 500_000_000,
            "acceleration": 1.0,
            "price_vs_vwap_pct": 0.2,
        }, "session2"))

    def test_session2_filter_rejects_below_vwap(self):
        self.assertFalse(web_app.passes_momentum_filter({
            "score": 80,
            "change_pct": 4,
            "session1_pct": 2,
            "session2_pct": 1.5,
            "session2_value": 500_000_000,
            "acceleration": 1.0,
            "price_vs_vwap_pct": -0.1,
        }, "session2"))

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

    def test_preopen_continues_when_ihsg_is_unavailable(self):
        def fake_history(ticker):
            if ticker == "^JKSE":
                raise ValueError("data IHSG kosong")
            return pd.DataFrame({
                "Open": [100] * 20 + [105],
                "High": [110] * 20 + [125],
                "Low": [95] * 20 + [104],
                "Close": [100] * 20 + [124],
                "Volume": [1_000_000] * 20 + [4_000_000],
            })

        with patch.object(web_app, "load_screener_universe", return_value=["FAST"]):
            with patch("data.price_fetcher.fetch_price_history", side_effect=fake_history):
                result = web_app.momentum_for_web(
                    mode="preopen",
                    use_relative_strength=True,
                )

        self.assertEqual([item["ticker"] for item in result["results"]], ["FAST"])
        self.assertIn("RS vs IHSG dilewati", result["warnings"][0])

    def test_sector_heat_adds_bonus_to_hot_sector(self):
        rows = [
            {"ticker": "AAA", "momentum": {"score": 50.0, "change_pct": 3.0, "signals": {}}},
            {"ticker": "BBB", "momentum": {"score": 50.0, "change_pct": 2.0, "signals": {}}},
            {"ticker": "CCC", "momentum": {"score": 50.0, "change_pct": 2.0, "signals": {}}},
        ]

        with patch("data.price_fetcher.fetch_quick_info", return_value={"sector": "Energy"}):
            web_app.apply_sector_heat(rows)

        self.assertGreater(rows[0]["momentum"]["score"], 50)
        self.assertEqual(rows[0]["sector"], "Energy")
        self.assertIn("sector_heat", rows[0]["momentum"]["signals"])

    def test_sector_heat_uses_session2_move_in_session2_mode(self):
        rows = [
            {
                "ticker": ticker,
                "momentum": {
                    "mode": "session2",
                    "score": 50.0,
                    "change_pct": -2.0,
                    "session2_pct": 2.0,
                    "signals": {},
                },
            }
            for ticker in ("AAA", "BBB", "CCC")
        ]

        with patch("data.price_fetcher.fetch_quick_info", return_value={"sector": "Energy"}):
            web_app.apply_sector_heat(rows)

        self.assertGreater(rows[0]["momentum"]["score"], 50)
        self.assertIn("sektor sesi 2 panas", rows[0]["momentum"]["signals"]["sector_heat"])

    def test_session2_ml_rerank_uses_existing_accurate_model(self):
        rows = [{
            "ticker": "FAST",
            "momentum": {"score": 50.0, "signals": {}},
        }]
        prediction = {"prob_naik": 80.0, "akurasi_test": 60.0}

        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory) / "random_forest"
            model_dir.mkdir()
            (model_dir / "FAST_rf.pkl").touch()
            with patch("analysis.ml_model.MODEL_ROOT", Path(directory)):
                with patch("analysis.ml_model.MLAnalyzer") as analyzer:
                    analyzer.return_value.prediksi_arah.return_value = prediction
                    covered = web_app.apply_ml_rerank(rows)

        self.assertEqual(covered, 1)
        self.assertEqual(rows[0]["momentum"]["score"], 56.0)
        self.assertEqual(rows[0]["ml_bonus"], 6.0)
        self.assertIn("RF naik 80%", rows[0]["momentum"]["signals"]["ml"])


if __name__ == "__main__":
    unittest.main()
