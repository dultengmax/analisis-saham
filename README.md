# Stock Analyzer

Analisa saham Indonesia berbasis teknikal, fundamental, likuiditas, bandarmologi, sentimen berita, dan screener momentum.

> Tool ini untuk membantu screening dan disiplin analisa. Bukan jaminan profit dan bukan sinyal auto-trading.

## Fitur Utama

- Analisa satu atau beberapa saham IDX.
- Skor teknikal, fundamental, likuiditas, bandarmologi, dan komposit.
- Red flag fundamental.
- Sentimen berita 30 hari terakhir dengan FinBERT lokal.
- Auto Screener IDX untuk mencari kandidat berkualitas.
- Momentum Screener:
  - Pre-Open besok
  - Sesi Pagi / 09:15
  - Sesi 2 / 13:30
  - Intraday / jelang close
- Relative Strength vs IHSG dan Akumulasi 5D untuk mode pre-open.
- Fibonacci retracement 23,6-78,6 sebagai konfirmasi teknikal maksimal +/-8 poin.
- Snapshot berita pagi per sektor IDX.
- Prediksi Machine Learning per emiten dengan Random Forest dan LSTM CPU.
- Web UI ringan tanpa framework frontend.
- Docker Compose untuk deploy VPS.

## Quick Start Lokal

```bash
cd stock_analyzer
pip install -r requirements.txt
python web_app.py
```

Buka:

```text
http://127.0.0.1:8002
```

## CLI

```bash
# Analisa satu saham
python main.py BBCA

# Analisa beberapa saham
python main.py BBCA TLKM BMRI ASII

# Backtest sinyal teknikal
python main.py BBCA --backtest

# Analisis berita dengan FinBERT lokal
python main.py BBCA --sentiment
```

Kode saham cukup ditulis kode IDX seperti `BBCA`, `TLKM`, `BMRI`. Suffix `.JK` ditambahkan otomatis.

## Sentimen FinBERT

Fitur sentimen membutuhkan model lokal di `models/finbert`.

```bash
pip install torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python scripts/download_model.py
```

Model hanya perlu diunduh sekali.

## Machine Learning

Model ML bersifat opsional dan disimpan per emiten di `models/ml/`.
Random Forest memprediksi arah besok, sedangkan LSTM memproyeksikan harga
tujuh hari. Pilih opsi `Machine Learning` di website atau gunakan:

```bash
python main.py BBCA --ml
```

Training awal watchlist:

```bash
python scripts/train_model.py
```

Training emiten tertentu atau Random Forest saja:

```bash
python scripts/train_model.py BBCA TLKM ASII
python scripts/train_model.py BBCA --rf-only
```

Contoh cron retrain mingguan pada deployment Docker:

```cron
0 1 * * 6 cd /opt/stock_analyzer && docker compose exec -T stock-analyzer python scripts/train_model.py >> logs/training.log 2>&1
```

Training memakai split kronologis tanpa shuffle. Model ML adalah faktor
tambahan dengan bobot 15% dan tidak digunakan jika training gagal.

## Deploy VPS dengan Docker Compose

```bash
git clone <repo-ini> stock_analyzer
cd stock_analyzer
docker compose up -d --build
```

Buka:

```text
http://IP_VPS:8002
```

Jika firewall aktif:

```bash
sudo ufw allow 8002/tcp
```

Update aplikasi:

```bash
git pull
docker compose up -d --build
```

Cek log:

```bash
docker compose logs -f
```

Catatan Docker:

- Folder `.cache/` dimount agar cache Yahoo Finance tidak hilang.
- Folder `models/finbert/` dimount read-only, sedangkan `models/ml/` dapat ditulis untuk retraining.
- Jika ingin fitur sentimen di VPS, pastikan `models/finbert` tersedia di VPS.

## Screener Web

### Auto Screener IDX

Mencari saham yang lolos filter kualitas:

- bukan `AVOID/SELL`
- tidak punya red flag
- skor komposit tinggi
- mempertimbangkan teknikal, fundamental, likuiditas, dan bandarmologi

Universe ticker ada di:

```text
data/idx_universe.txt
```

### Momentum Screener

Mode momentum:

