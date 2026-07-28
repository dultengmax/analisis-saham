"""
Modul VWAP (Volume Weighted Average Price) untuk trader intraday.
VWAP membantu melihat rata-rata harga yang tertimbang volume.
"""
from typing import Dict, Any

import pandas as pd


def run_vwap(price_df: pd.DataFrame) -> Dict[str, Any]:
    """Hitung VWAP dari data OHLCV."""
    if not {"High", "Low", "Close", "Volume"}.issubset(price_df.columns):
        raise ValueError("DataFrame harus memiliki kolom High, Low, Close, Volume.")

    df = price_df.copy()
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3.0
    vwap = (typical_price * df["Volume"]).cumsum() / df["Volume"].cumsum()

    if vwap.empty or pd.isna(vwap.iloc[-1]):
        raise ValueError("Tidak bisa menghitung VWAP dari data yang tersedia.")

    latest_price = float(df["Close"].iloc[-1])
    latest_vwap = float(vwap.iloc[-1])

    return {
        "vwap": round(latest_vwap, 4),
        "price_vs_vwap_pct": round(((latest_price - latest_vwap) / latest_vwap) * 100, 2) if latest_vwap else 0.0,
    }
