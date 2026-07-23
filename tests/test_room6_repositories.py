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


def test_attack_list_find_expired_mode_filters_by_batas_tcare_month(db_path):
    """expired_mode: filter berbasis strftime batas_tcare, BUKAN status --
    meniru logic tools/attack_list.py legacy (dikonfirmasi Wahyu)."""
    repo = AttackListRepository(db_path)
    df = repo.find(expired_mode=True, period_yyyymm="2026-07")
    assert len(df) == 1
    assert df.iloc[0]["no_rangka"] == "MHTCARE0000001"


def test_attack_list_find_expired_mode_excludes_converted(db_path):
    """Row 3 (CRM, batas_tcare 2026-07-20) status='converted' -- HARUS
    dikecualikan meski bulan batas_tcare-nya cocok (status NOT IN
    ('converted','resolved'))."""
    repo = AttackListRepository(db_path)
    df = repo.find(expired_mode=True, period_yyyymm="2026-07")
    assert "MHCRM00000002" not in df["no_rangka"].values


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
