"""
Analisa teknikal saham: menghitung indikator dan menghasilkan skor 0-100
plus sinyal per indikator.
"""
import pandas as pd
import ta

from analysis.fibonacci import evaluate_fibonacci, fibonacci_confirmation
from config import (
    SMA_SHORT, SMA_LONG, EMA_SHORT, EMA_LONG, RSI_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL, BB_PERIOD, STOCH_PERIOD, ADX_PERIOD,
    RSI_OVERSOLD, RSI_OVERBOUGHT,
)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan seluruh kolom indikator teknikal ke DataFrame OHLCV."""
    df = df.copy()
    close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"]

    # Trend
    df["sma_short"] = ta.trend.sma_indicator(close, window=SMA_SHORT)
    df["sma_long"] = ta.trend.sma_indicator(close, window=SMA_LONG)
    df["ema_short"] = ta.trend.ema_indicator(close, window=EMA_SHORT)
    df["ema_long"] = ta.trend.ema_indicator(close, window=EMA_LONG)
    df["adx"] = ta.trend.adx(high, low, close, window=ADX_PERIOD)

    # Momentum
    df["rsi"] = ta.momentum.rsi(close, window=RSI_PERIOD)
    macd = ta.trend.MACD(close, window_fast=MACD_FAST, window_slow=MACD_SLOW,
                          window_sign=MACD_SIGNAL)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    stoch = ta.momentum.StochasticOscillator(high, low, close, window=STOCH_PERIOD)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # Volatility
    bb = ta.volatility.BollingerBands(close, window=BB_PERIOD)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pct"] = bb.bollinger_pband()  # posisi harga relatif terhadap band (0-1)

    # Volume
    df["obv"] = ta.volume.on_balance_volume(close, volume)
    df["vol_sma20"] = volume.rolling(window=20).mean()

    return df


def evaluate_technical(df: pd.DataFrame) -> dict:
    """
    Evaluasi kondisi teknikal terkini berdasarkan baris terakhir data.
    Return dict berisi skor 0-100 dan breakdown sinyal per indikator.
    """
    df = add_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    signals = {}
    score = 0
    max_score = 0

    # 1. Trend: harga vs SMA & golden/death cross
    max_score += 20
    if last["Close"] > last["sma_long"] and last["sma_short"] > last["sma_long"]:
        signals["trend"] = "bullish (harga & SMA20 di atas SMA50)"
        score += 20
    elif last["Close"] < last["sma_long"] and last["sma_short"] < last["sma_long"]:
        signals["trend"] = "bearish (harga & SMA20 di bawah SMA50)"
        score += 0
    else:
        signals["trend"] = "sideways/mixed"
        score += 10

    # 2. MACD crossover
    max_score += 20
    if last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
        signals["macd"] = "baru golden cross (bullish momentum)"
        score += 20
    elif last["macd"] > last["macd_signal"]:
        signals["macd"] = "bullish (di atas signal line)"
        score += 15
    elif last["macd"] < last["macd_signal"] and prev["macd"] >= prev["macd_signal"]:
        signals["macd"] = "baru death cross (bearish momentum)"
        score += 0
    else:
        signals["macd"] = "bearish (di bawah signal line)"
        score += 5

    # 3. RSI
    max_score += 20
    rsi_val = last["rsi"]
    if rsi_val <= RSI_OVERSOLD:
        signals["rsi"] = f"oversold ({rsi_val:.1f}) - potensi rebound"
        score += 18
    elif rsi_val >= RSI_OVERBOUGHT:
        signals["rsi"] = f"overbought ({rsi_val:.1f}) - waspada koreksi"
        score += 6
    else:
        signals["rsi"] = f"netral ({rsi_val:.1f})"
        score += 12

    # 4. Stochastic
    max_score += 15
    if last["stoch_k"] < 20 and last["stoch_k"] > last["stoch_d"]:
        signals["stochastic"] = "oversold & mulai naik - sinyal beli"
        score += 15
    elif last["stoch_k"] > 80 and last["stoch_k"] < last["stoch_d"]:
        signals["stochastic"] = "overbought & mulai turun - sinyal jual"
        score += 3
    else:
        signals["stochastic"] = "netral"
        score += 8

    # 5. Bollinger Band position
    max_score += 10
    bb_pct = last["bb_pct"]
    if bb_pct <= 0.1:
        signals["bollinger"] = "harga dekat lower band - potensi undervalued jangka pendek"
        score += 9
    elif bb_pct >= 0.9:
        signals["bollinger"] = "harga dekat upper band - potensi overbought"
        score += 3
    else:
        signals["bollinger"] = "harga di tengah band - normal"
        score += 6

    # 6. Volume confirmation
    max_score += 15
    if last["Volume"] > last["vol_sma20"] * 1.5 and last["Close"] > prev["Close"]:
        signals["volume"] = "volume tinggi + harga naik - konfirmasi bullish kuat"
        score += 15
    elif last["Volume"] > last["vol_sma20"] * 1.5 and last["Close"] < prev["Close"]:
        signals["volume"] = "volume tinggi + harga turun - tekanan jual kuat"
        score += 2
    else:
        signals["volume"] = "volume normal"
        score += 8

    normalized_score = round((score / max_score) * 100, 1)
    try:
        fibonacci = evaluate_fibonacci(df)
        fib_confirmation = fibonacci_confirmation(
            fibonacci,
            volume_confirmed=bool(
                last["Volume"] > last["vol_sma20"] * 1.3
                and last["Close"] > prev["Close"]
            ),
        )
        fibonacci.update(fib_confirmation)
        signals["fibonacci"] = fib_confirmation["signal"]
        normalized_score = min(
            100.0,
            max(0.0, round(normalized_score + fib_confirmation["bonus"], 1)),
        )
    except ValueError as exc:
        fibonacci = None
        signals["fibonacci"] = str(exc)

    return {
        "technical_score": normalized_score,
        "signals": signals,
        "last_close": round(float(last["Close"]), 2),
        "rsi": round(float(rsi_val), 1),
        "macd_hist": round(float(last["macd_hist"]), 4),
        "fibonacci": fibonacci,
        "raw_df": df,
    }
