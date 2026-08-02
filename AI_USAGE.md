# Tutorial Penggunaan Aplikasi untuk AI

Dokumen ini adalah panduan ringkas agar AI atau agent otomatis bisa memakai
Stock Analyzer lewat web UI, CLI, atau HTTP API.

> Hasil aplikasi adalah shortlist analisis, bukan kepastian profit dan bukan
> instruksi auto-trading. AI wajib menyebut risiko data kosong, delay data,
> likuiditas rendah, berita mendadak, dan perubahan market intraday.

## 1. Jalankan Aplikasi

Lokal:

```bash
pip install -r requirements.txt
python web_app.py
```

Buka web:

```text
http://127.0.0.1:8002
```

Docker:

```bash
docker compose up -d --build
```

Buka VPS:

```text
http://IP_VPS:8002
```

## 2. Alur Pakai yang Disarankan

### Analisa satu atau beberapa saham

Gunakan saat user memberi kode emiten seperti `BBCA`, `TLKM`, `BMRI`.

1. Panggil `/api/analyze`.
2. Aktifkan opsi tambahan hanya jika dibutuhkan.
3. Jelaskan rekomendasi, skor komposit, alasan, red flag, dan sinyal penting.

### Cari saham kualitas terbaik

Gunakan `/api/screen` untuk shortlist awal dari universe IDX.

Mode ini cocok untuk mencari saham layak pantau berdasarkan komposit teknikal,
fundamental, likuiditas, dan bandarmologi.

### Cari potensi top gainer atau momentum

Gunakan `/api/momentum`.

- `preopen`: dipakai sore hari atau sebelum market buka untuk watchlist besok.
- `morning`: dipakai setelah 09:15 WIB untuk validasi Opening Range 15 menit.
- `session2`: dipakai setelah 13:30 WIB, atau setelah 14:00 WIB pada Jumat.
- `intraday`: dipakai saat market berjalan atau jelang close.

## 3. HTTP API

Base URL lokal:

```text
http://127.0.0.1:8002
```

### POST `/api/analyze`

Payload:

```json
{
  "tickers": "BBCA TLKM",
  "options": {
    "backtest": false,
    "monteCarlo": false,
    "bootstrap": false,
    "garch": false,
    "atr": false,
    "vwap": false,
    "sentiment": false,
    "ml": false
  }
}
```

Catatan:

- Maksimal 10 ticker per request.
- Kode cukup `BBCA`, suffix `.JK` ditambahkan otomatis.
- `sentiment` butuh model lokal `models/finbert`.
- `ml` butuh model hasil training di `models/ml`.

Contoh `curl`:

```bash
curl -s http://127.0.0.1:8002/api/analyze \
  -H "Content-Type: application/json" \
  -d "{\"tickers\":\"BBCA TLKM\",\"options\":{\"ml\":true,\"vwap\":true}}"
```

### POST `/api/screen`

Payload:

```json
{
  "maxTickers": 1009,
  "limit": 15
}
```

Catatan:

- `maxTickers` dibatasi maksimal 1200.
- `limit` dibatasi maksimal 50.
- Universe ticker dibaca dari `data/idx_universe.txt`.
- Ticker di `data/suspended_tickers.txt` otomatis tidak masuk hasil screener.

Contoh:

```bash
curl -s http://127.0.0.1:8002/api/screen \
  -H "Content-Type: application/json" \
  -d "{\"maxTickers\":1009,\"limit\":15}"
```

### POST `/api/momentum`

Payload rekomendasi pre-open:

```json
{
  "maxTickers": 1009,
  "limit": 15,
  "mode": "preopen",
  "relativeStrength": true,
  "accumulation": true,
  "sectorHeat": true,
  "sectorNews": true,
  "overnightCatalyst": true,
  "ml": false
}
```

Payload rekomendasi sesi 2:

```json
{
  "maxTickers": 1009,
  "limit": 15,
  "mode": "session2",
  "relativeStrength": false,
  "accumulation": false,
  "sectorHeat": true,
  "sectorNews": true,
  "overnightCatalyst": false,
  "ml": true
}
```

Mode yang valid:

```text
preopen, morning, session2, intraday
```

Contoh:

```bash
curl -s http://127.0.0.1:8002/api/momentum \
  -H "Content-Type: application/json" \
  -d "{\"maxTickers\":1009,\"limit\":15,\"mode\":\"preopen\",\"relativeStrength\":true,\"accumulation\":true,\"sectorHeat\":true,\"sectorNews\":true,\"overnightCatalyst\":true,\"ml\":false}"
```

