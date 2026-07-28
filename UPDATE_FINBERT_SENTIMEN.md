# UPDATE FITUR: Modul Sentimen Berita (FinBERT)
**Versi:** 2.0  
**Status:** Ready to Implement  
**Prioritas:** High  

---

## Konteks Proyek

Program analisis saham Python yang sudah ada terdiri dari modul:
- `modules/teknikal.py` — Indikator RSI, MACD, Bollinger, Stochastic
- `modules/fundamental.py` — PER, PBV, ROE, DER, Dividend Yield
- `modules/ml_model.py` — Random Forest + LSTM prediksi harga
- `modules/monte_carlo.py` — Simulasi Monte Carlo 1000x
- `modules/bandarmologi.py` — Deteksi akumulasi/distribusi bandar
- `modules/scoring.py` — Hitung skor komposit akhir
- `main.py` — Entry point program

**Modul sentimen belum ada** — ini adalah implementasi baru dari nol.

---

## Spesifikasi Hardware & Environment

```
VPS       : KVM 8 — 8 vCore, 32GB RAM
OS        : Ubuntu 22.04 / 24.04
GPU       : Tidak ada (CPU only)
Python    : 3.10+
Framework : PyTorch (CPU), HuggingFace Transformers
```

---

## Yang Harus Dibuat

### TASK 1 — Download & Simpan Model FinBERT ke Lokal

Buat script satu kali `scripts/download_model.py`:

```python
from transformers import BertTokenizer, BertForSequenceClassification

print("Downloading FinBERT... (~440MB)")

tokenizer = BertTokenizer.from_pretrained('ProsusAI/finbert')
model = BertForSequenceClassification.from_pretrained('ProsusAI/finbert')

tokenizer.save_pretrained('./models/finbert')
model.save_pretrained('./models/finbert')

print("Model tersimpan di ./models/finbert")
```

> Jalankan SEKALI sebelum program utama:
> `python scripts/download_model.py`

---

### TASK 2 — Install Dependencies Baru

Tambahkan ke `requirements.txt`:

```
transformers==4.40.0
torch==2.2.0
feedparser==6.0.11
requests==2.31.0
beautifulsoup4==4.12.3
```

Install di VPS:
```bash
pip install transformers torch --index-url https://download.pytorch.org/whl/cpu
pip install feedparser requests beautifulsoup4
```

> Gunakan versi CPU torch — lebih ringan, tidak butuh CUDA

---

### TASK 3 — Buat File Baru: `modules/sentimen.py`

Buat class `SentimenAnalyzer` dengan struktur:

```
class SentimenAnalyzer:
    __init__(self)
        → inisialisasi, model belum di-load (lazy load)
    
    _load_model(self)
        → load FinBERT dari ./models/finbert hanya saat pertama dipanggil
    
    ambil_berita_google(self, emiten, max) → List[str]
        → scraping judul berita dari Google News RSS
    
    ambil_berita_kontan(self, emiten, max) → List[str]
        → scraping berita dari Kontan.co.id
    
    analisis_sentimen(self, teks_list) → List[dict]
        → jalankan FinBERT inference pada list teks
    
    hitung_skor(self, hasil_sentimen) → dict
        → hitung skor agregat dari semua hasil sentimen
    
    _default_result(self) → dict
        → return default jika tidak ada berita atau error
    
    analisis(self, emiten) → dict
        → fungsi utama — gabungkan semua langkah
```

---

## Spesifikasi Lengkap `modules/sentimen.py`

### Import yang Dibutuhkan

```python
from transformers import BertTokenizer, BertForSequenceClassification, pipeline
import feedparser
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional
import os
```

---

### `__init__`

```python
def __init__(self):
    self.model = None
    self.tokenizer = None
    self.nlp = None
    self.model_path = './models/finbert'
```

---

### `_load_model`

```python
def _load_model(self):
    """
    Load model FinBERT dari lokal.
    Hanya dipanggil saat pertama kali dibutuhkan (lazy load).
    Setelah load pertama, model tetap di RAM selama program berjalan.
    """
    if self.nlp is not None:
        return  # sudah di-load, skip

    if not os.path.exists(self.model_path):
        raise FileNotFoundError(
            f"Model FinBERT tidak ditemukan di {self.model_path}. "
            f"Jalankan: python scripts/download_model.py"
        )

    print("Loading FinBERT dari lokal... (30-60 detik)")

    self.tokenizer = BertTokenizer.from_pretrained(self.model_path)
    self.model = BertForSequenceClassification.from_pretrained(self.model_path)

    self.nlp = pipeline(
        "sentiment-analysis",
        model=self.model,
        tokenizer=self.tokenizer,
        device=-1,          # -1 = CPU
        batch_size=8,       # proses 8 teks sekaligus
        truncation=True,    # potong teks > 512 token
        max_length=512
    )

    print("FinBERT siap digunakan")
```

