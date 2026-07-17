"""
handlers/history_tcare/service.py

Business logic INT003 (History TCARE). ADR004: business rule ADA di
sini, BUKAN di Repository/Handler.

Alur:
  1. Resolve `customer_identifier` -> no_rangka.
       - identifier_type == "no_rangka": nilainya ITU SENDIRI adalah
         no_rangka, tidak perlu query tambahan untuk resolusi (baru
         dicek exist di tcare_unit/tcare_schedule_full_history pada
         langkah 2).
       - identifier_type == "plate"/"name": resolve lewat
         CustomerProfileRepository (BR027, dipakai bareng INT002) untuk
         dapat no_rangka. 0 hasil -> NOT_FOUND. >1 -> AMBIGUOUS.
  2. Ambil info unit (`tcare_unit`) dan riwayat (`tcare_schedule_full_history`,
     ADR024 final — BUKAN `tcare_schedule`).
  3. PENTING (anti bug legacy, lihat ADR024): legacy menganggap unit
     "tidak ditemukan" hanya berdasarkan `tcare_unit` kosong, padahal
     tabel info bisa saja tidak mencakup semua no_rangka yang sebenarnya
     punya riwayat TCARE — persis kelas masalah yang sama yang membuat
     `tcare_schedule` salah dipakai sebagai source of truth riwayat.
     Karena itu Service ini menganggap NOT_FOUND HANYA kalau *keduanya*
     kosong (`tcare_unit` DAN `tcare_schedule_full_history`). Kalau info
     unit kosong tapi riwayat ADA, Service tetap mengembalikan hasil OK
     dengan identitas fallback dari `customer_profile`.
  4. RO/total kunjungan (BR020) dari `customer_profile.total_kunjungan_fisik`
     lewat repo yang sama dengan INT002 (BR027).
"""

from dataclasses import dataclass

from models.base_service import BaseService
from repositories.history_tcare_repository import HistoryTCARERepository
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HistoryTCAREParams:
    customer_identifier: str
    identifier_type: str  # "no_rangka" | "plate" | "name"


class HistoryTCAREService(BaseService):
    def __init__(self, repo: HistoryTCARERepository = None):
        self.repo = repo or HistoryTCARERepository()

    def execute(self, params: HistoryTCAREParams) -> dict:
        no_rangka_candidates, profiles = self._resolve_no_rangka(params)

        if not no_rangka_candidates:
            return {"status": "not_found"}

        if len(no_rangka_candidates) > 1:
            # `profiles` tersedia (identifier_type plate/name) supaya
            # Formatter bisa menyusun suggestions yang informatif
            # (nama/no_polisi/model), bukan cuma daftar no_rangka mentah.
            return {"status": "ambiguous", "candidates": profiles}

        no_rangka = no_rangka_candidates[0]

        unit_info = self.repo.get_unit_info(no_rangka)
        schedule_df = self.repo.get_schedule_history(no_rangka)

        if unit_info is None and schedule_df.empty:
            return {"status": "not_found"}

        if unit_info is None:
            # tcare_unit tidak punya baris untuk no_rangka ini, tapi
            # riwayatnya ADA di tcare_schedule_full_history — jangan
            # ulangi bug legacy yang melaporkan "tidak ditemukan" di
            # sini. Pakai identitas fallback dari customer_profile.
            logger.info(
                "tcare_unit kosong untuk no_rangka=%s, pakai fallback "
                "customer_profile (riwayat tetap ada: %d baris).",
                no_rangka,
                len(schedule_df),
            )
            fallback = self.repo.get_fallback_identity(no_rangka) or {}
            unit_info = {
                "no_rangka": no_rangka,
                "model": fallback.get("model"),
                "no_polisi": fallback.get("no_polisi"),
                "customer": fallback.get("customer"),
                "dealer_kategori": fallback.get("dealer_kategori"),
                "sa_terakhir": fallback.get("sa_terakhir"),
                "tcare_type": None,
                "batas_tcare": None,
                "sisa_detail": None,
                "tgl_do": None,
            }

        # BR020: RO WAJIB dari customer_profile.total_kunjungan_fisik,
        # sama seperti INT002 (BR027 — repo yang di-share).
        ro_total = self.repo.get_ro_count(no_rangka)

        return {
            "status": "ok",
            "no_rangka": no_rangka,
            "unit_info": unit_info,
            "schedule": schedule_df,
            "ro_total": ro_total,
        }

    def _resolve_no_rangka(self, params: HistoryTCAREParams):
        """
        Returns:
            (no_rangka_list, profiles_df_or_None). `profiles_df` hanya
            terisi untuk identifier_type "plate"/"name" (dipakai untuk
            suggestions kalau ambigu); untuk "no_rangka", None karena
            nilainya adalah no_rangka itu sendiri, tanpa perlu resolusi
            lewat customer_profile.
        """
        if params.identifier_type == "no_rangka":
            return [params.customer_identifier], None

        if params.identifier_type == "plate":
            profiles = self.repo.resolve_profile_by_no_polisi(params.customer_identifier)
        else:
            profiles = self.repo.resolve_profile_by_customer_name(
                params.customer_identifier
            )

        if profiles.empty:
            return [], profiles
        return profiles["no_rangka"].dropna().unique().tolist(), profiles
