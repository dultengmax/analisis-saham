"""Screener momentum untuk kandidat top gainer."""
from datetime import timedelta
from statistics import median

from analysis.fibonacci import evaluate_fibonacci, fibonacci_confirmation
from analysis.vwap import run_vwap


def _session2_start(timestamp):
    hour = 14 if timestamp.weekday() == 4 else 13
    return timestamp.normalize() + timedelta(hours=hour, minutes=0 if hour == 14 else 30)


def _morning_start(timestamp):
    return timestamp.normalize() + timedelta(hours=9)


def _intraday_jakarta(price_df):
    price_df = price_df.copy()
    if price_df.index.tz is None:
        price_df.index = price_df.index.tz_localize("UTC")
    price_df.index = price_df.index.tz_convert("Asia/Jakarta")
    return price_df


def _apply_fibonacci(score, signals, price_df, volume_confirmed, above_vwap=None):
    try:
        fibonacci = evaluate_fibonacci(price_df)
    except ValueError as exc:
        signals["fibonacci"] = str(exc)
        return score, None

    confirmation = fibonacci_confirmation(fibonacci, volume_confirmed, above_vwap)
    fibonacci.update(confirmation)
    signals["fibonacci"] = confirmation["signal"]
    return score + confirmation["bonus"], fibonacci


def _time_volume_ratio(price_df, day, session_start, start_for_day) -> tuple:
    slot_finish = session_start + timedelta(minutes=15)
    complete = day.index[-1] >= slot_finish
    slot_end = min(day.index[-1], slot_finish)
    current_slot = day[
        (day.index >= session_start)
        & ((day.index < slot_finish) if complete else (day.index <= slot_end))
    ]
    if current_slot.empty:
        return None, 0.0, 0.0, 0

    elapsed = slot_end - session_start
    historical = []
    prior = price_df[price_df.index.date < day.index[-1].date()]
    for _, group in prior.groupby(prior.index.date):
        start = start_for_day(group.index[0])
        end = start + elapsed
        slot = group[
            (group.index >= start)
            & ((group.index < end) if complete else (group.index <= end))
        ]
        if not slot.empty:
            historical.append(float(slot["Volume"].sum()))

    historical = historical[-20:]
    baseline = median(historical) if historical else 0.0
    current = float(current_slot["Volume"].sum())
    ratio = current / baseline if baseline else None
    return ratio, current, baseline, len(historical)


