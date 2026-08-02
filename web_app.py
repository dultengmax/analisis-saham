"""Web UI ringan untuk Stock Analyzer."""
from datetime import datetime
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from analysis.sentiment import SentimenAnalyzer

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
SENTIMENT_ANALYZER = SentimenAnalyzer()
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


def load_screener_universe() -> list[str]:
    path = ROOT / "data" / "idx_universe.txt"
    suspended = load_suspended_tickers()
    return [
        ticker
        for line in path.read_text(encoding="utf-8").splitlines()
        if (ticker := normalize_idx_code(line)) and ticker not in suspended
    ]


def normalize_idx_code(value: str) -> str:
    ticker = value.split("#", 1)[0].strip().upper().removesuffix(".JK")
    return ticker if ticker else ""


def load_suspended_tickers() -> set[str]:
    path = ROOT / "data" / "suspended_tickers.txt"
    if not path.is_file():
        return set()
    return {
        ticker
        for line in path.read_text(encoding="utf-8").splitlines()
        if (ticker := normalize_idx_code(line))
    }


def analyze_for_web(ticker: str, options: dict) -> dict:
    from analysis.atr import run_atr
    from analysis.bandarmologi import BandarmologiAnalyzer
    from analysis.bootstrapping import run_bootstrapping
    from analysis.fundamental import evaluate_fundamental
    from analysis.garch import run_garch
    from analysis.liquidity import evaluate_liquidity
    from analysis.monte_carlo import run_monte_carlo
    from analysis.ml_model import MLAnalyzer
    from analysis.scorer import build_full_report, compute_composite
    from analysis.technical import evaluate_technical
    from analysis.vwap import run_vwap
    from backtest.backtester import run_backtest
    from data.price_fetcher import fetch_price_history, fetch_quick_info

    quick_info = fetch_quick_info(ticker)
    price_df = fetch_price_history(ticker)
    technical = evaluate_technical(price_df)
    fundamental = evaluate_fundamental(quick_info)
    sentiment = (
        SENTIMENT_ANALYZER.analisis(ticker) if options.get("sentiment") else None
    )
    bandarmology = BandarmologiAnalyzer(ticker, price_df).analisis()
    liquidity = evaluate_liquidity(price_df)
    ml = MLAnalyzer(ticker).prediksi() if options.get("ml") else None
    composite = compute_composite(
        technical, fundamental, sentiment, bandarmology, liquidity, ml
    )
    report = build_full_report(
        ticker,
        quick_info,
        technical,
        fundamental,
        composite,
        sentiment,
        bandarmology,
        liquidity,
        ml,
    )

    extras = {}
    if options.get("backtest"):
        extras["backtest"] = run_backtest(price_df)
    if options.get("monteCarlo"):
        extras["monte_carlo"] = run_monte_carlo(price_df)
    if options.get("bootstrap"):
        extras["bootstrapping"] = run_bootstrapping(price_df)
    if options.get("garch"):
        extras["garch"] = run_garch(price_df)
    if options.get("atr"):
        extras["atr"] = run_atr(price_df)
    if options.get("vwap"):
        extras["vwap"] = run_vwap(price_df)

    report["extras"] = extras
    return report


def screen_for_web(limit: int = 15, max_tickers: int = 1009) -> dict:
    limit = max(1, min(limit, 50))
    universe = load_screener_universe()[:max(1, min(max_tickers, 1200))]
    rows = []
    errors = []
    for ticker in universe:
        try:
            data = analyze_for_web(ticker, {})
            if data["recommendation"] != "AVOID/SELL" and not data.get("red_flags"):
                rows.append(data)
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})

    rows.sort(key=lambda item: item["composite_score"], reverse=True)
    return {
        "results": rows[:limit],
        "checked": len(universe),
        "qualified": len(rows),
        "errors": errors[:10],
    }


