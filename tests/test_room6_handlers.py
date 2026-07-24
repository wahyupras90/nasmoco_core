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
    # Fixture (INT010): 6 baris bulan 2026-06 (1 TCARE + 3 CRM + 2 PX)
    assert result.summary["total_tercatat"] == 6
    assert result.summary["total_konversi"] == 3


def test_attack_list_handler_history_dataframe_filtered_to_converted_only(router):
    """KEPUTUSAN ROOM 0: dataframe yang DIKEMBALIKAN di mode history
    difilter ke 'converted saja' (tgl_konversi IS NOT NULL), SETELAH
    summary/total_tercatat/total_konversi dihitung dari populasi
    LENGKAP (bukan populasi yang sudah dipersempit). Jumlah baris
    dataframe HARUS SAMA PERSIS dengan angka total_konversi di summary,
    BUKAN dengan total_tercatat."""
    result = router.route("attack list konversi bulan 2026-06")
    assert len(result.dataframe) == result.summary["total_konversi"] == 3
    assert result.summary["total_tercatat"] == 6  # populasi lengkap, TIDAK ikut menyusut
    assert result.dataframe["tgl_konversi"].notna().all()


def test_attack_list_handler_list_mode_not_filtered_to_converted_only(router):
    """Regresi wajib: mode 'list' (attack_list <source>, TANPA kata
    konversi/histori/history) TIDAK disentuh oleh keputusan filter
    converted-saja -- tetap tampilkan semua baris (pending + converted),
    sesuai perilaku lama Room 6."""
    result = router.route("attack list tcare")
    assert result.summary["mode"] == "list"
    # Mode list pakai tabel attack_list (bukan attack_list_history),
    # tidak ada kolom tgl_konversi -- dataframe tidak difilter sama sekali.
    assert len(result.dataframe) >= 1


# -- INT010: breakdown/filter per program CRM --

def test_int010_history_program_breakdown_dynamic(router):
    """Mode history TANPA filter program -> breakdown per program CRM
    otomatis (dinamis, DISTINCT dari data), bukan hardcode daftar tetap."""
    result = router.route("attack list konversi bulan 2026-06")
    breakdown = result.summary["program_breakdown"]
    programs = {row["program"] for row in breakdown}
    assert programs == {"Panggil Pulang - At Risk", "Aktivasi New & Potential"}
    # Panggil Pulang - At Risk: 2 baris (id=2 pending, id=3 converted)
    pp_at_risk = next(r for r in breakdown if r["program"] == "Panggil Pulang - At Risk")
    assert pp_at_risk["total"] == 2
    assert pp_at_risk["konversi"] == 1


def test_int010_history_filter_program_spesifik(router):
    """Sebut nama program eksplisit -> trigger mode history natural (TANPA
    kata 'attack list'/'konversi' sama sekali), hasil terfilter ke program
    itu saja, source otomatis CRM."""
    result = router.route(
        "berapa yang datang dari program Aktivasi New & Potential bulan 2026-06"
    )
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "history"
    assert result.summary["filter_program"] == "Aktivasi New & Potential"
    assert result.summary["filter_source"] == "CRM"
    assert result.summary["total_tercatat"] == 1


# -- INT010 (Keputusan Room 0): filter SA di mode history via sa_konversi --

def test_int010_history_filter_sa_uses_sa_konversi_not_sa_terakhir(router):
    """KEPUTUSAN ROOM 0: filter SA di mode history/konversi dipetakan ke
    kolom `sa_konversi` (SA yang closing transaksi riil), BUKAN
    `attack_list.sa_terakhir` (SA assignment attack list -- konsep BEDA,
    dipakai mode list saja).

    Fixture: id=1 (TCARE, converted) sa_konversi='AGN'; id=3 (CRM
    Panggil Pulang - At Risk, converted) sa_konversi='ARIS'. Filter
    'sa agn' HARUS hanya menangkap baris id=1, bukan campur dgn baris
    lain yang kebetulan attack_list.sa_terakhir-nya AGN (jika ada)."""
    result = router.route("attack list konversi bulan 2026-06 sa agn")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "history"
    assert result.summary["filter_sa"] == "AGN"
    # DoD: summary HARUS menyempit ke SA yang diminta (BEDA dari filter
    # "converted saja" yang summary tetap dari populasi lengkap) --
    # hanya 1 baris (id=1) yang match sa_konversi='AGN'.
    assert result.summary["total_tercatat"] == 1
    assert result.summary["total_konversi"] == 1
    assert len(result.dataframe) == 1
    assert result.dataframe.iloc[0]["no_rangka"] == "MHTCARE0000001"


