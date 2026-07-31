"""Fibonacci sebagai konfirmasi support/resistance, bukan sinyal mandiri."""
import pandas as pd


RATIOS = {
    "23.6": 0.236,
    "38.2": 0.382,
    "50.0": 0.5,
    "61.8": 0.618,
    "78.6": 0.786,
}
CORE_LEVELS = ("38.2", "50.0", "61.8")


def evaluate_fibonacci(price_df: pd.DataFrame, lookback: int = 60) -> dict:
    if len(price_df) < 20:
        raise ValueError("Data kurang untuk Fibonacci.")

    window = price_df.tail(lookback)
    swing_window = window.iloc[:-1]
    high_pos = int(swing_window["High"].to_numpy().argmax())
    low_pos = int(swing_window["Low"].to_numpy().argmin())
    swing_high = float(swing_window["High"].iloc[high_pos])
    swing_low = float(swing_window["Low"].iloc[low_pos])
    span = swing_high - swing_low
    if span <= 0:
        raise ValueError("Rentang swing Fibonacci tidak valid.")

    trend = "UP" if low_pos < high_pos else "DOWN"
    levels = {
        name: (
            swing_high - span * ratio
            if trend == "UP"
            else swing_low + span * ratio
        )
        for name, ratio in RATIOS.items()
    }
    extensions = {
        "127.2": swing_high + span * 0.272 if trend == "UP" else swing_low - span * 0.272,
        "161.8": swing_high + span * 0.618 if trend == "UP" else swing_low - span * 0.618,
    }

    previous_close = window["Close"].shift(1)
    true_range = pd.concat(
        [
            window["High"] - window["Low"],
            (window["High"] - previous_close).abs(),
            (window["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = float(true_range.tail(14).mean())
    current = float(window["Close"].iloc[-1])
    previous = float(window["Close"].iloc[-2])
    nearest_name = min(CORE_LEVELS, key=lambda name: abs(current - levels[name]))
    nearest_price = levels[nearest_name]
    distance = abs(current - nearest_price)
    near_zone = bool(atr > 0 and distance <= atr * 0.5)
    bounce = bool(
        near_zone
        and (
            trend == "UP" and current >= nearest_price and current > previous
            or trend == "DOWN" and current <= nearest_price and current < previous
        )
    )
    beyond_61_8 = bool(
        current < levels["61.8"]
        if trend == "UP"
        else current > levels["61.8"]
    )
    breakout = bool(
        current > swing_high
        if trend == "UP"
        else current < swing_low
    )

    return {
        "trend": trend,
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "swing_high_at": str(swing_window.index[high_pos]),
        "swing_low_at": str(swing_window.index[low_pos]),
        "levels": {name: round(value, 2) for name, value in levels.items()},
        "extensions": {name: round(value, 2) for name, value in extensions.items()},
        "nearest_level": nearest_name,
        "nearest_price": round(nearest_price, 2),
        "distance_pct": round(distance / current * 100, 2) if current else None,
        "distance_atr": round(distance / atr, 2) if atr else None,
        "atr": round(atr, 2),
        "near_zone": near_zone,
        "bounce": bounce,
        "beyond_61_8": beyond_61_8,
        "breakout": breakout,
    }


def fibonacci_confirmation(
    fibonacci: dict,
    volume_confirmed: bool,
    above_vwap: bool | None = None,
) -> dict:
    confirmed = volume_confirmed and above_vwap is not False
    trend = fibonacci["trend"]
    bonus = 0
    signal = (
        f"Fib {fibonacci['nearest_level']} di {fibonacci['nearest_price']:,.0f}, "
        f"jarak {fibonacci['distance_atr'] or 0:.1f} ATR"
    )

    if trend == "UP" and fibonacci["bounce"] and confirmed:
        bonus = 8
        signal = f"bounce terkonfirmasi di Fib {fibonacci['nearest_level']} ({bonus:+d})"
    elif trend == "UP" and fibonacci["breakout"] and confirmed:
        bonus = 6
        signal = f"breakout swing high Fibonacci ({bonus:+d})"
    elif trend == "UP" and fibonacci["beyond_61_8"]:
        bonus = -8
        signal = f"struktur naik jatuh di bawah Fib 61.8 ({bonus:+d})"
    elif trend == "DOWN" and fibonacci["bounce"]:
        bonus = -6
        signal = f"tertolak resistance Fib {fibonacci['nearest_level']} ({bonus:+d})"
    elif trend == "DOWN" and fibonacci["breakout"]:
        bonus = -8
        signal = f"breakdown swing low Fibonacci ({bonus:+d})"
    elif trend == "DOWN" and fibonacci["beyond_61_8"] and confirmed:
        bonus = 4
        signal = f"downtrend melemah di atas Fib 61.8 ({bonus:+d})"

    return {"bonus": bonus, "signal": signal}
