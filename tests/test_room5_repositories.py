"""tests/test_room5_repositories.py"""

import os

import pytest

from db.connection import close_connection

from repositories.kpi_repository import KPIRepository
from repositories.ranking_repository import RankingRepository
from repositories.wip_repository import WIPRepository
from tests.fixtures_room5 import make_temp_db


@pytest.fixture()
def db_path():
    path = make_temp_db()
    yield path
    close_connection()
    os.remove(path)


def test_kpi_repository_get_distinct_sa(db_path):
    repo = KPIRepository(db_path)
    assert set(repo.get_distinct_sa()) == {"AGN", "IND", "Counter"}


def test_kpi_repository_get_daily_filters_by_sa_and_range(db_path):
    repo = KPIRepository(db_path)
    df = repo.get_daily("2026-01-01", "2026-01-31", sa="AGN")
    assert len(df) == 2
    assert set(df["tanggal"]) == {"2026-01-01", "2026-01-02"}


def test_kpi_repository_get_daily_outlet_level_includes_counter(db_path):
    repo = KPIRepository(db_path)
    df = repo.get_daily("2026-01-01", "2026-01-31", sa=None)
    assert "Counter" in set(df["sa"])


def test_kpi_repository_get_target_found(db_path):
    repo = KPIRepository(db_path)
    row = repo.get_target(2026, 1, "AGN")
    assert row is not None
    assert row["target_revenue"] == 6_000_000.0


def test_kpi_repository_get_target_not_available_for_2024(db_path):
    repo = KPIRepository(db_path)
    row = repo.get_target(2024, 1, "AGN")
    assert row is None
    assert repo.has_target_for_year(2024) is False
    assert repo.has_target_for_year(2026) is True


def test_ranking_repository_excludes_counter(db_path):
    repo = RankingRepository(db_path)
    df = repo.get_ranking_source("2026-01-01", "2026-01-31")
    assert "Counter" not in set(df["sa"])
    assert set(df["sa"]) == {"AGN", "IND"}


def test_ranking_repository_targets_exclude_total(db_path):
    repo = RankingRepository(db_path)
    df = repo.get_targets_for_ranking(2026, 1)
    assert "TOTAL" not in set(df["sa"])


def test_ranking_repository_outlet_total(db_path):
    repo = RankingRepository(db_path)
    row = repo.get_outlet_total(2026, 1)
    assert row is not None
    assert row["sa"] == "TOTAL"
    assert row["target_revenue"] == 12_000_000.0


def test_wip_repository_filters_unfinished_only(db_path):
    repo = WIPRepository(db_path)
    df = repo.get_wip_items()
    # WO 5001 (2 baris) + WO 5002 (1 baris) = 3 baris; WO 6001 sudah invoice
    assert len(df) == 3
    assert set(df["no_wo"]) == {5001, 5002}


def test_wip_repository_filter_by_kelompok(db_path):
    repo = WIPRepository(db_path)
    df = repo.get_wip_items(kelompok="SBI")
    assert len(df) == 1
    assert df.iloc[0]["no_wo"] == 5002


def test_wip_repository_filter_by_sa(db_path):
    repo = WIPRepository(db_path)
    df = repo.get_wip_items(sa="IND")
    assert len(df) == 1
    assert df.iloc[0]["no_wo"] == 5002
