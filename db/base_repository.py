"""
db/base_repository.py

Interface wajib untuk semua repository di nasmoco_core.

Aturan:
    - Semua repository spesifik (Room 4+) WAJIB extend BaseRepository.
    - execute() SELALU mengembalikan pandas.DataFrame.
    - HANYA read-only. INSERT / UPDATE / DELETE dilarang.
    - Tidak ada business rule di layer ini (itu tugas Service).
    - Tidak ada formatting di layer ini (itu tugas Service/Handler).

Selain execute(), tersedia tiga helper (ADR018) untuk kasus umum yang
sering dibutuhkan repository spesifik (mis. KPIRepository):
    - execute_one(sql, params) -> dict | None   (satu row pertama)
    - scalar(sql, params)      -> Any | None    (satu nilai kolom pertama)
    - exists(sql, params)      -> bool          (apakah ada minimal 1 row)

Ketiganya adalah wrapper tipis di atas execute() — tidak menambah jalur
akses baru ke DB, tetap tunduk pada aturan read-only yang sama.
"""

import re
import sqlite3
from typing import Any, Optional

import pandas as pd

from db.connection import get_connection
from utils.logger import get_logger

logger = get_logger(__name__)

# Statement yang dilarang karena repository ini read-only.
_FORBIDDEN_KEYWORDS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE)\b",
    re.IGNORECASE,
)


class RepositoryError(Exception):
    """Error umum pada layer repository (E002 - query error)."""


class BaseRepository:
    """
    Base class untuk semua repository.

    Repository spesifik cukup extend class ini dan menambahkan method
    query spesifik yang memanggil `self.execute(...)` di dalamnya.
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path

    def execute(self, sql: str, params=None) -> pd.DataFrame:
        """
        Jalankan query SELECT dan kembalikan hasilnya sebagai DataFrame.

        Args:
            sql: statement SQL. Hanya SELECT yang diizinkan.
            params: parameter untuk query (tuple, list, atau dict),
                    diteruskan langsung ke sqlite3 (parameterized query,
                    aman dari SQL injection selama caller tidak melakukan
                    string-concat manual ke `sql`).

        Returns:
            pandas.DataFrame — selalu, bahkan jika hasil kosong
            (DataFrame kosong dengan kolom sesuai cursor.description,
            atau tanpa kolom jika query tidak mengembalikan baris).

        Raises:
            RepositoryError: jika query bukan SELECT, atau terjadi
                              error koneksi/eksekusi (E001/E002).
        """
        if _FORBIDDEN_KEYWORDS.match(sql):
            logger.error("Query ditolak (bukan read-only): %s", sql)
            raise RepositoryError(
                "E003: hanya SELECT yang diizinkan pada BaseRepository."
            )

        try:
            conn = get_connection(self._db_path)
        except (sqlite3.Error, FileNotFoundError) as exc:
            logger.error("E001: koneksi database gagal — %s", exc)
            raise RepositoryError(f"E001: koneksi database gagal — {exc}") from exc

        try:
            cursor = conn.execute(sql, params or [])
            rows = cursor.fetchall()
            columns = (
                [description[0] for description in cursor.description]
                if cursor.description
                else []
            )
            return pd.DataFrame([dict(row) for row in rows], columns=columns)
        except sqlite3.Error as exc:
            logger.error("E002: query error — %s | sql=%s", exc, sql)
            raise RepositoryError(f"E002: query error — {exc}") from exc

    def execute_one(self, sql: str, params=None) -> Optional[dict]:
        """
        Jalankan query dan kembalikan row pertama sebagai dict.

        Berguna untuk lookup by-id atau query yang seharusnya
        mengembalikan tepat satu (atau nol) baris.

        Returns:
            dict — kolom row pertama, atau None jika tidak ada baris.
        """
        df = self.execute(sql, params)
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def scalar(self, sql: str, params=None) -> Optional[Any]:
        """
        Jalankan query dan kembalikan nilai kolom pertama dari row
        pertama saja. Cocok untuk COUNT(*), SUM(...), MAX(...), dsb.

        Returns:
            Nilai scalar, atau None jika tidak ada baris.
        """
        df = self.execute(sql, params)
        if df.empty:
            return None
        return df.iloc[0, 0]

    def exists(self, sql: str, params=None) -> bool:
        """
        Cek apakah query menghasilkan minimal satu baris.

        Berguna untuk validasi keberadaan data, mis. cek apakah
        customer_id tertentu ada di customer_profile, tanpa perlu
        menarik seluruh row-nya.

        Returns:
            True jika ada minimal satu baris, False jika kosong.
        """
        df = self.execute(sql, params)
        return not df.empty
