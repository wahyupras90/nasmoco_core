"""
handlers/history_service/service.py

Business logic INT002 (History Service). ADR004: business rule ADA di
sini, BUKAN di Repository/Handler.

Alur:
  1. Resolve `customer_identifier` (VIN/plat/nama) -> baris customer_profile.
     0 baris -> NOT_FOUND. >1 baris -> AMBIGUOUS.
  2. Ambil riwayat WO dari `unitmasuk` (opsional rentang tanggal). Satu
     baris di `unitmasuk` = satu ITEM PEKERJAAN, bukan satu kunjungan —
     satu WO/kunjungan bisa punya beberapa baris.
  3. Gabungkan revenue resmi dari `rekapbulanan.invoice` (BR003) ke tiap
     baris riwayat berdasarkan no_wo — BUKAN dari tabel `invoice` mentah
     atau `rekapbulanan.total_revenue` (BR026).
  4. Agregasi ke level WO/kunjungan (satu baris per `no_wo`), dengan
     kolom `jenis_pekerjaan` yang merangkum kode `klp` per WO (aturan
     disepakati eksplisit dengan user, bukan asumsi sepihak):
       a. Kalau ADA baris dengan `kelompok == "WRT"` (warranty, bisa
          menaungi klp GRP maupun SUB) -> `jenis_pekerjaan` untuk WO itu
          HANYA "WRT" (tidak digabung kode lain sama sekali).
       b. Kalau TIDAK ADA WRT -> ambil kode `klp` UNIK di WO itu, urutkan
          prioritas SBE > GRP > LUB > SBI > PDS > SUB, gabung dengan
          ", ". Khusus kode SBE, sertakan teks `pekerjaan` asli dari
          baris SBE PERTAMA yang muncul, format "SBE (<pekerjaan>)".
          Kode lain (GRP/LUB/SBI/PDS/SUB) ditampilkan sebagai kode saja.
  5. RO/total kunjungan WAJIB dari `customer_profile.total_kunjungan_fisik`
     (BR020) — tidak dihitung ulang dari jumlah baris/WO manapun.
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from models.base_service import BaseService
from repositories.history_service_repository import HistoryServiceRepository
from utils.logger import get_logger

logger = get_logger(__name__)

# Prioritas kode `klp` untuk menyusun `jenis_pekerjaan` per WO (disepakati
# eksplisit dengan user). "WRT" ditangani terpisah (lihat _build_jenis_pekerjaan)
# karena levelnya beda -- dia menggantikan seluruh kombinasi, bukan
# ikut diurutkan bersama kode lain.
_KLP_PRIORITY_ORDER = ["SBE", "GRP", "LUB", "SBI", "PDS", "SUB"]


@dataclass
class HistoryServiceParams:
    customer_identifier: str
    identifier_type: str  # "no_rangka" | "plate" | "name"
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class HistoryServiceService(BaseService):
    def __init__(self, repo: HistoryServiceRepository = None):
        self.repo = repo or HistoryServiceRepository()

    def execute(self, params: HistoryServiceParams) -> dict:
        profiles = self._resolve_profile(params)

        if profiles.empty:
            return {"status": "not_found"}

        if len(profiles) > 1:
            return {"status": "ambiguous", "candidates": profiles}

        profile = profiles.iloc[0].to_dict()
        no_rangka = profile["no_rangka"]

        history_df = self.repo.get_wo_history(
            no_rangka, params.date_from, params.date_to
        )
        history_df = self._attach_revenue(history_df)
        history_df = self._aggregate_by_wo(history_df)

        # BR020: RO WAJIB dari customer_profile.total_kunjungan_fisik,
        # sudah ada di `profile` (bukan dihitung ulang di sini).
        ro_total = profile.get("total_kunjungan_fisik")

        # Notifikasi opsional (disepakati eksplisit dengan user, bukan
        # keputusan sepihak): kalau unit ini juga punya riwayat TCARE,
        # beri tahu di message — tanpa menampilkan tabelnya (itu tetap
        # tanggung jawab INT003 sendiri kalau user memang bertanya
        # "history tcare ...").
        has_tcare_history = self.repo.has_any_tcare_history(no_rangka)

        return {
            "status": "ok",
            "profile": profile,
            "history": history_df,
            "ro_total": ro_total,
            "has_tcare_history": has_tcare_history,
        }

    def _resolve_profile(self, params: HistoryServiceParams) -> pd.DataFrame:
        if params.identifier_type == "no_rangka":
            return self.repo.resolve_profile_by_no_rangka(params.customer_identifier)
        if params.identifier_type == "plate":
            return self.repo.resolve_profile_by_no_polisi(params.customer_identifier)
        return self.repo.resolve_profile_by_customer_name(params.customer_identifier)

    def _attach_revenue(self, history_df: pd.DataFrame) -> pd.DataFrame:
        if history_df.empty or "no_wo" not in history_df.columns:
            return history_df

        no_wo_list = [int(v) for v in history_df["no_wo"].dropna().unique().tolist()]
        revenue_df = self.repo.get_revenue_by_no_wo(no_wo_list)

        if revenue_df.empty:
            history_df = history_df.copy()
            history_df["invoice"] = None
            return history_df

        merged = history_df.merge(revenue_df, on="no_wo", how="left")
        return merged

    def _aggregate_by_wo(self, history_df: pd.DataFrame) -> pd.DataFrame:
        """
        Agregasi dari level "baris per item pekerjaan" ke level "baris
        per WO/kunjungan", dengan kolom `jenis_pekerjaan` (lihat aturan
        di docstring modul). Kolom `pekerjaan`/`klp`/`kelompok` mentah
        DIHAPUS dari hasil akhir (digantikan `jenis_pekerjaan`), kolom
        lain (no_wo, no_polisi, customer, model, sa, mech, tanggal,
        tgl_invoice, kategori, tcare, invoice) diambil dari baris
        PERTAMA tiap grup WO (nilainya seragam per WO).
        """
        if history_df.empty or "no_wo" not in history_df.columns:
            return history_df

        rows = []
        for no_wo, group in history_df.groupby("no_wo", sort=False):
            base = group.iloc[0].to_dict()
            base["jenis_pekerjaan"] = _build_jenis_pekerjaan(group)
            for col in ("pekerjaan", "klp", "kelompok"):
                base.pop(col, None)
            rows.append(base)

        aggregated = pd.DataFrame(rows)

        # Urutan kolom yang enak dibaca: identitas dulu, jenis_pekerjaan,
        # baru tanggal/invoice.
        preferred_order = [
            "no_wo",
            "no_invoice",
            "no_polisi",
            "customer",
            "no_rangka",
            "model",
            "sa",
            "mech",
            "jenis_pekerjaan",
            "tanggal",
            "tgl_invoice",
            "kategori",
            "tcare",
            "invoice",
        ]
        ordered_cols = [c for c in preferred_order if c in aggregated.columns]
        remaining_cols = [c for c in aggregated.columns if c not in ordered_cols]
        return aggregated[ordered_cols + remaining_cols]


def _build_jenis_pekerjaan(group: pd.DataFrame) -> str:
    """Bangun label `jenis_pekerjaan` untuk satu WO sesuai aturan disepakati."""
    kelompok_values = {
        str(v).strip().upper() for v in group.get("kelompok", pd.Series(dtype=str)).fillna("")
    }
    if "WRT" in kelompok_values:
        return "WRT"

    seen_klp: dict = {}
    for _, row in group.iterrows():
        klp = str(row.get("klp") or "").strip().upper()
        if not klp or klp in seen_klp:
            continue
        seen_klp[klp] = row.get("pekerjaan")

    labels = []
    for code in _KLP_PRIORITY_ORDER:
        if code not in seen_klp:
            continue
        if code == "SBE":
            labels.append(f"SBE ({seen_klp[code]})")
        else:
            labels.append(code)

    # Kode tak terduga di luar daftar prioritas (mis. data baru di masa
    # depan) tetap ditampilkan, ditaruh di akhir, supaya tidak hilang
    # diam-diam.
    for code in seen_klp:
        if code not in _KLP_PRIORITY_ORDER:
            labels.append(code)

    return ", ".join(labels) if labels else "-"