- `Pre-Open besok`: mencari setup untuk dipantau sebelum market buka.
- `Sesi Pagi / 09:15`: membandingkan RVOL 09:00-09:15 terhadap 20 hari
  dan menilai breakout Opening Range 15 menit dengan konfirmasi VWAP.
- `Sesi 2 / 13:30`: mencari calon susulan sesi 2, bukan yang sudah top gainer dari pagi.
- `Intraday / jelang close`: mencari saham yang sedang punya momentum harian.

Mode `Sesi 2 / 13:30` memakai VWAP intraday. Kandidat yang bertahan di atas VWAP mendapat bonus, sedangkan yang sudah di bawah VWAP tidak lolos filter sesi 2.

Semua mode memakai Fibonacci dari 60 bar terakhir sebagai overlay konfirmasi.
Bonus atau penalti dibatasi maksimal 8 poin dan baru positif jika didukung volume
serta, untuk intraday, posisi harga di atas VWAP. Fibonacci bukan sinyal beli mandiri.

Opsi pre-open:

- `RS vs IHSG`: bonus jika saham naik saat IHSG lemah atau outperform IHSG.
- `Akumulasi 5D`: bonus jika close dan/atau volume naik bertahap dalam 3-5 hari terakhir.
- `Berita Sektor Pagi`: membaca katalis berita sektor 24 jam terakhir sebagai bonus/penalti kecil.
- `Katalis Overnight`: menggabungkan berita emiten, corporate-action dari berita,
  indeks regional, minyak, emas, tembaga, dan USD/IDR pada shortlist pre-open.

Berita sektor diperbarui otomatis mulai pukul 06.00 WIB dan disimpan di
`.cache/sector_news.json`. Skema lengkapnya dapat dibaca dari:

```text
GET http://127.0.0.1:8002/api/sector-news
```

Faktor ini memakai aturan frasa finansial yang ringan dan tidak memuat model FinBERT.

## Cara Kerja Skor

### Teknikal

Menggunakan:

- SMA/EMA trend
- MACD
- RSI
- Stochastic
- Bollinger Band
- Volume confirmation

### Fundamental

Menggunakan:

- PER
- PBV
- ROE
- DER
- Dividend Yield

Threshold ada di `config.py`.

### Likuiditas

Menggunakan:

- average traded value 20 hari
- average volume 20 hari

Saham terlalu sepi mendapat skor rendah.

### Bandarmologi

Menggunakan:

- akumulasi/distribusi
- OBV trend
- divergence
- MFI

### Sentimen

Menggunakan:

- Google News RSS
- Kontan
- filter 30 hari terakhir
- koreksi frasa finansial bahasa Indonesia

## Sumber Data

- Harga historis dan rasio dasar: Yahoo Finance.
- Daftar universe ticker: `data/idx_universe.txt`.
- Sentimen berita: Google News RSS dan Kontan.

Catatan:

- Data Yahoo bisa kosong untuk sebagian ticker kecil/tidak aktif.
- Beberapa rasio fundamental Yahoo bisa tidak lengkap atau formatnya berbeda.
- Untuk data resmi IDX atau broker summary, perlu integrasi sumber data tambahan.

## Struktur Proyek

```text
stock_analyzer/
├── analysis/
│   ├── technical.py
│   ├── fundamental.py
│   ├── liquidity.py
│   ├── bandarmologi.py
│   ├── momentum.py
│   ├── sentiment.py
│   └── scorer.py
├── backtest/
├── data/
│   ├── idx_universe.txt
│   ├── price_fetcher.py
│   └── idx_fetcher.py
├── scripts/
├── static/
├── tests/
├── config.py
├── main.py
├── web_app.py
├── Dockerfile
└── docker-compose.yml
```

## Testing

```bash
python -m unittest discover tests
```

## Batasan Akurasi

Screener membaca data historis dan kondisi terakhir, bukan masa depan. Hasil bisa meleset karena:

- berita mendadak
- market shock
- antrian bid/offer tidak tersedia
- data Yahoo terlambat/kosong
- saham tidak likuid
- aksi bandar atau rumor intraday

Gunakan hasil sebagai shortlist, lalu tetap validasi dengan chart, orderbook, value transaksi, dan risk management.