def test_int010_history_filter_sa_different_sa_narrows_to_different_row(router):
    """Filter SA lain (ARIS) menangkap baris berbeda (id=3, CRM), bukan
    baris yang sama seperti filter AGN -- bukti filter benar-benar
    membedakan per SA, bukan asal lolos semua."""
    result = router.route("attack list konversi bulan 2026-06 sa aris")
    assert result.summary["filter_sa"] == "ARIS"
    assert result.summary["total_tercatat"] == 1
    assert result.dataframe.iloc[0]["no_rangka"] == "MHCRM00000003"


def test_int010_history_filter_sa_null_data_not_matched(router):
    """DoD: baris dengan sa_konversi IS NULL (data lama belum
    di-backfill evaluator ATAU belum convert) TIDAK match filter SA
    apa pun -- diperlakukan sebagai "belum diketahui SA-nya", BUKAN
    error/crash. Fixture: id=2, 4, 5, 6 semua sa_konversi=NULL -- tidak
    ada satu pun yang muncul di hasil filter SA manapun."""
    result = router.route("attack list konversi bulan 2026-06 sa agn")
    no_rangka_hasil = set(result.dataframe["no_rangka"])
    assert "MHCRM00000001" not in no_rangka_hasil  # id=2, sa_konversi NULL
    assert "MHPX00000001" not in no_rangka_hasil   # id=5, sa_konversi NULL


def test_int010_list_mode_sa_filter_unaffected_by_history_change(router):
    """Regresi wajib (DoD Room 0): mode 'list' (attack_list <source> sa
    <nama>) TIDAK berubah sama sekali -- tetap pakai
    attack_list.sa_terakhir seperti sebelumnya, TIDAK ikut dipetakan ke
    sa_konversi."""
    result = router.route("attack list tcare sa agn")
    assert result.summary["mode"] == "list"
    assert result.summary["filter_sa"] == "AGN"


def test_int010_natural_trigger_konversi_program_without_attack_list_keyword(router):
    """'konversi program X' (tanpa kata 'attack list') tetap harus match
    dan masuk mode history -- kebutuhan trigger natural INT010."""
    result = router.route(
        "konversi program Panggil Pulang - At Risk bulan 2026-06"
    )
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "history"
    assert result.summary["total_tercatat"] == 2


def test_int010_generic_datang_without_domain_context_not_matched(router):
    """Regresi negatif eksplisit (ADR028): 'berapa yang datang' SENDIRIAN
    tanpa konteks domain attack list (source/program/kata konversi) TIDAK
    boleh match handler ini -- terlalu generik, bisa jadi soal domain lain
    (mis. WIP/servis)."""
    handler = AttackListHandler()
    assert handler.match("berapa yang datang") is False
    assert handler.match("berapa yang datang bulan ini") is False


def test_int010_datang_cross_domain_not_stolen_from_history_handlers(router):
    """Permintaan verifikasi eksplisit Room 0 (bukan cuma 'tanpa konteks'
    -- kasus LINTAS-DOMAIN yang lebih rawan): kalimat "datang" milik
    domain History Service/TCARE, TIDAK boleh dicuri attack_list.

    BUG DITEMUKAN & DIPERBAIKI lewat verifikasi ini: source (tcare/crm/cr7)
    di _wants_history_natural() dan match() sempat dicek dengan substring
    biasa (`key in t`), bukan word-boundary (`\\bkey\\b`) -- akibatnya VIN
    yang mengandung "tcare" sebagai substring (mis. "MHTCARE0000001") salah
    tertangkap sebagai penanda source, membuat kalimat riwayat servis biasa
    salah match ke attack_list padahal harusnya ke history_service/
    history_tcare. Diperbaiki dengan re.search(r"\\bkey\\b", ...)."""
    handler = AttackListHandler()
    # VIN mengandung "tcare" sebagai substring -- HARUS TETAP tidak match,
    # ini kalimat riwayat servis biasa, bukan soal attack list/konversi.
    assert handler.match("MHTCARE0000001 kapan terakhir datang service") is False
    assert handler.match("customer ini kapan terakhir datang service?") is False
    assert handler.match("kapan mobil ini datang ke bengkel") is False


