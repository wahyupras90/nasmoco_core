"""
repositories/tcare_realtime_web_repository.py

ADR026 — WebRepository pattern.

Beda dari Repository SQLite biasa (BaseRepository):
- Sumber data HTTP (web TAM), bukan SQLite -> TIDAK extend BaseRepository.
- Kontrak method tetap kembalikan pandas.DataFrame, supaya Service/Handler/
  Formatter di atasnya tidak perlu tahu bedanya sumber SQLite atau HTTP.

Aturan wajib (beda dari Repository SQLite):
- WAJIB error handling eksplisit, TIDAK BOLEH exit()/crash proses.
- Timeout wajib diset (10s connect / 20s read).
- TIDAK menulis ke nasmoco.db sama sekali.
- Session-per-request (bukan shared instance) -- app_v2.py melayani request
  konkuren via thread (ThreadingHTTPServer), shared mutable session berisiko
  race condition.
- Banyak VIN sekaligus: proses satu-satu, satu VIN gagal tidak boleh
  menggagalkan semua (kegagalan per-VIN dikembalikan sebagai bagian hasil,
  bukan exception yang menjalar ke atas).

Referensi asal (tcare_realtime.py, project lama) -- HANYA referensi logic,
BUKAN pola robustness (script lama pakai exit(), tanpa timeout, tanpa
penanganan error).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://aftersales.toyota.astra.co.id/data"

# Timeout: (connect_timeout, read_timeout) -- dikonfirmasi Wahyu: 10s / 20s
DEFAULT_TIMEOUT = (10, 20)


class TCARERealtimeError(Exception):
    """Error domain untuk kegagalan login/fetch/parse TCARE Realtime.

    Handler menangkap ini dan mengubahnya jadi HandlerResult dengan
    code {INT013}_ERROR -- TIDAK PERNAH dibiarkan menjalar sampai
    membuat app_v2.py crash.
    """


@dataclass
class VinFetchResult:
    """Hasil fetch satu VIN. Salah satu dari (data terisi) atau (error terisi)."""
    vin: str
    vehicle: Optional[pd.DataFrame] = None
    customer: Optional[pd.DataFrame] = None
    services: Optional[pd.DataFrame] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class TCARERealtimeWebRepository:
    """
    Bukan extend BaseRepository (itu khusus SQLite). Kontrak method mirip
    (kembalikan DataFrame) supaya Service/Handler/Formatter di atasnya
    tidak perlu tahu bedanya sumbernya SQLite atau HTTP.

    Instance ini dibuat BARU per request (session-per-request), TIDAK
    di-reuse lintas request -- lihat catatan thread-safety di atas.
    """

    def __init__(self, email: str, password: str, timeout: tuple = DEFAULT_TIMEOUT):
        if not email or not password:
            raise ValueError("email dan password wajib diisi (lihat config TAM_EMAIL/TAM_PASSWORD)")
        self._email = email
        self._password = password
        self._timeout = timeout
        self._session: Optional[requests.Session] = None

    # ------------------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------------------

    def _login(self) -> None:
        """Login sekali per instance repository. Raises TCARERealtimeError kalau gagal.

        TIDAK PERNAH exit()/crash -- semua kegagalan dibungkus jadi exception
        domain yang bisa ditangkap Handler.
        """
        session = requests.Session()

        try:
            r = session.get(f"{BASE_URL}/login", timeout=self._timeout)
            r.raise_for_status()
        except requests.RequestException as e:
            raise TCARERealtimeError(f"Gagal membuka halaman login TAM: {e}") from e

        soup = BeautifulSoup(r.text, "html.parser")
        token_input = soup.find("input", {"name": "_token"})

        if token_input is None or not token_input.get("value"):
            raise TCARERealtimeError("Token CSRF tidak ditemukan di halaman login TAM (kemungkinan struktur halaman berubah)")

        token = token_input["value"]

        payload = {
            "_token": token,
            "email": self._email,
            "password": self._password,
        }

        try:
            r = session.post(f"{BASE_URL}/login", data=payload, timeout=self._timeout)
        except requests.RequestException as e:
            raise TCARERealtimeError(f"Gagal mengirim login ke TAM: {e}") from e

        if "dashboard" not in r.url.lower():
            raise TCARERealtimeError("Login TAM gagal (kredensial ditolak atau redirect tidak sesuai)")

        self._session = session

    def _ensure_login(self) -> None:
        if self._session is None:
            self._login()

    # ------------------------------------------------------------------
    # PER-VIN FETCH
    # ------------------------------------------------------------------

    def get_vin_data(self, vin: str) -> VinFetchResult:
        """Fetch data satu VIN. Tidak pernah raise -- semua error masuk ke
        VinFetchResult.error supaya banyak VIN bisa diproses satu-satu tanpa
        satu kegagalan menggagalkan yang lain."""
        vin = (vin or "").strip().upper()

        if not vin:
            return VinFetchResult(vin=vin, error="VIN kosong")

        try:
            self._ensure_login()
        except TCARERealtimeError as e:
            return VinFetchResult(vin=vin, error=str(e))

        try:
            r = self._session.get(
                f"{BASE_URL}/tCare/vin",
                params={"vin": vin},
                timeout=self._timeout,
            )
            r.raise_for_status()
        except requests.Timeout:
            return VinFetchResult(vin=vin, error=f"Timeout saat mengambil data VIN {vin}")
        except requests.RequestException as e:
            return VinFetchResult(vin=vin, error=f"Gagal mengambil data VIN {vin}: {e}")

        try:
            return self._parse_vin_page(vin, r.text)
        except Exception as e:  # noqa: BLE001 -- parsing HTML pihak ketiga, harus defensif
            logger.exception("Gagal parse halaman TCARE realtime untuk VIN %s", vin)
            return VinFetchResult(vin=vin, error=f"Gagal parse data VIN {vin}: {e}")

    def get_multiple(self, vins: list[str]) -> list[VinFetchResult]:
        """Proses banyak VIN satu-satu. Tidak ada batas jumlah (sesuai keputusan),
        tapi satu VIN gagal tidak menggagalkan yang lain."""
        return [self.get_vin_data(vin) for vin in vins]

    # ------------------------------------------------------------------
    # PARSING
    # ------------------------------------------------------------------

    def _parse_vin_page(self, vin: str, html: str) -> VinFetchResult:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        if len(tables) < 3:
            return VinFetchResult(vin=vin, error="Data tidak ditemukan (VIN tidak terdaftar atau struktur halaman berubah)")

        vehicle_df = self._parse_keyvalue_table(tables[0])
        customer_df = self._parse_keyvalue_table(tables[1], blank_owner_not_registered=True)
        services_df = self._parse_history_table(tables[2])

        return VinFetchResult(vin=vin, vehicle=vehicle_df, customer=customer_df, services=services_df)

    @staticmethod
    def _parse_keyvalue_table(table, blank_owner_not_registered: bool = False) -> pd.DataFrame:
        """Parse tabel key-value (data kendaraan / customer).

        Kasus khusus (ditemukan dari inspeksi HTML asli, bukan asumsi):
        tabel customer bisa berisi SATU baris dengan `colspan="3"` berupa
        pesan teks (mis. "Owners have not registered, please register to
        download the certificate.") alih-alih baris key-value 3 kolom biasa
        -- ini muncul kalau customer belum registrasi. Baris seperti ini
        (hanya 1 <td>) ditangkap sebagai {"key": "catatan", "value": <teks>}
        supaya informasinya tetap tampil ke user, bukan diam-diam hilang.
        """
        rows = []
        for row in table.find_all("tr"):
            cols = [c.get_text(" ", strip=True) for c in row.find_all("td")]

            if len(cols) == 1:
                rows.append({"key": "catatan", "value": cols[0]})
                continue

            if len(cols) < 3:
                continue

            key, value = cols[0], cols[2]
            if blank_owner_not_registered and key.lower() == "owner" and "not registered" in value.lower():
                value = ""
            rows.append({"key": key, "value": value})
        return pd.DataFrame(rows, columns=["key", "value"])

    @staticmethod
    def _parse_history_table(table) -> pd.DataFrame:
        columns = ["kunjungan", "tanggal", "dealer", "tepat", "status", "ontime_service"]
        rows = []
        for row in table.find_all("tr")[1:]:  # skip header
            cols = [c.get_text(" ", strip=True) for c in row.find_all("td")]
            if len(cols) < 6:
                continue
            rows.append(dict(zip(columns, cols[:6])))
        return pd.DataFrame(rows, columns=columns)
