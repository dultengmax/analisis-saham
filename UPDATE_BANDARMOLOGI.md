# UPDATE FITUR: Modul Bandarmologi
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
- `modules/sentimen.py` — FinBERT analisis sentimen berita
- `modules/scoring.py` — Hitung skor komposit akhir
- `main.py` — Entry point program

---

## Yang Harus Dibuat

### TASK 1 — Buat File Baru: `modules/bandarmologi.py`

Buat class `BandarmologiAnalyzer` dengan struktur berikut:

```
class BandarmologiAnalyzer:
    __init__(self, kode: str)
        → ambil data historis 3 bulan via yfinance
        → panggil _hitung_semua()
    
    _hitung_semua(self)
        → hitung semua kolom turunan di dataframe
    
    deteksi_akumulasi(self) → List[dict]
        → deteksi hari-hari bandar akumulasi
    
    deteksi_distribusi(self) → List[dict]
        → deteksi hari-hari bandar distribusi
    
    hitung_obv(self) → dict
        → hitung On Balance Volume + deteksi divergensi
    
    hitung_mfi(self, period=14) → dict
        → hitung Money Flow Index
    
    analisis(self) → dict
        → rangkum semua + hitung skor 0-100
```

---

### TASK 2 — Update File: `modules/scoring.py`

Tambahkan parameter `bandar` ke fungsi `hitungSkorKomposit`.

**Bobot lama:**
```python
def hitungSkorKomposit(teknikal, fundamental, ml, monte_carlo, sentimen):
    skor = (
        teknikal['skor']    * 0.25 +
        fundamental['skor'] * 0.30 +
        ml['skor']          * 0.20 +
        monte_carlo['skor'] * 0.15 +
        sentimen['skor']    * 0.10
    )
    return round(skor, 1)
```

**Bobot baru (setelah update):**
```python
def hitungSkorKomposit(teknikal, fundamental, ml, monte_carlo, sentimen, bandar):
    skor = (
        teknikal['skor']    * 0.20 +   # turun dari 0.25
        fundamental['skor'] * 0.25 +   # turun dari 0.30
        ml['skor']          * 0.15 +   # turun dari 0.20
        monte_carlo['skor'] * 0.15 +   # tetap
        sentimen['skor']    * 0.10 +   # tetap
        bandar['skor']      * 0.15     # BARU
    )
    return round(skor, 1)
```

---

### TASK 3 — Update File: `main.py`

Tambahkan 3 hal:

**1. Import baru di bagian atas:**
```python
from modules.bandarmologi import BandarmologiAnalyzer
```

**2. Panggil modul di dalam fungsi `analisis_saham()`:**
```python
bandar = BandarmologiAnalyzer(kode).analisis()
```

**3. Tambahkan section bandarmologi di fungsi `tampilkan_hasil()`:**
```
║ [BANDARMOLOGI]   Skor: {bandar['skor']}/100
║   Fase           : {bandar['fase']}
║   OBV Trend      : {bandar['obv']['obv_trend'].upper()}
║   MFI            : {bandar['mfi']['mfi']} — {bandar['mfi']['status']}
║   Divergensi     : {bandar['obv']['divergensi'] or 'Tidak ada'}
```

---

## Spesifikasi Lengkap `modules/bandarmologi.py`

### Import yang Dibutuhkan
```python
import pandas as pd
import numpy as np
import yfinance as yf
from typing import List, Dict, Optional
```

---

### `__init__` dan `_hitung_semua`

```python
def __init__(self, kode: str):
    self.kode = kode
    self.df = yf.Ticker(f"{kode}.JK").history(period="3mo")
    self._hitung_semua()

def _hitung_semua(self):
    df = self.df

    # Volume
    df['vol_ma20']     = df['Volume'].rolling(20).mean()
    df['vol_ratio']    = df['Volume'] / df['vol_ma20']

    # Candle anatomy
    df['body']         = abs(df['Close'] - df['Open'])
    df['upper_shadow'] = df['High'] - df[['Close','Open']].max(axis=1)
    df['lower_shadow'] = df[['Close','Open']].min(axis=1) - df['Low']
    df['range']        = df['High'] - df['Low']
    df['bullish']      = df['Close'] > df['Open']

    # Close position dalam range (0 = bawah, 1 = atas)
    df['close_pos'] = (df['Close'] - df['Low']) / df['range'].replace(0, np.nan)

    self.df = df
```

