"""
handlers/attack_list/service.py — INT008 Attack List

BR026: status/tgl_konversi/bulan_konversi SUDAH dihitung evaluator_konversi.py
-- Service ini HANYA membaca kolom apa adanya, TIDAK menghitung ulang logic
konversi/dedup (itu domain etl_attack_list.py, di luar nasmoco_core).

Untuk mode "list" (source DISEBUT eksplisit): kalau `status` tidak
disebut user DAN bukan mode expired, default filter `status='pending'` --
MENGIKUTI persis logika `tools/attack_list.py` legacy:

    if expired_mode:
        where.append(strftime batas_tcare = bulan)
    else:
        where.append("status = 'pending'")

Dikonfirmasi Wahyu (2026-07-16) setelah ditemukan divergensi: implementasi
awal Room 6 SEMPAT tidak memfilter status sama sekali secara default
(menampilkan semua 10.348 baris tanpa filter) -- ini SALAH, tidak sesuai
project lama. Diperbaiki supaya konsisten.

## View "Attack List Semua" (source TIDAK disebut, bukan expired_mode)

Ditambahkan setelah diskusi panjang dengan Wahyu (2026-07-16), meniru
`handle_attack_list_all()`/`_summary_per_source()` di `tools/attack_list.py`
legacy TAPI dengan perbaikan konsistensi (bug lama: SA/bulan tidak dioper
ke sub-query TCARE Pending, sudah diperbaiki di sini) dan source of truth
yang disederhanakan (SEMUA angka, termasuk TCARE, dari tabel `attack_list`
saja -- TIDAK JOIN ke `tcare_schedule` lagi untuk view ini secara khusus).

Keputusan final (dikonfirmasi eksplisit):
- `resolved` DIKECUALIKAN TOTAL -- tidak dihitung di angka manapun, tidak
  ditampilkan sama sekali (dianggap "sudah ditutup", tidak relevan lagi).
- Total per kategori/segmen = `pending + converted` digabung.
- SA (kalau disebut user) difilter KONSISTEN di semua kategori (TCARE,
  CRM, CR7) -- bug lama membuat baris TCARE Pending tidak ikut ter-filter
  SA padahal CRM/CR7 sudah benar.
- Mode `expired` TIDAK didukung sama sekali di view ini (persis legacy --
  `handle_attack_list_all` tidak pernah memanggil `is_expired_query()`).
  Kalau user sebut kata "expired", itu tetap masuk `_execute_list()` biasa
  (source tetap boleh None di jalur expired, cuma path INI yang dilewati).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from handlers._shared.period_parser import ParsedPeriod, display_period
from models.base_service import BaseService
from repositories.attack_list_repository import AttackListRepository

# Urutan tampilan segment_rfm untuk breakdown CRM -- dari tools/attack_list.py
# legacy (SEGMENT_ORDER). Segment yang tidak punya baris (count 0) TIDAK
# ditampilkan (persis legacy: "if seg and seg != '-'").
SEGMENT_ORDER = ["Champion", "Loyal", "Potential", "At Risk", "New", "Lost"]


@dataclass
class AttackListServiceParams:
    mode: str = "list"
    source: Optional[str] = None
    status: Optional[str] = None
    sa_terakhir: Optional[str] = None
    segment_rfm: Optional[str] = None
    program_id: Optional[int] = None
    program: Optional[str] = None  # INT010: filter/breakdown nama program CRM
    period: Optional[ParsedPeriod] = None
    expired_mode: bool = False
    wants_summary_only: bool = False


class AttackListService(BaseService):
    def __init__(self, repo: AttackListRepository = None):
        self.repo = repo or AttackListRepository()

    def execute(self, params: AttackListServiceParams) -> dict:
        if params.mode == "history":
            return self._execute_history(params)
        if not params.expired_mode and params.source is None:
            return self._execute_all_summary(params)
        return self._execute_list(params)

    def _execute_all_summary(self, params: AttackListServiceParams) -> dict:
        """View 'Attack List Semua' -- source tidak disebut, bukan
        expired_mode. Source of truth tunggal: tabel attack_list, filter
        status IN ('pending','converted') -- resolved dikecualikan total."""
        df = self.repo.find_for_summary_all(
            sa_terakhir=params.sa_terakhir,
            segment_rfm=params.segment_rfm,
            program_id=params.program_id,
        )

        def _status_split(sub_df: pd.DataFrame):
            converted = int((sub_df["status"] == "converted").sum()) if not sub_df.empty else 0
            pending = int((sub_df["status"] == "pending").sum()) if not sub_df.empty else 0
            return converted, pending

        # TCARE unit/pekerjaan: dihitung dari `tcare_schedule` (BUKAN
        # `attack_list`), sesuai definisi bisnis yang benar (dikonfirmasi
        # Wahyu 2026-07-22): "pekerjaan" = sisa jadwal servis yang jatuh
        # tempo (bulan_jadwal <= periode). `attack_list` sudah di-dedup
        # 1 baris/unit oleh ETL, jadi TIDAK BISA dipakai untuk hitung
        # jumlah pekerjaan per unit -- itulah akar bug "pekerjaan selalu
        # sama dengan unit" yang dilaporkan.
        #
        # FIX (2026-07-23): pakai `params.period` (periode yang DIKETIK
        # user, mis. "juli") kalau ada -- SEBELUMNYA selalu pakai
        # `datetime.now()` (hari ini), mengabaikan periode yang diminta
        # user sama sekali. Fallback ke bulan berjalan cuma kalau user
        # memang tidak sebut periode apa pun.
        if params.period is not None:
            bulan_batas = f"{params.period.tahun:04d}-{params.period.bulan:02d}"
        else:
            bulan_batas = datetime.now().strftime("%Y-%m")
        tcare_pending_row = self.repo.tcare_pending_count(bulan_batas, sa_terakhir=params.sa_terakhir).iloc[0]
        tcare_converted_row = self.repo.tcare_converted_count(bulan_batas, sa_terakhir=params.sa_terakhir).iloc[0]

        crm_df = df[df["source"] == "CRM"] if not df.empty else df
        cr7_df = df[df["source"] == "CR7"] if not df.empty else df

        crm_converted, crm_pending = _status_split(crm_df)
        cr7_converted, cr7_pending = _status_split(cr7_df)

        segment_breakdown = []
        for seg in SEGMENT_ORDER:
            seg_df = crm_df[crm_df["segment_rfm"] == seg] if not crm_df.empty else crm_df
            if seg_df.empty:
                continue
            converted, pending = _status_split(seg_df)
            segment_breakdown.append({
                "segment": seg,
                "total": len(seg_df),
                "converted": converted,
                "pending": pending,
            })

        # INT010: breakdown per program CRM (P1-P4). Dinamis dari DISTINCT
        # data (`groupby`), TIDAK hardcode daftar tetap seperti SEGMENT_ORDER
        # -- sesuai arahan Room 0 (pelajaran bug PX mode "Semua": breakdown
        # harus otomatis mengikuti data, supaya program baru langsung
        # kebaca tanpa perlu ubah kode).
        program_breakdown = []
        if not crm_df.empty and "program" in crm_df.columns:
            crm_with_program_df = crm_df[crm_df["program"].notna()]
            for prog, prog_df in crm_with_program_df.groupby("program"):
                converted, pending = _status_split(prog_df)
                program_breakdown.append({
                    "program": prog,
                    "total": len(prog_df),
                    "converted": converted,
                    "pending": pending,
                })
            program_breakdown.sort(key=lambda row: row["program"])

        other_source_breakdown = []
        if "source" in df.columns:
            for source, source_df in df.groupby("source"):
                if source in ("TCARE", "CRM", "CR7"):
                    continue
                converted, pending = _status_split(source_df)
                other_source_breakdown.append({
                    "source": source,
                    "total": len(source_df),
                    "converted": converted,
                    "pending": pending,
                })

        return {
            "mode": "all",
            "sa_filter": params.sa_terakhir,
            "segment_rfm_filter": params.segment_rfm,
            "program_id_filter": params.program_id,
            "tcare_unit_pending": int(tcare_pending_row["unit"]),
            "tcare_pekerjaan_pending": int(tcare_pending_row["pekerjaan"]),
            "tcare_unit_converted": int(tcare_converted_row["unit"]),
            "tcare_pekerjaan_converted": int(tcare_converted_row["pekerjaan"]),
            "crm_total": int(len(crm_df)),
            "crm_converted": crm_converted,
            "crm_pending": crm_pending,
            "crm_segment_breakdown": segment_breakdown,
            "crm_program_breakdown": program_breakdown,
            "cr7_total": int(len(cr7_df)),
            "cr7_converted": cr7_converted,
            "cr7_pending": cr7_pending,
            "other_source_breakdown": other_source_breakdown,
            "raw_df": df.iloc[0:0] if params.wants_summary_only else df,
        }

    def _execute_list(self, params: AttackListServiceParams) -> dict:
        period_yyyymm = None
        if params.expired_mode:
            period_yyyymm = f"{params.period.tahun:04d}-{params.period.bulan:02d}"

        # Default status='pending' kalau tidak disebut user DAN bukan mode expired
        effective_status = params.status
        if not params.expired_mode and effective_status is None:
            effective_status = "pending"

        # BUGFIX: Sensitivitas huruf (case-sensitivity) untuk Segment RFM
        safe_segment = params.segment_rfm.title() if params.segment_rfm else None

        # Tarik data dari DB TANPA filter status agar bisa diagregasi (kecuali expired mode yang punya logic DB khusus)
        query_status = None if not params.expired_mode else effective_status

        raw_df = self.repo.find(
            source=params.source,
            status=query_status,
            sa_terakhir=params.sa_terakhir,
            segment_rfm=safe_segment,
            program_id=params.program_id,
            expired_mode=params.expired_mode,
            period_yyyymm=period_yyyymm,
        )
        
        summary_per_source_df = self.repo.summary_per_source()

        # Hitung agregasi dari raw data untuk ditampilkan di format message
        total_converted = 0
        total_pending = 0
        if not raw_df.empty and "status" in raw_df.columns:
            total_converted = int((raw_df["status"] == "converted").sum())
            total_pending = int((raw_df["status"] == "pending").sum())

        # Terapkan filter status menggunakan Pandas untuk membatasi ukuran tabel output (BR026 - Rule 16 Juli)
        if not params.expired_mode and effective_status:
            units_df = raw_df[raw_df["status"] == effective_status] if not raw_df.empty else raw_df
        else:
            units_df = raw_df

        total_unit = int(len(units_df))

        # PATCH pola Room 5 (WIP): query "total/berapa/jumlah" tanpa kata
        # list/daftar/detail/rincian tidak perlu tabel penuh
        returned_units_df = units_df.iloc[0:0] if params.wants_summary_only else units_df

        return {
            "mode": "list",
            "source_filter": params.source,
            "status_filter": effective_status,
            "segment_rfm_filter": safe_segment,
            "program_id_filter": params.program_id,
            "expired_mode": params.expired_mode,
            "period_yyyymm": period_yyyymm,
            "period_label": display_period(params.period.tahun, params.period.bulan) if params.expired_mode else None,
            "period_is_explicit": params.period.is_explicit if params.expired_mode else None,
            "units": returned_units_df,
            "total_unit": total_unit,
            "total_gabungan": total_converted + total_pending,
            "total_converted": total_converted,
            "total_pending": total_pending,
            "summary_per_source": summary_per_source_df,
            "sa_filter": params.sa_terakhir,
        }

    def _execute_history(self, params: AttackListServiceParams) -> dict:
        bulan_str = f"{params.period.tahun:04d}-{params.period.bulan:02d}"
        # BUGFIX (INT010): sama pola dengan segment_rfm -- whitelist VALID_PROGRAM
        # di parser disimpan lowercase, tapi nilai asli di DB title-case
        # ("Panggil Pulang - At Risk"). Tanpa .title() filter tidak akan
        # pernah match (ditemukan lewat test, bukan asumsi).
        safe_program = params.program.title() if params.program else None
        history_df = self.repo.find_history(
            bulan=bulan_str, source=params.source, program=safe_program,
        )

        total_konversi = 0
        if not history_df.empty and "tgl_konversi" in history_df.columns:
            total_konversi = int(history_df["tgl_konversi"].notna().sum())

        # INT010: breakdown per program -- HANYA relevan untuk baris CRM
        # (program NULL untuk TCARE/CR7/PX by design). Dinamis dari
        # DISTINCT data yang ada, TIDAK hardcode daftar P1-P4 (pelajaran
        # dari bug PX mode "Semua" -- breakdown harus ikut data, bukan
        # daftar tetap, supaya program baru otomatis kebaca).
        program_breakdown = []
        if not history_df.empty and "program" in history_df.columns:
            crm_history_df = history_df[history_df["program"].notna()]
            for prog, prog_df in crm_history_df.groupby("program"):
                prog_konversi = int(prog_df["tgl_konversi"].notna().sum())
                program_breakdown.append({
                    "program": prog,
                    "total": int(len(prog_df)),
                    "konversi": prog_konversi,
                })
            program_breakdown.sort(key=lambda row: row["program"])

        return {
            "mode": "history",
            "bulan": bulan_str,
            "bulan_label": display_period(params.period.tahun, params.period.bulan),
            "period_is_explicit": params.period.is_explicit,
            "source_filter": params.source,
            "program_filter": safe_program,
            "history": history_df,
            "total_tercatat": int(len(history_df)),
            "total_konversi": total_konversi,
            "program_breakdown": program_breakdown,
        }