### GET `/api/sector-news`

Dipakai untuk membaca snapshot berita sektor pagi.

```bash
curl -s http://127.0.0.1:8002/api/sector-news
```

### GET `/api/global-market`

Dipakai untuk membaca kondisi indeks global, VIX, dan USD/IDR sebagai konteks
`RISK ON`, `NETRAL`, atau `RISK OFF`.

```bash
curl -s http://127.0.0.1:8002/api/global-market
```

## 4. CLI

Analisa saham:

```bash
python main.py BBCA
python main.py BBCA TLKM BMRI
```

Dengan opsi:

```bash
python main.py BBCA --backtest
python main.py BBCA --sentiment
python main.py BBCA --ml
python main.py BBCA --vwap
python main.py --global-market
```

Training ML:

```bash
python scripts/train_model.py
python scripts/train_model.py BBCA TLKM
python scripts/train_model.py BBCA --rf-only
```

## 5. Cara AI Membaca Hasil

Field penting `/api/analyze`:

- `recommendation`: rekomendasi utama, misalnya `BUY`, `HOLD/WATCH`, atau `AVOID/SELL`.
- `composite_score`: skor gabungan.
- `technical.score`: skor teknikal.
- `fundamental.score`: skor fundamental.
- `liquidity.score`: skor likuiditas.
- `bandarmology.skor`: indikasi akumulasi/distribusi.
- `technical.fibonacci`: konfirmasi Fibonacci, bukan sinyal mandiri.
- `ml`: prediksi ML jika model tersedia.
- `red_flags`: risiko fundamental atau data yang perlu diwaspadai.
- `reason`: ringkasan alasan sistem.

Field penting `/api/momentum`:

- `qualified`: jumlah kandidat lolos filter.
- `checked`: jumlah ticker dicek.
- `results[].ticker`: kode emiten.
- `results[].momentum.score`: skor momentum.
- `results[].momentum.status`: `KUAT`, `MENARIK`, atau `LEMAH`.
- `results[].momentum.change_pct`: perubahan harga hari ini.
- `results[].momentum.time_volume_ratio`: RVOL slot waktu untuk morning/session2.
- `results[].momentum.price_vs_vwap_pct`: posisi harga terhadap VWAP.
- `results[].momentum.signals`: alasan teknikal yang lolos.
- `results[].orderflow`: bid/offer imbalance, foreign net buy, broker accumulation, frequency, dan running trade jika `data/broker_orderbook.csv` tersedia.
- `results[].cross_sectional_rank`: probabilitas model ranking lintas saham, jika histori tersedia.
- `warnings`: alasan fitur dilewati atau market belum masuk waktu yang benar.
- `errors`: contoh kegagalan data dari provider.

## 6. Template Jawaban AI

Gunakan format singkat seperti ini:

```text
Hasil screening:
1. TICKER - skor X, status Y.
   Alasan: sinyal utama, volume/RVOL, VWAP, sektor, Fibonacci/ML bila ada.
   Risiko: red flag, data kosong, likuiditas, atau market timing.

Kesimpulan:
Ini watchlist, bukan kepastian. Validasi lagi dengan orderbook, value transaksi,
support-resistance, dan batas cut loss.
```

## 7. Aturan Penting untuk AI

- Jangan klaim akurasi 100%.
- Jangan memberi instruksi beli tanpa konteks risiko.
- Jangan memakai `session2` sebelum waktu sesi 2 dimulai.
- Jangan memakai `morning` sebelum 09:15 WIB.
- Jika `qualified` bernilai 0, jelaskan filter terlalu ketat atau data provider kosong.
- Jika Yahoo Finance error, sarankan cek koneksi, firewall, VPN, atau coba ulang.
- Jika ML kosong, jelaskan model belum dilatih atau akurasi uji tidak layak.
- Jika ranking lintas saham kosong, jelaskan `data/momentum_rank_history.csv` belum tersedia atau label histori belum cukup.
- Jika orderflow kosong, jelaskan `data/broker_orderbook.csv` belum tersedia atau belum diisi dari sumber broker/orderbook.
- Untuk pre-open, prioritaskan RS vs IHSG, akumulasi 5D, sektor panas, berita sektor, katalis overnight, lalu konfirmasi Fibonacci.
- Untuk sesi 2, prioritaskan RVOL slot waktu, posisi di atas VWAP, akselerasi sesi 2, sektor panas, berita sektor, dan ML rerank jika tersedia.
- Kondisi global dipakai sebagai konteks market, bukan filter utama untuk beli/jual.
