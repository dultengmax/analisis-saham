"""Katalis overnight untuk shortlist pre-open."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from pathlib import Path
from statistics import mean
from threading import Lock

from analysis.sector_news import JAKARTA_TZ, score_sector_news
from data.price_fetcher import fetch_price_history


CACHE_PATH = Path(__file__).resolve().parents[1] / ".cache" / "overnight_market.json"
REFRESH_LOCK = Lock()
MARKET_SYMBOLS = {
    "sp500": ("^GSPC", "S&P 500"),
    "nikkei": ("^N225", "Nikkei 225"),
    "hang_seng": ("^HSI", "Hang Seng"),
    "shanghai": ("000001.SS", "Shanghai"),
    "oil": ("CL=F", "Minyak WTI"),
    "gold": ("GC=F", "Emas"),
    "copper": ("HG=F", "Tembaga"),
    "usd_idr": ("IDR=X", "USD/IDR"),
}
CORPORATE_ACTION_TERMS = (
    "buyback",
    "dividen",
    "right issue",
    "rights issue",
    "stock split",
    "reverse stock",
    "merger",
    "akuisisi",
    "tender offer",
    "rups",
    "suspensi",
    "uma",
)


def _instrument_snapshot(item) -> tuple[str, dict]:
    key, (symbol, name) = item
    history = fetch_price_history(symbol, period="5d", interval="1d")
    if len(history) < 2:
        raise ValueError(f"Data {name} kurang.")
    previous, latest = history["Close"].iloc[-2:]
    return key, {
        "symbol": symbol,
        "name": name,
        "last": round(float(latest), 4),
        "change_pct": round((float(latest) / float(previous) - 1) * 100, 2),
        "as_of": str(history.index[-1]),
    }


def build_market_snapshot(now: datetime | None = None) -> dict:
    now = now or datetime.now(JAKARTA_TZ)
    instruments = {}
    errors = {}

    def fetch(item):
        try:
            return _instrument_snapshot(item), None
        except Exception as exc:
            return (item[0], None), str(exc)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for ((key, result), error) in pool.map(fetch, MARKET_SYMBOLS.items()):
            if result:
                instruments[key] = result
            else:
                errors[key] = error

    return {
        "schema_version": 1,
        "market_date": now.astimezone(JAKARTA_TZ).date().isoformat(),
        "generated_at": now.astimezone(JAKARTA_TZ).isoformat(timespec="seconds"),
        "instruments": instruments,
        "errors": errors,
    }


def load_market_snapshot() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def refresh_market_snapshot(force: bool = False) -> dict:
    with REFRESH_LOCK:
        now = datetime.now(JAKARTA_TZ)
        cached = load_market_snapshot()
        try:
            age = now - datetime.fromisoformat(cached["generated_at"])
        except (KeyError, TypeError, ValueError):
            age = timedelta.max
        if (
            not force
            and cached.get("market_date") == now.date().isoformat()
            and cached.get("instruments")
            and age < timedelta(minutes=30)
        ):
            return cached

        snapshot = build_market_snapshot(now)
        if snapshot["instruments"]:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = CACHE_PATH.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(CACHE_PATH)
        return snapshot


def score_market_catalyst(snapshot: dict, sector: str) -> dict:
    instruments = snapshot.get("instruments", {})

    def changes(*keys):
        return [
            float(instruments[key]["change_pct"])
            for key in keys
            if key in instruments
        ]

    regional = changes("sp500", "nikkei", "hang_seng", "shanghai")
    regional_change = mean(regional) if regional else None
    bonus = (
        4 if regional_change is not None and regional_change >= 0.75
        else 2 if regional_change is not None and regional_change >= 0.25
        else -4 if regional_change is not None and regional_change <= -0.75
        else -2 if regional_change is not None and regional_change <= -0.25
        else 0
    )

    usd_idr = changes("usd_idr")
    fx_change = usd_idr[0] if usd_idr else None
    if fx_change is not None:
        bonus += 2 if fx_change <= -0.4 else -2 if fx_change >= 0.4 else 0

    commodity_change = None
    inverted = False
    if sector == "Energy":
        values = changes("oil")
    elif sector == "Basic Materials":
        values = changes("gold", "copper")
    elif sector == "Transportation & Logistic":
        values = changes("oil")
        inverted = True
    else:
        values = []
    if values:
        commodity_change = mean(values)
        direction = -commodity_change if inverted else commodity_change
        bonus += 3 if direction >= 1 else 1 if direction >= 0.3 else -3 if direction <= -1 else -1 if direction <= -0.3 else 0

    return {
        "bonus": max(-6, min(6, bonus)),
        "regional_change_pct": None if regional_change is None else round(regional_change, 2),
        "usd_idr_change_pct": fx_change,
        "commodity_change_pct": None if commodity_change is None else round(commodity_change, 2),
    }


def apply_overnight_catalysts(rows: list[dict], analyzer, snapshot: dict | None = None) -> int:
    snapshot = snapshot or refresh_market_snapshot()

    def fetch_news(row):
        headlines = analyzer.ambil_berita_google(row["ticker"], max=6, days=1)
        return row, score_sector_news(headlines)

    covered = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = pool.map(fetch_news, rows)
        for row, issuer_news in results:
            market = score_market_catalyst(snapshot, row.get("sector", "Unknown"))
            news_score = float(issuer_news["score"])
            news_bonus = 4 if news_score >= 70 else 2 if news_score >= 60 else -4 if news_score <= 30 else -2 if news_score <= 40 else 0
            bonus = max(-10, min(10, market["bonus"] + news_bonus))
            actions = [
                item["title"]
                for item in issuer_news["headlines"]
                if any(term in item["title"].casefold() for term in CORPORATE_ACTION_TERMS)
            ][:3]

            row["overnight"] = {
                "status": "POSITIF" if bonus > 0 else "NEGATIF" if bonus < 0 else "NETRAL",
                "bonus": bonus,
                "issuer_news": issuer_news,
                "sector_news": row.get("sector_news"),
                "market": market,
                "corporate_actions": actions,
                "market_generated_at": snapshot.get("generated_at"),
            }
            row["overnight_bonus"] = bonus
            momentum = row["momentum"]
            momentum["score"] = min(100.0, max(0.0, round(momentum["score"] + bonus, 1)))
            momentum["status"] = (
                "KUAT" if momentum["score"] >= 70 else "MENARIK" if momentum["score"] >= 45 else "LEMAH"
            )
            regional = market["regional_change_pct"]
            fx = market["usd_idr_change_pct"]
            commodity = market["commodity_change_pct"]
            momentum["signals"]["overnight"] = (
                f"katalis overnight {row['overnight']['status'].lower()} "
                f"(regional {regional:+.1f}%"
                if regional is not None
                else f"katalis overnight {row['overnight']['status'].lower()} (regional -"
            )
            momentum["signals"]["overnight"] += (
                f", USD/IDR {fx:+.1f}%" if fx is not None else ", USD/IDR -"
            )
            momentum["signals"]["overnight"] += (
                f", komoditas {commodity:+.1f}%" if commodity is not None else ", komoditas -"
            )
            momentum["signals"]["overnight"] += (
                f", berita {issuer_news['total']}, aksi {len(actions)}, total {bonus:+g})"
            )
            if issuer_news["total"] or snapshot.get("instruments"):
                covered += 1

    return covered
