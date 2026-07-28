"""
Scaffold untuk scraping data tambahan dari sumber lain (idx.co.id, RTI, Stockbit, dll).

CATATAN PENTING:
Saya sengaja TIDAK menghardcode endpoint API internal RTI Business / Stockbit / idx.co.id
di sini, karena:
  1. Endpoint tersebut tidak didokumentasikan resmi & sering berubah tanpa pemberitahuan.
  2. Kalau saya menebak endpoint tanpa verifikasi langsung, kode ini berisiko langsung
     gagal saat kamu jalankan (404 / berubah struktur JSON), dan kamu akan buang waktu debug.

Cara paling aman menemukan endpoint yang valid & terkini:
  1. Buka https://www.idx.co.id/ (atau RTI Business web version) di Chrome.
  2. Buka DevTools (F12) -> tab Network -> filter "Fetch/XHR".
  3. Cari saham (misal ketik "BBCA") atau buka halaman company profile.
  4. Perhatikan request JSON yang muncul (biasanya di bawah domain idx.co.id/primary/... ).
  5. Klik kanan request itu -> Copy -> Copy as cURL, lalu kirim ke saya.
     Saya akan bantu ubah jadi fungsi Python yang solid + parsing-nya.

Sambil menunggu itu, fundamental ratio dasar (PER, PBV, ROE, DER, EPS, dividend yield)
sudah tersedia lewat `data.price_fetcher.fetch_quick_info()` yang bersumber dari Yahoo
Finance -- cukup akurat untuk saham-saham likuid IDX (LQ45/IDX30) dan sudah dipakai
sebagai sumber utama fundamental di `analysis/fundamental.py`.

Fungsi di bawah ini adalah TEMPLATE generic scraper (pakai requests + BeautifulSoup)
yang bisa langsung kamu isi begitu endpoint/URL final sudah didapat.
"""
import time
import requests
from bs4 import BeautifulSoup

from config import HTTP_HEADERS, REQUEST_DELAY_SECONDS


def fetch_json(url: str, params: dict | None = None) -> dict:
    """Generic GET request yang mengembalikan JSON, dengan header wajar."""
    resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return resp.json()


def fetch_html(url: str) -> BeautifulSoup:
    """Generic GET request yang mengembalikan objek BeautifulSoup untuk parsing HTML."""
    resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(resp.text, "html.parser")


def fetch_company_profile_template(ticker: str) -> dict:
    """
    TODO: isi `url` dan mapping field di bawah setelah endpoint asli didapat
    dari langkah DevTools di atas. Struktur return disamakan dengan yang
    dipakai di analysis/fundamental.py supaya tinggal plug-and-play.
    """
    raise NotImplementedError(
        "Isi endpoint resmi di sini setelah kamu dapat URL dari DevTools Network tab. "
        "Lihat docstring modul ini untuk panduan langkah-langkahnya."
    )
