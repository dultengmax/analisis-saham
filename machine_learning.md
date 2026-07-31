# UPDATE FITUR: Modul Machine Learning (Random Forest + LSTM)
**Versi:** 2.0  
**Status:** Ready to Implement  
**Prioritas:** High  

---

## Konteks Proyek

Program analisis saham Python yang sudah ada terdiri dari modul:
- `modules/teknikal.py` — Indikator RSI, MACD, Bollinger, Stochastic
- `modules/fundamental.py` — PER, PBV, ROE, DER, Dividend Yield
- `modules/monte_carlo.py` — Simulasi Monte Carlo 1000x
- `modules/bandarmologi.py` — Deteksi akumulasi/distribusi bandar
- `modules/sentimen.py` — FinBERT analisis sentimen berita
- `modules/scoring.py` — Hitung skor komposit akhir
- `main.py` — Entry point program

**Modul ML belum ada** — ini adalah implementasi baru dari nol.

---

## Spesifikasi Hardware & Environment

```
VPS       : KVM 8 — 8 vCore, 32GB RAM
OS        : Ubuntu 22.04 / 24.04
GPU       : Tidak ada (CPU only)
Python    : 3.10+
Framework : scikit-learn, TensorFlow (CPU), joblib
```

---

## Yang Harus Dibuat

### TASK 1 — Install Dependencies Baru

Tambahkan ke `requirements.txt`:

```
scikit-learn==1.4.0
tensorflow==2.15.0
joblib==1.3.2
numpy==1.26.0
ta==0.11.0
```

Install di VPS:
```bash
pip install scikit-learn tensorflow-cpu joblib ta numpy
```

> Gunakan `tensorflow-cpu` — lebih ringan, tidak butuh CUDA

---

### TASK 2 — Buat Folder Model

```bash
mkdir -p models/ml/random_forest
mkdir -p models/ml/lstm
```

---

### TASK 3 — Buat File Baru: `modules/ml_model.py`

Buat class `MLAnalyzer` dengan struktur:

```
class MLAnalyzer:
    __init__(self, kode)
        → ambil data historis 2 tahun via yfinance
        → hitung fitur teknikal
    
    _hitung_fitur(self) → DataFrame
        → hitung RSI, MACD, Bollinger, EMA, Volume change
    
    _siapkan_data_klasifikasi(self) → tuple
        → siapkan X, y untuk Random Forest
    
    _siapkan_data_lstm(self) → tuple
        → siapkan sequence data untuk LSTM
    
    train_random_forest(self) → dict
        → train dan simpan model RF
    
    train_lstm(self) → dict
        → train dan simpan model LSTM
    
    prediksi_arah(self) → dict
        → prediksi naik/turun besok dengan RF
    
    prediksi_harga(self) → dict
        → prediksi harga 7 hari ke depan dengan LSTM
    
    prediksi(self) → dict
        → fungsi utama — gabungkan semua prediksi
```

---

## Spesifikasi Lengkap `modules/ml_model.py`

### Import yang Dibutuhkan

```python
import numpy as np
import pandas as pd
import yfinance as yf
import joblib
import os
import ta

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import accuracy_score

from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

from typing import Dict, Tuple, Optional
```

---

### Konstanta

```python
WINDOW_LSTM    = 60      # 60 hari data untuk prediksi 1 hari LSTM
HORIZON_LSTM   = 7       # prediksi 7 hari ke depan
EPOCH_LSTM     = 20      # jumlah epoch training LSTM
BATCH_LSTM     = 32      # batch size LSTM
RF_ESTIMATORS  = 200     # jumlah trees Random Forest
TEST_SIZE      = 0.2     # 20% data untuk testing
```

---

### `__init__`

```python
def __init__(self, kode: str):
    self.kode = kode
    self.df = yf.Ticker(f"{kode}.JK").history(period="2y")
    self.scaler = MinMaxScaler()
    self.model_rf_path   = f"./models/ml/random_forest/{kode}_rf.pkl"
    self.model_lstm_path = f"./models/ml/lstm/{kode}_lstm.h5"
    self.scaler_path     = f"./models/ml/lstm/{kode}_scaler.pkl"
    self._hitung_fitur()
```

---

### `_hitung_fitur`

