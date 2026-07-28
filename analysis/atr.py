"""
Modul ATR (Average True Range) untuk mengukur volatilitas harian.
Cocok untuk trader harian karena menunjukkan seberapa besar rentang pergerakan harga.
"""
from typing import Dict, Any

import pandas as pd


def run_atr(price_df: pd.DataFrame, period: int = 14) -> Dict[str, Any]:
    """Hitung ATR berdasarkan data OHLCV."""
    if not {"High", "Low", "Close"}.issubset(price_df.columns):
        raise ValueError("DataFrame harus memiliki kolom High, Low, Close.")

    df = price_df.copy()
    df["prev_close"] = df["Close"].shift(1)
    df["tr1"] = df["High"] - df["Low"]
    df["tr2"] = (df["High"] - df["prev_close"]).abs()
    df["tr3"] = (df["Low"] - df["prev_close"]).abs()
    df["true_range"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    atr = df["true_range"].rolling(window=period, min_periods=1).mean().dropna()

    if atr.empty:
        raise ValueError("Tidak bisa menghitung ATR dari data yang tersedia.")

    latest_atr = float(atr.iloc[-1])
    prev_atr = float(atr.iloc[-2]) if len(atr) > 1 else latest_atr

    return {
        "atr": round(latest_atr, 4),
        "atr_change_pct": round(((latest_atr - prev_atr) / prev_atr) * 100, 2) if prev_atr else 0.0,
        "period": period,
    }