def apply_sector_heat(
    rows: list[dict],
    use_price_heat: bool = True,
    use_sector_news: bool = False,
) -> None:
    from analysis.sector_news import jakarta_date, load_sector_news, normalize_sector
    from data.price_fetcher import fetch_quick_info

    sectors = {}
    for row in rows:
        info = fetch_quick_info(row["ticker"])
        sector = normalize_sector(info.get("sector"), info.get("industry"))
        row["sector"] = sector
        sectors.setdefault(sector, []).append(row)

    if use_price_heat:
        for sector_rows in sectors.values():
            session2 = sector_rows[0]["momentum"].get("mode") == "session2"
            avg_change = sum(
                item["momentum"].get("session2_pct", item["momentum"]["change_pct"])
                for item in sector_rows
            ) / len(sector_rows)
            bonus = 0
            if len(sector_rows) >= 3 and avg_change > 0:
                bonus = min(12, round(avg_change * 1.5 + len(sector_rows), 1))
            elif len(sector_rows) >= 2 and avg_change >= 1:
                bonus = min(8, round(avg_change * 1.2 + len(sector_rows), 1))
            elif avg_change >= 5:
                bonus = 5

            for row in sector_rows:
                row["sector_heat_bonus"] = bonus
                if bonus:
                    row["momentum"]["score"] = min(100.0, round(row["momentum"]["score"] + bonus, 1))
                    row["momentum"]["signals"]["sector_heat"] = (
                        f"sektor {'sesi 2 ' if session2 else ''}panas: {row['sector']} (+{bonus})"
                    )

    snapshot = load_sector_news() if use_sector_news else {}
    if snapshot.get("market_date") == jakarta_date():
        for sector, sector_rows in sectors.items():
            news = snapshot.get("sectors", {}).get(sector)
            if not news or not news.get("total"):
                continue
            score = float(news["score"])
            bonus = 8 if score >= 70 else 5 if score >= 60 else -8 if score <= 30 else -5 if score <= 40 else 0
            summary = {
                key: news[key]
                for key in ("score", "status", "total", "positive", "negative", "neutral")
            }
            summary["top_headline"] = news.get("headlines", [{}])[0].get("title")
            for row in sector_rows:
                row["sector_news"] = summary
                row["sector_news_bonus"] = bonus
                row["momentum"]["score"] = min(
                    100.0, max(0.0, round(row["momentum"]["score"] + bonus, 1))
                )
                row["momentum"]["signals"]["sector_news"] = (
                    f"berita sektor {news['status'].lower()} {score:.0f}/100 "
                    f"({news['total']} berita, {bonus:+g})"
                )

    for row in rows:
        score = row["momentum"]["score"]
        row["momentum"]["status"] = (
            "KUAT" if score >= 70 else "MENARIK" if score >= 45 else "LEMAH"
        )


def passes_momentum_filter(momentum: dict, mode: str) -> bool:
    if momentum["score"] < 45:
        return False

    if mode == "session2":
        return (
            momentum["change_pct"] > 0
            and momentum.get("session2_pct", 0) >= 0.8
            and momentum.get("session2_value", 0) >= 100_000_000
            and momentum.get("price_vs_vwap_pct", 0) >= 0
            and (
                momentum.get("session1_pct", 0) < 6
                or momentum.get("acceleration", 0) >= 1.5
            )
        )

    if mode == "morning":
        return (
            momentum.get("time_volume_ratio", 0) >= 1
            and momentum.get("price_vs_vwap_pct", -100) >= 0
            and momentum.get("value_today", 0) >= 100_000_000
            and (
                momentum.get("opening_range_breakout", False)
                or momentum.get("distance_to_breakout_pct", -100) >= -0.5
            )
        )

    return (
        momentum["value_today"] >= 250_000_000
        and (mode == "preopen" or momentum["change_pct"] > 0)
    )


