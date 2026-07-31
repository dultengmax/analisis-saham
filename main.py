"""
Stock Analyzer - CLI utama.

Contoh pemakaian:
    python main.py BBCA
    python main.py BBCA TLKM BMRI --backtest
"""
import argparse
from tabulate import tabulate

from data.price_fetcher import fetch_price_history, fetch_quick_info
from analysis.technical import evaluate_technical
from analysis.fundamental import evaluate_fundamental
from analysis.scorer import compute_composite, build_full_report
from analysis.monte_carlo import run_monte_carlo
from analysis.bootstrapping import run_bootstrapping
from analysis.garch import run_garch
from analysis.atr import run_atr
from analysis.vwap import run_vwap
from analysis.sentiment import SentimenAnalyzer
from analysis.bandarmologi import BandarmologiAnalyzer
from analysis.liquidity import evaluate_liquidity
from analysis.ml_model import MLAnalyzer
from backtest.backtester import run_backtest


SENTIMENT_ANALYZER = SentimenAnalyzer()


def analyze_ticker(
    ticker: str,
    do_backtest: bool = False,
    do_monte_carlo: bool = False,
    do_bootstrapping: bool = False,
    do_garch: bool = False,
    do_atr: bool = False,
    do_vwap: bool = False,
    do_sentiment: bool = False,
    do_ml: bool = False,
) -> dict:
    print(f"\n{'='*60}\nMenganalisa {ticker.upper()} ...\n{'='*60}")

    quick_info = fetch_quick_info(ticker)
    price_df = fetch_price_history(ticker)

    technical_result = evaluate_technical(price_df)
    fundamental_result = evaluate_fundamental(quick_info)
    sentiment_result = (
        SENTIMENT_ANALYZER.analisis(ticker) if do_sentiment else None
    )
    bandarmology_result = BandarmologiAnalyzer(ticker, price_df).analisis()
    liquidity_result = evaluate_liquidity(price_df)
    ml_result = MLAnalyzer(ticker).prediksi() if do_ml else None
    composite = compute_composite(
        technical_result,
        fundamental_result,
        sentiment_result,
        bandarmology_result,
        liquidity_result,
        ml_result,
    )
    report = build_full_report(
        ticker,
        quick_info,
        technical_result,
        fundamental_result,
        composite,
        sentiment_result,
        bandarmology_result,
        liquidity_result,
        ml_result,
    )

    print_report(report)

    if do_backtest:
        bt = run_backtest(price_df)
        print_backtest(ticker, bt)
        report["backtest"] = bt

    if do_monte_carlo:
        mc = run_monte_carlo(price_df)
        print_monte_carlo(ticker, mc)
        report["monte_carlo"] = mc

    if do_bootstrapping:
        bs = run_bootstrapping(price_df)
        print_bootstrapping(ticker, bs)
        report["bootstrapping"] = bs

    if do_garch:
        garch = run_garch(price_df)
        print_garch(ticker, garch)
        report["garch"] = garch

    if do_atr:
        atr = run_atr(price_df)
        print_atr(ticker, atr)
        report["atr"] = atr

    if do_vwap:
        vwap = run_vwap(price_df)
        print_vwap(ticker, vwap)
        report["vwap"] = vwap

    return report


