"""Screener momentum untuk kandidat top gainer."""


def evaluate_session2_momentum(price_df) -> dict:
    if len(price_df) < 12:
        raise ValueError("Data intraday kurang.")

    day = price_df[price_df.index.date == price_df.index[-1].date()]
    if len(day) < 6:
        raise ValueError("Data intraday hari terakhir kurang.")

    last = day.iloc[-1]
    first = day.iloc[0]
    session2 = day[(day.index.hour > 6) | ((day.index.hour == 6) & (day.index.minute >= 30))]
    pivot = session2.iloc[0] if not session2.empty else day.iloc[max(0, len(day) - 12)]

    change_pct = ((last["Close"] / first["Open"]) - 1) * 100
    session2_pct = ((last["Close"] / pivot["Open"]) - 1) * 100
    session1_pct = ((pivot["Open"] / first["Open"]) - 1) * 100
    avg_volume = price_df.iloc[:-len(day)]["Volume"].tail(60).mean()
    volume_ratio = last["Volume"] / avg_volume if avg_volume else 0
    value_today = float((day["Close"] * day["Volume"]).sum())
    day_range = day["High"].max() - day["Low"].min()
    close_position = (last["Close"] - day["Low"].min()) / day_range if day_range else 0

    score = 0
    signals = {}
    if session2_pct >= 3:
        score += 30
        signals["session2"] = f"sesi 2 kuat {session2_pct:.1f}%"
    elif session2_pct >= 1:
        score += 20
        signals["session2"] = f"sesi 2 mulai dorong {session2_pct:.1f}%"
    elif session2_pct > 0:
        score += 10
        signals["session2"] = f"sesi 2 hijau tipis {session2_pct:.1f}%"
    else:
        signals["session2"] = f"sesi 2 belum kuat {session2_pct:.1f}%"

    if session1_pct >= 8:
        score -= 18
        signals["session1"] = f"sesi 1 sudah top gainer {session1_pct:.1f}%"
    elif session1_pct >= 5:
        score -= 8
        signals["session1"] = f"sesi 1 sudah naik tinggi {session1_pct:.1f}%"
    else:
        score += 12
        signals["session1"] = f"sesi 1 belum terlalu naik {session1_pct:.1f}%"

    if 1 <= change_pct <= 7:
        score += 18
        signals["price"] = f"ruang naik masih sehat {change_pct:.1f}%"
    elif change_pct > 7:
        score += 4
        signals["price"] = f"chaser risk {change_pct:.1f}%"
    elif change_pct > 0:
        score += 8
        signals["price"] = f"hari ini hijau {change_pct:.1f}%"
    else:
        signals["price"] = f"hari ini merah {change_pct:.1f}%"

    if volume_ratio >= 3:
        score += 24
        signals["volume"] = f"volume bar terakhir {volume_ratio:.1f}x"
    elif volume_ratio >= 1.5:
        score += 14
        signals["volume"] = f"volume bar terakhir {volume_ratio:.1f}x"
    else:
        signals["volume"] = f"volume bar terakhir {volume_ratio:.1f}x"

    if close_position >= 0.8:
        score += 16
        signals["close"] = "harga dekat high hari ini"
    elif close_position >= 0.6:
        score += 8
        signals["close"] = "harga cukup dekat high"
    else:
        signals["close"] = "harga belum dekat high"

    if value_today >= 5_000_000_000:
        score += 10
        signals["value"] = "value intraday kuat"
    elif value_today >= 1_000_000_000:
        score += 6
        signals["value"] = "value intraday cukup"
    elif value_today >= 250_000_000:
        score += 3
        signals["value"] = "value intraday tipis"
    else:
        signals["value"] = "value intraday terlalu kecil"

    return {
        "score": min(float(score), 100.0),
        "mode": "session2",
        "status": "KUAT" if score >= 70 else "MENARIK" if score >= 45 else "LEMAH",
        "change_pct": round(float(change_pct), 2),
        "session1_pct": round(float(session1_pct), 2),
        "session2_pct": round(float(session2_pct), 2),
        "volume_ratio": round(float(volume_ratio), 2),
        "value_today": round(value_today, 0),
        "close_position": round(float(close_position), 2),
        "breakout_20d": False,
        "signals": signals,
    }


def _pct_change(series, days: int) -> float:
    if len(series) <= days:
        return 0.0
    return ((series.iloc[-1] / series.iloc[-1 - days]) - 1) * 100


def _accumulation_score(price_df) -> tuple[int, str]:
    recent = price_df.tail(5)
    close_up_days = int((recent["Close"].diff().dropna() > 0).sum())
    volume_up_days = int((recent["Volume"].diff().dropna() > 0).sum())
    if close_up_days >= 3 and volume_up_days >= 3:
        return 16, "akumulasi 5D kuat: close dan volume naik bertahap"
    if close_up_days >= 3:
        return 10, "close 5D naik bertahap"
    if volume_up_days >= 3:
        return 6, "volume 5D naik bertahap"
    return 0, "belum ada akumulasi 5D jelas"