def test_int010_all_mode_program_breakdown_dynamic(router):
    """Mode resume-semua (source tidak disebut) -> breakdown per program
    CRM ikut ditampilkan (dinamis, DISTINCT dari data attack_list)."""
    result = router.route("attack list")
    assert result.summary["mode"] == "all"
    breakdown = result.summary["crm_program_breakdown"]
    programs = {row["program"] for row in breakdown}
    # Fixture attack_list dasar: program_id 11 -> program "PROG B" (2 baris)
    assert "PROG B" in programs
    prog_b = next(r for r in breakdown if r["program"] == "PROG B")
    assert prog_b["total"] == 2
    assert prog_b["converted"] == 1
    assert prog_b["pending"] == 1


def test_int010_list_mode_not_affected_by_program_changes(router):
    """Regresi negatif: mode 'list' biasa (source eksplisit, TANPA sebut
    program) TIDAK terpengaruh perubahan INT010 -- perilaku identik
    dengan sebelum patch."""
    result = router.route("attack list tcare")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "list"
    assert result.summary["total_unit"] == 1
    assert result.summary["filter_status"] == "pending"


def test_int010_px_source_not_confused_with_program_name(router):
    """Regresi negatif: nama source PX custom (mis. hasil ekstraksi dinamis)
    tetap berfungsi seperti biasa, tidak tertukar dengan whitelist program
    CRM -- keduanya jalur ekstraksi yang terpisah."""
    handler = AttackListHandler()
    parsed = handler.parser.parse("attack list Recall_Rem_2026")
    assert parsed.source == "Recall_Rem_2026"
    assert parsed.program is None
    assert parsed.mode == "list"


# -- INT010 (extend): trigger history untuk nama program PX --

def test_int010_history_px_name_with_trigger_word_matches(router):
    """DoD #1: 'konversi <nama PX> bulan juli' berhasil match, masuk mode
    history dengan source = nama PX (bukan program, PX tidak granular)."""
    result = router.route("konversi T-CARE LITE FREE 2LT bulan 2026-06")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "history"
    assert result.summary["filter_source"] == "T-CARE LITE FREE 2LT"
    assert result.summary["total_tercatat"] == 2
    assert result.summary["total_konversi"] == 1


def test_int010_history_px_name_without_trigger_word_not_matched(router):
    """DoD #3 (ADR028): nama PX SENDIRIAN, tanpa kata pemicu
    (konversi/histori/history/datang+konteks), TIDAK boleh match --
    nama PX bebas/tidak whitelist seperti CRM, jadi wajib ada kata
    pemicu eksplisit supaya tidak salah tangkap kalimat lain."""
    handler = AttackListHandler()
    assert handler.match("T-CARE LITE FREE 2LT") is False
    assert handler.match("T-CARE LITE FREE 2LT bulan juli") is False


def test_int010_whitelist_crm_checked_before_px_fallback(router):
    """DoD #2: urutan whitelist CRM -> fallback PX dibuktikan EKSPLISIT
    lewat test, bukan cuma diasumsikan dari urutan kode (syarat wajib
    Room 0). Nama program CRM asli TIDAK PERNAH salah jatuh ke jalur PX,
    meski dicek lewat jalur trigger yang sama (kata 'konversi')."""
    handler = AttackListHandler()
    parsed = handler.parser.parse("konversi Panggil Pulang - At Risk bulan 2026-06")
    # HARUS masuk sebagai program CRM (source=CRM, program terisi),
    # BUKAN source=PX dengan nama "Panggil Pulang - At Risk".
    assert parsed.source == "CRM"
    assert parsed.program == "panggil pulang - at risk"


def test_int010_px_name_partially_similar_to_crm_whitelist_still_works_as_px(router):
    """DoD #2 (sisi sebaliknya): nama PX yang KEBETULAN mirip sebagian
    kata whitelist CRM (tapi TIDAK match utuh salah satu dari 4 nilai
    whitelist) tetap diproses BENAR sebagai PX -- bukan salah ke CRM,
    dan bukan juga gagal tidak match sama sekali."""
    handler = AttackListHandler()
    # "Panggil" saja (bukan "Panggil Pulang - At Risk" utuh) BUKAN
    # whitelist CRM yang valid -- harus fallback jadi source PX bernama
    # "Panggil", bukan program CRM.
    parsed = handler.parser.parse("konversi Panggil bulan 2026-06")
    assert parsed.program is None
    assert parsed.source == "Panggil"
    assert parsed.mode == "history"


