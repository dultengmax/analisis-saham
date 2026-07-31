import unittest

import pandas as pd

from analysis.fibonacci import evaluate_fibonacci, fibonacci_confirmation


class FibonacciTestCase(unittest.TestCase):
    def test_uptrend_levels_and_confirmed_bounce(self):
        size = 60
        close = [100 + index for index in range(size)]
        df = pd.DataFrame({
            "Open": close,
            "High": [value + 2 for value in close],
            "Low": [value - 2 for value in close],
            "Close": close,
            "Volume": [1_000_000] * size,
        })
        df.loc[size - 2, "Close"] = 136
        df.loc[size - 1, "Close"] = 139

        result = evaluate_fibonacci(df)
        confirmation = fibonacci_confirmation(
            result,
            volume_confirmed=True,
            above_vwap=True,
        )

        self.assertEqual(result["trend"], "UP")
        self.assertEqual(result["nearest_level"], "38.2")
        self.assertTrue(result["bounce"])
        self.assertEqual(confirmation["bonus"], 8)


if __name__ == "__main__":
    unittest.main()