def apply_ml_rerank(rows: list[dict]) -> int:
    from analysis.ml_model import MLAnalyzer, MODEL_ROOT

    covered = 0
    for row in rows:
        ticker = row["ticker"]
        if not (MODEL_ROOT / "random_forest" / f"{ticker}_rf.pkl").is_file():
            continue

        try:
            prediction = MLAnalyzer(ticker).prediksi_arah()
            accuracy = prediction.get("akurasi_test")
            if accuracy is None or accuracy < 52:
                continue
        except Exception:
            continue

        bonus = round((prediction["prob_naik"] - 50) * 0.2, 1)
        momentum = row["momentum"]
        momentum["score"] = min(100.0, max(0.0, round(momentum["score"] + bonus, 1)))
        momentum["status"] = (
            "KUAT" if momentum["score"] >= 70 else "MENARIK" if momentum["score"] >= 45 else "LEMAH"
        )
        momentum["signals"]["ml"] = (
            f"RF naik {prediction['prob_naik']:.0f}% "
            f"(akurasi uji {accuracy:.0f}%, {bonus:+g})"
        )
        row["ml"] = prediction
        row["ml_bonus"] = bonus
        covered += 1
    return covered


def momentum_for_web(
    limit: int = 15,
    max_tickers: int = 1009,
    mode: str = "preopen",
    use_relative_strength: bool = False,
    use_accumulation: bool = False,
    use_sector_heat: bool = False,
    use_sector_news: bool = False,
    use_ml: bool = False,
    use_overnight: bool = False,
) -> dict:
    from analysis.momentum import (
        evaluate_daily_momentum,
        evaluate_morning_momentum,
        evaluate_session2_momentum,
    )
    from data.price_fetcher import fetch_price_history

    limit = max(1, min(limit, 50))
    mode = mode if mode in {"preopen", "morning", "intraday", "session2"} else "preopen"
    universe = load_screener_universe()[:max(1, min(max_tickers, 1200))]
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    session_hour = 14 if now.weekday() == 4 else 13
    session_start = now.replace(
        hour=session_hour,
        minute=0 if session_hour == 14 else 30,
        second=0,
        microsecond=0,
    )
    if mode == "session2" and (now.weekday() >= 5 or now < session_start):
        warning = (
            "Bursa sedang tutup."
            if now.weekday() >= 5
            else f"Sesi 2 belum dimulai. Jalankan kembali setelah {session_start:%H:%M} WIB."
        )
        return {
            "results": [],
            "checked": 0,
            "qualified": 0,
            "mode": mode,
            "ml_covered": 0,
            "overnight_covered": 0,
            "warnings": [warning],
            "errors": [],
        }
    morning_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    if mode == "morning" and (now.weekday() >= 5 or now < morning_start):
        warning = (
            "Bursa sedang tutup."
            if now.weekday() >= 5
            else "Opening Range belum selesai. Jalankan kembali setelah 09:15 WIB."
        )
        return {
            "results": [],
            "checked": 0,
            "qualified": 0,
            "mode": mode,
            "ml_covered": 0,
            "overnight_covered": 0,
            "warnings": [warning],
            "errors": [],
        }
    ihsg_df = None
    warnings = []
    if mode == "preopen" and use_relative_strength:
        try:
            ihsg_df = fetch_price_history("^JKSE")
        except Exception as exc:
            warnings.append(f"RS vs IHSG dilewati: {exc}")
    rows = []
    errors = []
    for ticker in universe:
        try:
            if mode in {"morning", "session2"}:
                intraday = fetch_price_history(ticker, period="60d", interval="5m")
                momentum = (
                    evaluate_morning_momentum(intraday)
                    if mode == "morning"
                    else evaluate_session2_momentum(intraday)
                )
            else:
                momentum = evaluate_daily_momentum(
                    fetch_price_history(ticker),
                    mode=mode,
                    ihsg_df=ihsg_df,
                    use_relative_strength=use_relative_strength,
                    use_accumulation=use_accumulation,
                )
            if passes_momentum_filter(momentum, mode):
                rows.append({"ticker": ticker, "momentum": momentum})
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})

    if rows and (use_sector_heat or use_sector_news or (mode == "preopen" and use_overnight)):
        apply_sector_heat(rows, use_sector_heat, use_sector_news)
        rows = [row for row in rows if passes_momentum_filter(row["momentum"], mode)]

    overnight_covered = 0
    if rows and mode == "preopen" and use_overnight:
        from analysis.overnight import apply_overnight_catalysts

        rows.sort(key=lambda item: item["momentum"]["score"], reverse=True)
        # ponytail: score only displayed shortlist; widen after backtests show missed catalysts.
        overnight_covered = apply_overnight_catalysts(rows[:limit], SENTIMENT_ANALYZER)
        rows = [row for row in rows if passes_momentum_filter(row["momentum"], mode)]

    ml_covered = apply_ml_rerank(rows) if mode == "session2" and use_ml else 0
    if ml_covered:
        rows = [row for row in rows if passes_momentum_filter(row["momentum"], mode)]
    if mode == "session2" and use_ml and rows and not ml_covered:
        warnings.append("ML dilewati: belum ada model RF layak untuk kandidat yang lolos.")

    from analysis.orderflow import apply_orderflow

    orderflow_covered, orderflow_warning = apply_orderflow(rows)
    if orderflow_covered:
        rows = [row for row in rows if passes_momentum_filter(row["momentum"], mode)]
    elif orderflow_warning:
        warnings.append(orderflow_warning)

    from analysis.cross_sectional_ranker import apply_cross_sectional_ranking

    rank_covered, rank_warning = apply_cross_sectional_ranking(rows, mode)
    if rank_covered:
        rows = [row for row in rows if passes_momentum_filter(row["momentum"], mode)]
    elif rank_warning:
        warnings.append(rank_warning)

    rows.sort(
        key=lambda item: (
            item["momentum"]["score"],
            item.get("cross_sectional_rank", {}).get("probability", 0),
            item["momentum"].get("time_volume_ratio") or 0,
        ),
        reverse=True,
    )
    return {
        "results": rows[:limit],
        "checked": len(universe),
        "qualified": len(rows),
        "mode": mode,
        "ml_covered": ml_covered,
        "orderflow_covered": orderflow_covered,
        "cross_sectional_covered": rank_covered,
        "overnight_covered": overnight_covered,
        "warnings": warnings,
        "errors": errors[:10],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = "/index.html" if self.path == "/" else self.path.split("?", 1)[0]
        if path == "/api/sector-news":
            from analysis.sector_news import load_sector_news

            self._json(load_sector_news())
            return
        if path == "/api/global-market":
            from analysis.global_market import fetch_global_market

            self._json(fetch_global_market())
            return
        file_path = (STATIC / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(STATIC)) or not file_path.is_file():
            self.send_error(404)
            return

        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path not in {"/api/analyze", "/api/screen", "/api/momentum"}:
            self.send_error(404)
            return

        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or "{}")
            if self.path == "/api/screen":
                self._json(screen_for_web(
                    limit=int(payload.get("limit", 15)),
                    max_tickers=int(payload.get("maxTickers", 1009)),
                ))
                return
            if self.path == "/api/momentum":
                self._json(momentum_for_web(
                    limit=int(payload.get("limit", 15)),
                    max_tickers=int(payload.get("maxTickers", 1009)),
                    mode=str(payload.get("mode", "preopen")),
                    use_relative_strength=bool(payload.get("relativeStrength")),
                    use_accumulation=bool(payload.get("accumulation")),
                    use_sector_heat=bool(payload.get("sectorHeat")),
                    use_sector_news=bool(payload.get("sectorNews")),
                    use_ml=bool(payload.get("ml")),
                    use_overnight=bool(payload.get("overnightCatalyst")),
                ))
                return

            tickers = [t.strip().upper() for t in payload.get("tickers", "").replace(",", " ").split() if t.strip()]
            if not tickers:
                raise ValueError("Masukkan minimal satu kode saham.")

            results = []
            for ticker in tickers[:10]:
                try:
                    results.append({"ok": True, "data": analyze_for_web(ticker, payload.get("options", {}))})
                except Exception as exc:
                    results.append({"ok": False, "ticker": ticker, "error": str(exc)})
            self._json({"results": results})
        except Exception as exc:
            self._json({"error": str(exc)}, status=400)

    def _json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    from threading import Thread

    from analysis.sector_news import run_sector_news_scheduler

    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8002"))
    Thread(
        target=run_sector_news_scheduler,
        args=(SENTIMENT_ANALYZER,),
        daemon=True,
    ).start()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Stock Analyzer UI: http://{host}:{port}")
    server.serve_forever()
