"""
repositories/history_tcare_repository.py

Repository untuk INT003 (History TCARE).

ADR024 (FINAL, dikunci berdasarkan bukti empiris — lihat brief Room 4):
  - Source of truth riwayat kunjungan TCARE adalah
    `tcare_schedule_full_history`, BUKAN `tcare_schedule`.
    `tcare_schedule` hanya berisi ~3.544 no_rangka (kendaraan TCARE
    aktif, dipakai domain Attack List) sedangkan
    `tcare_schedule_full_history` berisi populasi lengkap (45.598
    no_rangka, termasuk yang sudah lama expired). 92% kendaraan di
    populasi lengkap TIDAK ADA di `tcare_schedule` sama sekali.
  - Kode legacy (`tools/history_tcare.py`) query ke `tcare_schedule` —
    ini BUG tersembunyi yang membuat 92% unit salah dilaporkan
    "tidak ditemukan". Repository ini WAJIB tidak mewarisi bug itu.
  - `tcare_schedule_v1_backup`, `tcare_monthly_v1_backup`,
    `tcare_monthly_full_history` DILARANG dipakai di mana pun.
  - KOREKSI (setelah verifikasi langsung ke nasmoco.db, lihat README
    Room 4 bagian "Koreksi ADR024"): `unit_tcare` BUKAN typo/nama lama
    dari tabel `tcare_unit` seperti dugaan awal brief. `unit_tcare`
    adalah VIEW asli (`CREATE VIEW unit_tcare AS SELECT r.*, ... FROM rs
    r LEFT JOIN tcare_unit t ON r.no_rangka = t.no_rangka`) yang
    menggabungkan identitas unit dari tabel `rs` dengan field
    operasional TCARE dari tabel `tcare_unit`. Info unit untuk INT003
    WAJIB query ke VIEW `unit_tcare`, BUKAN tabel mentah `tcare_unit`
    (yang tidak punya kolom identitas seperti `model`/`no_polisi`/
    `customer` sama sekali).

RO/kunjungan (BR020) diambil lewat CustomerProfileRepository yang SAMA
dipakai HistoryServiceRepository (BR027 — satu implementasi, bukan
disalin).

ADR003/ADR004: tidak ada business rule di sini (mis. keputusan fallback
saat `unit_tcare` kosong tapi riwayat ada) — itu tanggung jawab
HistoryTCAREService.
"""

from typing import Optional

import pandas as pd

from db.base_repository import BaseRepository
from repositories.customer_profile_repository import CustomerProfileRepository


class HistoryTCARERepository(BaseRepository):
    """Akses read-only ke VIEW `unit_tcare` + tabel `tcare_schedule_full_history`."""

    def __init__(self, db_path: str = None):
        super().__init__(db_path)
        # Komposisi, bukan duplikasi (BR027).
        self.profile_repo = CustomerProfileRepository(db_path)

    # -- Resolusi identifier customer (delegasi ke CustomerProfileRepository) --

    def resolve_profile_by_no_polisi(self, no_polisi: str) -> pd.DataFrame:
        return self.profile_repo.get_by_no_polisi(no_polisi)

    def resolve_profile_by_customer_name(self, customer_name: str) -> pd.DataFrame:
        return self.profile_repo.get_by_customer_name(customer_name)

    def get_ro_count(self, no_rangka: str) -> Optional[int]:
        """BR020, lewat implementasi bersama di CustomerProfileRepository."""
        return self.profile_repo.get_total_kunjungan_fisik(no_rangka)

    def get_fallback_identity(self, no_rangka: str) -> Optional[dict]:
        """
        Identitas cadangan dari `customer_profile` untuk kasus VIEW
        `unit_tcare`
        tidak punya baris untuk no_rangka ini (lihat HistoryTCAREService
        untuk kapan ini dipakai — supaya tidak mewarisi kelas bug yang
        sama seperti ADR024: sebuah tabel info yang tidak mencakup semua
        no_rangka membuat unit dianggap "tidak ditemukan" padahal riwayat
        TCARE-nya ada).
        """
        df = self.profile_repo.get_by_no_rangka(no_rangka)
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    # -- Info unit TCARE --

    def get_unit_info(self, no_rangka: str) -> Optional[dict]:
        """
        Info unit (1 baris per no_rangka) dari VIEW `unit_tcare`.

        PENTING (dikoreksi setelah verifikasi langsung ke `nasmoco.db`,
        lihat README Room 4 bagian "Koreksi ADR024"): `unit_tcare`
        BUKAN nama lama/typo dari tabel `tcare_unit` seperti dugaan awal
        di brief. `unit_tcare` adalah VIEW asli yang sungguh ada:

            CREATE VIEW unit_tcare AS
                SELECT r.*, t.tcare_type, t.sisa_service, t.sisa_detail,
                       t.next_service, t.last_sbe_km, t.last_sbe_date,
                       t.last_sbe_dealer, t.last_sbe_source,
                       t.sa_terakhir, t.tgl_sa_terakhir,
                       t.flag_pending_sbe, t.flag_sa,
                       t.flag_tgl_kunjungan, t.flag_wo_type,
                       t.next_sbe_expected, t.last_updated
                FROM rs r
                LEFT JOIN tcare_unit t ON r.no_rangka = t.no_rangka

        Field identitas (`model`, `no_polisi`, `customer`,
        `dealer_kategori`, `batas_tcare`, `tgl_do`) datang dari tabel
        `rs` (lewat `r.*`), BUKAN dari tabel `tcare_unit` mentah (yang
        cuma punya field operasional TCARE seperti `tcare_type`,
        `sisa_service`, dst — makanya query awal ke tabel `tcare_unit`
        langsung gagal "no such column: model"). Dibuktikan lewat
        smoke test nyata terhadap `nasmoco.db` (legacy `history_tcare.py`
        query ke `unit_tcare` dan berhasil menampilkan Customer/Model/
        No Polisi/Batas TCARE lengkap).

        Returns:
            dict kolom unit, atau None kalau no_rangka tidak ada di
            `unit_tcare` (bisa saja tetap ADA di
            `tcare_schedule_full_history` — lihat Service).
        """
        return self.execute_one(
            "SELECT no_rangka, model, no_polisi, customer, dealer_kategori, "
            "sa_terakhir, tcare_type, batas_tcare, sisa_detail, tgl_do "
            "FROM unit_tcare WHERE no_rangka = ?",
            (no_rangka,),
        )

    # -- Riwayat kunjungan TCARE (ADR024: full_history, BUKAN tcare_schedule) --

    def get_schedule_history(self, no_rangka: str) -> pd.DataFrame:
        """
        Riwayat kunjungan TCARE (1 baris per milestone 1K-60K) dari
        `tcare_schedule_full_history` — SATU-SATUNYA tabel yang boleh
        dipakai untuk ini (ADR024, final).
        """
        return self.execute(
            "SELECT kunjungan, pekerjaan, bulan_jadwal, bulan_realisasi, "
            "status, sa_realisasi, no_wo_real, expired "
            "FROM tcare_schedule_full_history WHERE no_rangka = ? "
            "ORDER BY kunjungan",
            (no_rangka,),
        )

    def has_any_tcare_history(self, no_rangka: str) -> bool:
        """Cek cepat (tanpa tarik semua kolom) apakah ada riwayat sama sekali."""
        return self.exists(
            "SELECT 1 FROM tcare_schedule_full_history WHERE no_rangka = ?",
            (no_rangka,),
        )