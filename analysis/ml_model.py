"""Prediksi arah dan harga saham dengan Random Forest dan LSTM CPU."""
from pathlib import Path
import re

import joblib
import numpy as np
import pandas as pd
import ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import MinMaxScaler

from data.price_fetcher import fetch_price_history


WINDOW_LSTM = 60
HORIZON_LSTM = 7
EPOCH_LSTM = 20
BATCH_LSTM = 32
RF_ESTIMATORS = 200
TEST_SIZE = 0.2

FEATURES = [
    "RSI",
    "Stoch",
    "MACD",
    "MACD_signal",
    "EMA20",
    "EMA50",
    "BB_upper",
    "BB_lower",
    "BB_width",
    "Volume_change",
    "Volume_ratio",
    "Price_change",
    "High_Low_ratio",
]

MODEL_ROOT = Path(__file__).resolve().parents[1] / "models" / "ml"


class MLAnalyzer:
    def __init__(self, kode: str, price_df: pd.DataFrame | None = None):
        kode = kode.strip().upper().removesuffix(".JK")
        if not re.fullmatch(r"[A-Z0-9]{1,12}", kode):
            raise ValueError("Kode emiten ML tidak valid.")

        self.kode = kode
        self.df = (
            price_df.copy()
            if price_df is not None
            else fetch_price_history(kode, period="2y", interval="1d")
        )
        self.scaler = MinMaxScaler()
        self.model_rf_path = MODEL_ROOT / "random_forest" / f"{kode}_rf.pkl"
        self.model_lstm_path = MODEL_ROOT / "lstm" / f"{kode}_lstm.h5"
        self.scaler_path = MODEL_ROOT / "lstm" / f"{kode}_scaler.pkl"
        self._hitung_fitur()

    def _hitung_fitur(self) -> None:
        df = self.df.copy()
        close, high, low, volume = (
            df["Close"],
            df["High"],
            df["Low"],
            df["Volume"],
        )

        df["RSI"] = ta.momentum.RSIIndicator(close).rsi()
        df["Stoch"] = ta.momentum.StochasticOscillator(high, low, close).stoch()
        macd = ta.trend.MACD(close)
        df["MACD"] = macd.macd()
        df["MACD_signal"] = macd.macd_signal()
        df["EMA20"] = ta.trend.EMAIndicator(close, 20).ema_indicator()
        df["EMA50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()

        bands = ta.volatility.BollingerBands(close)
        df["BB_upper"] = bands.bollinger_hband()
        df["BB_lower"] = bands.bollinger_lband()
        df["BB_width"] = (df["BB_upper"] - df["BB_lower"]) / close

        df["Volume_change"] = volume.pct_change()
        df["Volume_ratio"] = volume / volume.rolling(20).mean()
        df["Price_change"] = close.pct_change()
        df["High_Low_ratio"] = (high - low) / close
        self.df = df.replace([np.inf, -np.inf], np.nan).dropna()

        if len(self.df) <= WINDOW_LSTM + 20:
            raise ValueError(
                f"Data {self.kode} kurang untuk ML ({len(self.df)} bar bersih)."
            )

    def _siapkan_data_klasifikasi(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        # Baris terakhir tidak memiliki harga besok, jadi tidak boleh diberi label.
        train = self.df.iloc[:-1]
        target = (
            self.df["Close"].shift(-1).iloc[:-1] > train["Close"]
        ).astype(int)
        return train[FEATURES].to_numpy(), target.to_numpy(), FEATURES.copy()

    def _siapkan_data_lstm(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        data = self.df[["Close"]].to_numpy()
        sequence_count = len(data) - WINDOW_LSTM
        split = int(sequence_count * (1 - TEST_SIZE))
        if split < 1 or sequence_count - split < 1:
            raise ValueError("Data tidak cukup untuk split train/test LSTM.")

        # Fit scaler hanya sampai akhir train sequence agar test tidak bocor.
        train_end = WINDOW_LSTM + split
        self.scaler.fit(data[:train_end])
        data_scaled = self.scaler.transform(data)
        X = np.array([
            data_scaled[i - WINDOW_LSTM:i, 0]
            for i in range(WINDOW_LSTM, len(data_scaled))
        ]).reshape(sequence_count, WINDOW_LSTM, 1)
        y = data_scaled[WINDOW_LSTM:, 0]
        return X, y, data_scaled

    def train_random_forest(self) -> dict:
        X, y, fitur = self._siapkan_data_klasifikasi()
        split = int(len(X) * (1 - TEST_SIZE))
        if split < 1 or len(X) - split < 1 or len(np.unique(y[:split])) < 2:
            raise ValueError("Data kelas tidak cukup untuk training Random Forest.")

        model = RandomForestClassifier(
            n_estimators=RF_ESTIMATORS,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )
        model.fit(X[:split], y[:split])
        akurasi = accuracy_score(y[split:], model.predict(X[split:]))
        payload = {
            "model": model,
            "fitur": fitur,
            "akurasi": round(akurasi * 100, 1),
            "trained_through": str(self.df.index[-1]),
        }
        self.model_rf_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(payload, self.model_rf_path)
        return payload

    def train_lstm(self) -> dict:
        from tensorflow.keras.callbacks import EarlyStopping
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.models import Sequential

        X, y, _ = self._siapkan_data_lstm()
        split = int(len(X) * (1 - TEST_SIZE))
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(WINDOW_LSTM, 1)),
            Dropout(0.2),
            LSTM(64),
            Dropout(0.2),
            Dense(32, activation="relu"),
            Dense(1),
        ])
        model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        model.fit(
            X_train,
            y_train,
            epochs=EPOCH_LSTM,
            batch_size=BATCH_LSTM,
            validation_data=(X_test, y_test),
            callbacks=[
                EarlyStopping(
                    monitor="val_loss",
                    patience=3,
                    restore_best_weights=True,
                )
            ],
            verbose=0,
        )
        loss, mae = model.evaluate(X_test, y_test, verbose=0)
        self.model_lstm_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(self.model_lstm_path)
        joblib.dump(self.scaler, self.scaler_path)
        return {
            "model": model,
            "mae": round(float(mae), 4),
            "loss": round(float(loss), 4),
        }

    def prediksi_arah(self) -> dict:
        payload = (
            joblib.load(self.model_rf_path)
            if self.model_rf_path.exists()
            else self.train_random_forest()
        )
        model = payload["model"] if isinstance(payload, dict) else payload
        latest = self.df[FEATURES].iloc[-1:].to_numpy()
        probabilities = dict(
            zip(model.classes_, model.predict_proba(latest)[0])
        )
        prob_naik = round(float(probabilities.get(1, 0)) * 100, 1)
        prob_turun = round(float(probabilities.get(0, 0)) * 100, 1)
        arah = "NAIK" if prob_naik >= prob_turun else "TURUN"
        return {
            "arah": arah,
            "probabilitas": max(prob_naik, prob_turun),
            "prob_naik": prob_naik,
            "prob_turun": prob_turun,
            "skor": prob_naik,
            "akurasi_test": payload.get("akurasi") if isinstance(payload, dict) else None,
            "model_arah": "Random Forest",
        }

    def prediksi_harga(self) -> dict:
        if self.model_lstm_path.exists() and self.scaler_path.exists():
            from tensorflow.keras.models import load_model

            model = load_model(self.model_lstm_path, compile=False)
            self.scaler = joblib.load(self.scaler_path)
        else:
            model = self.train_lstm()["model"]

        data_scaled = self.scaler.transform(self.df[["Close"]].to_numpy())
        current_window = data_scaled[-WINDOW_LSTM:].reshape(
            1, WINDOW_LSTM, 1
        )
        predictions = []
        for _ in range(HORIZON_LSTM):
            prediction = model.predict(current_window, verbose=0)
            predictions.append(float(prediction[0][0]))
            current_window = np.append(
                current_window[:, 1:, :],
                prediction.reshape(1, 1, 1),
                axis=1,
            )

        prices = self.scaler.inverse_transform(
            np.array(predictions).reshape(-1, 1)
        ).flatten()
        current_price = float(self.df["Close"].iloc[-1])
        per_hari = [
            {
                "hari": index,
                "harga": round(float(price), 0),
                "perubahan_pct": round(
                    ((float(price) / current_price) - 1) * 100, 2
                ),
            }
            for index, price in enumerate(prices, start=1)
        ]
        return {
            "harga_sekarang": round(current_price, 0),
            "harga_7hari": round(float(prices[-1]), 0),
            "per_hari": per_hari,
            "model_harga": "LSTM",
        }

    def prediksi(self) -> dict:
        try:
            arah = self.prediksi_arah()
        except Exception as exc:
            result = self._default_result()
            result["error"] = str(exc)
            return result

        try:
            harga = self.prediksi_harga()
            status = "READY"
            error = None
        except Exception as exc:
            harga = {
                "harga_sekarang": round(float(self.df["Close"].iloc[-1]), 0),
                "harga_7hari": 0,
                "per_hari": [],
            }
            status = "PARTIAL"
            error = str(exc)

        harga_arah = (
            "NAIK"
            if harga["per_hari"] and harga["per_hari"][0]["perubahan_pct"] > 0
            else "TURUN"
            if harga["per_hari"]
            else "UNKNOWN"
        )
        return {
            **arah,
            **harga,
            "konsensus": (
                "KONSISTEN"
                if harga_arah == arah["arah"]
                else "KONFLIK"
                if harga_arah != "UNKNOWN"
                else "UNKNOWN"
            ),
            "status": status,
            "error": error,
        }

    @staticmethod
    def _default_result() -> dict:
        return {
            "skor": 50.0,
            "arah": "UNKNOWN",
            "probabilitas": 50.0,
            "prob_naik": 50.0,
            "prob_turun": 50.0,
            "akurasi_test": None,
            "harga_7hari": 0,
            "per_hari": [],
            "harga_sekarang": 0,
            "konsensus": "UNKNOWN",
            "status": "ERROR",
        }