---

### `deteksi_akumulasi`

**Logika deteksi (skor kumulatif per hari, threshold ≥ 30):**

| Kondisi | Skor | Makna |
|---------|------|-------|
| vol_ratio > 2.0 AND perubahan harga < 2% | +25 | Volume besar tapi harga stagnan → beli diam-diam |
| lower_shadow / range > 0.6 | +20 | Ekor bawah panjang → bandar tahan harga jatuh |
| Candle bearish AND vol_ratio < 0.5 | +15 | Turun tapi volume kecil → koreksi sehat |
| close_pos > 0.7 | +20 | Tutup di atas 70% range → buying pressure |

**Return format:**
```python
[
    {
        'tanggal': datetime,
        'harga': float,
        'volume': int,
        'vol_ratio': float,
        'skor_akumulasi': int,
        'alasan': List[str]
    },
    ...
]
```

---

### `deteksi_distribusi`

**Logika deteksi (skor kumulatif per hari, threshold ≥ 30):**

| Kondisi | Skor | Makna |
|---------|------|-------|
| vol_ratio > 2.0 AND candle bearish | +30 | Volume besar tapi harga turun → buang saham |
| upper_shadow / range > 0.6 | +25 | Ekor atas panjang → bandar jual di harga tinggi |
| Candle bullish AND vol_ratio < 0.5 | +15 | Naik tapi volume kecil → pump lemah |
| close_pos < 0.3 | +20 | Tutup di bawah 30% range → selling pressure |

**Return format:**
```python
[
    {
        'tanggal': datetime,
        'harga': float,
        'volume': int,
        'vol_ratio': float,
        'skor_distribusi': int,
        'alasan': List[str]
    },
    ...
]
```

---

### `hitung_obv`

**Logika:**
```
Jika Close[i] > Close[i-1] → OBV += Volume[i]
Jika Close[i] < Close[i-1] → OBV -= Volume[i]
Jika Close[i] == Close[i-1] → OBV tetap
```

**Deteksi divergensi:**
- Bandingkan trend harga 20 hari terakhir vs trend OBV 20 hari terakhir
- Bullish divergence: harga turun tapi OBV naik
- Bearish divergence: harga naik tapi OBV turun

**Return format:**
```python
{
    'obv_sekarang': int,
    'obv_trend': str,          # 'naik' atau 'turun'
    'divergensi': Optional[str] # pesan divergensi atau None
}
```

---

### `hitung_mfi`

**Logika:**
```
Typical Price (TP)  = (High + Low + Close) / 3
Money Flow (MF)     = TP × Volume
Positive MF         = MF jika TP[i] > TP[i-1]
Negative MF         = MF jika TP[i] < TP[i-1]
Money Flow Ratio    = Sum(Positive MF, 14) / Sum(Negative MF, 14)
MFI                 = 100 - (100 / (1 + Money Flow Ratio))
```

**Interpretasi:**
| MFI | Status |
|-----|--------|
| > 80 | OVERBOUGHT — Dana besar mulai keluar ⚠️ |
| < 20 | OVERSOLD — Dana besar mulai masuk 🚀 |
| 20–80 | NORMAL |

**Return format:**
```python
{
    'mfi': float,
    'status': str
}
```

---

### `analisis` — Fungsi Utama

**Logika skor:**

```
Skor awal = 50 (netral)

OBV trend naik      → +15
OBV trend turun     → -15

OBV Bullish divergence → +20
OBV Bearish divergence → -20

MFI < 20 (oversold)   → +15
MFI > 80 (overbought) → -15

Sinyal akumulasi 3 hari lebih banyak dari distribusi → +10, fase = AKUMULASI
Sinyal distribusi 3 hari lebih banyak dari akumulasi → -10, fase = DISTRIBUSI
Sama                                                  → fase = TIDAK JELAS

Clamp skor: min 0, max 100
```

