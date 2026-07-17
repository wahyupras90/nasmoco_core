"""
tests/test_base_repository.py

Unit test minimal untuk db.base_repository.BaseRepository.

Test ini membuat SQLite database sementara (bukan nasmoco.db asli)
supaya bisa dijalankan tanpa bergantung pada project lama
(D:\\AI_nasmoco). BaseRepository menerima `db_path` override lewat
constructor untuk keperluan ini.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.base_repository import BaseRepository, RepositoryError
from db import connection as connection_module


def _make_temp_db() -> str:
    """Buat SQLite db sementara berisi satu tabel `dummy` untuk testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany(
        "INSERT INTO dummy (id, name) VALUES (?, ?)",
        [(1, "alpha"), (2, "beta")],
    )
    conn.commit()
    conn.close()
    return path


def _reset_thread_local_connection():
    """Pastikan tiap test mulai dari koneksi bersih (bukan cache test lain)."""
    connection_module._local.connection = None
    connection_module._local.db_path = None


def test_execute_returns_dataframe():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        df = repo.execute("SELECT * FROM dummy ORDER BY id")
        assert isinstance(df, pd.DataFrame)
        assert list(df["name"]) == ["alpha", "beta"]
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_execute_with_params():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        df = repo.execute("SELECT * FROM dummy WHERE id = ?", (2,))
        assert len(df) == 1
        assert df.iloc[0]["name"] == "beta"
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_execute_empty_result_returns_empty_dataframe():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        df = repo.execute("SELECT * FROM dummy WHERE id = ?", (999,))
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_write_statements_are_rejected():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        for bad_sql in [
            "INSERT INTO dummy (id, name) VALUES (3, 'gamma')",
            "UPDATE dummy SET name = 'x' WHERE id = 1",
            "DELETE FROM dummy WHERE id = 1",
            "DROP TABLE dummy",
        ]:
            try:
                repo.execute(bad_sql)
                assert False, f"Harusnya ditolak: {bad_sql}"
            except RepositoryError as exc:
                assert "E003" in str(exc)
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_missing_database_raises_repository_error():
    _reset_thread_local_connection()
    repo = BaseRepository(db_path="/nonexistent/path/nasmoco.db")
    try:
        repo.execute("SELECT 1")
        assert False, "Harusnya raise RepositoryError (E001)"
    except RepositoryError as exc:
        assert "E001" in str(exc)


def test_execute_one_returns_dict_for_first_row():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        row = repo.execute_one("SELECT * FROM dummy WHERE id = ?", (2,))
        assert row == {"id": 2, "name": "beta"}
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_execute_one_returns_none_when_empty():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        row = repo.execute_one("SELECT * FROM dummy WHERE id = ?", (999,))
        assert row is None
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_scalar_returns_single_value():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        count = repo.scalar("SELECT COUNT(*) FROM dummy")
        assert count == 2
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_scalar_returns_none_when_empty():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        value = repo.scalar("SELECT name FROM dummy WHERE id = ?", (999,))
        assert value is None
    finally:
        connection_module.close_connection()
        os.remove(db_path)


def test_exists_true_and_false():
    _reset_thread_local_connection()
    db_path = _make_temp_db()
    try:
        repo = BaseRepository(db_path=db_path)
        assert repo.exists("SELECT 1 FROM dummy WHERE id = ?", (1,)) is True
        assert repo.exists("SELECT 1 FROM dummy WHERE id = ?", (999,)) is False
    finally:
        connection_module.close_connection()
        os.remove(db_path)


if __name__ == "__main__":
    test_execute_returns_dataframe()
    test_execute_with_params()
    test_execute_empty_result_returns_empty_dataframe()
    test_write_statements_are_rejected()
    test_missing_database_raises_repository_error()
    test_execute_one_returns_dict_for_first_row()
    test_execute_one_returns_none_when_empty()
    test_scalar_returns_single_value()
    test_scalar_returns_none_when_empty()
    test_exists_true_and_false()
    print("Semua test BaseRepository PASSED.")