```python
def _hitung_fitur(self):
    """
    Hitung semua fitur teknikal yang dipakai sebagai input model ML.
    Hasil disimpan di self.df
    """
    df = self.df.copy()

    # Momentum
    df['RSI']    = ta.momentum.RSIIndicator(df['Close']).rsi()
    df['Stoch']  = ta.momentum.StochasticOscillator(
                        df['High'], df['Low'], df['Close']
                   ).stoch()

    # Trend
    df['MACD']       = ta.trend.MACD(df['Close']).macd()
    df['MACD_signal'] = ta.trend.MACD(df['Close']).macd_signal()
    df['EMA20']      = ta.trend.EMAIndicator(df['Close'], 20).ema_indicator()
    df['EMA50']      = ta.trend.EMAIndicator(df['Close'], 50).ema_indicator()

    # Volatility
    bb = ta.volatility.BollingerBands(df['Close'])
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_lower'] = bb.bollinger_lband()
    df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['Close']

    # Volume
    df['Volume_change'] = df['Volume'].pct_change()
    df['Volume_MA20']   = df['Volume'].rolling(20).mean()
    df['Volume_ratio']  = df['Volume'] / df['Volume_MA20']

    # Price derived
    df['Price_change']  = df['Close'].pct_change()
    df['High_Low_ratio'] = (df['High'] - df['Low']) / df['Close']

    self.df = df.dropna()
```

---

### `_siapkan_data_klasifikasi`

```python
def _siapkan_data_klasifikasi(self) -> Tuple:
    """
    Siapkan data untuk Random Forest (klasifikasi naik/turun).

    Label:
    - 1 = harga besok lebih tinggi dari hari ini (NAIK)
    - 0 = harga besok lebih rendah atau sama (TURUN)
    """
    df = self.df.copy()

    # Label: apakah harga besok naik?
    df['target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    df = df.dropna()

    fitur = [
        'RSI', 'Stoch', 'MACD', 'MACD_signal',
        'EMA20', 'EMA50', 'BB_upper', 'BB_lower', 'BB_width',
        'Volume_change', 'Volume_ratio',
        'Price_change', 'High_Low_ratio'
    ]

    X = df[fitur].values
    y = df['target'].values

    return X, y, fitur
```

---

### `_siapkan_data_lstm`

```python
def _siapkan_data_lstm(self) -> Tuple:
    """
    Siapkan sequence data untuk LSTM prediksi harga.
    Gunakan 60 hari terakhir untuk prediksi hari berikutnya.
    """
    data = self.df[['Close']].values
    data_scaled = self.scaler.fit_transform(data)

    X, y = [], []
    for i in range(WINDOW_LSTM, len(data_scaled)):
        X.append(data_scaled[i - WINDOW_LSTM:i, 0])
        y.append(data_scaled[i, 0])

    X = np.array(X)
    y = np.array(y)
    X = X.reshape(X.shape[0], X.shape[1], 1)

    return X, y, data_scaled
```

---

### `train_random_forest`

```python
def train_random_forest(self) -> dict:
    """
    Train Random Forest untuk prediksi arah harga (naik/turun).
    Simpan model ke disk setelah training.
    """
    print(f"[ML] Training Random Forest untuk {self.kode}...")

    X, y, fitur = self._siapkan_data_klasifikasi()

    # Split data — shuffle=False penting untuk time series
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, shuffle=False
    )

    # Train
    model = RandomForestClassifier(
        n_estimators=RF_ESTIMATORS,
        max_depth=10,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1       # gunakan semua core
    )
    model.fit(X_train, y_train)

    # Evaluasi
    y_pred    = model.predict(X_test)
    akurasi   = accuracy_score(y_test, y_pred)

    # Simpan model
    os.makedirs(os.path.dirname(self.model_rf_path), exist_ok=True)
    joblib.dump(model, self.model_rf_path)

    print(f"[ML] RF selesai — Akurasi: {akurasi:.2%}")

    return {
        'model': model,
        'akurasi': round(akurasi * 100, 1),
        'fitur': fitur
    }
```

---

### `train_lstm`