def evaluate_morning_momentum(price_df) -> dict:
    if len(price_df) < 12:
        raise ValueError("Data intraday kurang.")

    price_df = _intraday_jakarta(price_df)
    day = price_df[price_df.index.date == price_df.index[-1].date()]
    start = _morning_start(day.index[-1])
    range_end = start + timedelta(minutes=15)
    opening = day[(day.index >= start) & (day.index < range_end)]
    if len(opening) < 3 or day.index[-1] < range_end:
        raise ValueError("Opening Range 15 menit belum selesai.")

    last = day.iloc[-1]
    prior = price_df[price_df.index.date < day.index[-1].date()]
    previous_close = float(prior["Close"].iloc[-1]) if not prior.empty else float(opening["Open"].iloc[0])
    change_pct = (float(last["Close"]) / previous_close - 1) * 100
    opening_high = float(opening["High"].max())
    opening_low = float(opening["Low"].min())
    opening_range_pct = (opening_high / opening_low - 1) * 100 if opening_low else 0
    distance_to_breakout = (float(last["Close"]) / opening_high - 1) * 100 if opening_high else 0
    opening_breakout = bool(float(last["Close"]) > opening_high)
    value_today = float((day["Close"] * day["Volume"]).sum())
    day_range = float(day["High"].max() - day["Low"].min())
    close_position = (float(last["Close"]) - float(day["Low"].min())) / day_range if day_range else 0
    vwap = run_vwap(day)
    price_vs_vwap_pct = float(vwap["price_vs_vwap_pct"])
    time_volume_ratio, slot_volume, slot_baseline, time_volume_days = _time_volume_ratio(
        price_df, day, start, _morning_start
    )

    score = 0
    signals = {}
    if opening_breakout:
        score += 35
        signals["opening_range"] = f"breakout high OR15 {opening_high:,.0f}"
    elif distance_to_breakout >= -0.5:
        score += 15
        signals["opening_range"] = f"dekat breakout OR15 ({distance_to_breakout:.1f}%)"
    else:
        signals["opening_range"] = f"belum breakout OR15 ({distance_to_breakout:.1f}%)"

    if time_volume_ratio is not None and time_volume_days >= 5:
        if time_volume_ratio >= 2:
            score += 25
        elif time_volume_ratio >= 1.5:
            score += 20
        elif time_volume_ratio >= 1.2:
            score += 12
        elif time_volume_ratio >= 1:
            score += 6
        signals["time_rvol"] = (
            f"RVOL 09:00-09:15 {time_volume_ratio:.1f}x median {time_volume_days} hari"
        )
    else:
        signals["time_rvol"] = f"RVOL pagi belum cukup data ({time_volume_days}/20 hari)"

    if price_vs_vwap_pct >= 1:
        score += 20
        signals["vwap"] = f"kuat di atas VWAP {price_vs_vwap_pct:.1f}%"
    elif price_vs_vwap_pct >= 0:
        score += 14
        signals["vwap"] = f"bertahan di atas VWAP {price_vs_vwap_pct:.1f}%"
    elif price_vs_vwap_pct > -0.5:
        score -= 5
        signals["vwap"] = f"sedikit di bawah VWAP {price_vs_vwap_pct:.1f}%"
    else:
        score -= 15
        signals["vwap"] = f"di bawah VWAP {price_vs_vwap_pct:.1f}%"

    if 0.5 <= change_pct <= 6:
        score += 10
        signals["price"] = f"kenaikan pagi sehat {change_pct:.1f}%"
    elif change_pct > 8:
        score -= 8
        signals["price"] = f"chaser risk {change_pct:.1f}%"
    elif change_pct > 0:
        score += 5
        signals["price"] = f"pagi hijau {change_pct:.1f}%"
    else:
        score -= 5
        signals["price"] = f"pagi merah {change_pct:.1f}%"

    if value_today >= 2_000_000_000:
        score += 10
        signals["value"] = "value pagi kuat"
    elif value_today >= 500_000_000:
        score += 7
        signals["value"] = "value pagi cukup"
    elif value_today >= 100_000_000:
        score += 3
        signals["value"] = "value pagi tipis"
    else:
        signals["value"] = "value pagi terlalu kecil"

    daily = price_df.groupby(price_df.index.date).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    score, fibonacci = _apply_fibonacci(
        score,
        signals,
        daily,
        volume_confirmed=bool(time_volume_ratio is not None and time_volume_ratio >= 1.2),
        above_vwap=price_vs_vwap_pct >= 0,
    )
    score = min(max(float(score), 0.0), 100.0)
    return {
        "score": score,
        "mode": "morning",
        "status": "KUAT" if score >= 70 else "MENARIK" if score >= 45 else "LEMAH",
        "change_pct": round(change_pct, 2),
        "volume_ratio": None if time_volume_ratio is None else round(float(time_volume_ratio), 2),
        "time_volume_ratio": None if time_volume_ratio is None else round(float(time_volume_ratio), 2),
        "time_volume_days": time_volume_days,
        "time_slot_volume": round(slot_volume, 0),
        "time_slot_baseline": round(slot_baseline, 0),
        "opening_range_high": round(opening_high, 2),
        "opening_range_low": round(opening_low, 2),
        "opening_range_pct": round(opening_range_pct, 2),
        "opening_range_breakout": opening_breakout,
        "distance_to_breakout_pct": round(distance_to_breakout, 2),
        "value_today": round(value_today, 0),
        "close_position": round(close_position, 2),
        "vwap": vwap["vwap"],
        "price_vs_vwap_pct": round(price_vs_vwap_pct, 2),
        "breakout_20d": False,
        "fibonacci": fibonacci,
        "fibonacci_bonus": fibonacci["bonus"] if fibonacci else 0,
        "signals": signals,
    }


