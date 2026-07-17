"""
repositories/kpi_repository.py

Repository SHARED untuk INT004 (KPI Summary) dan INT005 (KPI Detail),
sesuai BR027 (satu implementasi untuk sumber data yang sama) -- pola yang
sama seperti `CustomerProfileRepository` di Room 4.

Tabel yang dipakai (skema dikonfirmasi via inspeksi langsung ke
nasmoco.db, BUKAN asumsi):
  - `daily_kpi` (6.593 baris): sudah hasil ETL per (tanggal, sa).
    Kolom: tanggal, sa, is_counter, unit_entry, cpus, revenue, jasa,
    tgp, adt, sublet, upselling, total_liter.
    BR026: dibaca APA ADANYA, tidak dihitung ulang.
    Revenue di `daily_kpi.revenue` DIKONFIRMASI konsisten dengan
    `rekapbulanan.invoice` (BR003) -- tidak perlu JOIN ke `rekapbulanan`.
  - `target_bulanan` (96 baris, HANYA ada tahun 2026): tahun, bulan,
    bulan_nama, sa, target_cpus, target_revenue, target_liter, tipe.
    `sa='TOTAL'` (tipe='ALL') adalah baris AGREGAT outlet, bukan SA
    individual -- caller (Service) yang memutuskan kapan pakai baris ini
    vs baris per-SA.

Catatan `sa` di `daily_kpi` (dikonfirmasi eksplisit dengan user):
  - `'Counter'` : transaksi tanpa WO (walk-in). BUKAN nama SA individual.
    Tetap dibaca apa adanya di sini -- exclude dari Ranking adalah
    keputusan RankingRepository/Service, bukan repository ini.
  - `'ARDI'`, `'SUPP'` : diperlakukan sebagai SA biasa apa adanya sesuai
    data yang ada (dikonfirmasi user, tidak ada logic khusus).

ADR003/ADR004: tidak ada business rule di sini -- itu tugas
KPISummaryService / KPIDetailService.
"""

from typing import List, Optional

import pandas as pd

from db.base_repository import BaseRepository


class KPIRepository(BaseRepository):
    """Akses read-only ke `daily_kpi` + `target_bulanan`."""

    # -- daily_kpi --

    def get_distinct_sa(self) -> List[str]:
        """Daftar semua nilai `sa` yang benar-benar ada di `daily_kpi`."""
        df = self.execute("SELECT DISTINCT sa FROM daily_kpi ORDER BY sa")
        if df.empty:
            return []
        return df["sa"].tolist()

    def get_daily(
        self,
        date_from: str,
        date_to: str,
        sa: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Ambil baris `daily_kpi` pada rentang tanggal [date_from, date_to]
        (inklusif), opsional difilter per SA. Tanpa filter SA -> semua SA
        termasuk 'Counter' (level outlet, caller yang memutuskan apakah
        Counter perlu di-exclude untuk kasus penggunaannya).
        """
        sql = "SELECT * FROM daily_kpi WHERE tanggal >= ? AND tanggal <= ?"
        params: List = [date_from, date_to]
        if sa:
            sql += " AND sa = ?"
            params.append(sa)
        sql += " ORDER BY tanggal, sa"
        return self.execute(sql, params)

    # -- target_bulanan --

    def get_target(self, tahun: int, bulan: int, sa: str) -> Optional[dict]:
        """
        Ambil satu baris target untuk (tahun, bulan, sa) persis.

        `sa` di sini bisa berupa kode SA individual (mis. "AGN") ATAU
        "TOTAL" untuk target level outlet -- caller yang memilih.
        Return None kalau tidak ada baris (mis. tahun di luar 2026,
        dikonfirmasi user tidak ada data 2024/2025).
        """
        return self.execute_one(
            "SELECT * FROM target_bulanan WHERE tahun = ? AND bulan = ? AND sa = ?",
            (tahun, bulan, sa),
        )

    def has_target_for_year(self, tahun: int) -> bool:
        """Cek cepat apakah tahun ini punya data target sama sekali."""
        return self.exists(
            "SELECT 1 FROM target_bulanan WHERE tahun = ? LIMIT 1", (tahun,)
        )