```python
def train_lstm(self) -> dict:
    """
    Train LSTM untuk prediksi harga numerik.
    Simpan model dan scaler ke disk setelah training.
    """
    print(f"[ML] Training LSTM untuk {self.kode}...")

    X, y, data_scaled = self._siapkan_data_lstm()

    # Split data
    split     = int(len(X) * (1 - TEST_SIZE))
    X_train   = X[:split]
    X_test    = X[split:]
    y_train   = y[:split]
    y_test    = y[split:]

    # Bangun model
    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(WINDOW_LSTM, 1)),
        Dropout(0.2),
        LSTM(64, return_sequences=False),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dense(1)
    ])

    model.compile(optimizer='adam', loss='mse', metrics=['mae'])

    # Early stopping agar tidak overfit
    early_stop = EarlyStopping(
        monitor='val_loss',
        patience=3,
        restore_best_weights=True
    )

    model.fit(
        X_train, y_train,
        epochs=EPOCH_LSTM,
        batch_size=BATCH_LSTM,
        validation_data=(X_test, y_test),
        callbacks=[early_stop],
        verbose=0
    )

    # Evaluasi
    loss, mae = model.evaluate(X_test, y_test, verbose=0)

    # Simpan model dan scaler
    os.makedirs(os.path.dirname(self.model_lstm_path), exist_ok=True)
    model.save(self.model_lstm_path)
    joblib.dump(self.scaler, self.scaler_path)

    print(f"[ML] LSTM selesai — MAE: {mae:.4f}")

    return {
        'model': model,
        'mae': round(mae, 4),
        'loss': round(loss, 4)
    }
```

---

### `prediksi_arah`

```python
def prediksi_arah(self) -> dict:
    """
    Prediksi arah harga besok (NAIK/TURUN) menggunakan Random Forest.
    Load model dari disk jika sudah ada, training ulang jika belum.
    """
    # Load atau train model
    if os.path.exists(self.model_rf_path):
        model = joblib.load(self.model_rf_path)
        print(f"[ML] RF loaded dari disk")
    else:
        hasil_train = self.train_random_forest()
        model = hasil_train['model']

    # Siapkan data terbaru untuk prediksi
    X, y, fitur = self._siapkan_data_klasifikasi()
    X_terbaru = X[-1:].reshape(1, -1)

    # Prediksi
    prediksi      = model.predict(X_terbaru)[0]
    probabilitas  = model.predict_proba(X_terbaru)[0]
    prob_naik     = round(probabilitas[1] * 100, 1)
    prob_turun    = round(probabilitas[0] * 100, 1)

    arah = 'NAIK' if prediksi == 1 else 'TURUN'

    # Hitung skor ML (berbasis probabilitas prediksi)
    # Naik dengan prob tinggi = skor tinggi, Turun dengan prob tinggi = skor rendah
    skor = prob_naik if arah == 'NAIK' else (100 - prob_turun)

    return {
        'arah': arah,
        'probabilitas': prob_naik if arah == 'NAIK' else prob_turun,
        'prob_naik': prob_naik,
        'prob_turun': prob_turun,
        'skor': round(skor, 1),
        'model': 'Random Forest'
    }
```

---

### `prediksi_harga`

```python
def prediksi_harga(self) -> dict:
    """
    Prediksi harga numerik 7 hari ke depan menggunakan LSTM.
    Load model dari disk jika sudah ada, training ulang jika belum.
    """
    # Load atau train model + scaler
    if os.path.exists(self.model_lstm_path) and \
       os.path.exists(self.scaler_path):
        model  = load_model(self.model_lstm_path)
        self.scaler = joblib.load(self.scaler_path)
        print(f"[ML] LSTM loaded dari disk")
    else:
        hasil_train = self.train_lstm()
        model = hasil_train['model']

    # Ambil 60 hari terakhir
    data        = self.df[['Close']].values
    data_scaled = self.scaler.transform(data)
    last_window = data_scaled[-WINDOW_LSTM:].reshape(1, WINDOW_LSTM, 1)

    # Prediksi iteratif HORIZON_LSTM hari ke depan
    prediksi_scaled = []
    current_window  = last_window.copy()

    for _ in range(HORIZON_LSTM):
        pred = model.predict(current_window, verbose=0)
        prediksi_scaled.append(pred[0][0])

        # Geser window — tambah prediksi terbaru, hapus hari terlama
        current_window = np.append(
            current_window[:, 1:, :],
            pred.reshape(1, 1, 1),
            axis=1
        )

    # Kembalikan ke harga asli
    prediksi_harga = self.scaler.inverse_transform(
        np.array(prediksi_scaled).reshape(-1, 1)
    ).flatten()

    harga_sekarang = float(self.df['Close'].iloc[-1])

    hasil_per_hari = []
    for i, harga in enumerate(prediksi_harga):
        perubahan = ((harga - harga_sekarang) / harga_sekarang) * 100
        hasil_per_hari.append({
            'hari': i + 1,
            'harga': round(float(harga), 0),
            'perubahan_pct': round(float(perubahan), 2)
        })

    return {
        'harga_sekarang': round(harga_sekarang, 0),
        'harga_7hari': round(float(prediksi_harga[-1]), 0),
        'per_hari': hasil_per_hari,
        'model': 'LSTM'
    }
```

