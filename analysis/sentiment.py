"""Analisis sentimen berita saham menggunakan FinBERT lokal."""
from calendar import timegm
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from threading import Lock
from urllib.parse import urlencode

import requests


# ponytail: lexical correction covers Indonesian headlines; replace it after
# a validated Indonesian financial-news training set is available.
POSITIVE_PHRASES = {
    # --- Corporate action / legal status (bobot 5) ---
    "suspensi dicabut": 5,
    "cabut suspensi": 5,
    "pencabutan suspensi": 5,
    "perdagangan dibuka kembali": 5,
    "saham dibuka kembali": 5,
    "lolos dari pailit": 5,
    "lolos pkpu": 5,
    "hindari delisting": 5,
    "batal delisting": 5,
    "relisting": 5,
    "restrukturisasi berhasil": 5,
    "damai pkpu": 5,
    "homologasi disetujui": 5,
    "restu pemegang saham": 4,
    "disetujui ojk": 4,
    "mendapat restu": 4,

    # --- Kinerja keuangan (bobot 4) ---
    "laba melonjak": 4,
    "laba tumbuh": 4,
    "laba naik": 4,
    "laba meroket": 4,
    "laba berlipat": 4,
    "laba fantastis": 4,
    "cetak rekor laba": 4,
    "rekor laba bersih": 4,
    "kinerja moncer": 4,
    "kinerja cemerlang": 4,
    "kinerja gemilang": 4,
    "kinerja solid": 4,
    "kembali cetak laba": 4,
    "balik untung": 4,
    "berbalik untung": 4,
    "arus kas positif": 4,
    "ebitda tumbuh": 4,
    "marjin membaik": 4,
    "marjin menebal": 4,

    # --- Aksi asing / institusi (bobot 4) ---
    "asing borong": 4,
    "diborong asing": 4,
    "diserbu asing": 4,
    "net buy": 4,
    "net buy asing": 4,
    "akumulasi asing": 4,
    "asing masuk": 4,
    "dana asing masuk": 4,
    "big fund masuk": 4,
    "bandar masuk": 4,
    "akumulasi bandar": 4,
    "smart money masuk": 4,
    "institusi masuk": 4,
    "foreign inflow": 4,
    "capital inflow": 4,

    # --- Pergerakan harga (bobot 3) ---
    "menguat": 3,
    "menguat tajam": 3,
    "menguat signifikan": 3,
    "melesat": 3,
    "melonjak": 3,
    "meroket": 3,
    "terbang": 3,
    "melejit": 3,
    "melambung": 3,
    "rebound": 3,
    "berbalik menguat": 3,
    "bangkit": 3,
    "reli": 3,
    "rally": 3,
    "rally panjang": 3,
    "reli berlanjut": 3,
    "top gainers": 3,
    "top gainer": 3,
    "saham pilihan": 3,
    "primadona investor": 3,
    "diburu investor": 3,
    "diminati investor": 3,
    "banjir order beli": 3,
    "antrean beli": 3,
    "auto reject atas": 3,
    "ara": 3,
    "menembus resistance": 3,
    "breakout": 3,
    "tembus level psikologis": 3,
    "all time high": 3,
    "rekor tertinggi": 3,
    "level tertinggi baru": 3,

    # --- Aksi korporasi (bobot 3) ---
    "buyback": 3,
    "pembelian kembali saham": 3,
    "right issue disambut positif": 3,
    "stock split": 3,
    "kontrak baru": 3,
    "kontrak jumbo": 3,
    "kontrak besar": 3,
    "raih kontrak": 3,
    "menang tender": 3,
    "akuisisi strategis": 3,
    "merger menguntungkan": 3,
    "ekspansi bisnis": 3,
    "kerja sama strategis": 3,
    "kemitraan baru": 3,
    "investasi baru masuk": 3,
    "suntikan modal": 3,
    "pendanaan segar": 3,
    "ipo sukses": 3,
    "oversubscribed": 3,
    "kelebihan permintaan": 3,

    # --- Rekomendasi analis (bobot 3) ---
    "rekomendasi beli": 3,
    "rating buy": 3,
    "rating overweight": 3,
    "outperform": 3,
    "target harga naik": 3,
    "target harga dinaikkan": 3,
    "revisi target naik": 3,
    "layak koleksi": 3,
    "saham undervalued": 3,
    "valuasi menarik": 3,
    "rekomendasi tambah": 3,
    "rekomendasi akumulasi": 3,

    # --- Dividen (bobot 3) ---
    "dividen naik": 3,
    "dividen jumbo": 3,
    "dividen spesial": 3,
    "yield dividen tinggi": 3,
    "bagi dividen interim": 3,
    "naik tajam": 3,

    # --- Prospek & makro (bobot 2) ---
    "ekspansi": 2,
    "dividen": 2,
    "prospek cerah": 2,
    "prospek positif": 2,
    "outlook positif": 2,
    "sentimen positif": 2,
    "optimisme investor": 2,
    "pendapatan naik": 2,
    "penjualan naik": 2,
    "penjualan meningkat": 2,
    "permintaan meningkat": 2,
    "pemulihan bisnis": 2,
    "pemulihan ekonomi": 2,
    "insentif pemerintah": 2,
    "relaksasi kebijakan": 2,
    "stimulus pemerintah": 2,
    "penurunan suku bunga": 2,
    "rupiah menguat": 2,
    "permintaan ekspor naik": 2,
    "harga komoditas naik": 2,
}

