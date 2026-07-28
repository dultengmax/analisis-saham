import unittest
import pandas as pd

from analysis.garch import run_garch


class GarchTestCase(unittest.TestCase):
    def test_run_garch_returns_expected_keys(self):
        df = pd.DataFrame(
            {
                "Close": [100, 102, 101, 103, 105, 104, 106, 108, 107, 109],
            }
        )

        result = run_garch(df, horizon_days=5)

        self.assertIn("forecast_volatility", result)
        self.assertIn("current_volatility", result)
        self.assertIn("alpha_plus_beta", result)
        self.assertGreaterEqual(result["forecast_volatility"], 0.0)
        self.assertGreaterEqual(result["current_volatility"], 0.0)


if __name__ == "__main__":
    unittest.main()
