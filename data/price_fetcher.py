"""
Pengambil data harga historis saham Indonesia via Yahoo Finance.
Ticker IDX di Yahoo Finance pakai suffix .JK, contoh: BBCA.JK, TLKM.JK
"""
from pathlib import Path
import time
import pandas as pd
import requests
import yfinance as yf

from config import PRICE_PERIOD, PRICE_INTERVAL, REQUEST_DELAY_SECONDS

CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "yfinance"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(CACHE_DIR))


def _fetch_yahoo_chart(ticker: str, period: str, interval: str) -> dict:
    response = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"range": period, "interval": interval},
        headers={"User-Agent": "StockAnalyzer/2.0"},
        timeout=15,
    )
    response.raise_for_status()
    result = response.json()["chart"]["result"][0]
    if result.get("timestamp") is None:
        raise ValueError(f"Data harga untuk {ticker} kosong.")
    return result


def _chart_to_history(result: dict) -> pd.DataFrame:
    quote = result["indicators"]["quote"][0]
    df = pd.DataFrame(
        {
            "Open": quote["open"],
            "High": quote["high"],
            "Low": quote["low"],
            "Close": quote["close"],
            "Volume": quote["volume"],
        },
        index=pd.to_datetime(result["timestamp"], unit="s"),
    )
    df.dropna(inplace=True)
    return df


def _raise_yahoo_error(exc: Exception):
    message = str(exc)
    if "fc.yahoo.com" in message or "curl:" in message:
        raise ConnectionError(
            "Yahoo Finance tidak bisa diakses dari komputer ini. "
            "Cek koneksi internet/VPN/firewall, lalu coba lagi."
        ) from exc
    raise exc


def normalize_ticker(ticker: str) -> str:
    """Pastikan ticker punya suffix .JK untuk saham IDX."""
    ticker = ticker.strip().upper()
    if ticker.startswith("^") or "." in ticker or "=" in ticker:
        return ticker
    if not ticker.endswith(".JK"):
        ticker += ".JK"
    return ticker


def fetch_price_history(ticker: str, period: str = PRICE_PERIOD,
                         interval: str = PRICE_INTERVAL) -> pd.DataFrame:
    """
    Ambil data OHLCV historis.
    Return DataFrame dengan kolom: Open, High, Low, Close, Volume
    Index: tanggal (DatetimeIndex)
    """
    yf_ticker = normalize_ticker(ticker)
    stock = yf.Ticker(yf_ticker)
    try:
        df = stock.history(period=period, interval=interval)
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        try:
            df = _chart_to_history(_fetch_yahoo_chart(yf_ticker, period, interval))
        except Exception as exc:
            _raise_yahoo_error(exc)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)
    return df


def fetch_quick_info(ticker: str) -> dict:
    """
    Ambil ringkasan info saham (harga terakhir, market cap, dsb) sekaligus
    beberapa rasio fundamental dasar yang tersedia di Yahoo Finance
    (fallback kalau data IDX resmi belum lengkap).
    """
    yf_ticker = normalize_ticker(ticker)
    stock = yf.Ticker(yf_ticker)
    try:
        info = stock.info or {}
    except Exception as exc:
        try:
            meta = _fetch_yahoo_chart(yf_ticker, "5d", "1d")["meta"]
        except Exception:
            _raise_yahoo_error(exc)
        info = {
            "shortName": yf_ticker,
            "regularMarketPrice": meta.get("regularMarketPrice"),
        }

    return {
        "ticker": yf_ticker,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "last_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "per": info.get("trailingPE"),
        "pbv": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "der": info.get("debtToEquity"),
        "eps": info.get("trailingEps"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
    }


def fetch_multiple(tickers: list[str], period: str = PRICE_PERIOD) -> dict:
    """Ambil data harga untuk banyak ticker sekaligus, dengan jeda sopan antar request."""
    result = {}
    for t in tickers:
        try:
            result[t] = fetch_price_history(t, period=period)
        except Exception as e:
            print(f"[WARNING] Gagal mengambil {t}: {e}")
        time.sleep(REQUEST_DELAY_SECONDS)
    return result
