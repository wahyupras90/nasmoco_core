"""
db/connection.py

Koneksi SQLite READ-ONLY ke database milik project lama
(D:\\AI_nasmoco\\db\\nasmoco.db).

nasmoco_core tidak pernah menulis ke database ini. ETL tetap berjalan
di project lama.

Connection pooling di sini sengaja dibuat sederhana: satu koneksi SQLite
di-reuse per thread (SQLite connection tidak thread-safe untuk dipakai
lintas thread tanpa `check_same_thread=False`, jadi kita simpan koneksi
per-thread memakai `threading.local`).
"""

import os
import sqlite3
import threading

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

_local = threading.local()


def _to_ro_uri(db_path: str) -> str:
    """
    Ubah path file biasa menjadi SQLite URI read-only.

    Contoh:
        D:\\AI_nasmoco\\db\\nasmoco.db
        -> file:D:/AI_nasmoco/db/nasmoco.db?mode=ro
    """
    normalized = db_path.replace("\\", "/")
    return f"file:{normalized}?mode=ro"


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """
    Ambil koneksi SQLite read-only untuk thread yang sedang berjalan.

    Koneksi di-cache per thread (`threading.local`) supaya tidak
    membuka koneksi baru di setiap pemanggilan. Jika `db_path` tidak
    diberikan, akan memakai `config.settings.DB_PATH` (yang sendiri
    bisa di-override lewat environment variable `NASMOCO_DB_PATH`).

    Raises:
        sqlite3.Error: jika koneksi ke database gagal dibuka.
    """
    path = db_path or settings.DB_PATH

    existing = getattr(_local, "connection", None)
    existing_path = getattr(_local, "db_path", None)

    # Reuse koneksi hanya jika masih untuk db_path yang sama.
    if existing is not None and existing_path == path:
        return existing

    if not os.path.exists(path):
        logger.error("Database file tidak ditemukan: %s", path)
        raise FileNotFoundError(f"Database file tidak ditemukan: {path}")

    try:
        uri = _to_ro_uri(path)
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.connection = conn
        _local.db_path = path
        logger.info("Koneksi database dibuka (read-only): %s", path)
        return conn
    except sqlite3.Error as exc:
        logger.error("Gagal membuka koneksi database %s: %s", path, exc)
        raise


def close_connection() -> None:
    """Tutup koneksi milik thread saat ini, jika ada."""
    conn = getattr(_local, "connection", None)
    if conn is not None:
        try:
            conn.close()
            logger.info("Koneksi database ditutup.")
        finally:
            _local.connection = None
            _local.db_path = None