def print_report(report: dict):
    print(f"\nEmiten     : {report['ticker']} - {report.get('name') or '-'}")
    print(f"Sektor     : {report.get('sector') or '-'}")
    print(f"Harga Now  : {report.get('last_price')}")

    print(f"\n[TEKNIKAL] Skor: {report['technical']['score']}/100  (RSI: {report['technical']['rsi']})")
    for k, v in report["technical"]["signals"].items():
        print(f"  - {k}: {v}")

    fscore = report["fundamental"]["score"]
    print(f"\n[FUNDAMENTAL] Skor: {fscore if fscore is not None else 'N/A'}/100")
    for k, v in report["fundamental"]["signals"].items():
        print(f"  - {k}: {v}")
    if report["fundamental"]["missing_data"]:
        print(f"  (data tidak tersedia: {', '.join(report['fundamental']['missing_data'])})")

    liquidity = report["liquidity"]
    print(f"\n[LIKUIDITAS] Skor: {liquidity['score']}/100")
    print(f"  Status       : {liquidity['status']}")
    print(f"  Avg value 20D: Rp {liquidity['avg_value_20d']:,.0f}")
    print(f"  Avg vol 20D  : {liquidity['avg_volume_20d']:,.0f}")

    sentiment = report.get("sentiment")
    if sentiment:
        print(f"\n[SENTIMEN BERITA] Skor: {sentiment['skor']}/100")
        print(f"  Status       : {sentiment['status']}")
        print(f"  Total berita : {sentiment['total']}")
        print(
            f"  Positif/Negatif/Netral : "
            f"{sentiment['positif']}/{sentiment['negatif']}/{sentiment['netral']}"
        )
        print(f"  Confidence   : {sentiment['confidence']:.1%}")
        for item in sentiment["detail"]:
            print(
                f"  - {item['sentimen']} ({item['confidence']:.1%}) "
                f"- {item['judul']}"
            )

    ml = report.get("ml")
    if ml:
        print(f"\n[MACHINE LEARNING] Skor: {ml['skor']}/100")
        print(
            f"  Prediksi besok : {ml['arah']} "
            f"({ml['probabilitas']:.1f}%)"
        )
        print(f"  Prob naik/turun: {ml['prob_naik']:.1f}%/{ml['prob_turun']:.1f}%")
        print(f"  Akurasi test   : {ml.get('akurasi_test') or 'N/A'}%")
        print(f"  Konsensus model: {ml.get('konsensus', 'UNKNOWN')}")
        if ml.get("harga_7hari"):
            print(f"  Harga +7 hari  : Rp {ml['harga_7hari']:,.0f}")
            for item in ml["per_hari"]:
                print(
                    f"  +{item['hari']}: Rp {item['harga']:,.0f} "
                    f"({item['perubahan_pct']:+.2f}%)"
                )
        if ml.get("error"):
            print(f"  Catatan        : {ml['error']}")

    bandarmology = report["bandarmology"]
    print(f"\n[BANDARMOLOGI] Skor: {bandarmology['skor']}/100")
    print(f"  Fase       : {bandarmology['fase']}")
    print(f"  OBV Trend  : {bandarmology['obv']['obv_trend'].upper()}")
    print(
        f"  MFI        : {bandarmology['mfi']['mfi']} - "
        f"{bandarmology['mfi']['status']}"
    )
    print(f"  Divergensi : {bandarmology['obv']['divergensi'] or 'Tidak ada'}")
    for label, items in (
        ("AKUMULASI", bandarmology["akumulasi_3hari"]),
        ("DISTRIBUSI", bandarmology["distribusi_3hari"]),
    ):
        for item in items:
            print(
                f"  - {label} {item['tanggal']} | Harga {item['harga']} | "
                f"Vol {item['vol_ratio']}x | {', '.join(item['alasan'])}"
            )

    print(f"\n>>> SKOR KOMPOSIT : {report['composite_score']}/100")
    print(f">>> REKOMENDASI   : {report['recommendation']}")
    print(f">>> ALASAN        : {report['reason']}")
    if report.get("red_flags"):
        print(f">>> RED FLAGS     : {', '.join(report['red_flags'])}")
    if report.get("note"):
        print(f">>> CATATAN       : {report['note']}")


def print_backtest(ticker: str, bt: dict):
    print(f"\n--- Backtest historis {ticker.upper()} (1 tahun terakhir) ---")
    if bt["total_trades"] == 0:
        print("  Tidak ada trade yang tercatat pada rule ini di periode data.")
        return
    print(f"  Total trade : {bt['total_trades']}")
    print(f"  Win rate    : {bt['win_rate']}%")
    print(f"  Avg return  : {bt['avg_return_pct']}% per trade")
    print(tabulate(bt["trades"][-5:], headers="keys", tablefmt="simple"))
    print("  (menampilkan 5 trade terakhir)")


def print_monte_carlo(ticker: str, mc: dict):
    print(f"\n--- Monte Carlo probabilitas {ticker.upper()} ---")
    print(f"  Simulasi      : {mc['simulations']}")
    print(f"  Horizon       : {mc['horizon_days']} hari")
    print(f"  Prob. return > 0% : {mc['probability_positive_return'] * 100:.1f}%")
    print(f"  Prob. target {mc['target_return_pct']}% : {mc['probability_target_return'] * 100:.1f}%")
    print(f"  Expected return : {mc['expected_return_pct']:.2f}%")
    print(f"  Expected price  : {mc['expected_terminal_price']:.2f}")
    print("\n  [Distribusi return simulasi]")
    print(mc["return_histogram"])
    print("\n  [Tren harga historis]")
    print(mc["price_trend"])


