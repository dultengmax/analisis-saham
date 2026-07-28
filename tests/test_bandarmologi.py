import json
import unittest

import pandas as pd

from analysis.bandarmologi import BandarmologiAnalyzer


def sample_prices() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=25, freq="D")
    df = pd.DataFrame(
        {
            "Open": [100.0] * 25,
            "High": [102.0] * 25,
            "Low": [99.0] * 25,
            "Close": [101.0] * 25,
            "Volume": [1000] * 25,
        },
        index=index,
    )
    for row in (-2, -1):
        df.iloc[row] = [100.0, 101.0, 95.0, 101.0, 4000]
    return df


class BandarmologiAnalyzerTestCase(unittest.TestCase):
    def test_detects_recent_accumulation_and_returns_complete_result(self):
        result = BandarmologiAnalyzer("TEST", sample_prices()).analisis()

        self.assertEqual(result["fase"], "AKUMULASI")
        self.assertEqual(len(result["akumulasi_3hari"]), 2)
        self.assertEqual(result["distribusi_3hari"], [])
        self.assertLessEqual(result["skor"], 100)
        self.assertGreaterEqual(result["skor"], 0)
        self.assertIn(result["obv"]["obv_trend"], {"naik", "turun"})
        self.assertLessEqual(result["mfi"]["mfi"], 100)
        json.dumps(result)

    def test_invalid_data_returns_error_result(self):
        analyzer = BandarmologiAnalyzer("TEST", pd.DataFrame({"Close": [100]}))

        result = analyzer.analisis()

        self.assertEqual(result["skor"], 50.0)
        self.assertEqual(result["fase"], "ERROR")
        self.assertEqual(result["akumulasi_3hari"], [])

    def test_detects_recent_distribution(self):
        df = sample_prices()
        for row in (-2, -1):
            df.iloc[row] = [101.0, 106.0, 100.0, 100.0, 4000]

        result = BandarmologiAnalyzer("TEST", df).analisis()

        self.assertEqual(result["fase"], "DISTRIBUSI")
        self.assertEqual(len(result["distribusi_3hari"]), 2)
        self.assertEqual(result["akumulasi_3hari"], [])


if __name__ == "__main__":
    unittest.main()
