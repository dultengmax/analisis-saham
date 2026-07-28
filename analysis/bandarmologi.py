"""Deteksi akumulasi/distribusi berbasis harga dan volume."""
import numpy as np
import pandas as pd


class BandarmologiAnalyzer:
    def __init__(self, kode: str, df: pd.DataFrame | None = None):
        self.kode = kode.strip().upper()
        self.df = pd.DataFrame()
        self.error = None
        try:
            if df is None:
                from data.price_fetcher import fetch_price_history

                source = fetch_price_history(self.kode, period="3mo")
            else:
                source = df.copy()
            if source.empty:
                raise ValueError("Data harga kosong")
            if not isinstance(source.index, pd.DatetimeIndex):
                raise ValueError("Index data harga harus berupa tanggal")
            cutoff = source.index.max() - pd.DateOffset(months=3)
            self.df = source.loc[source.index >= cutoff].copy()
            self._hitung_semua()
        except Exception as exc:
            self.error = str(exc)

    def _hitung_semua(self):
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(self.df.columns):
            raise ValueError(f"Kolom OHLCV tidak lengkap: {sorted(required - set(self.df.columns))}")

        df = self.df
        df["vol_ma20"] = df["Volume"].rolling(20).mean()
        df["vol_ratio"] = df["Volume"] / df["vol_ma20"]
        df["body"] = (df["Close"] - df["Open"]).abs()
        df["upper_shadow"] = df["High"] - df[["Close", "Open"]].max(axis=1)
        df["lower_shadow"] = df[["Close", "Open"]].min(axis=1) - df["Low"]
        df["range"] = df["High"] - df["Low"]
        df["bullish"] = df["Close"] > df["Open"]
        df["close_pos"] = (
            (df["Close"] - df["Low"]) / df["range"].replace(0, np.nan)
        )
        df["price_change_pct"] = df["Close"].pct_change().abs() * 100

    @staticmethod
    def _record(tanggal, row, score_key: str, score: int, alasan: list[str]) -> dict:
        vol_ratio = 0.0 if pd.isna(row["vol_ratio"]) else float(row["vol_ratio"])
        return {
            "tanggal": pd.Timestamp(tanggal).date().isoformat(),
            "harga": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
            "vol_ratio": round(vol_ratio, 2),
            score_key: score,
            "alasan": alasan,
        }

    def deteksi_akumulasi(self) -> list[dict]:
        if self.error or self.df.empty:
            return []

        signals = []
        for tanggal, row in self.df.iterrows():
            score, alasan = 0, []
            range_value = float(row["range"])
            lower_ratio = float(row["lower_shadow"]) / range_value if range_value > 0 else 0

            if row["vol_ratio"] > 2 and row["price_change_pct"] < 2:
                score += 25
                alasan.append("Volume besar, harga stagnan")
            if lower_ratio > 0.6:
                score += 20
                alasan.append("Ekor bawah panjang")
            if not row["bullish"] and row["vol_ratio"] < 0.5:
                score += 15
                alasan.append("Turun dengan volume kecil")
            if row["close_pos"] > 0.7:
                score += 20
                alasan.append("Tutup dekat harga tertinggi")

            if score >= 30:
                signals.append(
                    self._record(
                        tanggal, row, "skor_akumulasi", score, alasan
                    )
                )
        return signals

    def deteksi_distribusi(self) -> list[dict]:
        if self.error or self.df.empty:
            return []

        signals = []
        for tanggal, row in self.df.iterrows():
            score, alasan = 0, []
            range_value = float(row["range"])
            upper_ratio = float(row["upper_shadow"]) / range_value if range_value > 0 else 0

            if row["vol_ratio"] > 2 and not row["bullish"]:
                score += 30
                alasan.append("Volume besar saat harga turun")
            if upper_ratio > 0.6:
                score += 25
                alasan.append("Ekor atas panjang")
            if row["bullish"] and row["vol_ratio"] < 0.5:
                score += 15
                alasan.append("Naik dengan volume kecil")
            if row["close_pos"] < 0.3:
                score += 20
                alasan.append("Tutup dekat harga terendah")

            if score >= 30:
                signals.append(
                    self._record(
                        tanggal, row, "skor_distribusi", score, alasan
                    )
                )
        return signals

    def hitung_obv(self) -> dict:
        default = {"obv_sekarang": 0, "obv_trend": "unknown", "divergensi": None}
        if self.error or len(self.df) < 2:
            return default

        direction = np.sign(self.df["Close"].diff()).fillna(0)
        obv = (direction * self.df["Volume"]).cumsum()
        window = min(20, len(self.df))
        price_delta = float(self.df["Close"].iloc[-1] - self.df["Close"].iloc[-window])
        obv_delta = float(obv.iloc[-1] - obv.iloc[-window])
        trend = "naik" if obv_delta >= 0 else "turun"
        divergence = None
        if price_delta < 0 < obv_delta:
            divergence = "BULLISH DIVERGENCE - Harga turun tetapi OBV naik"
        elif price_delta > 0 > obv_delta:
            divergence = "BEARISH DIVERGENCE - Harga naik tetapi OBV turun"

        return {
            "obv_sekarang": int(round(obv.iloc[-1])),
            "obv_trend": trend,
            "divergensi": divergence,
        }

    def hitung_mfi(self, period: int = 14) -> dict:
        default = {"mfi": 50.0, "status": "ERROR"}
        if self.error or len(self.df) < 2:
            return default

        typical_price = (
            self.df["High"] + self.df["Low"] + self.df["Close"]
        ) / 3
        money_flow = typical_price * self.df["Volume"]
        positive = money_flow.where(typical_price.diff() > 0, 0).tail(period).sum()
        negative = money_flow.where(typical_price.diff() < 0, 0).tail(period).sum()

        if negative == 0:
            mfi = 100.0 if positive > 0 else 50.0
        else:
            mfi = 100 - (100 / (1 + positive / negative))
        status = (
            "OVERBOUGHT - dana besar mulai keluar"
            if mfi > 80
            else "OVERSOLD - dana besar mulai masuk"
            if mfi < 20
            else "NORMAL"
        )
        return {"mfi": round(float(mfi), 1), "status": status}

    def _default_result(self) -> dict:
        return {
            "skor": 50.0,
            "fase": "ERROR",
            "obv": {
                "obv_sekarang": 0,
                "obv_trend": "unknown",
                "divergensi": None,
            },
            "mfi": {"mfi": 50.0, "status": "ERROR"},
            "akumulasi_3hari": [],
            "distribusi_3hari": [],
        }

    def analisis(self) -> dict:
        try:
            if self.error:
                raise ValueError(self.error)

            obv = self.hitung_obv()
            mfi = self.hitung_mfi()
            recent_dates = {
                pd.Timestamp(index).date().isoformat()
                for index in self.df.tail(3).index
            }
            akumulasi = [
                item
                for item in self.deteksi_akumulasi()
                if item["tanggal"] in recent_dates
            ]
            distribusi = [
                item
                for item in self.deteksi_distribusi()
                if item["tanggal"] in recent_dates
            ]

            score = 50
            score += 15 if obv["obv_trend"] == "naik" else -15
            if obv["divergensi"]:
                score += 20 if obv["divergensi"].startswith("BULLISH") else -20
            if mfi["mfi"] < 20:
                score += 15
            elif mfi["mfi"] > 80:
                score -= 15

            if len(akumulasi) > len(distribusi):
                score += 10
                fase = "AKUMULASI"
            elif len(distribusi) > len(akumulasi):
                score -= 10
                fase = "DISTRIBUSI"
            else:
                fase = "TIDAK JELAS"

            return {
                "skor": round(float(min(100, max(0, score))), 1),
                "fase": fase,
                "obv": obv,
                "mfi": mfi,
                "akumulasi_3hari": akumulasi,
                "distribusi_3hari": distribusi,
            }
        except Exception as exc:
            print(f"[BANDARMOLOGI] Error: {exc}")
            return self._default_result()
