"""Training model ML per emiten untuk dijalankan manual atau dari cron."""
import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.ml_model import MLAnalyzer  # noqa: E402


DEFAULT_WATCHLIST = ["DEWA", "BBCA", "TLKM", "ASII", "GOTO"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="*", default=DEFAULT_WATCHLIST)
    parser.add_argument(
        "--rf-only",
        action="store_true",
        help="Latih Random Forest saja tanpa LSTM.",
    )
    args = parser.parse_args()

    for ticker in args.tickers:
        kode = ticker.strip().upper()
        try:
            print(f"[ML] Training {kode}...")
            analyzer = MLAnalyzer(kode)
            rf = analyzer.train_random_forest()
            print(f"[ML] RF {kode}: akurasi test {rf['akurasi']}%")
            if not args.rf_only:
                lstm = analyzer.train_lstm()
                print(f"[ML] LSTM {kode}: MAE {lstm['mae']}")
        except Exception as exc:
            print(f"[ML] GAGAL {kode}: {exc}")


if __name__ == "__main__":
    main()
