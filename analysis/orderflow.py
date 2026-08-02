"""Overlay orderbook/broker flow untuk momentum jika data lokal tersedia."""
from pathlib import Path

import pandas as pd


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "broker_orderbook.csv"


def _number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_ticker(value: str) -> str:
    return str(value).strip().upper().removesuffix(".JK")


def load_orderflow(path: Path = DATA_PATH) -> dict[str, dict]:
    if not path.is_file():
        return {}
    frame = pd.read_csv(path)
    if "ticker" not in frame:
        raise ValueError("broker_orderbook.csv wajib punya kolom ticker")
    return {
        _normalize_ticker(row["ticker"]): row.to_dict()
        for _, row in frame.iterrows()
        if _normalize_ticker(row["ticker"])
    }


def score_orderflow(row: dict) -> dict:
    bid = _number(row.get("bid_volume"))
    offer = _number(row.get("offer_volume"))
    foreign = _number(row.get("foreign_net_buy"))
    broker = _number(row.get("broker_accumulation"))
    frequency = _number(row.get("transaction_frequency"))
    spike = _number(row.get("running_trade_spike"))

    imbalance = (bid - offer) / (bid + offer) if bid + offer else 0.0
    bonus = 0.0
    bonus += 6 if imbalance >= 0.25 else 3 if imbalance >= 0.1 else -6 if imbalance <= -0.25 else -3 if imbalance <= -0.1 else 0
    bonus += 4 if foreign > 0 else -4 if foreign < 0 else 0
    bonus += 4 if broker > 0 else -4 if broker < 0 else 0
    bonus += 3 if frequency >= 500 else 1 if frequency >= 200 else 0
    bonus += 3 if spike >= 2 else 1 if spike >= 1.2 else 0

    return {
        "bonus": max(-15.0, min(15.0, round(bonus, 1))),
        "bid_offer_imbalance": round(imbalance, 3),
        "foreign_net_buy": foreign,
        "broker_accumulation": broker,
        "transaction_frequency": frequency,
        "running_trade_spike": spike,
    }


def apply_orderflow(rows: list[dict], path: Path = DATA_PATH) -> tuple[int, str | None]:
    try:
        snapshot = load_orderflow(path)
    except Exception as exc:
        return 0, f"Broker/orderbook dilewati: {exc}"
    if not snapshot:
        return 0, "Broker/orderbook dilewati: data/broker_orderbook.csv belum ada atau kosong."

    covered = 0
    for row in rows:
        flow = snapshot.get(_normalize_ticker(row["ticker"]))
        if not flow:
            continue
        result = score_orderflow(flow)
        bonus = result["bonus"]
        momentum = row["momentum"]
        momentum["score"] = min(100.0, max(0.0, round(momentum["score"] + bonus, 1)))
        momentum["status"] = "KUAT" if momentum["score"] >= 70 else "MENARIK" if momentum["score"] >= 45 else "LEMAH"
        row["orderflow"] = result
        row["orderflow_bonus"] = bonus
        momentum["signals"]["orderflow"] = (
            f"orderflow {bonus:+g}: imbalance {result['bid_offer_imbalance']:+.2f}, "
            f"foreign {result['foreign_net_buy']:+,.0f}, broker {result['broker_accumulation']:+,.0f}, "
            f"freq {result['transaction_frequency']:,.0f}, running {result['running_trade_spike']:.1f}x"
        )
        covered += 1
    return covered, None
