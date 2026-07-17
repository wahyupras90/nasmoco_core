"""
handlers/wip/service.py

Business logic INT007 (WIP). ADR004.

Definisi WIP (dikonfirmasi eksplisit user): `tgl_invoice` atau
`no_invoice` kosong/NULL -- filter ini sudah diterapkan di
WIPRepository (BR026-style: satu implementasi filter, tidak disalin).

WAJIB agregasi ke level `no_wo` (1 baris `unitmasuk` = 1 item pekerjaan,
BUKAN 1 unit) sebelum menghitung "N unit WIP" -- pelajaran eksplisit
Room 4, diverifikasi ulang lewat sample data Room 5 (no_wo yang sama
muncul di beberapa baris dengan `pekerjaan` berbeda).

Tidak ada validasi keberadaan SA di sini (beda dengan INT004/005) --
0 hasil untuk SA/kelompok tertentu adalah jawaban valid ("tidak ada unit
WIP saat ini"), bukan error/NOT_FOUND.
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from models.base_service import BaseService
from repositories.wip_repository import KNOWN_KELOMPOK, WIPRepository


@dataclass
class WIPParams:
    kelompok: Optional[str] = None
    sa_candidate: Optional[str] = None
    wants_summary_only: bool = False


class WIPService(BaseService):
    def __init__(self, repo: WIPRepository = None):
        self.repo = repo or WIPRepository()

    def execute(self, params: WIPParams) -> dict:
        items_df = self.repo.get_wip_items(sa=params.sa_candidate, kelompok=params.kelompok)
        units_df = _aggregate_to_unit(items_df)

        breakdown = {}
        if params.kelompok is None:
            # Breakdown per kelompok dihitung dari SEMUA item WIP (hanya
            # difilter sa kalau ada), supaya breakdown tetap bermakna --
            # bukan dari items_df yang sudah difilter kelompok tunggal.
            all_items_df = self.repo.get_wip_items(sa=params.sa_candidate, kelompok=None)
            breakdown = _count_unique_wo_per_kelompok(all_items_df)

        total_unit_wip = int(len(units_df))

        # PATCH Room 5: query "total/berapa/jumlah" (tanpa kata
        # list/daftar/detail/rincian) tidak perlu tabel daftar unit penuh
        # di HandlerResult.dataframe -- summary (total & breakdown) tetap
        # dihitung dari data lengkap di atas, cuma DataFrame yang
        # dikembalikan dikosongkan (bukan None, supaya tipe tetap
        # konsisten dengan kontrak HandlerResult.dataframe).
        returned_units_df = units_df.iloc[0:0] if params.wants_summary_only else units_df

        return {
            "status": "ok",
            "kelompok_filter": params.kelompok,
            "sa_filter": params.sa_candidate,
            "units": returned_units_df,
            "total_unit_wip": total_unit_wip,
            "breakdown_per_kelompok": breakdown,
        }


def _aggregate_to_unit(items_df: pd.DataFrame) -> pd.DataFrame:
    """
    Agregasi dari level "baris per item pekerjaan" ke level "baris per
    unit/WO" (no_wo). Kolom `kelompok_list` merangkum semua kategori
    pekerjaan yang menyertai WO tersebut (bisa lebih dari satu).
    """
    if items_df.empty or "no_wo" not in items_df.columns:
        return items_df

    rows = []
    for no_wo, group in items_df.groupby("no_wo", sort=False):
        base = group.iloc[0].to_dict()
        kelompok_values = sorted(
            {str(v).strip() for v in group.get("kelompok", pd.Series(dtype=str)).fillna("") if str(v).strip()}
        )
        base["kelompok_list"] = kelompok_values
        base["jumlah_item_pekerjaan"] = len(group)
        rows.append(base)

    unit_df = pd.DataFrame(rows)
    preferred_order = [
        "no_wo", "no_polisi", "customer", "model", "sa", "mech",
        "kelompok_list", "jumlah_item_pekerjaan", "tanggal", "jam",
    ]
    ordered_cols = [c for c in preferred_order if c in unit_df.columns]
    remaining_cols = [c for c in unit_df.columns if c not in ordered_cols]
    return unit_df[ordered_cols + remaining_cols]


def _count_unique_wo_per_kelompok(items_df: pd.DataFrame) -> dict:
    """
    Jumlah UNIT (no_wo unik) yang punya minimal satu item pekerjaan pada
    tiap `kelompok`. Satu WO bisa terhitung di lebih dari satu kelompok
    kalau memang punya item pekerjaan dari kategori berbeda -- bukan
    partisi eksklusif, murni "kelompok apa saja yang muncul di WIP ini".
    """
    result = {code: 0 for code in KNOWN_KELOMPOK}
    if items_df.empty or "no_wo" not in items_df.columns or "kelompok" not in items_df.columns:
        return result

    for _no_wo, group in items_df.groupby("no_wo", sort=False):
        present = {str(v).strip() for v in group["kelompok"].fillna("") if str(v).strip()}
        for code in KNOWN_KELOMPOK:
            if code in present:
                result[code] += 1
    return result
