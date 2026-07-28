import unittest
import pandas as pd

from analysis.bootstrapping import run_bootstrapping


class BootstrappingTestCase(unittest.TestCase):
    def test_run_bootstrapping_returns_expected_keys(self):
        df = pd.DataFrame(
            {
                "Close": [100, 102, 101, 103, 105, 104, 106, 108, 107, 109],
            }
        )

        result = run_bootstrapping(df, simulations=50, horizon_days=5, target_return_pct=5.0)

        self.assertIn("probability_positive_return", result)
        self.assertIn("probability_target_return", result)
        self.assertIn("expected_return_pct", result)
        self.assertIn("expected_terminal_price", result)
        self.assertGreaterEqual(result["probability_positive_return"], 0.0)
        self.assertLessEqual(result["probability_positive_return"], 1.0)
        self.assertGreaterEqual(result["probability_target_return"], 0.0)
        self.assertLessEqual(result["probability_target_return"], 1.0)


if __name__ == "__main__":
    unittest.main()
