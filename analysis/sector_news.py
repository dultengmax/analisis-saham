"""Snapshot berita pagi untuk sektor IDX."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from threading import Event, Lock

from analysis.sentiment import NEGATIVE_PHRASES, POSITIVE_PHRASES, SentimenAnalyzer


JAKARTA_TZ = timezone(timedelta(hours=7))
CACHE_PATH = Path(__file__).resolve().parents[1] / ".cache" / "sector_news.json"
REFRESH_LOCK = Lock()

SECTOR_QUERIES = {
    "Basic Materials": '("sektor barang baku" OR "saham semen" OR "saham nikel")',
    "Consumer Cyclicals": '("konsumer siklikal" OR "saham otomotif" OR "saham ritel")',
    "Consumer Non-Cyclicals": '("konsumer primer" OR "saham makanan" OR "saham minuman")',
    "Energy": '("sektor energi" OR "saham batu bara" OR "saham minyak")',
    "Financials": '("sektor keuangan" OR "saham bank" OR "saham asuransi")',
    "Healthcare": '("sektor kesehatan" OR "saham rumah sakit" OR "saham farmasi")',
    "Industrials": '("sektor perindustrian" OR "saham manufaktur")',
    "Infrastructures": '("sektor infrastruktur" OR "saham telekomunikasi" OR "saham menara")',
    "Properties & Real Estate": '("sektor properti" OR "saham real estat")',
    "Technology": '("sektor teknologi" OR "saham digital")',
    "Transportation & Logistic": '("sektor transportasi" OR "saham logistik" OR "saham pelayaran")',
}

SECTOR_ALIASES = {
    "Consumer Cyclical": "Consumer Cyclicals",
    "Consumer Defensive": "Consumer Non-Cyclicals",
    "Financial Services": "Financials",
    "Communication Services": "Infrastructures",
    "Utilities": "Infrastructures",
    "Real Estate": "Properties & Real Estate",
}


def jakarta_date() -> str:
    return datetime.now(JAKARTA_TZ).date().isoformat()


def normalize_sector(sector: str | None, industry: str | None = None) -> str:
    industry_text = (industry or "").casefold()
    if any(
        word in industry_text
        for word in ("airline", "airport", "railroad", "trucking", "shipping", "freight", "logistic")
    ):
        return "Transportation & Logistic"
    value = (sector or "Unknown").strip()
    return SECTOR_ALIASES.get(value, value)


def score_sector_news(headlines: list[str]) -> dict:
    details = []
    seen = set()
    for raw_title in headlines:
        raw_title = raw_title.strip()
        title, separator, source = raw_title.rpartition(" - ")
        title = title if separator else raw_title
        key = title.casefold()
        if len(title) <= 10 or key in seen:
            continue
        seen.add(key)
        positive = SentimenAnalyzer._phrase_score(key, POSITIVE_PHRASES)
        negative = SentimenAnalyzer._phrase_score(key, NEGATIVE_PHRASES)
        label = "positif" if positive > negative else "negatif" if negative > positive else "netral"
        details.append({
            "title": title,
            "source": source if separator else "",
            "label": label,
            "strength": max(positive, negative),
        })

    total = len(details)
    net_strength = sum(
        item["strength"] if item["label"] == "positif"
        else -item["strength"] if item["label"] == "negatif"
        else 0
        for item in details
    )
    score = 50.0 if not total else round(max(0, min(100, 50 + net_strength / total * 10)), 1)
    return {
        "score": score,
        "status": "NO_DATA" if not total else "POSITIF" if score >= 60 else "NEGATIF" if score <= 40 else "NETRAL",
        "total": total,
        "positive": sum(item["label"] == "positif" for item in details),
        "negative": sum(item["label"] == "negatif" for item in details),
        "neutral": sum(item["label"] == "netral" for item in details),
        "headlines": details[:8],
    }


def build_sector_news_snapshot(
    analyzer: SentimenAnalyzer,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(JAKARTA_TZ)

    def fetch(item):
        sector, query = item
        return sector, score_sector_news(
            analyzer.ambil_berita_google(query, max=8, days=1)
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        sectors = dict(pool.map(fetch, SECTOR_QUERIES.items()))

    return {
        "schema_version": 1,
        "market_date": now.astimezone(JAKARTA_TZ).date().isoformat(),
        "generated_at": now.astimezone(JAKARTA_TZ).isoformat(timespec="seconds"),
        "source": "Google News RSS",
        "lookback_hours": 24,
        "total_headlines": sum(item["total"] for item in sectors.values()),
        "sectors": sectors,
    }


def load_sector_news() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "schema_version": 1,
            "market_date": None,
            "generated_at": None,
            "source": "Google News RSS",
            "lookback_hours": 24,
            "total_headlines": 0,
            "sectors": {},
        }


def refresh_sector_news(analyzer: SentimenAnalyzer, force: bool = False) -> dict:
    with REFRESH_LOCK:
        cached = load_sector_news()
        if (
            not force
            and cached.get("market_date") == jakarta_date()
            and cached.get("total_headlines", 0) > 0
        ):
            return cached

        snapshot = build_sector_news_snapshot(analyzer)
        if snapshot["total_headlines"] > 0:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = CACHE_PATH.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(CACHE_PATH)
        return snapshot


def run_sector_news_scheduler(analyzer: SentimenAnalyzer) -> None:
    timer = Event()
    while True:
        if datetime.now(JAKARTA_TZ).hour >= 6:
            try:
                refresh_sector_news(analyzer)
            except Exception as exc:
                print(f"[BERITA SEKTOR] Gagal memperbarui: {exc}")
        timer.wait(30 * 60)