---

### `prediksi` — Fungsi Utama

```python
def prediksi(self) -> dict:
    """
    Fungsi utama — gabungkan prediksi RF (arah) + LSTM (harga).
    """
    try:
        print(f"[ML] Memulai prediksi untuk {self.kode}...")

        hasil_arah  = self.prediksi_arah()
        hasil_harga = self.prediksi_harga()

        return {
            'skor'        : hasil_arah['skor'],
            'arah'        : hasil_arah['arah'],
            'probabilitas': hasil_arah['probabilitas'],
            'prob_naik'   : hasil_arah['prob_naik'],
            'prob_turun'  : hasil_arah['prob_turun'],
            'harga_7hari' : hasil_harga['harga_7hari'],
            'per_hari'    : hasil_harga['per_hari'],
            'harga_sekarang': hasil_harga['harga_sekarang'],
        }

    except Exception as e:
        print(f"[ML] Error: {e}")
        return self._default_result()

def _default_result(self) -> dict:
    return {
        'skor'          : 50,
        'arah'          : 'UNKNOWN',
        'probabilitas'  : 50.0,
        'prob_naik'     : 50.0,
        'prob_turun'    : 50.0,
        'harga_7hari'   : 0,
        'per_hari'      : [],
        'harga_sekarang': 0,
    }
```

---

## TASK 4 — Buat Script Training Awal: `scripts/train_model.py`

Jalankan sekali untuk training dan simpan semua model:

```python
import sys
sys.path.append('.')

from modules.ml_model import MLAnalyzer

# Daftar saham yang ingin dianalisis
watchlist = ["DEWA", "BBCA", "TLKM", "ASII", "GOTO"]

for kode in watchlist:
    print(f"\nTraining model untuk {kode}...")
    try:
        analyzer = MLAnalyzer(kode)
        analyzer.train_random_forest()
        analyzer.train_lstm()
        print(f"OK — Model {kode} tersimpan")
    except Exception as e:
        print(f"GAGAL — {kode}: {e}")

print("\nSemua training selesai.")
print("Model tersimpan di: models/ml/")
```

Jalankan:
```bash
python scripts/train_model.py
```

---

## TASK 5 — Update `modules/scoring.py`

Pastikan parameter `ml` sudah ada dan bobot sesuai:

```python
def hitungSkorKomposit(teknikal, fundamental, ml, monte_carlo, bandar, sentimen):
    skor = (
        teknikal['skor']    * 0.20 +
        fundamental['skor'] * 0.25 +
        ml['skor']          * 0.15 +   # dari MLAnalyzer
        monte_carlo['skor'] * 0.15 +
        bandar['skor']      * 0.15 +
        sentimen['skor']    * 0.10
    )
    return round(skor, 1)
```

---

## TASK 6 — Update `main.py`

### Tambah Import

```python
from modules.ml_model import MLAnalyzer
```

### Panggil di fungsi `analisis_saham()`

```python
def analisis_saham(kode: str):
    # modul lain ...
    ml = MLAnalyzer(kode).prediksi()
```

### Tambah Section di `tampilkan_hasil()`

```
[MACHINE LEARNING]
  Prediksi arah besok : {ml['arah']} ({ml['probabilitas']}%)
  Prob naik           : {ml['prob_naik']}%
  Prob turun          : {ml['prob_turun']}%
  Prediksi harga +7hr : Rp {ml['harga_7hari']:,.0f}

  Detail per hari:
  +1: Rp {ml['per_hari'][0]['harga']:,.0f} ({ml['per_hari'][0]['perubahan_pct']:+.2f}%)
  +2: Rp {ml['per_hari'][1]['harga']:,.0f} ({ml['per_hari'][1]['perubahan_pct']:+.2f}%)
  +3: Rp {ml['per_hari'][2]['harga']:,.0f} ({ml['per_hari'][2]['perubahan_pct']:+.2f}%)
  ...
```

