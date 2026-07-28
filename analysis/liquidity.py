"""Skor likuiditas saham dari harga dan volume historis."""


def evaluate_liquidity(price_df) -> dict:
    traded_value = (price_df["Close"] * price_df["Volume"]).tail(20)
    avg_value = float(traded_value.mean()) if not traded_value.empty else 0.0
    avg_volume = float(price_df["Volume"].tail(20).mean()) if not price_df.empty else 0.0

    if avg_value >= 20_000_000_000:
        score, status = 100.0, "SANGAT LIKUID"
    elif avg_value >= 5_000_000_000:
        score, status = 80.0, "LIKUID"
    elif avg_value >= 1_000_000_000:
        score, status = 60.0, "CUKUP LIKUID"
    elif avg_value >= 250_000_000:
        score, status = 40.0, "KURANG LIKUID"
    else:
        score, status = 20.0, "TIDAK LIKUID"

    return {
        "score": score,
        "status": status,
        "avg_value_20d": round(avg_value, 0),
        "avg_volume_20d": round(avg_volume, 0),
    }