def evaluate_daily_momentum(
    price_df,
    mode: str = "intraday",
    ihsg_df=None,
    use_relative_strength: bool = False,
    use_accumulation: bool = False,
) -> dict:
    if len(price_df) < 21:
        raise ValueError("Data harga kurang dari 21 hari.")

    last = price_df.iloc[-1]
    prev = price_df.iloc[-2]
    prior = price_df.iloc[-21:-1]

    change_pct = ((last["Close"] / prev["Close"]) - 1) * 100
    avg_volume = prior["Volume"].mean()
    volume_ratio = last["Volume"] / avg_volume if avg_volume else 0
    value_today = float(last["Close"] * last["Volume"])
    day_range = last["High"] - last["Low"]
    close_position = (last["Close"] - last["Low"]) / day_range if day_range else 0
    breakout_20d = bool(last["Close"] >= prior["High"].max())

    score = 0
    signals = {}
    preopen = mode == "preopen"

    if preopen and 1 <= change_pct <= 8:
        score += 28
        signals["price"] = f"setup sehat {change_pct:.1f}%"
    elif preopen and change_pct > 8:
        score += 14
        signals["price"] = f"sudah naik tinggi {change_pct:.1f}%"
    elif change_pct >= 10:
        score += 35
        signals["price"] = f"naik kuat {change_pct:.1f}%"
    elif change_pct >= 5:
        score += 28
        signals["price"] = f"naik {change_pct:.1f}%"
    elif change_pct >= 2:
        score += 18
        signals["price"] = f"mulai bergerak {change_pct:.1f}%"
    elif change_pct > 0:
        score += 8
        signals["price"] = f"hijau tipis {change_pct:.1f}%"
    else:
        signals["price"] = f"belum momentum ({change_pct:.1f}%)"

    if volume_ratio >= 3:
        score += 30 if preopen else 25
        signals["volume"] = f"volume spike {volume_ratio:.1f}x"
    elif volume_ratio >= 2:
        score += 24 if preopen else 20
        signals["volume"] = f"volume naik {volume_ratio:.1f}x"
    elif volume_ratio >= 1.3:
        score += 12
        signals["volume"] = f"volume di atas rata-rata {volume_ratio:.1f}x"
    else:
        signals["volume"] = f"volume biasa {volume_ratio:.1f}x"

    if breakout_20d:
        score += 24 if preopen else 20
        signals["breakout"] = "close breakout high 20 hari"
    else:
        signals["breakout"] = "belum breakout 20 hari"

    if close_position >= 0.8:
        score += 18 if preopen else 10
        signals["close"] = "tutup dekat high"
    elif close_position >= 0.6:
        score += 10 if preopen else 6
        signals["close"] = "tutup cukup kuat"
    else:
        signals["close"] = "tutup belum kuat"

    if value_today >= 5_000_000_000:
        score += 10
        signals["value"] = "value transaksi kuat"
    elif value_today >= 1_000_000_000:
        score += 6
        signals["value"] = "value transaksi cukup"
    elif value_today >= 250_000_000:
        score += 3
        signals["value"] = "value transaksi tipis"
    else:
        signals["value"] = "value transaksi terlalu kecil"

    relative_strength = None
    if preopen and use_relative_strength and ihsg_df is not None and len(ihsg_df) >= 6:
        stock_5d = _pct_change(price_df["Close"], 5)
        ihsg_5d = _pct_change(ihsg_df["Close"], 5)
        relative_strength = stock_5d - ihsg_5d
        if ihsg_5d < 0 and stock_5d > 0:
            score += 18
            signals["relative_strength"] = f"naik saat IHSG lemah ({relative_strength:.1f} pp)"
        elif relative_strength >= 3:
            score += 12
            signals["relative_strength"] = f"unggul vs IHSG {relative_strength:.1f} pp"
        elif relative_strength <= -3:
            score -= 8
            signals["relative_strength"] = f"kalah vs IHSG {relative_strength:.1f} pp"
        else:
            signals["relative_strength"] = f"sejalan IHSG {relative_strength:.1f} pp"

    accumulation_score = 0
    if preopen and use_accumulation:
        accumulation_score, signals["accumulation"] = _accumulation_score(price_df)
        score += accumulation_score

    return {
        "score": min(float(score), 100.0),
        "mode": mode,
        "status": "KUAT" if score >= 70 else "MENARIK" if score >= 45 else "LEMAH",
        "change_pct": round(float(change_pct), 2),
        "volume_ratio": round(float(volume_ratio), 2),
        "value_today": round(value_today, 0),
        "close_position": round(float(close_position), 2),
        "breakout_20d": breakout_20d,
        "relative_strength": None if relative_strength is None else round(float(relative_strength), 2),
        "accumulation_score": accumulation_score,
        "signals": signals,
    }