def print_bootstrapping(ticker: str, bs: dict):
    print(f"\n--- Bootstrapping probabilitas {ticker.upper()} ---")
    print(f"  Simulasi      : {bs['simulations']}")
    print(f"  Horizon       : {bs['horizon_days']} hari")
    print(f"  Prob. return > 0% : {bs['probability_positive_return'] * 100:.1f}%")
    print(f"  Prob. target {bs['target_return_pct']}% : {bs['probability_target_return'] * 100:.1f}%")
    print(f"  Expected return : {bs['expected_return_pct']:.2f}%")
    print(f"  Expected price  : {bs['expected_terminal_price']:.2f}")
    print("\n  [Distribusi return hasil bootstrapping]")
    print(bs["return_histogram"])


def print_garch(ticker: str, garch: dict):
    print(f"\n--- GARCH volatilitas {ticker.upper()} ---")
    print(f"  Horizon       : {garch['horizon_days']} hari")
    print(f"  Forecast volatility : {garch['forecast_volatility']:.4f}")
    print(f"  Current volatility  : {garch['current_volatility']:.4f}")
    print(f"  Alpha + Beta        : {garch['alpha_plus_beta']:.3f}")


def print_atr(ticker: str, atr: dict):
    print(f"\n--- ATR volatilitas {ticker.upper()} ---")
    print(f"  ATR          : {atr['atr']:.4f}")
    print(f"  ATR change   : {atr['atr_change_pct']:.2f}%")
    print(f"  Period       : {atr['period']}")


def print_vwap(ticker: str, vwap: dict):
    print(f"\n--- VWAP intraday {ticker.upper()} ---")
    print(f"  VWAP         : {vwap['vwap']:.4f}")
    print(f"  Price vs VWAP: {vwap['price_vs_vwap_pct']:.2f}%")


def main():
    parser = argparse.ArgumentParser(description="Stock Analyzer - Saham Indonesia")
    parser.add_argument("tickers", nargs="+", help="Kode saham, contoh: BBCA TLKM BMRI")
    parser.add_argument("--backtest", action="store_true",
                         help="Jalankan backtest sinyal teknikal historis")
    parser.add_argument("--monte-carlo", action="store_true",
                         help="Jalankan simulasi Monte Carlo untuk probabilitas return")
    parser.add_argument("--bootstrap", action="store_true",
                         help="Jalankan analisis bootstrapping untuk probabilitas return")
    parser.add_argument("--garch", action="store_true",
                         help="Jalankan estimasi volatilitas GARCH")
    parser.add_argument("--atr", action="store_true",
                         help="Jalankan analisis ATR untuk volatilitas harian")
    parser.add_argument("--vwap", action="store_true",
                         help="Jalankan analisis VWAP untuk trader intraday")
    parser.add_argument("--sentiment", action="store_true",
                         help="Analisis berita dengan model FinBERT lokal")
    parser.add_argument("--ml", action="store_true",
                         help="Prediksi Random Forest dan LSTM")
    args = parser.parse_args()

    all_reports = []
    for ticker in args.tickers:
        try:
            report = analyze_ticker(
                ticker,
                do_backtest=args.backtest,
                do_monte_carlo=args.monte_carlo,
                do_bootstrapping=args.bootstrap,
                do_garch=args.garch,
                do_atr=args.atr,
                do_vwap=args.vwap,
                do_sentiment=args.sentiment,
                do_ml=args.ml,
            )
            all_reports.append(report)
        except Exception as e:
            print(f"[ERROR] Gagal menganalisa {ticker}: {e}")

    if len(all_reports) > 1:
        print(f"\n{'='*60}\nRINGKASAN\n{'='*60}")
        summary = [
            {
                "Ticker": r["ticker"],
                "Skor Teknikal": r["technical"]["score"],
                "Skor Fundamental": r["fundamental"]["score"] or "N/A",
                "Skor Sentimen": (
                    r["sentiment"]["skor"] if r.get("sentiment") else "N/A"
                ),
                "Skor Likuiditas": r["liquidity"]["score"],
                "Skor ML": r["ml"]["skor"] if r.get("ml") else "N/A",
                "Skor Bandarmologi": r["bandarmology"]["skor"],
                "Skor Komposit": r["composite_score"],
                "Rekomendasi": r["recommendation"],
            }
            for r in all_reports
        ]
        print(tabulate(summary, headers="keys", tablefmt="grid"))


if __name__ == "__main__":
    main()
