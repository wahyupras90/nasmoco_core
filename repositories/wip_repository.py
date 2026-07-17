"""
repositories/wip_repository.py

Repository untuk INT007 (WIP -- Work In Progress).

Tabel: `unitmasuk` (114.328 baris). SAMA seperti Room 4: 1 baris di
`unitmasuk` = 1 ITEM PEKERJAAN, BUKAN 1 unit/kunjungan -- WAJIB
diagregasi ke level `no_wo` sebelum dihitung sebagai "N unit WIP"
(pelajaran eksplisit dari Room 4, diverifikasi ulang di sample data
Room 5: no_wo yang sama muncul di beberapa baris dengan `pekerjaan`
berbeda).

Definisi WIP (dikonfirmasi eksplisit dengan user): unit yang BELUM
diinvoice -- `tgl_invoice` kosong/NULL ATAU `no_invoice` kosong/NULL.

Breakdown kategori pekerjaan WAJIB pakai kolom `kelompok` (dikonfirmasi
eksplisit user), BUKAN `klp` -- keduanya ada di `unitmasuk` tapi
`kelompok` yang representatif untuk kategori resmi (SBE/GRP/WRT/SBI/
LUB/PDS), sama seperti dipakai Room 4 untuk agregasi `jenis_pekerjaan`.

ADR003/ADR004: tidak ada business rule (definisi "unit" vs "item
pekerjaan", validasi kelompok) di sini -- itu tugas WIPService.
"""

from typing import List, Optional

import pandas as pd

from db.base_repository import BaseRepository

# Definisi WIP, dikonfirmasi eksplisit dengan user: belum diinvoice.
_WIP_FILTER_SQL = (
    "(tgl_invoice IS NULL OR TRIM(tgl_invoice) = '' "
    "OR no_invoice IS NULL OR TRIM(no_invoice) = '')"
)

KNOWN_KELOMPOK = ("SBE", "GRP", "WRT", "SBI", "LUB", "PDS")


class WIPRepository(BaseRepository):
    """Akses read-only ke `unitmasuk`, filter WIP (belum invoice)."""

    def get_wip_items(
        self,
        sa: Optional[str] = None,
        kelompok: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Semua baris (level item pekerjaan) yang termasuk WIP, opsional
        difilter per SA dan/atau `kelompok`. Caller (Service) WAJIB
        mengagregasi ke level `no_wo` sebelum menghitung "jumlah unit".
        """
        sql = f"SELECT * FROM unitmasuk WHERE {_WIP_FILTER_SQL}"
        params: List = []
        if sa:
            sql += " AND sa = ?"
            params.append(sa)
        if kelompok:
            sql += " AND kelompok = ?"
            params.append(kelompok)
        sql += " ORDER BY tanggal, no_wo"
        return self.execute(sql, params)

    def get_wip_count_by_kelompok(self) -> pd.DataFrame:
        """
        Jumlah BARIS (item pekerjaan) WIP per `kelompok` -- dipakai
        Service sebagai basis breakdown, TAPI Service tetap wajib
        menghitung ulang jumlah `no_wo` UNIK per kelompok di Python
        (satu no_wo bisa punya baris dengan kelompok campuran, sama
        seperti kasus Room 4), bukan langsung dipakai sebagai "jumlah
        unit".
        """
        return self.execute(
            f"SELECT kelompok, COUNT(*) AS jumlah_baris "
            f"FROM unitmasuk WHERE {_WIP_FILTER_SQL} "
            "GROUP BY kelompok ORDER BY jumlah_baris DESC"
        )

    def get_distinct_sa_in_wip(self) -> List[str]:
        df = self.execute(
            f"SELECT DISTINCT sa FROM unitmasuk WHERE {_WIP_FILTER_SQL} ORDER BY sa"
        )
        if df.empty:
            return []
        return df["sa"].tolist()
