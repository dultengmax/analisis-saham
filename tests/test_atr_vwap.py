import unittest
import pandas as pd

from analysis.atr import run_atr
from analysis.vwap import run_vwap


class AtrVwapTestCase(unittest.TestCase):
    def test_run_atr_returns_expected_keys(self):
        df = pd.DataFrame(
            {
                "High": [110, 112, 111, 113, 115],
                "Low": [100, 101, 100, 103, 104],
                "Close": [105, 108, 107, 110, 112],
            }
        )

        result = run_atr(df)
        self.assertIn("atr", result)
        self.assertIn("atr_change_pct", result)

    def test_run_vwap_returns_expected_keys(self):
        df = pd.DataFrame(
            {
                "High": [110, 112, 111, 113, 115],
                "Low": [100, 101, 100, 103, 104],
                "Close": [105, 108, 107, 110, 112],
                "Volume": [100, 120, 130, 140, 150],
            }
        )

        result = run_vwap(df)
        self.assertIn("vwap", result)
        self.assertIn("price_vs_vwap_pct", result)


if __name__ == "__main__":
    unittest.main()
