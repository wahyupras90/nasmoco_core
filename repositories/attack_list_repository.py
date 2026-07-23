"""
repositories/attack_list_repository.py — INT008 Attack List

Signature BaseRepository (execute/execute_one/scalar/exists) sudah diverifikasi
langsung dari db/base_repository.py di codebase -- bukan asumsi lagi.

Aturan (BR008, brief Room 6):
- HANYA baca tabel `attack_list` (master unified) dan `attack_list_history`
  (kalau butuh histori konversi).
- JANGAN PERNAH baca `crm_attack_list` (tabel sumber ETL) atau `attack_list_lama`
  (artefak legacy tidak dipakai) langsung dari sini.
- Dedup TCARE>CRM>CR7 SUDAH ditangani ETL (etl_attack_list.py) -- Repository
  TIDAK mengimplementasikan ulang logic ini, cukup baca attack_list apa adanya.
- status/tgl_konversi/bulan_konversi SUDAH dihitung evaluator_konversi.py (BR026)
  -- dibaca apa adanya, tidak dihitung ulang di sini.
- sawa_status/sawa_expiry: asal-usul pengisian belum teridentifikasi -- tampilkan
  apa adanya, NULL ditampilkan sebagai "tidak tersedia" (di layer Formatter,
  bukan di Repository).
- SEMUA query WAJIB parameterized (?), TIDAK ADA f-string SQL interpolation
  seperti attack_list.py legacy.

Untuk hitung TCARE-pending count di Attack List, per konfirmasi Room 0:
JOIN ke tcare_schedule (subset ~3,544 kendaraan aktif) + unit_tcare (VIEW) --
BUKAN tcare_schedule_full_history (itu domain INT002/INT003, ADR024).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from db.base_repository import BaseRepository


class AttackListRepository(BaseRepository):

    def find(
        self,
        source: Optional[str] = None,
        status: Optional[str] = None,
        sa_terakhir: Optional[str] = None,
        segment_rfm: Optional[str] = None,
        program_id: Optional[int] = None,
        expired_mode: bool = False,
        period_yyyymm: Optional[str] = None,
    ) -> pd.DataFrame:
        """Query attack_list dengan filter opsional. Semua filter parameterized.

        Meniru logika filter attack_list.py legacy, TAPI implementasi aman
        (parameterized), bukan f-string interpolation.

        `expired_mode`/`period_yyyymm`: mode filter TERPISAH dari `status`,
        persis logic legacy (`tools/attack_list.py::_query_attack_list`) --
        "expired" BUKAN nilai status, tapi filter berbasis `batas_tcare`:

            WHERE strftime('%Y-%m', batas_tcare) = <period_yyyymm>
              AND status NOT IN ('converted', 'resolved')

        Kalau `expired_mode=True`, parameter `status` diabaikan (expired_mode
        menggantikan filter status, bukan ditambahkan ke atasnya -- sama
        seperti legacy: expired_mode dan status='pending' saling eksklusif).
        """
        conditions = []
        params: list = []

        if source is not None:
            conditions.append("source = ?")
            params.append(source)

        if expired_mode:
            if not period_yyyymm:
                raise ValueError("period_yyyymm wajib diisi kalau expired_mode=True")
            conditions.append("strftime('%Y-%m', batas_tcare) = ?")
            params.append(period_yyyymm)
            conditions.append("status NOT IN ('converted', 'resolved')")
        elif status is not None:
            conditions.append("status = ?")
            params.append(status)

        if sa_terakhir is not None:
            conditions.append("sa_terakhir = ?")
            params.append(sa_terakhir)
        if segment_rfm is not None:
            conditions.append("segment_rfm = ?")
            params.append(segment_rfm)
        if program_id is not None:
            conditions.append("program_id = ?")
            params.append(program_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT *
            FROM attack_list
            {where_clause}
            ORDER BY source, sa_terakhir, program
        """
        return self.execute(sql, params)

    def summary_per_source(self) -> pd.DataFrame:
        """Ringkasan jumlah unit per source (TCARE/CRM/CR7), dibaca apa adanya
        dari attack_list -- dedup sudah ditangani ETL, tidak dihitung ulang di sini."""
        sql = """
            SELECT source, COUNT(*) AS jumlah_unit
            FROM attack_list
            GROUP BY source
        """
        return self.execute(sql, [])

    def find_for_summary_all(
        self,
        sa_terakhir: Optional[str] = None,
        segment_rfm: Optional[str] = None,
        program_id: Optional[int] = None,
    ) -> pd.DataFrame:
        """Baca attack_list untuk view 'Attack List Semua' (breakdown per
        kategori TCARE/CRM/CR7 + segment_rfm untuk CRM).

        Dikonfirmasi Wahyu (2026-07-16): source of truth TUNGGAL untuk
        view ini adalah tabel `attack_list` (bukan `tcare_schedule` --
        beda dari `tcare_pending_count()` yang dipakai di path lain).
        Filter dasar `status IN ('pending', 'converted')` -- `resolved`
        dikecualikan TOTAL (tidak relevan lagi, tidak dihitung sama
        sekali di angka manapun).
        """
        conditions = ["status IN ('pending', 'converted')"]
        params: list = []

        if sa_terakhir is not None:
            conditions.append("sa_terakhir = ?")
            params.append(sa_terakhir)
        if segment_rfm is not None:
            conditions.append("segment_rfm = ?")
            params.append(segment_rfm)
        if program_id is not None:
            conditions.append("program_id = ?")
            params.append(program_id)

        sql = f"""
            SELECT *
            FROM attack_list
            WHERE {' AND '.join(conditions)}
        """
        return self.execute(sql, params)

    def tcare_pending_count(self, bulan_batas: str, sa_terakhir: Optional[str] = None) -> pd.DataFrame:
        """Hitung TCARE-pending count untuk Attack List.

        Per konfirmasi Room 0: JOIN ke tcare_schedule (subset aktif, ~3,544
        kendaraan), BUKAN tcare_schedule_full_history -- beda sengaja dari
        INT002/INT003 karena Attack List hanya relevan untuk unit yang masih
        aktif follow-up-nya (ADR024, klarifikasi Room 6).

        `sa_terakhir`: filter opsional -- WAJIB didukung supaya konsisten
        dengan kategori lain (CRM/CR7) di view "Attack List Semua"
        (ADR027 Bug#1: bug legacy dulu filter SA cuma jalan di CRM/CR7,
        TCARE Pending diabaikan -- jangan sampai regresi lagi di sini).
        """
        conditions = ["ts.bulan_jadwal <= ?", "ts.bulan_realisasi IS NULL", "ts.expired = 0"]
        params: list = [bulan_batas]
        if sa_terakhir is not None:
            conditions.append("ut.sa_terakhir = ?")
            params.append(sa_terakhir)

        sql = f"""
            SELECT COUNT(DISTINCT ts.no_rangka) AS unit, COUNT(*) AS pekerjaan
            FROM tcare_schedule ts
            JOIN unit_tcare ut ON ts.no_rangka = ut.no_rangka
            WHERE {' AND '.join(conditions)}
        """
        return self.execute(sql, params)

    def tcare_converted_count(self, bulan_target: str, sa_terakhir: Optional[str] = None) -> pd.DataFrame:
        """Hitung TCARE-converted count -- pasangan `tcare_pending_count()`,
        sumber SAMA (`tcare_schedule`, BUKAN `attack_list`).

        Ditambahkan setelah ditemukan bug (2026-07-22): view "Attack List
        Semua" sebelumnya menghitung unit/pekerjaan TCARE dari tabel
        `attack_list` (yang sudah di-dedup 1 baris/unit oleh ETL), membuat
        `unit == pekerjaan` SELALU -- padahal 1 unit bisa punya beberapa
        baris jadwal (`pekerjaan`) sekaligus jatuh tempo (mis. 10K + 20K).
        Definisi benar (dikonfirmasi Wahyu): "pekerjaan" = sisa jadwal
        service yang JATUH TEMPO (`bulan_jadwal <= hari ini`), dihitung
        dari `tcare_schedule`, bukan dari `attack_list`.

        REVISI (2026-07-23, bug ditemukan Wahyu, KEDUA KALI): definisi
        "converted" versi sebelumnya pakai
        `strftime('%Y-%m', ts.bulan_realisasi) = bulan_target` -- SELALU
        gagal (return 0) terhadap data ASLI, karena `bulan_realisasi`
        ternyata SUDAH tersimpan dalam format `"YYYY-MM"` (mis. "2024-05"),
        BUKAN `"YYYY-MM-DD"` seperti asumsi awal. `strftime()` SQLite
        butuh minimal format tanggal lengkap (`YYYY-MM-DD`) untuk bisa
        parsing -- input `"YYYY-MM"` saja bikin `strftime()` gagal total
        (return NULL untuk SEMUA baris, dikonfirmasi lewat query
        diagnostik: 12.478 dari 12.478 baris gagal di-parse).

        Fix: `bulan_realisasi` SUDAH dalam format target yang benar,
        TIDAK PERLU `strftime()` sama sekali -- cukup perbandingan
        string langsung (`=`), persis seperti `bulan_jadwal` di
        `tcare_pending_count()`.

        `expired` SENGAJA TIDAK dicek di sini (beda dari `tcare_pending_count`)
        -- dikonfirmasi Wahyu: "expired" itu kategori TERPISAH ("hangus",
        bukan converted maupun pending). Kalau `bulan_realisasi` sudah
        terisi, itu SUDAH converted, terlepas dari nilai `expired`.
        """
        conditions = ["ts.bulan_realisasi = ?"]
        params: list = [bulan_target]
        if sa_terakhir is not None:
            conditions.append("ut.sa_terakhir = ?")
            params.append(sa_terakhir)

        sql = f"""
            SELECT COUNT(DISTINCT ts.no_rangka) AS unit, COUNT(*) AS pekerjaan
            FROM tcare_schedule ts
            JOIN unit_tcare ut ON ts.no_rangka = ut.no_rangka
            WHERE {' AND '.join(conditions)}
        """
        return self.execute(sql, params)

    def find_history(
        self,
        bulan: str,
        source: Optional[str] = None,
        program: Optional[str] = None,
    ) -> pd.DataFrame:
        """Baca attack_list_history untuk statistik konversi per bulan.

        Dipakai kalau user tanya mis. 'berapa unit attack list bulan lalu
        sudah konversi' -- HANYA baca kolom status yang sudah dihitung
        evaluator_konversi.py, tidak menghitung ulang (BR026).

        `program` (INT010): filter granular untuk breakdown per program
        CRM (P1-P4). Kolom `program` di attack_list_history NULL untuk
        source TCARE/CR7/PX (tidak granular by design, dikonfirmasi Room 0)
        -- filter ini hanya bermakna kalau dikombinasikan dengan
        source="CRM" atau dibiarkan tanpa source sekaligus sebut nama
        program (nama program CRM unik, tidak overlap TCARE/CR7/PX).
        """
        conditions = ["bulan = ?"]
        params: list = [bulan]

        if source is not None:
            conditions.append("source = ?")
            params.append(source)

        if program is not None:
            conditions.append("program = ?")
            params.append(program)

        sql = f"""
            SELECT *
            FROM attack_list_history
            WHERE {' AND '.join(conditions)}
            ORDER BY source, no_rangka
        """
        return self.execute(sql, params)