**Return format:**
```python
{
    'skor': float,              # 0–100
    'fase': str,                # AKUMULASI / DISTRIBUSI / TIDAK JELAS
    'obv': dict,                # hasil hitung_obv()
    'mfi': dict,                # hasil hitung_mfi()
    'akumulasi_3hari': List[dict],
    'distribusi_3hari': List[dict],
}
```

---

## Contoh Output yang Diharapkan

```
[BANDARMOLOGI]   Skor: 72.0/100
  Fase           : AKUMULASI
  OBV Trend      : NAIK
  MFI            : 28.4 — NORMAL
  Divergensi     : BULLISH DIVERGENCE — Harga turun tapi OBV naik → bandar akumulasi diam-diam 🚀
  
  Sinyal 3 hari terakhir:
  ✅ 2026-07-22 | Harga: 430 | Vol 2.3x | Lower shadow panjang → bandar support
  ✅ 2026-07-23 | Harga: 425 | Vol 0.4x | Turun tapi volume kecil → koreksi sehat
```

---

## Error Handling

Tambahkan try-except di setiap fungsi:

```python
def analisis(self) -> dict:
    try:
        # ... kode analisis ...
    except Exception as e:
        print(f"[BANDARMOLOGI] Error: {e}")
        return {
            'skor': 50,
            'fase': 'ERROR',
            'obv': {'obv_sekarang': 0, 'obv_trend': 'unknown', 'divergensi': None},
            'mfi': {'mfi': 50, 'status': 'ERROR'},
            'akumulasi_3hari': [],
            'distribusi_3hari': [],
        }
```

---

## Testing

Setelah implementasi, test dengan:

```python
# Test standalone
from modules.bandarmologi import BandarmologiAnalyzer

analyzer = BandarmologiAnalyzer("DEWA")
hasil = analyzer.analisis()

# Validasi output
assert 'skor' in hasil
assert 0 <= hasil['skor'] <= 100
assert hasil['fase'] in ['AKUMULASI', 'DISTRIBUSI', 'TIDAK JELAS', 'ERROR']
assert 'obv' in hasil
assert 'mfi' in hasil

print("✅ Semua test passed")
print(f"Skor: {hasil['skor']}")
print(f"Fase: {hasil['fase']}")
print(f"OBV: {hasil['obv']}")
print(f"MFI: {hasil['mfi']}")
```

---

## Checklist Implementasi

- [ ] Buat `modules/bandarmologi.py` dengan class `BandarmologiAnalyzer`
- [ ] Implementasi `_hitung_semua()` dengan semua kolom turunan
- [ ] Implementasi `deteksi_akumulasi()` dengan 4 kondisi dan threshold 30
- [ ] Implementasi `deteksi_distribusi()` dengan 4 kondisi dan threshold 30
- [ ] Implementasi `hitung_obv()` dengan deteksi divergensi
- [ ] Implementasi `hitung_mfi()` dengan period default 14
- [ ] Implementasi `analisis()` dengan logika skor dan return format lengkap
- [ ] Tambahkan error handling di semua fungsi
- [ ] Update `modules/scoring.py` — tambah parameter `bandar` dan bobot baru
- [ ] Update `main.py` — tambah import, panggil modul, tampilkan output
- [ ] Jalankan testing dengan saham DEWA, BBCA, TLKM
- [ ] Verifikasi output format sesuai spesifikasi

---

## Catatan untuk AI

1. **Jangan ubah** struktur modul lain yang sudah ada kecuali `scoring.py` dan `main.py`
2. **Gunakan** `yfinance` untuk ambil data — sudah terinstall di project
3. **Lazy load** tidak diperlukan di modul ini karena tidak ada model berat
4. **Semua perhitungan** menggunakan `pandas` dan `numpy` — tidak perlu library tambahan
5. **Nama fungsi dan return key** harus persis seperti di spesifikasi — modul lain bergantung padanya
6. **Period data** yang diambil adalah 3 bulan (`period="3mo"`) — cukup untuk analisis bandarmologi
