import unittest

import pandas as pd

from analysis.liquidity import evaluate_liquidity


class LiquidityTestCase(unittest.TestCase):
    def test_evaluate_liquidity_scores_average_traded_value(self):
        df = pd.DataFrame(
            {
                "Close": [1000] * 20,
                "Volume": [10_000_000] * 20,
            }
        )

        result = evaluate_liquidity(df)

        self.assertEqual(result["score"], 80.0)
        self.assertEqual(result["status"], "LIKUID")
        self.assertEqual(result["avg_value_20d"], 10_000_000_000)


if __name__ == "__main__":
    unittest.main()
