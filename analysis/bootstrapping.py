"""
Modul Bootstrapping sederhana untuk estimasi distribusi return saham.
Metode ini resampling return historis secara acak untuk menghasilkan skenario probabilistik.
"""
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


def run_bootstrapping(
    price_df: pd.DataFrame,
    simulations: int = 1000,
    horizon_days: int = 30,
    target_return_pct: float = 10.0,
) -> Dict[str, Any]:
    """
    Jalankan bootstrapping berdasarkan return harian historis.

    Metode ini mengambil sampel acak dari return historis yang ada dan
    menghitung return akumulasi untuk setiap simulasi.
    """
    if "Close" not in price_df.columns:
        raise ValueError("DataFrame harus memiliki kolom 'Close'.")

    closes = pd.to_numeric(price_df["Close"], errors="coerce").dropna()
    if len(closes) < 2:
        raise ValueError("Perlu minimal 2 titik data Close untuk bootstrapping.")

    returns = closes.pct_change().dropna()
    if returns.empty:
        raise ValueError("Tidak ada return historis yang bisa dihitung.")

    last_price = float(closes.iloc[-1])
    rng = np.random.default_rng(42)
    sampled_returns = returns.to_numpy()

    terminal_prices = []
    for _ in range(simulations):
        path = last_price
        for _ in range(horizon_days):
            sampled_return = rng.choice(sampled_returns)
            path *= (1 + sampled_return)
        terminal_prices.append(path)

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
    }