NEGATIVE_PHRASES = {
    # --- Status hukum / bursa (bobot 5) ---
    "hentikan sementara perdagangan": 5,
    "penghentian sementara perdagangan": 5,
    "disuspensi": 5,
    "suspensi": 4,
    "perpanjangan suspensi": 5,
    "delisting": 5,
    "force delisting": 5,
    "delisting paksa": 5,
    "gagal bayar": 5,
    "default": 5,
    "wanprestasi": 5,
    "pailit": 5,
    "pkpu": 5,
    "pkpu sementara": 5,
    "bangkrut": 5,
    "kebangkrutan": 5,
    "fraud": 5,
    "penipuan": 5,
    "manipulasi saham": 5,
    "manipulasi pasar": 5,
    "tersandung kasus": 5,
    "terseret kasus": 5,
    "terjerat kasus": 5,
    "kasus korupsi": 5,
    "dugaan korupsi": 5,
    "ditetapkan tersangka": 5,
    "diperiksa kpk": 5,
    "disegel": 5,
    "aset disita": 5,
    "penyitaan aset": 5,
    "gugatan pailit": 5,
    "somasi": 4,

    # --- Aksi asing / institusi (bobot 4) ---
    "asing kabur": 4,
    "asing keluar": 4,
    "asing lepas": 4,
    "dibuang asing": 4,
    "dilepas asing": 4,
    "net sell": 4,
    "net sell asing": 4,
    "capital outflow": 4,
    "foreign outflow": 4,
    "dana asing keluar": 4,
    "big fund keluar": 4,
    "distribusi bandar": 4,
    "tekanan jual": 4,
    "aksi jual masif": 4,
    "aksi ambil untung": 4,
    "profit taking": 4,
    "panic selling": 4,
    "jual panik": 4,

    # --- Kinerja keuangan (bobot 4) ---
    "laba anjlok": 4,
    "laba merosot": 4,
    "laba turun": 4,
    "laba tergerus": 4,
    "laba menyusut": 4,
    "rugi bersih": 4,
    "rugi membengkak": 4,
    "berbalik rugi": 4,
    "kembali merugi": 4,
    "kinerja loyo": 4,
    "kinerja mengecewakan": 4,
    "kinerja memburuk": 4,
    "arus kas negatif": 4,
    "ekuitas negatif": 4,
    "modal tergerus": 4,
    "utang jatuh tempo": 4,
    "utang menumpuk": 4,
    "beban utang membengkak": 4,
    "restrukturisasi utang": 4,
    "gagal restrukturisasi": 5,
    "likuiditas ketat": 4,
    "kesulitan keuangan": 4,

    # --- Pergerakan harga (bobot 3-4) ---
    "top losers": 4,
    "top loser": 4,
    "terpuruk": 4,
    "ambruk": 4,
    "anjlok": 3,
    "ambles": 3,
    "jeblok": 3,
    "terjun bebas": 3,
    "jatuh": 3,
    "terjun": 3,
    "merosot": 3,
    "tertekan": 3,
    "melemah tajam": 3,
    "tergerus": 3,
    "longsor": 3,
    "rontok": 3,
    "dijauhi investor": 3,
    "ditinggal investor": 3,
    "sepi peminat": 3,
    "auto reject bawah": 3,
    "arb": 3,
    "menembus support": 3,
    "breakdown": 3,
    "level terendah baru": 3,
    "titik terendah": 3,
    "all time low": 3,

    # --- Aksi korporasi / manajemen (bobot 3) ---
    "ditendang": 3,
    "dibuang": 3,
    "dicoret dari indeks": 3,
    "keluar dari indeks": 3,
    "digugat": 3,
    "digugat pailit": 4,
    "denda": 3,
    "sanksi": 3,
    "sanksi ojk": 3,
    "sanksi bei": 3,
    "peringatan bei": 3,
    "surat peringatan": 3,
    "uma": 3,
    "unusual market activity": 3,
    "mundur dari jabatan": 3,
    "direksi mengundurkan diri": 3,
    "pergantian direksi mendadak": 3,
    "konflik internal": 3,
    "sengketa pemegang saham": 3,
    "rights issue dilusi": 3,
    "dilusi saham": 3,
    "right issue ditolak": 3,
    "batal akuisisi": 3,
    "gagal merger": 3,
    "putus kontrak": 3,
    "kehilangan kontrak": 3,
    "kontrak dibatalkan": 3,
    "phk massal": 3,
    "tutup pabrik": 3,
    "hentikan produksi": 3,
    "setop operasional": 3,

    # --- Rekomendasi analis (bobot 3) ---
    "rekomendasi jual": 3,
    "rating sell": 3,
    "rating underweight": 3,
    "underperform": 3,
    "target harga turun": 3,
    "target harga dipangkas": 3,
    "revisi target turun": 3,
    "saham overvalued": 3,
    "valuasi mahal": 3,
    "turun tajam": 3,

    # --- Prospek & makro (bobot 2) ---
    "berhati-hati": 2,
    "waspada": 2,
    "wait and see": 2,
    "koreksi": 2,
    "koreksi wajar": 2,
    "melemah": 2,
    "sentimen negatif": 2,
    "outlook negatif": 2,
    "prospek suram": 2,
    "prospek redup": 2,
    "ketidakpastian": 2,
    "tekanan makro": 2,
    "rupiah melemah": 2,
    "inflasi meningkat": 2,
    "suku bunga naik": 2,
    "permintaan melemah": 2,
    "harga komoditas turun": 2,
    "penjualan turun": 2,
    "penjualan melambat": 2,
    "pendapatan turun": 2,
    "beban meningkat": 2,
}

