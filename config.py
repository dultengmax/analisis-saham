"""
Konfigurasi utama untuk Stock Analyzer.
Ubah bobot & threshold di sini sesuai gaya analisamu.
"""

# Bobot dasar teknikal/fundamental berjumlah 1.0; fitur lain menjadi overlay.
WEIGHT_TECHNICAL = 0.5
WEIGHT_FUNDAMENTAL = 0.5
WEIGHT_SENTIMENT = 0.1  # diterapkan ke 10% skor akhir saat sentimen dipilih
WEIGHT_BANDARMOLOGY = 0.15
WEIGHT_LIQUIDITY = 0.15

# Periode data historis harga yang diambil untuk analisa teknikal
PRICE_PERIOD = "1y"      # 1y, 6mo, 2y, 5y, max
PRICE_INTERVAL = "1d"    # 1d, 1wk

# Parameter indikator teknikal
SMA_SHORT = 20
SMA_LONG = 50
EMA_SHORT = 12
EMA_LONG = 26
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
STOCH_PERIOD = 14
ADX_PERIOD = 14

# Threshold sinyal teknikal
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Threshold fundamental "wajar" untuk saham Indonesia (bisa disesuaikan per sektor)
FUNDAMENTAL_THRESHOLDS = {
    "per_max": 20,        # PER di bawah ini dianggap wajar/murah
    "pbv_max": 3,         # PBV di bawah ini dianggap wajar
    "roe_min": 0.10,      # ROE minimal 10% dianggap sehat
    "der_max": 1.0,       # DER di bawah 1x dianggap aman
    "dividend_yield_min": 0.02,
}

# User-Agent untuk request ke idx.co.id (supaya tidak diblok sebagai bot kosong)
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.idx.co.id/",
}

# Batas jeda antar request scraping (detik) — jangan dihapus, untuk sopan santun ke server
REQUEST_DELAY_SECONDS = 1.5