---

## Jadwal Retrain Mingguan di VPS

Model ML perlu diperbarui secara berkala agar tetap akurat:

```bash
crontab -e

# Retrain setiap Sabtu jam 01:00 dini hari (market tutup)
0 1 * * 6 /root/saham-env/bin/python /root/saham_analyzer/scripts/train_model.py >> /root/logs/training.log 2>&1

# Analisis harian jam 05:30 (gunakan model yang sudah ada)
30 5 * * 1-5 /root/saham-env/bin/python /root/saham_analyzer/main.py >> /root/logs/analisis.log 2>&1
```

---

## Performa di VPS (8 vCore, 32GB RAM)

| Operasi | Estimasi Waktu | RAM |
|---------|---------------|-----|
| Ambil data 2 tahun (1 saham) | 3–5 detik | < 1 GB |
| Hitung fitur teknikal | < 1 detik | < 1 GB |
| Training Random Forest | 10–30 detik | 1–2 GB |
| Training LSTM (20 epoch) | 3–8 menit | 2–4 GB |
| Load RF dari disk + prediksi | < 2 detik | < 1 GB |
| Load LSTM dari disk + prediksi 7 hari | 5–10 detik | 2–3 GB |
| Training 10 saham sekaligus | ~60–90 menit | 4–6 GB |

---

## Struktur Folder Final

```
saham_analyzer/
├── main.py                           <- Update
├── modules/
│   ├── teknikal.py                   — Tidak berubah
│   ├── fundamental.py                — Tidak berubah
│   ├── monte_carlo.py                — Tidak berubah
│   ├── bandarmologi.py               — Tidak berubah
│   ├── sentimen.py                   — Tidak berubah
│   ├── ml_model.py                   BARU — implementasi ini
│   └── scoring.py                    <- Update bobot
├── scripts/
│   ├── download_model.py             — Sudah ada (FinBERT)
│   └── train_model.py                BARU — training ML
├── models/
│   ├── finbert/                      — Sudah ada
│   └── ml/
│       ├── random_forest/
│       │   ├── DEWA_rf.pkl
│       │   ├── BBCA_rf.pkl
│       │   └── ...
│       └── lstm/
│           ├── DEWA_lstm.h5
│           ├── DEWA_scaler.pkl
│           ├── BBCA_lstm.h5
│           └── ...
├── logs/
│   ├── analisis.log
│   └── training.log
└── requirements.txt                  <- Update
```

---

## Contoh Output yang Diharapkan

```
[MACHINE LEARNING]
  Prediksi arah besok : NAIK (67.3%)
  Prob naik           : 67.3%
  Prob turun          : 32.7%
  Prediksi harga +7hr : Rp 468.000

  Detail per hari:
  +1 : Rp 445.000 (+1.14%)
  +2 : Rp 451.000 (+2.50%)
  +3 : Rp 458.000 (+4.09%)
  +4 : Rp 462.000 (+5.00%)
  +5 : Rp 464.000 (+5.45%)
  +6 : Rp 466.000 (+5.91%)
  +7 : Rp 468.000 (+6.36%)
```

---

## Testing