---

### `ambil_berita_google`

```python
def ambil_berita_google(self, emiten: str, max: int = 15) -> List[str]:
    """
    Ambil judul berita dari Google News RSS.
    Gratis, tidak butuh API key.
    """
    query = f"{emiten} saham IDX Indonesia"
    url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"

    try:
        feed = feedparser.parse(url)
        judul = [
            entry.title
            for entry in feed.entries[:max]
            if hasattr(entry, 'title')
        ]
        return judul
    except Exception as e:
        print(f"[SENTIMEN] Google News error: {e}")
        return []
```

---

### `ambil_berita_kontan`

```python
def ambil_berita_kontan(self, emiten: str, max: int = 10) -> List[str]:
    """
    Ambil berita dari Kontan.co.id
    """
    url = f"https://search.kontan.co.id/search?q={emiten}&channel=news"
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; SahamBot/1.0)'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        judul = []
        for item in soup.select('.list-berita h2')[:max]:
            if item.text.strip():
                judul.append(item.text.strip())

        return judul
    except Exception as e:
        print(f"[SENTIMEN] Kontan error: {e}")
        return []
```

---

### `analisis_sentimen`

```python
def analisis_sentimen(self, teks_list: List[str]) -> List[dict]:
    """
    Jalankan FinBERT inference pada list teks.

    Return label:
    - 'positive' — sentimen positif untuk saham
    - 'negative' — sentimen negatif untuk saham
    - 'neutral'  — sentimen netral
    """
    self._load_model()

    if not teks_list:
        return []

    # Filter teks kosong atau terlalu pendek
    teks_valid = [t for t in teks_list if t and len(t.strip()) > 10]

    if not teks_valid:
        return []

    try:
        hasil = self.nlp(teks_valid)
        return hasil
    except Exception as e:
        print(f"[SENTIMEN] Inference error: {e}")
        return []
```

---

### `hitung_skor`

**Logika skor normalisasi 0–100:**

| Kondisi | Skor |
|---------|------|
| Semua berita positif | 100 |
| Semua berita negatif | 0 |
| Berimbang | 50 |
| Mayoritas positif (>60%) | 60–85 |
| Mayoritas negatif (>60%) | 15–40 |

```python
def hitung_skor(self, hasil_sentimen: List[dict]) -> dict:
    """
    Hitung skor agregat dari hasil sentimen FinBERT.
    Skor 0-100: makin tinggi makin bullish.
    """
    if not hasil_sentimen:
        return {
            'skor': 50,
            'status': 'NO_DATA',
            'positif': 0,
            'negatif': 0,
            'netral': 0,
            'total': 0,
            'confidence': 0.0
        }

    positif = sum(1 for h in hasil_sentimen if h['label'] == 'positive')
    negatif = sum(1 for h in hasil_sentimen if h['label'] == 'negative')
    netral  = sum(1 for h in hasil_sentimen if h['label'] == 'neutral')
    total   = len(hasil_sentimen)

    avg_confidence = sum(h['score'] for h in hasil_sentimen) / total

    # Normalisasi ke 0-100
    raw  = (positif - negatif) / total     # range -1 sampai +1
    skor = (raw + 1) / 2 * 100            # normalisasi ke 0-100
    skor = round(skor, 1)

    if skor >= 65:
        status = 'BULLISH'
    elif skor <= 35:
        status = 'BEARISH'
    else:
        status = 'NETRAL'

    return {
        'skor': skor,
        'status': status,
        'positif': positif,
        'negatif': negatif,
        'netral': netral,
        'total': total,
        'confidence': round(avg_confidence, 3)
    }
```

---

### `_default_result`

```python
def _default_result(self) -> dict:
    return {
        'skor': 50,
        'status': 'NO_DATA',
        'positif': 0,
        'negatif': 0,
        'netral': 0,
        'total': 0,
        'confidence': 0.0,
        'detail': [],
        'sumber': {'google_news': 0, 'kontan': 0}
    }
```

