"""Web UI ringan untuk Stock Analyzer."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def analyze_for_web(ticker: str, options: dict) -> dict:
    from analysis.atr import run_atr
    from analysis.bandarmologi import BandarmologiAnalyzer
    from analysis.bootstrapping import run_bootstrapping
    from analysis.fundamental import evaluate_fundamental
    from analysis.garch import run_garch
    from analysis.liquidity import evaluate_liquidity
    from analysis.monte_carlo import run_monte_carlo
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
    composite = compute_composite(
        technical, fundamental, sentiment, bandarmology, liquidity
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


def apply_sector_heat(rows: list[dict]) -> None:
    from data.price_fetcher import fetch_quick_info

    sectors = {}
    for row in rows:
        info = fetch_quick_info(row["ticker"])
        sector = info.get("sector") or "Unknown"
        row["sector"] = sector
        sectors.setdefault(sector, []).append(row)

    for sector_rows in sectors.values():
        avg_change = sum(item["momentum"]["change_pct"] for item in sector_rows) / len(sector_rows)
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
                    f"sektor panas: {row['sector']} (+{bonus})"
                )


def momentum_for_web(
    limit: int = 15,
    max_tickers: int = 1009,
    mode: str = "preopen",
    use_relative_strength: bool = False,
    use_accumulation: bool = False,
    use_sector_heat: bool = False,
) -> dict:
    from analysis.momentum import evaluate_daily_momentum, evaluate_session2_momentum
    from data.price_fetcher import fetch_price_history

    limit = max(1, min(limit, 50))
    mode = mode if mode in {"preopen", "intraday", "session2"} else "preopen"
    universe = load_screener_universe()[:max(1, min(max_tickers, 1200))]
    ihsg_df = (
        fetch_price_history("^JKSE")
        if mode == "preopen" and use_relative_strength
        else None
    )
    rows = []
    errors = []
    for ticker in universe:
        try:
            if mode == "session2":
                momentum = evaluate_session2_momentum(
                    fetch_price_history(ticker, period="5d", interval="5m")
                )
            else:
                momentum = evaluate_daily_momentum(
                    fetch_price_history(ticker),
                    mode=mode,
                    ihsg_df=ihsg_df,
                    use_relative_strength=use_relative_strength,
                    use_accumulation=use_accumulation,
                )
            if (
                momentum["score"] >= 45
                and momentum["value_today"] >= 250_000_000
                and (mode == "preopen" or momentum["change_pct"] > 0)
                and (
                    mode != "session2"
                    or momentum.get("session1_pct", 0) < 8
                    or momentum.get("session2_pct", 0) >= 3
                )
            ):
                rows.append({"ticker": ticker, "momentum": momentum})
        except Exception as exc:
            errors.append({"ticker": ticker, "error": str(exc)})

    if use_sector_heat and rows:
        apply_sector_heat(rows)

    rows.sort(key=lambda item: item["momentum"]["score"], reverse=True)
    return {
        "results": rows[:limit],
        "checked": len(universe),
        "qualified": len(rows),
        "mode": mode,
        "errors": errors[:10],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = "/index.html" if self.path == "/" else self.path.split("?", 1)[0]
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
    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8002"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Stock Analyzer UI: http://{host}:{port}")
    server.serve_forever()
