"""
Backtest sederhana: mengukur seberapa akurat sinyal teknikal (RSI + MACD + trend)
kalau dipakai untuk keputusan beli/jual di masa lalu.

Metodologi (rule-based, disederhanakan untuk validasi cepat):
- BUY jika RSI < 40 dan MACD histogram baru berbalik positif dan harga > SMA50
- SELL/EXIT jika RSI > 70 atau MACD histogram berbalik negatif
- Hitung return tiap trade & win-rate keseluruhan
"""
import pandas as pd
from analysis.technical import add_indicators


def run_backtest(df: pd.DataFrame) -> dict:
    df = add_indicators(df).dropna().reset_index()
    position = None
    entry_price = 0
    trades = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        buy_signal = (
            row["rsi"] < 40
            and row["macd_hist"] > 0
            and prev["macd_hist"] <= 0
            and row["Close"] > row["sma_long"]
        )
        sell_signal = (
            row["rsi"] > 70
            or (row["macd_hist"] < 0 and prev["macd_hist"] >= 0)
        )

        if position is None and buy_signal:
            position = "long"
            entry_price = row["Close"]
            entry_date = row["Date"]
        elif position == "long" and sell_signal:
            exit_price = row["Close"]
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            trades.append({
                "entry_date": str(entry_date.date()),
                "exit_date": str(row["Date"].date()),
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
            position = None

    if not trades:
        return {"total_trades": 0, "win_rate": None, "avg_return_pct": None, "trades": []}

    wins = [t for t in trades if t["pnl_pct"] > 0]
    win_rate = round(len(wins) / len(trades) * 100, 1)
    avg_return = round(sum(t["pnl_pct"] for t in trades) / len(trades), 2)

    return {
        "total_trades": len(trades),
        "win_rate": win_rate,
        "avg_return_pct": avg_return,
        "trades": trades,
    }
