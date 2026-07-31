"""Skoring akhir saham: komposit, red flags, dan rekomendasi."""
import math
from typing import Any

from config import (
    WEIGHT_BANDARMOLOGY,
    WEIGHT_FUNDAMENTAL,
    WEIGHT_LIQUIDITY,
    WEIGHT_ML,
    WEIGHT_SENTIMENT,
    WEIGHT_TECHNICAL,
)


def _to_float(value: Any) -> float | None:
    if value is None or value == "N/A":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def evaluate_red_flags(fundamental_result: dict) -> list[str]:
    raw = fundamental_result.get("raw", {})
    per = _to_float(raw.get("per"))
    roe = _to_float(raw.get("roe"))
    last_price = _to_float(raw.get("last_price"))
    red_flags = []

    if roe is not None and roe <= 0:
        red_flags.append(f"ROE negatif/minus ({roe * 100:.1f}%)")
    elif roe is not None and roe < 0.05:
        red_flags.append(f"ROE terlalu rendah ({roe * 100:.1f}%)")

    if per is not None and per <= 0:
        red_flags.append(f"PER negatif/minus ({per:.1f}x)")
    elif per is not None and per > 50:
        red_flags.append(f"PER overvalued ({per:.1f}x)")

    if last_price is not None and last_price < 100:
        red_flags.append(f"Harga di bawah Rp 100 ({last_price:.0f})")

    return red_flags


def compute_composite(
    technical_result: dict,
    fundamental_result: dict,
    sentiment_result: dict | None = None,
    bandarmology_result: dict | None = None,
    liquidity_result: dict | None = None,
    ml_result: dict | None = None,
) -> dict:
    tech_score = technical_result["technical_score"]
    fund_score = fundamental_result["fundamental_score"]
    sentiment_score = (
        _to_float(sentiment_result.get("skor"))
        if sentiment_result and sentiment_result.get("status") != "NO_DATA"
        else None
    )
    bandarmology_score = (
        _to_float(bandarmology_result.get("skor"))
        if bandarmology_result and bandarmology_result.get("fase") != "ERROR"
        else None
    )
    liquidity_score = _to_float(liquidity_result.get("score")) if liquidity_result else None
    ml_score = (
        _to_float(ml_result.get("skor"))
        if ml_result
        and ml_result.get("status") in {"READY", "PARTIAL"}
        and ml_result.get("arah") in {"NAIK", "TURUN"}
        else None
    )
    rsi = _to_float(technical_result.get("rsi"))
    red_flags = evaluate_red_flags(fundamental_result)

    if fund_score is None:
        # Data fundamental tidak tersedia sama sekali -> full bobot ke teknikal
        composite = tech_score
        note = "Skor fundamental tidak tersedia, bobot dasar memakai teknikal."
    else:
        composite = round(
            tech_score * WEIGHT_TECHNICAL + fund_score * WEIGHT_FUNDAMENTAL, 1
        )
        note = None

    extra_weight = 0.0
    extra_score = 0.0
    if sentiment_score is not None:
        extra_weight += WEIGHT_SENTIMENT
        extra_score += sentiment_score * WEIGHT_SENTIMENT
    if bandarmology_score is not None:
        extra_weight += WEIGHT_BANDARMOLOGY
        extra_score += bandarmology_score * WEIGHT_BANDARMOLOGY
    if liquidity_score is not None:
        extra_weight += WEIGHT_LIQUIDITY
        extra_score += liquidity_score * WEIGHT_LIQUIDITY
    if ml_score is not None:
        extra_weight += WEIGHT_ML
        extra_score += ml_score * WEIGHT_ML
    composite = round(composite * (1 - extra_weight) + extra_score, 1)

    if red_flags:
        composite = min(composite, 40.0)
        recommendation = "AVOID/SELL"
        reason = "Terkena red flag kualitas: " + "; ".join(red_flags)
    elif rsi is not None and rsi >= 70:
        recommendation = "AVOID/SELL"
        reason = f"RSI overbought ({rsi:.1f}) - risiko koreksi tinggi."
    elif composite >= 75:
        recommendation = "BUY"
        reason = "Skor komposit tinggi, RSI belum overbought, dan tidak ada red flag."
    elif composite >= 55:
        recommendation = "HOLD/WATCH"
        reason = "Skor komposit netral - belum ada sinyal kuat, pantau lebih lanjut."
    else:
        recommendation = "AVOID/SELL"
        reason = "Skor komposit rendah - kondisi teknikal dan/atau fundamental kurang mendukung."

    return {
        "technical_score": tech_score,
        "fundamental_score": fund_score,
        "sentiment_score": sentiment_score,
        "bandarmology_score": bandarmology_score,
        "liquidity_score": liquidity_score,
        "ml_score": ml_score,
        "composite_score": composite,
        "recommendation": recommendation,
        "reason": reason,
        "note": note,
        "red_flags": red_flags,
    }


def build_full_report(
    ticker: str,
    quick_info: dict,
    technical_result: dict,
    fundamental_result: dict,
    composite: dict,
    sentiment_result: dict | None = None,
    bandarmology_result: dict | None = None,
    liquidity_result: dict | None = None,
    ml_result: dict | None = None,
) -> dict:
    """Kumpulkan semua hasil analisa jadi satu struktur laporan yang rapi."""
    return {
        "ticker": ticker.upper(),
        "name": quick_info.get("name"),
        "sector": quick_info.get("sector"),
        "last_price": quick_info.get("last_price"),
        "technical": {
            "score": technical_result["technical_score"],
            "signals": technical_result["signals"],
            "rsi": technical_result["rsi"],
            "fibonacci": technical_result.get("fibonacci"),
        },
        "fundamental": {
            "score": fundamental_result["fundamental_score"],
            "signals": fundamental_result["signals"],
            "missing_data": fundamental_result["missing_data"],
        },
        "sentiment": sentiment_result,
        "liquidity": liquidity_result,
        "ml": ml_result,
        "bandarmology": bandarmology_result,
        "composite_score": composite["composite_score"],
        "recommendation": composite["recommendation"],
        "reason": composite["reason"],
        "note": composite["note"],
        "red_flags": composite["red_flags"],
    }
