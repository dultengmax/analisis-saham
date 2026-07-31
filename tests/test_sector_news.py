import unittest
from datetime import datetime
from unittest.mock import patch

import web_app
from analysis.sector_news import JAKARTA_TZ, build_sector_news_snapshot


class FakeAnalyzer:
    def ambil_berita_google(self, query, max=8, days=1):
        if "batu bara" in query:
            return ["Harga Komoditas Naik, Saham Energi Menguat - Media Uji"]
        return ["Pelaku Pasar Menanti Perdagangan Hari Ini - Media Uji"]


class SectorNewsTestCase(unittest.TestCase):
    def test_snapshot_is_read_by_momentum_sector_score(self):
        snapshot = build_sector_news_snapshot(
            FakeAnalyzer(),
            datetime(2026, 7, 29, 6, 0, tzinfo=JAKARTA_TZ),
        )
        energy = snapshot["sectors"]["Energy"]

        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(energy["status"], "POSITIF")
        self.assertGreater(energy["score"], 50)

        snapshot["market_date"] = datetime.now(JAKARTA_TZ).date().isoformat()
        rows = [{
            "ticker": "TEST",
            "momentum": {
                "mode": "preopen",
                "score": 65.0,
                "change_pct": 2.0,
                "value_today": 1_000_000_000,
                "signals": {},
            },
        }]
        with patch(
            "data.price_fetcher.fetch_quick_info",
            return_value={"sector": "Energy", "industry": "Coal"},
        ), patch("analysis.sector_news.load_sector_news", return_value=snapshot):
            web_app.apply_sector_heat(
                rows,
                use_price_heat=False,
                use_sector_news=True,
            )

        self.assertGreater(rows[0]["momentum"]["score"], 65)
        self.assertEqual(rows[0]["momentum"]["status"], "KUAT")
        self.assertIn("sector_news", rows[0]["momentum"]["signals"])


if __name__ == "__main__":
    unittest.main()
