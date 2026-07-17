"""tests/test_room5_services.py"""

import os

import pytest

from db.connection import close_connection

from handlers._shared.period_parser import ParsedPeriod
from handlers.kpi_detail.service import KPIDetailParams, KPIDetailService
from handlers.kpi_summary.service import KPISummaryParams, KPISummaryService
from handlers.ranking.service import RankingParams, RankingService
from handlers.wip.service import WIPParams, WIPService
from repositories.kpi_repository import KPIRepository
from repositories.ranking_repository import RankingRepository
from repositories.wip_repository import WIPRepository
from tests.fixtures_room5 import make_temp_db

JAN_2026 = ParsedPeriod(tahun=2026, bulan=1, is_explicit=True)
FEB_2024 = ParsedPeriod(tahun=2024, bulan=2, is_explicit=True)


@pytest.fixture()
def db_path():
    path = make_temp_db()
    yield path
    close_connection()
    os.remove(path)


# -- KPI Summary --

def test_kpi_summary_specific_sa_with_target(db_path):
    service = KPISummaryService(KPIRepository(db_path))
    result = service.execute(KPISummaryParams(sa_candidate="AGN", period=JAN_2026))
    assert result["status"] == "ok"
    assert result["sa"] == "AGN"
    assert result["totals"]["revenue"] == 7_000_000.0  # 3jt + 4jt
    assert result["target"] is not None
    assert result["target"]["target_revenue"] == 6_000_000.0


def test_kpi_summary_unknown_sa_not_found(db_path):
    service = KPISummaryService(KPIRepository(db_path))
    result = service.execute(KPISummaryParams(sa_candidate="ZZZ", period=JAN_2026))
    assert result["status"] == "not_found"


def test_kpi_summary_outlet_level_includes_counter(db_path):
    service = KPISummaryService(KPIRepository(db_path))
    result = service.execute(KPISummaryParams(sa_candidate=None, period=JAN_2026))
    assert result["status"] == "ok"
    assert result["sa"] is None
    # AGN(3jt+4jt) + IND(1.5jt+6jt) + Counter(200rb) = 14.7jt
    assert result["totals"]["revenue"] == 14_700_000.0


def test_kpi_summary_year_without_target_data(db_path):
    service = KPISummaryService(KPIRepository(db_path))
    result = service.execute(KPISummaryParams(sa_candidate="AGN", period=FEB_2024))
    assert result["status"] == "ok"
    assert result["target"] is None
    assert result["target_year_covered"] is False


# -- KPI Detail --

def test_kpi_detail_returns_daily_rows(db_path):
    service = KPIDetailService(KPIRepository(db_path))
    result = service.execute(KPIDetailParams(sa_candidate="AGN", period=JAN_2026))
    assert result["status"] == "ok"
    assert len(result["daily"]) == 2


def test_kpi_detail_unknown_sa_not_found(db_path):
    service = KPIDetailService(KPIRepository(db_path))
    result = service.execute(KPIDetailParams(sa_candidate="ZZZ", period=JAN_2026))
    assert result["status"] == "not_found"


# -- Ranking --

def test_ranking_excludes_counter_and_total(db_path):
    service = RankingService(RankingRepository(db_path))
    result = service.execute(RankingParams(metric="revenue", period=JAN_2026))
    ranking_df = result["ranking"]
    assert set(ranking_df["sa"]) == {"AGN", "IND"}
    # IND (1.5jt+6jt=7.5jt) > AGN (3jt+4jt=7jt) -> IND rank 1
    assert ranking_df.iloc[0]["sa"] == "IND"
    assert ranking_df.iloc[0]["rank"] == 1
    assert result["outlet_total"]["sa"] == "TOTAL"


def test_ranking_year_without_target(db_path):
    service = RankingService(RankingRepository(db_path))
    period_2024 = ParsedPeriod(tahun=2024, bulan=1, is_explicit=True)
    result = service.execute(RankingParams(metric="revenue", period=period_2024))
    assert result["target_year_covered"] is False


# -- WIP --

def test_wip_aggregates_to_unit_level(db_path):
    service = WIPService(WIPRepository(db_path))
    result = service.execute(WIPParams())
    assert result["total_unit_wip"] == 2  # WO 5001 dan 5002, bukan 3 baris
    units_df = result["units"]
    wo_5001 = units_df[units_df["no_wo"] == 5001].iloc[0]
    assert set(wo_5001["kelompok_list"]) == {"SBE", "GRP"}
    assert wo_5001["jumlah_item_pekerjaan"] == 2


def test_wip_breakdown_per_kelompok(db_path):
    service = WIPService(WIPRepository(db_path))
    result = service.execute(WIPParams())
    breakdown = result["breakdown_per_kelompok"]
    assert breakdown["SBE"] == 1  # WO 5001
    assert breakdown["GRP"] == 1  # WO 5001
    assert breakdown["SBI"] == 1  # WO 5002


def test_wip_filter_by_sa_excludes_other_sa_units(db_path):
    service = WIPService(WIPRepository(db_path))
    result = service.execute(WIPParams(sa_candidate="IND"))
    assert result["total_unit_wip"] == 1
    assert result["units"].iloc[0]["no_wo"] == 5002


def test_wip_no_results_is_valid_not_error(db_path):
    service = WIPService(WIPRepository(db_path))
    result = service.execute(WIPParams(sa_candidate="ZZZ"))
    assert result["status"] == "ok"
    assert result["total_unit_wip"] == 0


def test_wip_summary_only_empties_units_but_keeps_total(db_path):
    """Patch Room 5: wants_summary_only=True -> units kosong, total tetap benar."""
    service = WIPService(WIPRepository(db_path))
    result = service.execute(WIPParams(wants_summary_only=True))
    assert result["total_unit_wip"] == 2
    assert result["units"].empty is True
    assert result["breakdown_per_kelompok"]["SBE"] == 1


def test_wip_list_request_keeps_units_full(db_path):
    """wants_summary_only=False (default / list eksplisit) -> units tetap penuh."""
    service = WIPService(WIPRepository(db_path))
    result = service.execute(WIPParams(wants_summary_only=False))
    assert result["total_unit_wip"] == 2
    assert len(result["units"]) == 2