class SentimenAnalyzer:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.nlp = None
        self.model_path = Path(__file__).resolve().parents[1] / "models" / "finbert"
        self._load_lock = Lock()

    def _load_model(self):
        """Lazy-load FinBERT sekali per instance dan jalankan di CPU."""
        if self.nlp is not None:
            return

        with self._load_lock:
            if self.nlp is not None:
                return
            if not self.model_path.is_dir():
                raise FileNotFoundError(
                    f"Model FinBERT tidak ditemukan di {self.model_path}. "
                    "Jalankan: python scripts/download_model.py"
                )

            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
                pipeline,
            )

            print("[SENTIMEN] Loading FinBERT lokal...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, local_files_only=True
            )
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_path, local_files_only=True
            )
            self.nlp = pipeline(
                "sentiment-analysis",
                model=self.model,
                tokenizer=self.tokenizer,
                device=-1,
            )
            print("[SENTIMEN] FinBERT siap digunakan")

    @staticmethod
    def _cutoff(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)

    @staticmethod
    def _entry_is_recent(entry, cutoff: datetime) -> bool:
        published = getattr(entry, "published_parsed", None)
        return bool(
            published
            and datetime.fromtimestamp(timegm(published), timezone.utc) >= cutoff
        )

    @staticmethod
    def _kontan_date(teks: str) -> datetime | None:
        bulan = {
            "januari": 1, "februari": 2, "maret": 3, "april": 4,
            "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
            "september": 9, "oktober": 10, "november": 11, "desember": 12,
        }
        match = re.search(
            r"\b(\d{1,2})\s+("
            + "|".join(bulan)
            + r")\s+(\d{4})\b",
            teks.casefold(),
        )
        if not match:
            return None
        hari, nama_bulan, tahun = match.groups()
        return datetime(int(tahun), bulan[nama_bulan], int(hari), tzinfo=timezone.utc)

    def ambil_berita_google(self, emiten: str, max: int = 15, days: int = 30) -> list[str]:
        """Ambil judul berita dari Google News RSS."""
        from feedparser import parse

        query = urlencode(
            {
                "q": f"{emiten.strip().upper()} saham IDX Indonesia when:{days}d",
                "hl": "id",
                "gl": "ID",
                "ceid": "ID:id",
            }
        )
        try:
            response = requests.get(
                f"https://news.google.com/rss/search?{query}",
                timeout=10,
                headers={"User-Agent": "StockAnalyzer/2.0"},
            )
            response.raise_for_status()
            feed = parse(response.content)
            cutoff = self._cutoff(days)
            return [
                entry.title.strip()
                for entry in feed.entries
                if getattr(entry, "title", "").strip()
                and self._entry_is_recent(entry, cutoff)
            ][:max]
        except Exception as exc:
            print(f"[SENTIMEN] Google News error: {exc}")
            return []

    def ambil_berita_kontan(self, emiten: str, max: int = 10, days: int = 30) -> list[str]:
        """Ambil judul berita dari halaman pencarian Kontan."""
        from bs4 import BeautifulSoup

        try:
            response = requests.get(
                f"https://insight.kontan.co.id/tag/saham-{emiten.strip().lower()}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; StockAnalyzer/2.0)"},
                timeout=10,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select(".card__title")
            cutoff = self._cutoff(days)
            berita = []
            for item in items:
                title = item.get_text(" ", strip=True)
                container = item.find_parent(["article", "div", "li"]) or item
                tanggal = self._kontan_date(container.get_text(" ", strip=True))
                if title and tanggal and tanggal >= cutoff:
                    berita.append(title)
                if len(berita) == max:
                    break
            return berita
        except Exception as exc:
            print(f"[SENTIMEN] Kontan error: {exc}")
            return []

    def analisis_sentimen(self, teks_list: list[str]) -> list[dict]:
        """Jalankan inference FinBERT untuk teks yang valid."""
        teks_valid = [teks.strip() for teks in teks_list if teks and len(teks.strip()) > 10]
        if not teks_valid:
            return []

        try:
            self._load_model()
            hasil = self.nlp(
                teks_valid,
                batch_size=8,
                truncation=True,
                max_length=512,
            )
            return [
                self._koreksi_bahasa_indonesia(teks, item)
                for teks, item in zip(teks_valid, hasil)
            ]
        except Exception as exc:
            print(f"[SENTIMEN] Inference error: {exc}")
            return []

    @staticmethod
    def _phrase_score(teks: str, phrases: dict[str, int]) -> int:
        score = 0
        for phrase, weight in phrases.items():
            pattern = rf"\b{re.escape(phrase)}\b"
            for match in re.finditer(pattern, teks):
                prefix = teks[max(0, match.start() - 20):match.start()]
                if not re.search(
                    r"\b(?:tidak|bukan|tanpa|batal|belum)(?:\s+jadi)?\s+$",
                    prefix,
                ):
                    score = max(score, weight)
                    break
        return score

    def _koreksi_bahasa_indonesia(self, teks: str, hasil: dict) -> dict:
        normalized = teks.casefold()
        positive_score = self._phrase_score(normalized, POSITIVE_PHRASES)
        negative_score = self._phrase_score(normalized, NEGATIVE_PHRASES)
        finbert_label = str(hasil["label"]).lower()
        finbert_score = float(hasil["score"])

        if positive_score == negative_score:
            return {
                "label": finbert_label,
                "score": finbert_score,
                "metode": "finbert",
            }

        rule_label = "positive" if positive_score > negative_score else "negative"
        rule_strength = max(positive_score, negative_score)
        if finbert_label == "neutral" or rule_strength >= 3:
            rule_confidence = min(0.95, 0.67 + rule_strength * 0.07)
            return {
                "label": rule_label,
                "score": max(finbert_score, rule_confidence)
                if finbert_label == rule_label
                else rule_confidence,
                "metode": "finbert+bahasa_id",
            }

        return {
            "label": finbert_label,
            "score": finbert_score,
            "metode": "finbert",
        }

    def hitung_skor(self, hasil_sentimen: list[dict]) -> dict:
        """Normalisasi sentimen ke skor bullish 0-100."""
        if not hasil_sentimen:
            return self._default_result()

        labels = [
            label if label in {"positive", "negative", "neutral"} else "neutral"
            for item in hasil_sentimen
            for label in [str(item.get("label", "")).lower()]
        ]
        total = len(labels)
        positif = labels.count("positive")
        negatif = labels.count("negative")
        netral = labels.count("neutral")
        weighted = 0.0
        for item in hasil_sentimen:
            label = str(item.get("label", "")).lower()
            score = float(item.get("score", 0))
            if label == "positive":
                weighted += score
            elif label == "negative":
                weighted -= score
        skor = round(((weighted / total) + 1) * 50, 1)
        confidence = sum(float(item.get("score", 0)) for item in hasil_sentimen) / total

        return {
            "skor": skor,
            "status": "BULLISH" if skor >= 65 else "BEARISH" if skor <= 35 else "NETRAL",
            "positif": positif,
            "negatif": negatif,
            "netral": netral,
            "total": total,
            "confidence": round(confidence, 3),
        }

    def _default_result(self) -> dict:
        return {
            "skor": 50,
            "status": "NO_DATA",
            "positif": 0,
            "negatif": 0,
            "netral": 0,
            "total": 0,
            "confidence": 0.0,
            "detail": [],
            "sumber": {"google_news": 0, "kontan": 0},
        }

    def analisis(self, emiten: str) -> dict:
        """Ambil berita, jalankan FinBERT, lalu kembalikan hasil lengkap."""
        try:
            print(f"[SENTIMEN] Menganalisis berita {emiten.upper()}...")
            berita_google = self.ambil_berita_google(emiten, max=15)
            berita_kontan = self.ambil_berita_kontan(emiten, max=10)
            semua_berita = []
            sudah_ada = set()
            for judul in berita_google + berita_kontan:
                judul = judul.strip() if judul else ""
                kunci = judul.rsplit(" - ", 1)[0].casefold()
                if len(judul) > 10 and kunci not in sudah_ada:
                    semua_berita.append(judul)
                    sudah_ada.add(kunci)
            if not semua_berita:
                return self._default_result()

            hasil_sentimen = self.analisis_sentimen(semua_berita)
            skor_data = self.hitung_skor(hasil_sentimen)
            detail = [
                {
                    "judul": judul,
                    "sentimen": hasil["label"],
                    "confidence": round(float(hasil["score"]), 3),
                    "metode": hasil.get("metode", "finbert"),
                }
                for judul, hasil in zip(semua_berita, hasil_sentimen)
            ]
            return {
                **skor_data,
                "detail": detail,
                "periode_hari": 30,
                "sumber": {
                    "google_news": len(berita_google),
                    "kontan": len(berita_kontan),
                },
            }
        except Exception as exc:
            print(f"[SENTIMEN] Error: {exc}")
            return self._default_result()
