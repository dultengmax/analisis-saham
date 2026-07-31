import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.ml_model import FEATURES, MLAnalyzer


def synthetic_prices(outlier_tail: bool = False) -> pd.DataFrame:
    size = 320
    step = np.arange(size)
    close = 100 + step * 0.08 + np.sin(step / 3) * 3
    if outlier_tail:
        close[-20:] *= 3
    return pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.5,
            "Low": close - 1.5,
            "Close": close,
            "Volume": 1_000_000 + (step % 17) * 40_000,
        },
        index=pd.date_range("2025-01-01", periods=size, freq="B"),
    )


class MLAnalyzerTestCase(unittest.TestCase):
    def test_features_rf_and_latest_unlabeled_row(self):
        analyzer = MLAnalyzer("TEST", synthetic_prices())
        X, y, features = analyzer._siapkan_data_klasifikasi()

        self.assertEqual(features, FEATURES)
        self.assertEqual(len(X), len(analyzer.df) - 1)
        self.assertEqual(len(y), len(X))

        with tempfile.TemporaryDirectory() as directory:
            analyzer.model_rf_path = Path(directory) / "TEST_rf.pkl"
            training = analyzer.train_random_forest()
            prediction = analyzer.prediksi_arah()

        self.assertTrue(0 <= training["akurasi"] <= 100)
        self.assertIn(prediction["arah"], {"NAIK", "TURUN"})
        self.assertEqual(prediction["model_arah"], "Random Forest")
        self.assertAlmostEqual(
            prediction["prob_naik"] + prediction["prob_turun"],
            100,
            places=1,
        )

    def test_lstm_scaler_is_fit_on_training_period_only(self):
        analyzer = MLAnalyzer("TEST", synthetic_prices(outlier_tail=True))

        X, y, scaled = analyzer._siapkan_data_lstm()

        self.assertEqual(X.shape[1:], (60, 1))
        self.assertEqual(len(X), len(y))
        self.assertGreater(float(scaled[-1, 0]), 1.0)


if __name__ == "__main__":
    unittest.main()
