"""
repositories/customer_profile_repository.py

Repository untuk tabel `customer_profile` (48.137 baris, PK: no_rangka).

Dipakai BERSAMA oleh HistoryServiceRepository (INT002) dan
HistoryTCARERepository (INT003) lewat komposisi (has-a), BUKAN
disalin ke masing-masing file. Ini implementasi tunggal untuk:

  - BR020: RO/kunjungan = customer_profile.total_kunjungan_fisik,
    dibaca apa adanya, tidak pernah dihitung ulang dari tabel transaksi.
  - BR027: satu implementasi rumus yang dipakai bersama INT002 & INT003
    (di sini: cara resolve identifier customer -> baris customer_profile,
    dan cara membaca RO). Kalau ada Room lain (5-8) yang juga butuh data
    customer_profile, mereka sebaiknya memakai class ini juga alih-alih
    menulis ulang query yang sama (ADR008: Single Source of Truth).

Aturan repository standar tetap berlaku (ADR001/ADR003): hanya query,
tidak ada business logic, selalu mengembalikan DataFrame lewat
BaseRepository.execute()/execute_one().
"""

from typing import Optional

import pandas as pd

from db.base_repository import BaseRepository


def _normalize_plate(value: str) -> str:
    """Hilangkan spasi & strip, uppercase — lihat get_by_no_polisi()."""
    return value.upper().replace("-", "").replace(" ", "")


class CustomerProfileRepository(BaseRepository):
    """Akses read-only ke `customer_profile`."""

    def get_by_no_rangka(self, no_rangka: str) -> pd.DataFrame:
        """Cari profil customer berdasarkan no_rangka (PK, exact match)."""
        return self.execute(
            "SELECT * FROM customer_profile WHERE no_rangka = ?",
            (no_rangka,),
        )

    def get_by_no_polisi(self, no_polisi: str) -> pd.DataFrame:
        """
        Cari profil customer berdasarkan no_polisi (exact match setelah
        normalisasi, case-insensitive).

        PENTING (ditemukan lewat smoke test nyata terhadap nasmoco.db):
        format `no_polisi` di data asli TERNYATA memakai strip sebagai
        pemisah (mis. "G-1576-DF"), bukan spasi ("G 1576 DF") seperti
        yang diasumsikan di awal berdasarkan format plat konvensional.
        Karena parser (`handlers/*/parser.py`) mengekstrak plat sebagai
        alfanumerik tanpa pemisah SAMA SEKALI (mis. "G1576DF") atau
        dengan spasi ("G 1576 DF"), sisi database maupun sisi parameter
        query di sini DIHILANGKAN spasi dan striplah sebelum dibandingkan
        — supaya "G1576DF", "G 1576 DF", dan "G-1576-DF" semuanya
        dianggap identifier yang sama.

        Bisa mengembalikan >1 baris kalau no_polisi pernah dipakai ulang
        oleh lebih dari satu no_rangka di data historis — Service yang
        memutuskan apakah ini AMBIGUOUS.
        """
        normalized_input = _normalize_plate(no_polisi)
        return self.execute(
            "SELECT * FROM customer_profile "
            "WHERE REPLACE(REPLACE(UPPER(no_polisi), '-', ''), ' ', '') = ?",
            (normalized_input,),
        )

    def get_by_customer_name(self, customer_name: str) -> pd.DataFrame:
        """
        Cari profil customer berdasarkan nama (partial match, case-insensitive).

        Sengaja pakai LIKE (bukan exact match) karena input user biasanya
        tidak persis sama dengan nama di database (mis. "budi" vs
        "BUDI SANTOSO"). Bisa mengembalikan banyak baris -> Service yang
        memutuskan AMBIGUOUS + suggestions.
        """
        return self.execute(
            "SELECT * FROM customer_profile WHERE UPPER(customer) LIKE UPPER(?)",
            (f"%{customer_name}%",),
        )

    def get_total_kunjungan_fisik(self, no_rangka: str) -> Optional[int]:
        """
        BR020: RO (jumlah kunjungan) = customer_profile.total_kunjungan_fisik.

        Dibaca langsung dari kolom hasil ETL (BR026) — tidak pernah
        dihitung ulang dari agregasi tabel transaksi (unitmasuk,
        tcare_schedule_full_history, dll).
        """
        value = self.scalar(
            "SELECT total_kunjungan_fisik FROM customer_profile WHERE no_rangka = ?",
            (no_rangka,),
        )
        if value is None:
            return None
        return int(value)