def test_int010_px_list_mode_unaffected_by_history_extension(router):
    """DoD #4 (regresi wajib): mode 'list' untuk PX (`attack list <nama
    PX>`, fungsi lama Room 6 yang sudah stabil) TIDAK berubah sama sekali
    oleh penambahan trigger history natural PX."""
    handler = AttackListHandler()
    parsed = handler.parser.parse("attack list T-CARE LITE FREE 2LT")
    assert parsed.mode == "list"
    assert parsed.source == "T-CARE LITE FREE 2LT"
    assert parsed.program is None


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


# -- Room 7a: bug "expired diabaikan di mode history" (Opsi A, KEPUTUSAN
# FINAL ROOM 0 2026-07-24) --

def test_room7a_konversi_expired_combo_returns_explanation_not_number(router):
    """DoD: 'konversi attack list tcare expired ...' TIDAK menghitung
    angka konversi apa pun -- 'expired' adalah status akhir final (unit
    gugur dari follow-up), jadi kombinasi ini ditolak dengan pesan
    penjelasan, response code TETAP sukses (INT008_OK, bukan error)."""
    result = router.route("konversi attack list tcare expired bulan 2026-07")
    assert result.code == "INT008_OK"
    assert result.success is True
    assert "expired" in result.message.lower()
    assert "gugur" in result.message.lower() or "tidak berlaku" in result.message.lower()
    # Bukan pesan histori/angka konversi biasa
    assert "total_konversi" not in result.summary
    assert result.summary["mode"] == "conversion_summary_rejected"


def test_room7a_konversi_expired_combo_does_not_touch_history_table(router):
    """DoD: TIDAK ada query ke attack_list_history untuk kombinasi ini --
    dibuktikan lewat dataframe kosong (bukan hasil find_history()) dan
    mode summary yang eksplisit menandakan jalur ditolak sebelum sampai
    ke repository history sama sekali."""
    result = router.route("konversi attack list tcare expired bulan 2026-07")
    assert result.dataframe.empty


def test_room7a_histori_keyword_expired_combo_also_rejected(router):
    """Regresi: kata 'histori'/'history' (bukan cuma 'konversi') + expired
    juga harus ditolak dengan pola yang sama."""
    result = router.route("histori attack list tcare expired bulan 2026-07")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "conversion_summary_rejected"


def test_room7a_konversi_without_expired_still_uses_history_unaffected(router):
    """Regresi wajib PASS: 'konversi' TANPA kata 'expired' TIDAK berubah
    sama sekali -- tetap mode history seperti sebelum fix Room 7a."""
    result = router.route("konversi attack list tcare bulan 2026-06")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "history"
    assert result.summary["total_konversi"] == 1


def test_room7a_expired_mode_list_without_konversi_keyword_unaffected(router):
    """Regresi wajib PASS: mode list 'expired' TANPA kata trigger
    konversi/history sama sekali TIDAK terpengaruh oleh perubahan Room 7a."""
    result = router.route("attack list tcare expired bulan 2026-07")
    assert result.code == "INT008_OK"
    assert result.summary["mode"] == "list"
    assert result.summary["expired_mode"] is True
    assert result.summary["total_unit"] == 1


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
    """TCARE unit/pekerjaan sekarang dari `tcare_schedule` (BUKAN
    `attack_list` lagi -- fix bug "pekerjaan selalu=unit", 2026-07-22):
    MHTCARE0000001 + MHTCARE0000002 pending (2 unit, 2 pekerjaan --
    kebetulan 1:1 di fixture ini karena masing-masing cuma 1 baris
    jadwal, BUKAN karena source-nya attack_list); MHTCARE0000004
    converted (1 unit, 1 pekerjaan). CRM 1 pending (MHCRM00000001, At
    Risk) + 1 converted (MHCRM00000002, At Risk); CR7 1 pending
    (MHCR700000001)."""
    result = router.route("attack list")
    s = result.summary
    assert s["mode"] == "all"

    assert s["tcare_unit_pending"] == 2
    assert s["tcare_pekerjaan_pending"] == 2
    assert s["tcare_unit_converted"] == 1
    assert s["tcare_pekerjaan_converted"] == 1

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
    assert result.summary["tcare_unit_pending"] == 2
    assert result.summary["crm_total"] == 2
    assert result.summary["cr7_total"] == 1


