"""tests/test_room6_repositories.py"""

import os

import pytest

from db.connection import close_connection
from repositories.attack_list_repository import AttackListRepository
from repositories.tcare_web_status_repository import TCAREWebStatusRepository
from tests.fixtures_room6 import make_temp_db


@pytest.fixture()
def db_path():
    path = make_temp_db()
    yield path
    close_connection()
    os.remove(path)


# -- AttackListRepository --

def test_attack_list_find_no_filter_returns_all(db_path):
    repo = AttackListRepository(db_path)
    df = repo.find()
    assert len(df) == 4


def test_attack_list_find_filters_by_source(db_path):
    repo = AttackListRepository(db_path)
    df = repo.find(source="CRM")
    assert len(df) == 2
    assert set(df["source"]) == {"CRM"}


def test_attack_list_find_filters_by_status(db_path):
    repo = AttackListRepository(db_path)
    df = repo.find(status="converted")
    assert len(df) == 1
    assert df.iloc[0]["no_rangka"] == "MHCRM00000002"


def test_attack_list_find_combines_filters(db_path):
    repo = AttackListRepository(db_path)
    df = repo.find(source="CRM", sa_terakhir="AGN")
    assert len(df) == 1
    assert df.iloc[0]["status"] == "converted"


def test_attack_list_summary_per_source(db_path):
    repo = AttackListRepository(db_path)
    df = repo.summary_per_source()
    per_source = dict(zip(df["source"], df["jumlah_unit"]))
    assert per_source == {"TCARE": 1, "CRM": 2, "CR7": 1}


def test_attack_list_tcare_pending_count_excludes_expired(db_path):
    """ADR024 klarifikasi Room 6: tcare_schedule (bukan _full_history) --
    unit expired=1 TIDAK boleh terhitung."""
    repo = AttackListRepository(db_path)
    df = repo.tcare_pending_count(bulan_batas="2026-07")
    assert df.iloc[0]["unit"] == 2  # MHTCARE0000001 & 0002, bukan yang expired


def test_attack_list_find_history_by_bulan(db_path):
    repo = AttackListRepository(db_path)
    df = repo.find_history(bulan="2026-06")
    # Fixture (INT010): 1 TCARE + 3 CRM (2 program berbeda) + 2 PX di bulan sama
    assert len(df) == 6


def test_attack_list_find_history_filters_by_source(db_path):
    repo = AttackListRepository(db_path)
    df = repo.find_history(bulan="2026-06", source="TCARE")
    assert len(df) == 1
    assert df.iloc[0]["tgl_konversi"] == "2026-06-15"


def test_attack_list_find_history_filters_by_program(db_path):
    """INT010: filter granular per program CRM, kolom program tersedia
    di attack_list_history sejak perubahan skema (ALTER TABLE, disepakati
    Room 0)."""
    repo = AttackListRepository(db_path)
    df = repo.find_history(bulan="2026-06", program="Panggil Pulang - At Risk")
    assert len(df) == 2
    assert set(df["no_rangka"]) == {"MHCRM00000001", "MHCRM00000003"}


def test_attack_list_find_history_combines_source_and_program(db_path):
    """INT010: source + program dikombinasikan -- filter paling spesifik."""
    repo = AttackListRepository(db_path)
    df = repo.find_history(bulan="2026-06", source="CRM", program="Aktivasi New & Potential")
    assert len(df) == 1
    assert df.iloc[0]["no_rangka"] == "MHCRM00000004"


def test_attack_list_find_history_filters_by_sa_konversi(db_path):
    """KEPUTUSAN ROOM 0: filter `sa` di find_history() memakai kolom
    `sa_konversi` (SA closing transaksi riil), BUKAN attack_list.sa_terakhir.
    Fixture: id=1 (TCARE) sa_konversi='AGN'."""
    repo = AttackListRepository(db_path)
    df = repo.find_history(bulan="2026-06", sa="AGN")
    assert len(df) == 1
    assert df.iloc[0]["no_rangka"] == "MHTCARE0000001"


def test_attack_list_find_history_sa_null_rows_not_matched(db_path):
    """DoD: baris sa_konversi IS NULL (data lama belum di-backfill/belum
    convert) TIDAK match filter sa apa pun -- bukan error."""
    repo = AttackListRepository(db_path)
    df = repo.find_history(bulan="2026-06", sa="AGN")
    assert "MHCRM00000001" not in df["no_rangka"].values  # id=2, sa_konversi NULL


def test_attack_list_find_expired_mode_filters_by_batas_tcare_month(db_path):
    """expired_mode: filter berbasis strftime batas_tcare -- BUKAN lagi
    exclude status (lihat riwayat perubahan di test di bawah). Bulan
    2026-07 punya 2 baris fixture: id=1 (TCARE, pending) DAN id=3 (CRM,
    converted) -- keduanya sekarang masuk populasi expired."""
    repo = AttackListRepository(db_path)
    df = repo.find(expired_mode=True, period_yyyymm="2026-07")
    assert len(df) == 2
    assert set(df["no_rangka"]) == {"MHTCARE0000001", "MHCRM00000002"}


