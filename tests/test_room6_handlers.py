"""tests/test_room6_handlers.py

INT013 (TCARE Realtime) TIDAK diuji di sini -- itu butuh HTTP mock,
lihat tests/test_room6_tcare_realtime.py (DoD: jangan hit web TAM asli
di unit test).
"""

import os
import sqlite3

import pytest

from ai.router import NullFallbackProvider, Router
from db.connection import close_connection
from handlers.attack_list.handler import AttackListHandler
from handlers.attack_list.service import AttackListService
from handlers.tcare_web_status.handler import TCAREWebStatusHandler
from handlers.tcare_web_status.service import TCAREWebStatusService
from repositories.attack_list_repository import AttackListRepository
from repositories.tcare_web_status_repository import TCAREWebStatusRepository
from tests.fixtures_room6 import make_temp_db


@pytest.fixture()
def db_path():
    path = make_temp_db()
    yield path
    close_connection()
    os.remove(path)


@pytest.fixture()
def db_path_with_resolved_row(db_path):
    """Sama seperti `db_path`, ditambah 1 baris CRM berstatus 'resolved'
    (segment 'Loyal') -- KHUSUS untuk test mode 'all' memastikan resolved
    dikecualikan total (tidak dihitung di angka manapun, tidak muncul di
    breakdown segment sama sekali). Tidak mengubah fixtures_room6.py."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO attack_list (id, source, no_rangka, sa_terakhir, "
        "segment_rfm, program_id, program, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (5, "CRM", "MHCRM00000003", "IND", "Loyal", 12, "PROG C", "resolved"),
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def router(db_path):
    r = Router(fallback=NullFallbackProvider())
    r.register(
        AttackListHandler(AttackListService(AttackListRepository(db_path))),
        priority=10,
    )
    r.register(
        TCAREWebStatusHandler(TCAREWebStatusService(TCAREWebStatusRepository(db_path))),
        priority=10,
    )
    return r


@pytest.fixture()
def router_with_resolved(db_path_with_resolved_row):
    r = Router(fallback=NullFallbackProvider())
    r.register(
        AttackListHandler(AttackListService(AttackListRepository(db_path_with_resolved_row))),
        priority=10,
    )
    return r


# -- INT008 Attack List --

def test_attack_list_handler_ok(router):
    """Default status='pending' kalau tidak disebut (dikonfirmasi Wahyu,
    sesuai tools/attack_list.py legacy). Source disebut eksplisit (TCARE)
    supaya tetap masuk mode 'list' biasa, bukan mode 'all' (lihat test
    khusus mode 'all' di bawah)."""
    result = router.route("attack list tcare")
    assert result.success is True
    assert result.code == "INT008_OK"
    assert result.summary["total_unit"] == 1
    assert result.summary["filter_status"] == "pending"


def test_attack_list_handler_explicit_status_overrides_default(router):
    """User sebut status eksplisit -> itu yang dipakai, BUKAN default 'pending'."""
    result = router.route("attack list source crm status converted")
    assert result.code == "INT008_OK"
    assert result.summary["filter_status"] == "converted"
    assert result.summary["total_unit"] == 1


def test_attack_list_handler_expired_mode_not_affected_by_pending_default(router):
    """Mode expired TIDAK boleh kena default status='pending' -- filternya
    sendiri (strftime batas_tcare + status NOT IN converted/resolved)."""
    result = router.route("attack list expired bulan 2026-07")
    assert result.code == "INT008_OK"
    assert result.summary["expired_mode"] is True
    assert result.summary["filter_status"] is None  # BUKAN 'pending'


def test_attack_list_handler_filter_source(router):
    """CRM + default status='pending' -> hanya 1 (yang 'converted' dikecualikan)."""
    result = router.route("attack list source crm")
    assert result.code == "INT008_OK"
    assert result.summary["total_unit"] == 1
    assert result.summary["filter_source"] == "CRM"


def test_attack_list_handler_summary_only_empties_dataframe(router):
    """Pola sama seperti WIP Room 5: 'total/berapa/jumlah' tanpa kata
    list/daftar/detail/rincian -> dataframe kosong, summary tetap terisi.
    Source disebut eksplisit supaya masuk mode 'list' (bukan 'all')."""
    result = router.route("berapa total attack list tcare")
    assert result.code == "INT008_OK"
    assert result.dataframe.empty
    assert result.summary["total_unit"] == 1


def test_attack_list_handler_history_mode(router):
    result = router.route("attack list konversi bulan 2026-06")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "history"
    assert result.summary["total_tercatat"] == 2
    assert result.summary["total_konversi"] == 1


def test_attack_list_handler_not_matched_by_unrelated_text(router):
    handler = AttackListHandler()
    assert handler.match("kpi AGN Januari 2026") is False


def test_attack_list_handler_expired_mode_end_to_end(router):
    result = router.route("attack list expired bulan 2026-07")
    assert result.code == "INT008_OK"
    assert result.summary["expired_mode"] is True
    assert result.summary["total_unit"] == 1
    assert "EXPIRED" in result.message


def test_attack_list_handler_expired_mode_excludes_converted(router):
    result = router.route("attack list expired bulan 2026-07")
    assert "MHCRM00000002" not in result.dataframe["no_rangka"].values


def test_attack_list_handler_expired_mode_combined_with_source(router):
    result = router.route("attack list tcare expired bulan 2026-07")
    assert result.code == "INT008_OK"
    assert result.summary["total_unit"] == 1
    assert result.summary["filter_source"] == "TCARE"


# -- INT012 TCARE Web Status --

def test_tcare_web_status_handler_ok(router):
    result = router.route("status tcare web MHKA6GK6JSJ084260")
    assert result.success is True
    assert result.code == "INT012_OK"
    assert result.summary["ditemukan"] is True
    assert result.summary["total_kunjungan"] == 2


def test_tcare_web_status_handler_not_found(router):
    result = router.route("status tcare web MHTIDAKADA000001")
    assert result.code == "INT012_OK"  # 0 hasil = jawaban valid, bukan error
    assert result.summary["ditemukan"] is False


def test_tcare_web_status_handler_errors_mode(router):
    result = router.route("tcare web status error terakhir")
    assert result.code == "INT012_OK"
    assert result.summary["total_error"] == 1


def test_tcare_web_status_handler_missing_no_rangka(router):
    result = router.route("status tcare web")
    assert result.code == "INT012_OK"
    assert "tidak terdeteksi" in result.message.lower()


# =====================================================================
# Mode "all" -- "Attack List Semua" (source TIDAK disebut, bukan expired)
# Dikonfirmasi Wahyu (2026-07-16): source of truth tunggal attack_list,
# status IN (pending, converted), resolved dikecualikan TOTAL.
# =====================================================================

def test_attack_list_all_mode_triggered_when_source_not_specified(router):
    result = router.route("attack list juli 26")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "all"


def test_attack_list_all_mode_correct_numbers(router):
    """Fixture: TCARE 1 pending (MHTCARE0000001); CRM 1 pending
    (MHCRM00000001, At Risk) + 1 converted (MHCRM00000002, At Risk);
    CR7 1 pending (MHCR700000001)."""
    result = router.route("attack list")
    s = result.summary
    assert s["mode"] == "all"

    assert s["tcare_unit_pending"] == 1
    assert s["tcare_pekerjaan_pending"] == 1
    assert s["tcare_unit_converted"] == 0
    assert s["tcare_pekerjaan_converted"] == 0

    assert s["crm_total"] == 2
    assert s["crm_converted"] == 1
    assert s["crm_pending"] == 1

    assert s["cr7_total"] == 1
    assert s["cr7_converted"] == 0
    assert s["cr7_pending"] == 1


def test_attack_list_all_mode_segment_breakdown_in_message(router):
    result = router.route("attack list")
    assert "At Risk" in result.message
    assert "1 converted, 1 pending" in result.message  # segment At Risk


def test_attack_list_all_mode_dataframe_is_raw_filtered_df(router):
    """dataframe (raw_df) harus berisi baris pending+converted saja
    (bukan None, bukan kosong -- beda dari mode list biasa yang bisa
    sengaja dikosongkan untuk query 'berapa')."""
    result = router.route("attack list")
    assert result.dataframe is not None
    assert not result.dataframe.empty
    assert set(result.dataframe["status"].unique()) <= {"pending", "converted"}


def test_attack_list_all_mode_excludes_resolved_completely(router_with_resolved):
    """Baris resolved (CRM, segment 'Loyal') TIDAK BOLEH dihitung di
    angka manapun ATAU muncul di breakdown segment sama sekali."""
    result = router_with_resolved.route("attack list")
    s = result.summary

    # CRM total TETAP 2 (id2 pending + id3 converted) -- baris resolved
    # (id5, 'Loyal') TIDAK ikut menambah angka ini.
    assert s["crm_total"] == 2

    # Segment 'Loyal' (yang cuma diisi baris resolved) TIDAK BOLEH
    # muncul di message sama sekali -- karena setelah difilter
    # status IN (pending,converted), segment ini kosong.
    assert "Loyal" not in result.message

    # dataframe (raw_df) juga TIDAK BOLEH mengandung baris resolved.
    assert "resolved" not in result.dataframe["status"].values
    assert "MHCRM00000003" not in result.dataframe["no_rangka"].values


def test_attack_list_all_mode_sa_filter_applies_consistently_across_categories(router):
    """Dikonfirmasi Wahyu: kalau ada filter SA, SEMUA kategori (TCARE,
    CRM, CR7) konsisten terfilter SA itu -- bug lama (legacy) cuma
    filter CRM/CR7, TCARE Pending diabaikan. Fixture: SA 'AGN' muncul di
    TCARE (id1), CRM (id3, converted), CR7 (id4) -- TIDAK di CRM id2 (BUD)."""
    result = router.route("attack list sa agn")
    s = result.summary

    assert s["filter_sa"] == "AGN"
    assert s["tcare_unit_pending"] == 1  # id1 (AGN) tetap masuk
    assert s["crm_total"] == 1  # HANYA id3 (AGN, converted) -- id2 (BUD) dikecualikan
    assert s["crm_converted"] == 1
    assert s["crm_pending"] == 0
    assert s["cr7_total"] == 1  # id4 (AGN)


def test_attack_list_all_mode_not_triggered_when_expired(router):
    """Mode 'expired' TIDAK boleh masuk mode 'all' -- tetap mode 'list'
    biasa (persis legacy: handle_attack_list_all tidak pernah cek
    is_expired_query())."""
    result = router.route("attack list expired bulan 2026-07")
    assert result.summary["mode"] == "list"
    assert result.summary["expired_mode"] is True


def test_attack_list_all_mode_not_triggered_when_source_specified(router):
    """Source disebut eksplisit -> tetap mode 'list' biasa, BUKAN 'all'."""
    result = router.route("attack list tcare")
    assert result.summary["mode"] == "list"
def test_attack_list_all_mode_summary_only_empties_dataframe(router):
    """ADR028: mode 'all' juga wajib menghormati wants_summary_only."""
    result = router.route("berapa attack list")
    print(result.summary)

    assert result.summary["mode"] == "all"
    assert result.dataframe is not None
    assert result.dataframe.empty

    # Angka summary tetap tersedia walaupun dataframe dikosongkan.
    assert result.summary["tcare_unit_pending"] == 1
    assert result.summary["crm_total"] == 2
    assert result.summary["cr7_total"] == 1





