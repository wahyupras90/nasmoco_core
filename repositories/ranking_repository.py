"""
repositories/ranking_repository.py

Repository untuk INT006 (Ranking).

Tabel: `daily_kpi` + `target_bulanan` (sama seperti KPIRepository, lihat
docstring modul tersebut untuk skema lengkap). Query di sini SENGAJA
terpisah dari `KPIRepository` walau tabelnya sama, karena Ranking butuh
agregasi GROUP BY sa per periode (bentuk query beda dari KPI
Summary/Detail yang query per-tanggal) -- bukan duplikasi tanpa alasan,
tapi shape data yang beda (BR027 dipatuhi lewat SQL SUM/GROUP BY di sini,
bukan agregasi ulang di Python atas data yang sama yang sudah diambil
KPIRepository).

Aturan exclude (dikonfirmasi eksplisit dengan user):
  - `sa = 'Counter'` : SELALU di-exclude dari hasil ranking per-SA
    (transaksi tanpa WO, bukan entitas yang bisa di-rank).
  - `target_bulanan.sa = 'TOTAL'` (tipe='ALL') : baris agregat outlet,
    bukan entitas rank -- diambil terpisah lewat `get_outlet_total()`,
    TIDAK ikut di `get_ranking_source()`.

ADR003/ADR004: tidak ada business rule (penentuan skor/urutan akhir) di
sini -- itu tugas RankingService. Repository hanya menyediakan data
mentah teragregasi per SA.
"""

from typing import Optional

import pandas as pd

from db.base_repository import BaseRepository

EXCLUDED_SA_FROM_RANKING = ("Counter",)


class RankingRepository(BaseRepository):
    """Akses read-only ke `daily_kpi` (agregat per SA) + `target_bulanan`."""

    def get_ranking_source(self, date_from: str, date_to: str) -> pd.DataFrame:
        """
        Agregat `daily_kpi` per SA pada rentang tanggal, EXCLUDE
        `sa='Counter'`. Kolom hasil: sa, unit_entry, cpus, revenue,
        jasa, tgp, adt, sublet, upselling, total_liter (semua SUM).
        """
        placeholders = ",".join(["?"] * len(EXCLUDED_SA_FROM_RANKING))
        sql = (
            "SELECT sa, "
            "SUM(unit_entry) AS unit_entry, "
            "SUM(cpus) AS cpus, "
            "SUM(revenue) AS revenue, "
            "SUM(jasa) AS jasa, "
            "SUM(tgp) AS tgp, "
            "SUM(adt) AS adt, "
            "SUM(sublet) AS sublet, "
            "SUM(upselling) AS upselling, "
            "SUM(total_liter) AS total_liter "
            "FROM daily_kpi "
            "WHERE tanggal >= ? AND tanggal <= ? "
            f"AND sa NOT IN ({placeholders}) "
            "GROUP BY sa"
        )
        params = [date_from, date_to, *EXCLUDED_SA_FROM_RANKING]
        return self.execute(sql, params)

    def get_targets_for_ranking(self, tahun: int, bulan: int) -> pd.DataFrame:
        """
        Target per-SA untuk (tahun, bulan), EXCLUDE `sa='TOTAL'`
        (baris agregat outlet, bukan entitas rank).
        """
        return self.execute(
            "SELECT * FROM target_bulanan "
            "WHERE tahun = ? AND bulan = ? AND sa != 'TOTAL' "
            "ORDER BY sa",
            (tahun, bulan),
        )

    def get_outlet_total(self, tahun: int, bulan: int) -> Optional[dict]:
        """
        Baris target agregat outlet (`sa='TOTAL'`, `tipe='ALL'`) untuk
        (tahun, bulan) -- ditampilkan TERPISAH di akhir hasil ranking,
        bukan ikut di-rank sebagai SA (dikonfirmasi eksplisit user).
        """
        return self.execute_one(
            "SELECT * FROM target_bulanan WHERE tahun = ? AND bulan = ? AND sa = 'TOTAL'",
            (tahun, bulan),
        )

    def has_target_for_year(self, tahun: int) -> bool:
        return self.exists(
            "SELECT 1 FROM target_bulanan WHERE tahun = ? LIMIT 1", (tahun,)
        )