---

### `analisis` — Fungsi Utama

```python
def analisis(self, emiten: str) -> dict:
    """
    Fungsi utama:
    1. Ambil berita dari Google News + Kontan
    2. Jalankan FinBERT inference
    3. Hitung skor agregat
    4. Return hasil lengkap
    """
    try:
        print(f"[SENTIMEN] Menganalisis berita {emiten}...")

        berita_google = self.ambil_berita_google(emiten, max=15)
        berita_kontan = self.ambil_berita_kontan(emiten, max=10)

        # Gabungkan & deduplikasi
        semua_berita = list(set(berita_google + berita_kontan))

        if not semua_berita:
            print(f"[SENTIMEN] Tidak ada berita ditemukan untuk {emiten}")
            return self._default_result()

        print(f"[SENTIMEN] {len(semua_berita)} berita ditemukan, menganalisis...")

        hasil_sentimen = self.analisis_sentimen(semua_berita)
        skor_data = self.hitung_skor(hasil_sentimen)

        # Buat detail per berita
        detail = []
        for teks, hasil in zip(semua_berita[:len(hasil_sentimen)], hasil_sentimen):
            detail.append({
                'judul': teks,
                'sentimen': hasil['label'],
                'confidence': round(hasil['score'], 3),
            })

        return {
            **skor_data,
            'detail': detail,
            'sumber': {
                'google_news': len(berita_google),
                'kontan': len(berita_kontan),
            }
        }

    except Exception as e:
        print(f"[SENTIMEN] Error: {e}")
        return self._default_result()
```

---

## TASK 4 — Update `modules/scoring.py`

**Bobot baru (dengan sentimen):**

```python
def hitungSkorKomposit(teknikal, fundamental, ml, monte_carlo, bandar, sentimen):
    skor = (
        teknikal['skor']    * 0.20 +   # turun dari 0.25
        fundamental['skor'] * 0.25 +   # turun dari 0.30
        ml['skor']          * 0.15 +   # turun dari 0.20
        monte_carlo['skor'] * 0.15 +   # tetap
        bandar['skor']      * 0.15 +   # tetap
        sentimen['skor']    * 0.10     # BARU
    )
    return round(skor, 1)
```

---

## TASK 5 — Update `main.py`

### Tambah Import

```python
from modules.sentimen import SentimenAnalyzer
```

### Inisialisasi di Luar Loop

```python
# Inisialisasi SEKALI di luar fungsi — model tidak di-load ulang setiap saham
sentimen_analyzer = SentimenAnalyzer()

def analisis_saham(kode: str, pakai_sentimen: bool = True):
    # modul lain ...

    sentimen = sentimen_analyzer._default_result()
    if pakai_sentimen:
        sentimen = sentimen_analyzer.analisis(kode)
```

> JANGAN buat `SentimenAnalyzer()` di dalam loop atau fungsi `analisis_saham()`.
> Model FinBERT ~440MB harus di-load sekali saja.

### Tambah Section di `tampilkan_hasil()`

```
[SENTIMEN BERITA]  Skor: {sentimen.get('skor', 'N/A')}/100
  Status          : {sentimen.get('status', 'N/A')}
  Total berita    : {sentimen.get('total', 0)}
  Positif         : {sentimen.get('positif', 0)}
  Negatif         : {sentimen.get('negatif', 0)}
  Netral          : {sentimen.get('netral', 0)}
  Confidence      : {sentimen.get('confidence', 0):.1%}
```

---

## Contoh Output yang Diharapkan

```
[SENTIMEN BERITA]  Skor: 74.0/100
  Status          : BULLISH
  Total berita    : 18
  Positif         : 12
  Negatif         : 3
  Netral          : 3
  Confidence      : 89.3%

  Detail berita:
  positive (96.2%) — DEWA catat laba naik 40% di semester pertama
  positive (88.1%) — Harga batu bara stabil topang kinerja emiten energi
  negative (91.4%) — Kekhawatiran perlambatan ekspor batu bara ke China
  neutral  (79.3%) — DEWA rencanakan rights issue tahun depan
```

---

## Performa di VPS (8 vCore, 32GB RAM)