def test_attack_list_find_expired_mode_includes_converted_and_pending(db_path):
    """KEPUTUSAN ROOM 0 (REVISI KEDUA, 2026-07-24, dikonfirmasi ulang
    langsung Wahyu): "expired bulan X" = SEMUA unit dengan batas_tcare
    jatuh di bulan X, PENDING + CONVERTED SEKALIGUS -- TIDAK dikecualikan
    berdasarkan status.

    RIWAYAT: test ini DULU bernama
    test_attack_list_find_expired_mode_excludes_converted dan mengecek
    HAL SEBALIKNYA (unit converted HARUS dikecualikan). Root cause bug:
    dengan definisi lama, populasi "expired" selalu 100% pending (unit
    converted dibuang di level SQL), membuat pertanyaan "berapa yang
    converted dari yang expired" (INT010) secara struktural mustahil
    dijawab dengan angka apa pun -- selalu 0, bukan karena data kosong.
    Setelah klarifikasi ulang dengan Wahyu, definisi "expired" itu
    sendiri diperbaiki jadi murni berbasis waktu (batas_tcare), BUKAN
    exclude status -- konsisten dengan cara mode list non-expired
    menghitung total gabungan (converted+pending)."""
    repo = AttackListRepository(db_path)
    df = repo.find(expired_mode=True, period_yyyymm="2026-07")
    # Row 3 (CRM, batas_tcare 2026-07-20, status='converted') SEKARANG
    # HARUS IKUT MUNCUL -- kebalikan dari perilaku lama.
    assert "MHCRM00000002" in df["no_rangka"].values
    converted_row = df[df["no_rangka"] == "MHCRM00000002"].iloc[0]
    assert converted_row["status"] == "converted"


def test_attack_list_find_expired_mode_still_excludes_resolved(db_path):
    """`resolved` TETAP dikecualikan total -- konsisten dengan pola
    project ini di mana pun (mis. find_for_summary_all()), TIDAK berubah
    oleh revisi definisi expired. Insert baris resolved khusus test ini
    (tidak mengubah fixtures_room6.py bersama)."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO attack_list (id, source, no_rangka, sa_terakhir, "
        "segment_rfm, program_id, program, status, batas_tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (99, "TCARE", "MHTCARE0000099", "AGN", "Champions", 10, "PROG A", "resolved", "2026-07-25"),
    )
    conn.commit()
    conn.close()

    repo = AttackListRepository(db_path)
    df = repo.find(expired_mode=True, period_yyyymm="2026-07")
    assert "MHTCARE0000099" not in df["no_rangka"].values


def test_attack_list_find_expired_mode_different_month(db_path):
    repo = AttackListRepository(db_path)
    df = repo.find(expired_mode=True, period_yyyymm="2026-08")
    assert len(df) == 1
    assert df.iloc[0]["no_rangka"] == "MHCRM00000001"


def test_attack_list_find_expired_mode_requires_period(db_path):
    repo = AttackListRepository(db_path)
    with pytest.raises(ValueError):
        repo.find(expired_mode=True, period_yyyymm=None)


def test_attack_list_find_expired_mode_combined_with_source(db_path):
    """Filter source TCARE + expired 2026-07 -- hanya id=1 (TCARE), id=3
    (CRM converted) TIDAK ikut karena source berbeda. Membuktikan filter
    source tetap bekerja independen dari perubahan definisi status."""
    repo = AttackListRepository(db_path)
    df = repo.find(source="TCARE", expired_mode=True, period_yyyymm="2026-07")
    assert len(df) == 1
    assert df.iloc[0]["source"] == "TCARE"


# -- TCAREWebStatusRepository --

def test_tcare_web_status_find_vehicle(db_path):
    repo = TCAREWebStatusRepository(db_path)
    df = repo.find_vehicle("MHKA6GK6JSJ084260")
    assert len(df) == 1
    assert df.iloc[0]["model"] == "CALYA"


def test_tcare_web_status_find_vehicle_not_found(db_path):
    repo = TCAREWebStatusRepository(db_path)
    df = repo.find_vehicle("TIDAK_ADA")
    assert df.empty


def test_tcare_web_status_find_service_ordered(db_path):
    repo = TCAREWebStatusRepository(db_path)
    df = repo.find_service("MHKA6GK6JSJ084260")
    assert len(df) == 2


def test_tcare_web_status_find_error(db_path):
    repo = TCAREWebStatusRepository(db_path)
    df = repo.find_error()
    assert len(df) == 1
    assert df.iloc[0]["no_rangka"] == "MHERROR000000001"
