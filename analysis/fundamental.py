"""
Analisa fundamental saham berdasarkan rasio keuangan dasar.
Sumber data utama: Yahoo Finance (via data.price_fetcher.fetch_quick_info),
bisa diperkaya nanti dengan data resmi IDX (lihat data/idx_fetcher.py).
"""
from config import FUNDAMENTAL_THRESHOLDS as T

PRIMARY_MISSING_PENALTY = 15


def evaluate_fundamental(info: dict) -> dict:
    """
    info: dict hasil dari price_fetcher.fetch_quick_info()
    Return dict berisi skor 0-100 dan breakdown per rasio.
    """
    signals = {}
    score = 0
    max_score = 0
    missing = []

    per = info.get("per")
    pbv = info.get("pbv")
    roe = info.get("roe")
    der = info.get("der")
    dividend_yield = info.get("dividend_yield")
    if dividend_yield is not None and dividend_yield > 1:
        dividend_yield = dividend_yield / 100

    # 1. PER (Price to Earning Ratio) - makin rendah & positif makin baik
    max_score += 25
    if per is None:
        missing.append("PER")
        signals["per"] = "PER tidak tersedia - penalti data fundamental"
    elif per <= 0:
        signals["per"] = f"PER negatif ({per:.1f}) - perusahaan rugi, waspada"
        score += 0
    elif per <= T["per_max"] * 0.5:
        signals["per"] = f"PER sangat murah ({per:.1f}x)"
        score += 25
    elif per <= T["per_max"]:
        signals["per"] = f"PER wajar ({per:.1f}x)"
        score += 18
    else:
        signals["per"] = f"PER mahal ({per:.1f}x)"
        score += 8

    # 2. PBV (Price to Book Value)
    max_score += 20
    if pbv is None:
        missing.append("PBV")
    elif pbv <= T["pbv_max"] * 0.5:
        signals["pbv"] = f"PBV murah ({pbv:.2f}x)"
        score += 20
    elif pbv <= T["pbv_max"]:
        signals["pbv"] = f"PBV wajar ({pbv:.2f}x)"
        score += 14
    else:
        signals["pbv"] = f"PBV mahal ({pbv:.2f}x)"
        score += 5

    # 3. ROE (Return on Equity) - makin tinggi makin baik
    max_score += 25
    if roe is None:
        missing.append("ROE")
        signals["roe"] = "ROE tidak tersedia - penalti data fundamental"
    elif roe >= T["roe_min"] * 2:
        signals["roe"] = f"ROE sangat sehat ({roe*100:.1f}%)"
        score += 25
    elif roe >= T["roe_min"]:
        signals["roe"] = f"ROE sehat ({roe*100:.1f}%)"
        score += 18
    elif roe > 0:
        signals["roe"] = f"ROE rendah ({roe*100:.1f}%)"
        score += 8
    else:
        signals["roe"] = f"ROE negatif ({roe*100:.1f}%) - perusahaan rugi"
        score += 0

    # 4. DER (Debt to Equity Ratio) - makin rendah makin aman
    max_score += 15
    if der is None:
        missing.append("DER")
        signals["der"] = "DER tidak tersedia - penalti data fundamental"
    else:
        der_ratio = der / 100 if der > 10 else der  # yfinance kadang return dalam %
        if der_ratio <= T["der_max"] * 0.5:
            signals["der"] = f"DER aman ({der_ratio:.2f}x)"
            score += 15
        elif der_ratio <= T["der_max"]:
            signals["der"] = f"DER moderat ({der_ratio:.2f}x)"
            score += 10
        else:
            signals["der"] = f"DER tinggi ({der_ratio:.2f}x) - beban utang besar"
            score += 3

    # 5. Dividend Yield
    max_score += 15
    if dividend_yield is None:
        missing.append("Dividend Yield")
    elif dividend_yield >= T["dividend_yield_min"] * 2:
        signals["dividend_yield"] = f"dividend yield menarik ({dividend_yield*100:.1f}%)"
        score += 15
    elif dividend_yield >= T["dividend_yield_min"]:
        signals["dividend_yield"] = f"dividend yield cukup ({dividend_yield*100:.1f}%)"
        score += 10
    else:
        signals["dividend_yield"] = f"dividend yield kecil ({dividend_yield*100:.1f}%)"
        score += 4

    normalized_score = round((score / max_score) * 100, 1) if max_score > 0 else None
    if normalized_score is not None:
        primary_missing = sum(1 for key in ("PER", "DER", "ROE") if key in missing)
        normalized_score = max(0.0, round(normalized_score - primary_missing * PRIMARY_MISSING_PENALTY, 1))

    return {
        "fundamental_score": normalized_score,
        "signals": signals,
        "missing_data": missing,
        "raw": {"per": per, "pbv": pbv, "roe": roe, "der": der,
                "dividend_yield": dividend_yield,
                "last_price": info.get("last_price")},
    }