@pytest.fixture()
def db_path_with_multi_pekerjaan_unit(db_path):
    """Tambahan KHUSUS: 1 no_rangka TCARE dengan 2 baris jadwal pending
    sekaligus (10K + 20K) -- untuk membuktikan fix bug "pekerjaan
    selalu=unit" (2026-07-22). TIDAK mengubah fixtures_room6.py, insert
    langsung ke temp DB yang sudah ada."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO unit_tcare (no_rangka, sa_terakhir) VALUES (?, ?)",
        ("MHMULTIPEKERJAAN01", "AGN"),
    )
    conn.executemany(
        "INSERT INTO tcare_schedule (no_rangka, bulan_jadwal, bulan_realisasi, expired) "
        "VALUES (?, ?, ?, ?)",
        [
            ("MHMULTIPEKERJAAN01", "2025-09", None, 0),  # 20K, masih pending
            ("MHMULTIPEKERJAAN01", "2026-03", None, 0),  # 30K, masih pending juga
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def router_with_multi_pekerjaan(db_path_with_multi_pekerjaan_unit):
    r = Router(fallback=NullFallbackProvider())
    r.register(
        AttackListHandler(AttackListService(AttackListRepository(db_path_with_multi_pekerjaan_unit))),
        priority=10,
    )
    return r


def test_attack_list_all_mode_tcare_pekerjaan_can_exceed_unit(router_with_multi_pekerjaan):
    """BUKTI UTAMA fix bug 'pekerjaan selalu=unit' (2026-07-22, contoh
    nyata Wahyu: no_rangka JF1ZD8K72RG010081 dengan 20K+30K pending
    sekaligus). 1 no_rangka dengan 2 baris jadwal pending -> pekerjaan
    (3) HARUS lebih besar dari unit (3, karena 2 unit lain di fixture
    dasar cuma 1 baris masing-masing) -- total unit tetap 3 (2 dari
    fixture dasar + 1 baru), tapi pekerjaan jadi 4 (2+1+1, karena unit
    baru menyumbang 2 baris)."""
    result = router_with_multi_pekerjaan.route("attack list")
    s = result.summary

    # 3 unit unik (MHTCARE0000001, MHTCARE0000002, MHMULTIPEKERJAAN01)
    assert s["tcare_unit_pending"] == 3
    # TAPI 4 baris jadwal (1 + 1 + 2) -- pekerjaan > unit, BUKAN 1:1 lagi.
    assert s["tcare_pekerjaan_pending"] == 4
    assert s["tcare_pekerjaan_pending"] > s["tcare_unit_pending"]


def test_attack_list_all_mode_uses_period_from_query_not_today(router):
    """FIX (2026-07-23, ditemukan Wahyu): sebelumnya `_execute_all_summary()`
    SELALU pakai `datetime.now()` untuk bulan_batas, mengabaikan periode
    yang diminta user ("juli"). Fixture: MHTCARE0000004 realisasi persis
    di 2026-07-10 -- HARUS kebaca sebagai converted kalau user minta
    'juli' (match persis), TAPI HARUS 0 kalau user minta bulan lain
    (mis. 'agustus') karena realisasinya bukan di bulan itu."""
    result_juli = router.route("attack list juli 2026")
    assert result_juli.summary["tcare_unit_converted"] == 1

    result_agustus = router.route("attack list agustus 2026")
    assert result_agustus.summary["tcare_unit_converted"] == 0


def test_attack_list_all_mode_converted_not_cumulative_across_months(router):
    """REVISI (2026-07-23): 'converted' TIDAK BOLEH kumulatif (bulan_jadwal
    <= periode) -- harus match PERSIS bulan realisasi. MHTCARE0000001
    (bulan_jadwal 2026-07, TAPI belum direalisasi -- masih pending)
    TIDAK BOLEH ikut dihitung sebagai converted di bulan manapun."""
    result = router.route("attack list juli 2026")
    # Cuma MHTCARE0000004 yang converted (realisasi persis Juli) --
    # MHTCARE0000001/0000002 (keduanya masih pending) TIDAK ikut.
    assert result.summary["tcare_unit_converted"] == 1