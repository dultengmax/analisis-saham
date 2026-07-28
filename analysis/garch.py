"""
Modul GARCH sederhana untuk memperkirakan volatilitas dinamis dari return historis.
Metode ini cocok untuk menilai seberapa besar fluktuasi yang mungkin terjadi di masa depan.
"""
from typing import Dict, Any

import numpy as np
import pandas as pd


def run_garch(price_df: pd.DataFrame, horizon_days: int = 5) -> Dict[str, Any]:
    """
    Estimasi volatilitas jangka pendek menggunakan model GARCH(1,1) sederhana.

    Parameter
    ---------
    price_df : pd.DataFrame
        DataFrame dengan kolom Close.
    horizon_days : int
        Jumlah hari ke depan untuk forecast volatilitas.
    """
    if "Close" not in price_df.columns:
        raise ValueError("DataFrame harus memiliki kolom 'Close'.")

    closes = pd.to_numeric(price_df["Close"], errors="coerce").dropna()
    if len(closes) < 3:
        raise ValueError("Perlu minimal 3 titik data Close untuk GARCH.")

    returns = closes.pct_change().dropna()
    if returns.empty:
        raise ValueError("Tidak ada return historis yang bisa dihitung.")

    r = returns.to_numpy(dtype=float)
    residuals = r - np.mean(r)
    variance = np.var(residuals, ddof=1)

    if variance <= 0:
        variance = 1e-6

    alpha = 0.1
    beta = 0.8
    omega = 0.01 * variance
    sigma2 = variance

    for _ in range(len(r)):
        if len(r) > 0:
            eps = residuals[-1]
            sigma2 = omega + alpha * (eps ** 2) + beta * sigma2

    current_volatility = float(np.sqrt(sigma2))
    forecast_volatility = float(np.sqrt(omega + (alpha + beta) * sigma2))

    return {
        "forecast_volatility": round(forecast_volatility, 4),
        "current_volatility": round(current_volatility, 4),
        "alpha_plus_beta": round(alpha + beta, 3),
        "horizon_days": horizon_days,
    }