def evaluate_session2_momentum(price_df) -> dict:
    if len(price_df) < 12:
        raise ValueError("Data intraday kurang.")

    price_df = _intraday_jakarta(price_df)

    day = price_df[price_df.index.date == price_df.index[-1].date()]
    if len(day) < 6:
        raise ValueError("Data intraday hari terakhir kurang.")

    last = day.iloc[-1]
    first = day.iloc[0]
    session_start = _session2_start(day.index[-1])
    session2 = day[day.index >= session_start]
    if session2.empty:
        raise ValueError("Sesi 2 belum dimulai.")
    pivot = session2.iloc[0]
    morning = day[day.index < session_start]

    change_pct = ((last["Close"] / first["Open"]) - 1) * 100
    session2_pct = ((last["Close"] / pivot["Open"]) - 1) * 100
    session1_pct = ((pivot["Open"] / first["Open"]) - 1) * 100
    morning_avg_volume = morning["Volume"].mean() if not morning.empty else 0
    session2_avg_volume = session2["Volume"].mean() if not session2.empty else last["Volume"]
    volume_ratio = session2_avg_volume / morning_avg_volume if morning_avg_volume else 0
    value_today = float((day["Close"] * day["Volume"]).sum())
    session2_value = float((session2["Close"] * session2["Volume"]).sum()) if not session2.empty else value_today
    day_range = day["High"].max() - day["Low"].min()
    close_position = (last["Close"] - day["Low"].min()) / day_range if day_range else 0
    acceleration = session2_pct - max(session1_pct, 0)
    vwap = run_vwap(day)
    price_vs_vwap_pct = float(vwap["price_vs_vwap_pct"])
    time_volume_ratio, slot_volume, slot_baseline, time_volume_days = _time_volume_ratio(
        price_df, day, session_start, _session2_start
    )

    score = 0
    signals = {}
    if session2_pct >= 2.5:
        score += 32
        signals["session2"] = f"sesi 2 kuat {session2_pct:.1f}%"
    elif session2_pct >= 1:
        score += 24
        signals["session2"] = f"sesi 2 mulai dorong {session2_pct:.1f}%"
    elif session2_pct > 0:
        score += 8
        signals["session2"] = f"sesi 2 hijau tipis {session2_pct:.1f}%"
    else:
        signals["session2"] = f"sesi 2 belum kuat {session2_pct:.1f}%"

    if session1_pct >= 8:
        score -= 30
        signals["session1"] = f"sesi 1 sudah top gainer {session1_pct:.1f}%"
    elif session1_pct >= 5:
        score -= 14
        signals["session1"] = f"sesi 1 sudah naik tinggi {session1_pct:.1f}%"
    elif session1_pct >= 0:
        score += 18
        signals["session1"] = f"sesi 1 masih tenang {session1_pct:.1f}%"
    else:
        score += 10
        signals["session1"] = f"sesi 1 tertahan {session1_pct:.1f}%"

    if acceleration >= 1:
        score += 14
        signals["acceleration"] = f"akselerasi sesi 2 {acceleration:.1f} pp"
    elif acceleration > 0:
        score += 6
        signals["acceleration"] = f"akselerasi tipis {acceleration:.1f} pp"
    else:
        signals["acceleration"] = f"belum akselerasi ({acceleration:.1f} pp)"

    if 1 <= change_pct <= 6:
        score += 14
        signals["price"] = f"ruang naik masih sehat {change_pct:.1f}%"
    elif change_pct > 9:
        score -= 12
        signals["price"] = f"chaser risk {change_pct:.1f}%"
    elif change_pct > 6:
        score += 4
        signals["price"] = f"mulai tinggi {change_pct:.1f}%"
    elif change_pct > 0:
        score += 8
        signals["price"] = f"hari ini hijau {change_pct:.1f}%"
    else:
        signals["price"] = f"hari ini merah {change_pct:.1f}%"

    if volume_ratio >= 2:
        score += 22
        signals["volume"] = f"volume sesi 2 {volume_ratio:.1f}x sesi 1"
    elif volume_ratio >= 1.2:
        score += 14
        signals["volume"] = f"volume sesi 2 {volume_ratio:.1f}x sesi 1"
    else:
        signals["volume"] = f"volume sesi 2 {volume_ratio:.1f}x sesi 1"

    if close_position >= 0.8:
        score += 18
        signals["close"] = "harga dekat high hari ini"
    elif close_position >= 0.6:
        score += 8
        signals["close"] = "harga cukup dekat high"
    else:
        signals["close"] = "harga belum dekat high"

    if price_vs_vwap_pct >= 1:
        score += 12
        signals["vwap"] = f"di atas VWAP {price_vs_vwap_pct:.1f}%"
    elif price_vs_vwap_pct >= 0:
        score += 8
        signals["vwap"] = f"bertahan di atas VWAP {price_vs_vwap_pct:.1f}%"
    elif price_vs_vwap_pct > -1:
        score -= 4
        signals["vwap"] = f"sedikit di bawah VWAP {price_vs_vwap_pct:.1f}%"
    else:
        score -= 12
        signals["vwap"] = f"di bawah VWAP {price_vs_vwap_pct:.1f}%"

    if session2_value >= 2_000_000_000:
        score += 10
        signals["value"] = "value sesi 2 kuat"
    elif session2_value >= 500_000_000:
        score += 6
        signals["value"] = "value sesi 2 cukup"
    elif session2_value >= 100_000_000:
        score += 3
        signals["value"] = "value sesi 2 tipis"
    else:
        signals["value"] = "value sesi 2 terlalu kecil"

    if time_volume_ratio is not None and time_volume_days >= 5:
        rvol_score = (
            100 if time_volume_ratio >= 2
            else 80 if time_volume_ratio >= 1.5
            else 65 if time_volume_ratio >= 1.2
            else 50 if time_volume_ratio >= 0.8
            else 20
        )
        score = score * 0.85 + rvol_score * 0.15
        signals["time_rvol"] = (
            f"RVOL slot awal sesi 2 {time_volume_ratio:.1f}x "
            f"median {time_volume_days} hari"
        )
    else:
        signals["time_rvol"] = f"RVOL slot belum cukup data ({time_volume_days}/20 hari)"

    score, fibonacci = _apply_fibonacci(
        score,
        signals,
        day,
        volume_confirmed=bool(
            (time_volume_ratio is not None and time_volume_ratio >= 1.2)
            or volume_ratio >= 1.2
        ),
        above_vwap=price_vs_vwap_pct >= 0,
    )
    score = min(max(float(score), 0.0), 100.0)
    return {
        "score": score,
        "mode": "session2",
        "status": "KUAT" if score >= 70 else "MENARIK" if score >= 45 else "LEMAH",
        "change_pct": round(float(change_pct), 2),
        "session1_pct": round(float(session1_pct), 2),
        "session2_pct": round(float(session2_pct), 2),
        "acceleration": round(float(acceleration), 2),
        "volume_ratio": round(float(volume_ratio), 2),
        "time_volume_ratio": None if time_volume_ratio is None else round(float(time_volume_ratio), 2),
        "time_volume_days": time_volume_days,
        "time_slot_volume": round(slot_volume, 0),
        "time_slot_baseline": round(slot_baseline, 0),
        "value_today": round(value_today, 0),
        "session2_value": round(session2_value, 0),
        "close_position": round(float(close_position), 2),
        "vwap": vwap["vwap"],
        "price_vs_vwap_pct": round(price_vs_vwap_pct, 2),
        "breakout_20d": False,
        "fibonacci": fibonacci,
        "fibonacci_bonus": fibonacci["bonus"] if fibonacci else 0,
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

    score, fibonacci = _apply_fibonacci(
        score,
        signals,
        price_df,
        volume_confirmed=bool(volume_ratio >= 1.3),
    )
    score = min(max(float(score), 0.0), 100.0)
    return {
        "score": score,
        "mode": mode,
        "status": "KUAT" if score >= 70 else "MENARIK" if score >= 45 else "LEMAH",
        "change_pct": round(float(change_pct), 2),
        "volume_ratio": round(float(volume_ratio), 2),
        "value_today": round(value_today, 0),
        "close_position": round(float(close_position), 2),
        "breakout_20d": breakout_20d,
        "relative_strength": None if relative_strength is None else round(float(relative_strength), 2),
        "accumulation_score": accumulation_score,
        "fibonacci": fibonacci,
        "fibonacci_bonus": fibonacci["bonus"] if fibonacci else 0,
        "signals": signals,
    }
