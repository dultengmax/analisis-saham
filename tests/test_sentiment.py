import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from analysis.sentiment import SentimenAnalyzer


class SentimenAnalyzerTestCase(unittest.TestCase):
    def test_hitung_skor(self):
        analyzer = SentimenAnalyzer()

        result = analyzer.hitung_skor(
            [
                {"label": "positive", "score": 0.9},
                {"label": "positive", "score": 0.8},
                {"label": "negative", "score": 0.7},
                {"label": "neutral", "score": 0.6},
            ]
        )

        self.assertEqual(result["skor"], 62.5)
        self.assertEqual(result["status"], "NETRAL")
        self.assertEqual(result["positif"], 2)
        self.assertEqual(result["negatif"], 1)
        self.assertEqual(result["netral"], 1)
        self.assertEqual(result["confidence"], 0.75)

    def test_hitung_skor_weights_confidence(self):
        analyzer = SentimenAnalyzer()

        result = analyzer.hitung_skor(
            [
                {"label": "positive", "score": 0.55},
                {"label": "negative", "score": 0.95},
            ]
        )

        self.assertEqual(result["skor"], 40.0)
        self.assertEqual(result["status"], "NETRAL")

    def test_news_date_filters(self):
        cutoff = datetime(2026, 7, 1, tzinfo=timezone.utc)
        recent = SimpleNamespace(published_parsed=(2026, 7, 10, 8, 0, 0, 0, 0, 0))
        old = SimpleNamespace(published_parsed=(2026, 6, 10, 8, 0, 0, 0, 0, 0))

        self.assertTrue(SentimenAnalyzer._entry_is_recent(recent, cutoff))
        self.assertFalse(SentimenAnalyzer._entry_is_recent(old, cutoff))
        self.assertEqual(
            SentimenAnalyzer._kontan_date("Senin, 27 Juli 2026 / 12:10 WIB"),
            datetime(2026, 7, 27, tzinfo=timezone.utc),
        )

    def test_analisis_deduplicates_and_keeps_headlines_aligned(self):
        analyzer = SentimenAnalyzer()
        analyzer.ambil_berita_google = Mock(
            return_value=[
                "Laba BBCA tumbuh kuat tahun ini - Kontan",
                "BBCA membagikan dividen interim",
            ]
        )
        analyzer.ambil_berita_kontan = Mock(
            return_value=[
                "Laba BBCA tumbuh kuat tahun ini",
                "Risiko kredit perbankan meningkat",
            ]
        )
        analyzer.analisis_sentimen = Mock(
            return_value=[
                {"label": "positive", "score": 0.95},
                {"label": "positive", "score": 0.85},
                {"label": "negative", "score": 0.75},
            ]
        )

        result = analyzer.analisis("BBCA")

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["periode_hari"], 30)
        self.assertEqual(
            [item["judul"] for item in result["detail"]],
            [
                "Laba BBCA tumbuh kuat tahun ini - Kontan",
                "BBCA membagikan dividen interim",
                "Risiko kredit perbankan meningkat",
            ],
        )
        self.assertEqual(result["sumber"], {"google_news": 2, "kontan": 2})

    def test_indonesian_financial_phrases_correct_neutral_finbert(self):
        analyzer = SentimenAnalyzer()
        analyzer.nlp = Mock(
            return_value=[
                {"label": "neutral", "score": 0.904},
                {"label": "neutral", "score": 0.946},
                {"label": "neutral", "score": 0.91},
                {"label": "neutral", "score": 0.932},
            ]
        )

        result = analyzer.analisis_sentimen(
            [
                "Asing Kabur Bawa Rp 1,93 Triliun dari Pasar Saham RI, Investor Mesti Berhati-hati",
                "BEI Hentikan Sementara Perdagangan Saham AGAR",
                "Laba BBCA melonjak dan asing borong saham",
                "Saham Rights Issue Terpuruk: SINI hingga COCO Top Losers",
            ]
        )

        self.assertEqual([item["label"] for item in result], [
            "negative",
            "negative",
            "positive",
            "negative",
        ])
        self.assertTrue(all(item["metode"] == "finbert+bahasa_id" for item in result))

    def test_indonesian_negation_does_not_trigger_correction(self):
        analyzer = SentimenAnalyzer()
        analyzer.nlp = Mock(return_value=[{"label": "neutral", "score": 0.8}])

        result = analyzer.analisis_sentimen(
            ["BEI memastikan saham AGAR tidak jadi disuspensi"]
        )

        self.assertEqual(result[0]["label"], "neutral")
        self.assertEqual(result[0]["metode"], "finbert")

    def test_clear_indonesian_phrase_overrides_wrong_finbert(self):
        analyzer = SentimenAnalyzer()
        analyzer.nlp = Mock(return_value=[{"label": "positive", "score": 0.91}])

        result = analyzer.analisis_sentimen(
            ["Saham emiten batu bara jatuh tajam setelah rugi membengkak"]
        )

        self.assertEqual(result[0]["label"], "negative")
        self.assertEqual(result[0]["metode"], "finbert+bahasa_id")


if __name__ == "__main__":
    unittest.main()
