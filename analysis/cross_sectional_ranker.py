"""Rerank momentum lintas saham dari histori hasil screener."""
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


HISTORY_PATH = Path(__file__).resolve().parents[1] / "data" / "momentum_rank_history.csv"
MIN_SAMPLES = 30
FEATURES = [
    "score",
    "change_pct",
    "volume_ratio",
    "time_volume_ratio",
    "value_today",
    "session2_value",
    "price_vs_vwap_pct",
    "close_position",
    "breakout_20d",
    "relative_strength",
    "accumulation_score",
    "fibonacci_bonus",
    "sector_heat_bonus",
    "sector_news_bonus",
    "overnight_bonus",
    "orderflow_bonus",
]


def _target(history: pd.DataFrame) -> pd.Series:
    if "target" in history:
        return history["target"].astype(int)
    if "is_top_gainer" in history:
        return history["is_top_gainer"].astype(int)
    if "next_return_pct" in history:
        return (history["next_return_pct"].astype(float) >= 5).astype(int)
    raise ValueError("kolom target/is_top_gainer/next_return_pct belum ada")


def _frame(rows: list[dict]) -> pd.DataFrame:
    records = []
    for row in rows:
        momentum = row["momentum"]
        record = {key: momentum.get(key, 0) for key in FEATURES}
        record.update({
            "sector_heat_bonus": row.get("sector_heat_bonus", 0),
            "sector_news_bonus": row.get("sector_news_bonus", 0),
            "overnight_bonus": row.get("overnight_bonus", 0),
            "orderflow_bonus": row.get("orderflow_bonus", 0),
        })
        records.append(record)
    return pd.DataFrame(records).reindex(columns=FEATURES).fillna(0).astype(float)


def apply_cross_sectional_ranking(
    rows: list[dict],
    mode: str,
    history_path: Path = HISTORY_PATH,
) -> tuple[int, str | None]:
    """Apply model ranking across current candidates. Returns covered count + warning."""
    if not rows:
        return 0, None
    if not history_path.is_file():
        return 0, "Ranking lintas saham dilewati: data/momentum_rank_history.csv belum ada."

    try:
        history = pd.read_csv(history_path)
        if "mode" in history:
            mode_history = history[history["mode"] == mode]
            history = mode_history if len(mode_history) >= MIN_SAMPLES else history
        y = _target(history)
        X = history.reindex(columns=FEATURES).fillna(0).astype(float)
        valid = y.notna()
        X, y = X[valid], y[valid].astype(int)
        if len(X) < MIN_SAMPLES or y.nunique() < 2:
            return 0, "Ranking lintas saham dilewati: histori belum cukup atau target satu kelas."

        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=500, class_weight="balanced"),
        )
        model.fit(X, y)
        probabilities = model.predict_proba(_frame(rows))[:, 1] * 100
    except Exception as exc:
        return 0, f"Ranking lintas saham dilewati: {exc}"

    for row, probability in zip(rows, probabilities):
        bonus = max(-10.0, min(10.0, round((float(probability) - 50) * 0.25, 1)))
        momentum = row["momentum"]
        momentum["score"] = min(100.0, max(0.0, round(momentum["score"] + bonus, 1)))
        momentum["status"] = "KUAT" if momentum["score"] >= 70 else "MENARIK" if momentum["score"] >= 45 else "LEMAH"
        row["cross_sectional_rank"] = {
            "probability": round(float(probability), 1),
            "bonus": bonus,
            "samples": len(X),
        }
        row["cross_sectional_bonus"] = bonus
        momentum["signals"]["cross_sectional_ml"] = (
            f"ranking lintas saham {probability:.0f}% ({bonus:+g})"
        )
    return len(rows), None
