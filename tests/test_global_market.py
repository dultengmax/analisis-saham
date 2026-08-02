import unittest
from unittest.mock import patch

import pandas as pd

from analysis.global_market import fetch_global_market


class GlobalMarketTestCase(unittest.TestCase):
    @patch("analysis.global_market.fetch_price_history")
    def test_fetch_global_market_scores_inverse_assets(self, fetch_price):
        closes = {
            "A": [100, 101],
            "B": [100, 102],
            "VIX": [20, 19],
        }
        fetch_price.side_effect = lambda symbol, **_: pd.DataFrame({"Close": closes[symbol]})

        result = fetch_global_market([
            {"symbol": "A", "name": "Market A", "region": "US"},
            {"symbol": "B", "name": "Market B", "region": "Asia"},
            {"symbol": "VIX", "name": "VIX", "region": "Risk", "inverse": True},
        ])

        self.assertEqual(result["status"], "RISK ON")
        self.assertEqual(len(result["markets"]), 3)
        self.assertGreater(result["score"], 50)
        self.assertGreater(result["markets"][2]["impact"], 0)


if __name__ == "__main__":
    unittest.main()
