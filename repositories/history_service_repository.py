"""
repositories/history_service_repository.py

Repository untuk INT002 (History Service).

Tabel yang dipakai (lihat brief Room 4, hasil PRAGMA table_info):
  - `unitmasuk`      : sumber utama riwayat kunjungan/WO servis
                       (no_wo, no_rangka, no_polisi, customer, model,
                       tanggal, pekerjaan, klp, kelompok, sa, mech, ...)
  - `rekapbulanan`   : sumber revenue RESMI (BR003) — kolom `invoice`,
                       JOIN by no_wo. Tabel `invoice` mentah TIDAK dipakai
                       (BR026: jangan hitung ulang dari tabel pre-ETL).
  - `customer_profile`: RO/kunjungan (BR020) dan profil customer, diakses
                       lewat CustomerProfileRepository (BR027 — shared
                       dengan HistoryTCARERepository, bukan disalin).

Catatan tipe kolom (WAJIB diperhatikan saat JOIN manual di Python,
karena BaseRepository tidak mendukung JOIN lintas-tabel otomatis):
  - `unitmasuk.no_wo`    -> INTEGER
  - `rekapbulanan.no_wo` -> REAL
  Makanya saat query rekapbulanan berdasarkan daftar no_wo dari
  unitmasuk, kita CAST(no_wo AS INTEGER) di sisi SQL supaya match persis
  (bukan cast di Python lalu string-concat ke SQL — tetap parameterized).

`klp`/`kelompok` diambil karena dibutuhkan HistoryServiceService untuk
agregasi `jenis_pekerjaan` per WO (disepakati eksplisit dengan user).

ADR003/ADR004: tidak ada business rule di sini. Resolusi ambigu, definisi
RO, dan penggabungan revenue/agregasi ke history adalah tanggung jawab
HistoryServiceService, bukan repository ini.
"""

from typing import List, Optional

import pandas as pd

from db.base_repository import BaseRepository
from repositories.customer_profile_repository import CustomerProfileRepository


class HistoryServiceRepository(BaseRepository):
    """Akses read-only ke `unitmasuk` + `rekapbulanan`, plus profil customer."""

    def __init__(self, db_path: str = None):
        super().__init__(db_path)
        # Komposisi, bukan duplikasi (BR027) — resolusi customer_profile
        # dipakai bersama oleh HistoryTCARERepository juga.
        self.profile_repo = CustomerProfileRepository(db_path)

    # -- Resolusi identifier customer (delegasi ke CustomerProfileRepository) --

    def resolve_profile_by_no_rangka(self, no_rangka: str) -> pd.DataFrame:
        return self.profile_repo.get_by_no_rangka(no_rangka)

    def resolve_profile_by_no_polisi(self, no_polisi: str) -> pd.DataFrame:
        return self.profile_repo.get_by_no_polisi(no_polisi)

    def resolve_profile_by_customer_name(self, customer_name: str) -> pd.DataFrame:
        return self.profile_repo.get_by_customer_name(customer_name)

    # -- Riwayat WO (unitmasuk) --

    def get_wo_history(
        self,
        no_rangka: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Ambil riwayat WO untuk satu no_rangka, urut dari yang terbaru.

        `tanggal` disimpan sebagai TEXT (format ISO diasumsikan konsisten
        hasil ETL) sehingga perbandingan string >=/<= aman dipakai
        selama formatnya seragam (YYYY-MM-DD).
        """
        sql = (
            "SELECT no_wo, no_invoice, no_polisi, customer, no_rangka, model, "
            "sa, mech, pekerjaan, klp, kelompok, tanggal, tgl_invoice, kategori, tcare "
            "FROM unitmasuk WHERE no_rangka = ?"
        )
        params: List = [no_rangka]

        if date_from:
            sql += " AND tanggal >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND tanggal <= ?"
            params.append(date_to)

        sql += " ORDER BY tanggal DESC"
        return self.execute(sql, params)

    # -- Revenue resmi (rekapbulanan, BR003) --

    def get_revenue_by_no_wo(self, no_wo_list: List[int]) -> pd.DataFrame:
        """
        Ambil revenue resmi (`rekapbulanan.invoice`) untuk sekumpulan no_wo
        sekaligus (hindari N+1 query per baris history).

        BR003/BR026: hanya kolom `invoice` yang dipakai sebagai revenue
        resmi — bukan `total_revenue` di tabel yang sama, dan bukan tabel
        `invoice` mentah.
        """
        if not no_wo_list:
            return pd.DataFrame(columns=["no_wo", "invoice"])

        placeholders = ",".join(["?"] * len(no_wo_list))
        sql = (
            "SELECT CAST(no_wo AS INTEGER) AS no_wo, invoice "
            f"FROM rekapbulanan WHERE CAST(no_wo AS INTEGER) IN ({placeholders})"
        )
        return self.execute(sql, list(no_wo_list))

    def has_any_tcare_history(self, no_rangka: str) -> bool:
        """
        Cek cepat (EXISTS, bukan JOIN berat) apakah no_rangka ini juga
        punya riwayat TCARE — dipakai Handler untuk notifikasi opsional
        saat user query "history <nama>" polos tanpa kata domain
        (keputusan disepakati, bukan bagian ADR024/BR027; ini query
        EXISTS satu baris, sengaja diduplikasi kecil dari
        `HistoryTCARERepository.has_any_tcare_history` alih-alih membuat
        dependency silang antar Repository intent yang berbeda).
        """
        return self.exists(
            "SELECT 1 FROM tcare_schedule_full_history WHERE no_rangka = ?",
            (no_rangka,),
        )

    def find_identity_by_customer_name_in_unitmasuk(self, customer_name: str) -> pd.DataFrame:
        """
        Fallback pencarian nama customer LANGSUNG ke `unitmasuk`, dipakai
        HANYA kalau `customer_profile.get_by_customer_name()` mengembalikan
        0 hasil (keputusan Room 0: Opsi A -- `customer_profile` tetap
        prioritas mutlak; `unitmasuk` murni jaring pengaman, tidak pernah
        digabung/dicek kalau `customer_profile` sudah ada hasil).

        Root cause yang dikonfirmasi Room 0: ini BUKAN data cacat, tapi
        lag ETL bulanan yang wajar -- `customer_profile` di-update tiap
        bulan, jadi customer baru "belum ada" sampai siklus ETL
        berikutnya. Kejadian rutin, bukan edge case langka.

        Mengembalikan identitas MINIMAL (customer, no_rangka, model,
        no_polisi) -- SATU baris per no_rangka unik (bisa >1 no_rangka
        untuk nama yang sama, mis. armada). Field profil yang cuma ada
        di `customer_profile` (segment, dealer_kategori, dst.) TIDAK
        ada di sini -- itu sengaja diisi None di Service (BR020/BR026:
        RO tidak dihitung ulang dari unitmasuk).
        """
        return self.execute(
            "SELECT DISTINCT no_rangka, customer, model, no_polisi "
            "FROM unitmasuk WHERE UPPER(customer) LIKE UPPER(?)",
            (f"%{customer_name}%",),
        )