| Operasi | Estimasi Waktu |
|---------|---------------|
| Load model pertama kali | 30–60 detik |
| Load model berikutnya (sudah di RAM) | 0 detik |
| Ambil berita 1 emiten | 3–5 detik |
| Inference 20 berita | 5–15 detik |
| Total analisis 1 emiten | ~20 detik |
| Total analisis 10 emiten | ~3 menit |
| RAM yang dipakai FinBERT | ~6–8 GB |

---

## Struktur Folder Final

```
saham_analyzer/
├── main.py                     <- Update: import + inisialisasi luar loop
├── modules/
│   ├── teknikal.py             — Tidak berubah
│   ├── fundamental.py          — Tidak berubah
│   ├── ml_model.py             — Tidak berubah
│   ├── monte_carlo.py          — Tidak berubah
│   ├── bandarmologi.py         — Tidak berubah
│   ├── sentimen.py             BARU — implementasi ini
│   └── scoring.py              <- Update: tambah parameter sentimen
├── scripts/
│   └── download_model.py       BARU — jalankan sekali
├── models/
│   └── finbert/                BARU — hasil download model
│       ├── config.json
│       ├── pytorch_model.bin
│       └── vocab.txt
├── logs/
│   └── analisis.log
└── requirements.txt            <- Update: tambah dependencies baru
```

---

## Testing

```python
from modules.sentimen import SentimenAnalyzer

analyzer = SentimenAnalyzer()

# Test 1: Analisis satu emiten
hasil = analyzer.analisis("DEWA")
assert 'skor' in hasil
assert 0 <= hasil['skor'] <= 100
assert hasil['status'] in ['BULLISH', 'BEARISH', 'NETRAL', 'NO_DATA']
assert 'total' in hasil
assert 'detail' in hasil
print(f"Test 1 passed — Skor: {hasil['skor']}, Status: {hasil['status']}")

# Test 2: Lazy load — model tidak di-load ulang
hasil2 = analyzer.analisis("BBCA")
assert analyzer.nlp is not None
print("Test 2 passed — Lazy load bekerja")

# Test 3: Emiten tidak ada beritanya
hasil3 = analyzer.analisis("XYZABC123")
assert hasil3['skor'] == 50
assert hasil3['status'] == 'NO_DATA'
print("Test 3 passed — No data handling bekerja")
```

---

## Checklist Implementasi

- [ ] Buat `scripts/download_model.py`
- [ ] Jalankan `python scripts/download_model.py` — pastikan `models/finbert/` terbentuk
- [ ] Update `requirements.txt` dengan dependencies baru
- [ ] Install: `pip install transformers torch feedparser requests beautifulsoup4`
- [ ] Buat `modules/sentimen.py` dengan class `SentimenAnalyzer`
- [ ] Implementasi `_load_model()` dengan lazy load dari path lokal
- [ ] Implementasi `ambil_berita_google()` via feedparser RSS
- [ ] Implementasi `ambil_berita_kontan()` via BeautifulSoup
- [ ] Implementasi `analisis_sentimen()` dengan batch_size=8
- [ ] Implementasi `hitung_skor()` dengan formula normalisasi 0-100
- [ ] Implementasi `_default_result()` untuk fallback
- [ ] Implementasi `analisis()` sebagai fungsi utama dengan error handling
- [ ] Update `modules/scoring.py` — tambah parameter `sentimen` dan bobot baru
- [ ] Update `main.py` — import, inisialisasi di luar loop, tampilkan output
- [ ] Buat folder `logs/`
- [ ] Jalankan semua test cases
- [ ] Verifikasi RAM tidak melebihi 20GB saat semua modul aktif
- [ ] Setup cron job di VPS: `30 5 * * 1-5`

---

## Catatan untuk AI

1. **JANGAN** buat instance `SentimenAnalyzer()` di dalam loop — model harus di-load sekali saja
2. **JANGAN** download model setiap kali program dijalankan — simpan ke `./models/finbert/`
3. **Gunakan** `device=-1` untuk CPU — VPS tidak punya GPU
4. **Gunakan** `batch_size=8` untuk keseimbangan kecepatan dan RAM
5. **Selalu** tambahkan `truncation=True, max_length=512` di pipeline
6. **Key wajib** di return `analisis()`: `skor`, `status`, `positif`, `negatif`, `netral`, `total`, `confidence`, `detail`
7. **Jangan ubah** modul lain selain `scoring.py` dan `main.py`
8. **Tambahkan** `logs/` dan `models/` ke `.gitignore`
