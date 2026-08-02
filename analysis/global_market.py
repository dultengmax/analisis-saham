"""Ringkasan kondisi indeks global untuk konteks IHSG."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

from data.price_fetcher import fetch_price_history


GLOBAL_MARKETS = [
    {"symbol": "^GSPC", "name": "S&P 500", "region": "US"},
    {"symbol": "^IXIC", "name": "Nasdaq", "region": "US"},
    {"symbol": "^DJI", "name": "Dow Jones", "region": "US"},
    {"symbol": "^N225", "name": "Nikkei 225", "region": "Asia"},
    {"symbol": "^HSI", "name": "Hang Seng", "region": "Asia"},
    {"symbol": "000001.SS", "name": "Shanghai", "region": "Asia"},
    {"symbol": "^STI", "name": "STI", "region": "Asia"},
    {"symbol": "^FTSE", "name": "FTSE 100", "region": "Europe"},
    {"symbol": "^GDAXI", "name": "DAX", "region": "Europe"},
    {"symbol": "^VIX", "name": "VIX", "region": "Risk", "inverse": True},
    {"symbol": "IDR=X", "name": "USD/IDR", "region": "FX", "inverse": True},
]


def fetch_global_market(markets: list[dict] | None = None) -> dict:
    items = list(markets or GLOBAL_MARKETS)
    rows = []
    errors = []
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(items)))) as executor:
        futures = {
            executor.submit(_fetch_market, index, item): item
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:
                item = futures[future]
                errors.append({"symbol": item["symbol"], "name": item["name"], "error": str(exc)})

    rows.sort(key=lambda row: row.pop("_order"))
    avg_impact = sum(row["impact"] for row in rows) / len(rows) if rows else 0
    score = min(100.0, max(0.0, round(50 + avg_impact * 10, 1))) if rows else 0
    status = (
        "DATA KOSONG"
        if not rows
        else "RISK ON" if avg_impact >= 0.3
        else "RISK OFF" if avg_impact <= -0.3
        else "NETRAL"
    )
    return {
        "status": status,
        "score": score,
        "average_impact": round(avg_impact, 2),
        "as_of": datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d %H:%M WIB"),
        "summary": _summary(status, rows),
        "markets": rows,
        "errors": errors[:5],
    }


def _fetch_market(index: int, item: dict) -> dict:
    try:
        df = fetch_price_history(item["symbol"], period="5d", interval="1d")
        close = df["Close"].dropna()
        if len(close) < 2:
            raise ValueError("data kurang dari 2 hari")
        price = float(close.iloc[-1])
        change_pct = (price - float(close.iloc[-2])) / float(close.iloc[-2]) * 100
        impact = -change_pct if item.get("inverse") else change_pct
        return {
            "_order": index,
            "symbol": item["symbol"],
            "name": item["name"],
            "region": item["region"],
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "impact": round(impact, 2),
            "status": "UP" if change_pct > 0.1 else "DOWN" if change_pct < -0.1 else "FLAT",
        }
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc


def _summary(status: str, rows: list[dict]) -> str:
    if not rows:
        return "Data global belum tersedia."
    leaders = sorted(rows, key=lambda row: row["impact"], reverse=True)
    strong = leaders[0]
    weak = leaders[-1]
    return (
        f"{status}: dukungan terkuat dari {strong['name']} "
        f"({strong['change_pct']:+.2f}%), tekanan utama dari {weak['name']} "
        f"({weak['change_pct']:+.2f}%)."
    )