```python
# tests/test_ml.py
import sys
sys.path.append('.')
from modules.ml_model import MLAnalyzer

analyzer = MLAnalyzer("DEWA")

# Test 1: Fitur teknikal terhitung
assert len(analyzer.df) > 0
assert 'RSI' in analyzer.df.columns
assert 'MACD' in analyzer.df.columns
print("Test 1 passed — Fitur teknikal OK")

# Test 2: Training Random Forest
hasil_rf = analyzer.train_random_forest()
assert 'akurasi' in hasil_rf
assert 0 <= hasil_rf['akurasi'] <= 100
print(f"Test 2 passed — RF akurasi: {hasil_rf['akurasi']}%")

# Test 3: Training LSTM
hasil_lstm = analyzer.train_lstm()
assert 'mae' in hasil_lstm
assert hasil_lstm['mae'] >= 0
print(f"Test 3 passed — LSTM MAE: {hasil_lstm['mae']}")

# Test 4: Prediksi arah
hasil_arah = analyzer.prediksi_arah()
assert hasil_arah['arah'] in ['NAIK', 'TURUN']
assert 0 <= hasil_arah['prob_naik'] <= 100
assert 0 <= hasil_arah['prob_turun'] <= 100
assert abs(hasil_arah['prob_naik'] + hasil_arah['prob_turun'] - 100) < 0.1
print(f"Test 4 passed — Prediksi: {hasil_arah['arah']} ({hasil_arah['probabilitas']}%)")

# Test 5: Prediksi harga 7 hari
hasil_harga = analyzer.prediksi_harga()
assert 'harga_7hari' in hasil_harga
assert hasil_harga['harga_7hari'] > 0
assert len(hasil_harga['per_hari']) == 7
print(f"Test 5 passed — Harga +7hr: Rp {hasil_harga['harga_7hari']:,.0f}")

# Test 6: Fungsi utama prediksi()
hasil = analyzer.prediksi()
assert 'skor' in hasil
assert 0 <= hasil['skor'] <= 100
assert 'arah' in hasil
assert 'harga_7hari' in hasil
assert len(hasil['per_hari']) == 7
print(f"Test 6 passed — Skor ML: {hasil['skor']}/100")

# Test 7: Load model dari disk (tidak training ulang)
import os
assert os.path.exists(f"models/ml/random_forest/DEWA_rf.pkl")
assert os.path.exists(f"models/ml/lstm/DEWA_lstm.h5")
analyzer2 = MLAnalyzer("DEWA")
hasil2 = analyzer2.prediksi()
assert hasil2['arah'] in ['NAIK', 'TURUN']
print("Test 7 passed — Load dari disk OK")

print("\nSemua test ML passed!")
```

---

## Checklist Implementasi

- [ ] Update `requirements.txt` dengan dependencies ML
- [ ] Install: `pip install scikit-learn tensorflow-cpu joblib ta`
- [ ] Buat folder `models/ml/random_forest/` dan `models/ml/lstm/`
- [ ] Buat `modules/ml_model.py` dengan class `MLAnalyzer`
- [ ] Implementasi `__init__()` dengan path model per emiten
- [ ] Implementasi `_hitung_fitur()` dengan 13 fitur teknikal
- [ ] Implementasi `_siapkan_data_klasifikasi()` dengan label naik/turun
- [ ] Implementasi `_siapkan_data_lstm()` dengan window 60 hari
- [ ] Implementasi `train_random_forest()` dengan simpan ke disk
- [ ] Implementasi `train_lstm()` dengan EarlyStopping dan simpan ke disk
- [ ] Implementasi `prediksi_arah()` dengan load dari disk
- [ ] Implementasi `prediksi_harga()` dengan prediksi 7 hari iteratif
- [ ] Implementasi `prediksi()` sebagai fungsi utama
- [ ] Implementasi `_default_result()` untuk fallback error
- [ ] Buat `scripts/train_model.py` untuk training awal semua saham
- [ ] Jalankan `python scripts/train_model.py` untuk training pertama
- [ ] Update `modules/scoring.py` — pastikan parameter `ml` ada
- [ ] Update `main.py` — import, panggil, tampilkan output
- [ ] Setup cron job retrain mingguan di VPS (Sabtu 01:00)
- [ ] Jalankan semua test cases

---

## Catatan untuk AI

1. **Gunakan** `shuffle=False` saat train_test_split — data time series tidak boleh diacak
2. **Gunakan** `n_jobs=-1` di RandomForest — manfaatkan semua 8 vCore VPS
3. **Gunakan** `tensorflow-cpu` bukan `tensorflow` — VPS tidak punya GPU
4. **Simpan scaler** bersama model LSTM — scaler harus sama saat training dan inference
5. **Model disimpan per emiten** — `DEWA_rf.pkl`, `BBCA_rf.pkl`, dst. Jangan satu file untuk semua saham
6. **WINDOW_LSTM = 60** — jangan diubah tanpa mengubah shape input model
7. **Key wajib** di return `prediksi()`: `skor`, `arah`, `probabilitas`, `prob_naik`, `prob_turun`, `harga_7hari`, `per_hari`
8. **Panjang `per_hari`** harus selalu 7 item sesuai HORIZON_LSTM
9. **Jangan ubah** modul lain selain `scoring.py` dan `main.py`
10. **EarlyStopping patience=3** — agar training tidak terlalu lama di CPU