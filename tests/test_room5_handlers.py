"""tests/test_room5_handlers.py"""

import os

import pytest

from db.connection import close_connection

from ai.router import NullFallbackProvider, Router
from handlers.kpi_detail.handler import KPIDetailHandler
from handlers.kpi_detail.service import KPIDetailService
from handlers.kpi_summary.handler import KPISummaryHandler
from handlers.kpi_summary.service import KPISummaryService
from handlers.ranking.handler import RankingHandler
from handlers.ranking.service import RankingService
from handlers.wip.handler import WIPHandler
from handlers.wip.service import WIPService
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


@pytest.fixture()
def router(db_path):
    r = Router(fallback=NullFallbackProvider())
    r.register(
        KPISummaryHandler(KPISummaryService(KPIRepository(db_path))), priority=10
    )
    r.register(
        KPIDetailHandler(KPIDetailService(KPIRepository(db_path))), priority=20
    )
    r.register(RankingHandler(RankingService(RankingRepository(db_path))), priority=10)
    r.register(WIPHandler(WIPService(WIPRepository(db_path))), priority=10)
    return r


def test_kpi_summary_handler_ok(router):
    result = router.route("kpi AGN Januari 2026")
    assert result.success is True
    assert result.code == "INT004_OK"
    assert result.summary["sa"] == "AGN"


def test_kpi_summary_handler_not_found(router):
    result = router.route("kpi ZZZ Januari 2026")
    assert result.success is False
    assert result.code == "INT004_NOT_FOUND"


def test_kpi_detail_handler_routed_correctly_not_summary(router):
    result = router.route("kpi detail AGN Januari 2026")
    assert result.code == "INT005_OK"
    assert result.dataframe is not None
    assert len(result.dataframe) == 2


def test_ranking_handler_ok(router):
    result = router.route("ranking revenue Januari 2026")
    assert result.code == "INT006_OK"
    assert result.dataframe.iloc[0]["sa"] == "IND"


def test_wip_handler_ok(router):
    result = router.route("wip")
    assert result.code == "INT007_OK"
    assert result.summary["total_unit_wip"] == 2


def test_wip_handler_total_query_empties_dataframe(router):
    """DoD patch: 'total wip' -> dataframe kosong, summary tetap terisi."""
    result = router.route("total wip")
    assert result.code == "INT007_OK"
    assert result.dataframe.empty is True
    assert result.summary["total_unit_wip"] == 2


def test_wip_handler_berapa_jumlah_query_empties_dataframe(router):
    result = router.route("berapa jumlah wip")
    assert result.dataframe.empty is True
    assert result.summary["total_unit_wip"] == 2


def test_wip_handler_list_query_keeps_dataframe_full(router):
    """DoD patch: 'daftar wip'/'list wip' -> dataframe tetap penuh."""
    result = router.route("daftar wip")
    assert result.dataframe.empty is False
    assert len(result.dataframe) == 2


def test_wip_handler_daftar_total_wip_still_treated_as_list(router):
    """DoD patch: 'daftar total wip' -> LIST menang, dataframe tetap penuh."""
    result = router.route("daftar total wip")
    assert result.dataframe.empty is False
    assert len(result.dataframe) == 2


def test_router_dispatches_to_correct_intent_no_overlap(router):
    """Pastikan match() antar intent Room 5 tidak saling bentrok."""
    assert router.route("kpi AGN Januari 2026").code == "INT004_OK"
    assert router.route("kpi detail AGN Januari 2026").code == "INT005_OK"
    assert router.route("ranking revenue Januari 2026").code == "INT006_OK"
    assert router.route("wip").code == "INT007_OK"
