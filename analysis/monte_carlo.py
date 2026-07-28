"""
Simulasi Monte Carlo sederhana untuk memperkirakan probabilitas return saham.
Digunakan sebagai tambahan analisa probabilistik berdasarkan return historis.
"""
import math
from typing import Dict, Any

import numpy as np
import pandas as pd


def _build_ascii_histogram(values: np.ndarray, bins: int = 8, width: int = 40) -> str:
    """Buat histogram ASCII sederhana dari nilai numerik."""
    if len(values) == 0:
        return "(tidak ada data)"

    counts, edges = np.histogram(values, bins=bins)
    max_count = max(counts) if counts.size else 1
    lines = []
    for i in range(bins):
        left = edges[i]
        right = edges[i + 1]
        bar_len = int(round((counts[i] / max_count) * width)) if max_count else 0
        bar = "#" * bar_len if bar_len > 0 else "-"
        lines.append(f"{left:>7.1f}..{right:>7.1f} | {bar}")
    return "\n".join(lines)


def _build_ascii_trend(values: np.ndarray, width: int = 40, height: int = 8) -> str:
    """Buat garis tren ASCII sederhana dari deret nilai."""
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return "(cukup data)"

    min_val = float(values.min())
    max_val = float(values.max())
    if np.isclose(min_val, max_val):
        max_val = min_val + 1.0

    scaled = (values - min_val) / (max_val - min_val)
    rows = []
    for y in range(height, -1, -1):
        row = []
        for x in range(len(values)):
            pos = int(round(scaled[x] * height))
            row.append("*" if pos == y else " ")
        rows.append("".join(row))
    return "\n".join(rows)


def run_monte_carlo(
    price_df: pd.DataFrame,
    simulations: int = 1000,
    horizon_days: int = 30,
    target_return_pct: float = 10.0,
) -> Dict[str, Any]:
    """
    Jalankan simulasi Monte Carlo berdasarkan return harian historis.

    Parameters
    ----------
    price_df : pd.DataFrame
        DataFrame dengan kolom Close.
    simulations : int
        Jumlah simulasi yang dijalankan.
    horizon_days : int
        Jumlah hari ke depan yang disimulasikan.
    target_return_pct : float
        Target return persen yang dipakai untuk menghitung probabilitas pencapaian.

    Returns
    -------
    dict
        Berisi probabilitas return positif, probabilitas mencapai target,
        expected return, dan harga terminal rata-rata.
    """
    if "Close" not in price_df.columns:
        raise ValueError("DataFrame harus memiliki kolom 'Close'.")

    closes = pd.to_numeric(price_df["Close"], errors="coerce").dropna()
    if len(closes) < 2:
        raise ValueError("Perlu minimal 2 titik data Close untuk Monte Carlo.")

    returns = closes.pct_change().dropna()
    if returns.empty:
        raise ValueError("Tidak ada return historis yang bisa dihitung.")

    mu = float(returns.mean())
    sigma = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    if sigma <= 0:
        sigma = 0.01

    last_price = float(closes.iloc[-1])
    rng = np.random.default_rng(42)

    terminal_prices = []
    for _ in range(simulations):
        path = [last_price]
        for _ in range(horizon_days):
            drift = mu - 0.5 * sigma * sigma
            shock = rng.normal(loc=0.0, scale=sigma)
            next_price = path[-1] * math.exp(drift + shock)
            path.append(next_price)
        terminal_prices.append(path[-1])

    terminal_prices = np.array(terminal_prices, dtype=float)
    final_returns = (terminal_prices / last_price - 1.0) * 100.0

    probability_positive_return = float(np.mean(final_returns > 0.0))
    probability_target_return = float(np.mean(final_returns >= target_return_pct))
    expected_return_pct = float(np.mean(final_returns))
    expected_terminal_price = float(np.mean(terminal_prices))

    return {
        "probability_positive_return": round(probability_positive_return, 3),
        "probability_target_return": round(probability_target_return, 3),
        "expected_return_pct": round(expected_return_pct, 2),
        "expected_terminal_price": round(expected_terminal_price, 2),
        "simulations": simulations,
        "horizon_days": horizon_days,
        "target_return_pct": target_return_pct,
        "return_histogram": _build_ascii_histogram(final_returns),
        "price_trend": _build_ascii_trend(closes.tail(30).to_numpy()),
    }
