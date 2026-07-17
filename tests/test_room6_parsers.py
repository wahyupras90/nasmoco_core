"""tests/test_room6_parsers.py"""

from handlers.attack_list.parser import AttackListParser
from handlers.tcare_realtime.parser import TCARERealtimeParser
from handlers.tcare_web_status.parser import TCAREWebStatusParser

# -- AttackListParser --

parser = AttackListParser()


def test_attack_list_match_positive():
    assert parser.match("cek attack list dong") is True


def test_attack_list_match_no_space_variant():
    """Dikonfirmasi Wahyu: 'attacklist' (tanpa spasi) harus didukung juga."""
    assert parser.match("attacklist tcare expired agustus sa bdr") is True


def test_attack_list_match_negative():
    assert parser.match("kpi AGN Januari 2026") is False


def test_attack_list_parse_source_filter():
    p = parser.parse("attack list source tcare")
    assert p.mode == "list"
    assert p.source == "TCARE"


def test_attack_list_parse_status_filter():
    p = parser.parse("attack list status pending")
    assert p.status == "pending"


def test_attack_list_parse_sa_candidate():
    p = parser.parse("attack list untuk AGN")
    assert p.sa_terakhir == "AGN"


def test_attack_list_parse_sa_not_confused_with_source_keyword():
    """'TCARE'/'CRM'/'CR7' tidak boleh ketangkap jadi kandidat SA."""
    p = parser.parse("attack list source tcare untuk AGN")
    assert p.source == "TCARE"
    assert p.sa_terakhir == "AGN"


def test_attack_list_parse_program_id():
    p = parser.parse("attack list program 11")
    assert p.program_id == 11


def test_attack_list_parse_wants_summary_only():
    p = parser.parse("berapa total attack list")
    assert p.wants_summary_only is True


def test_attack_list_parse_list_keyword_wins_over_summary():
    p = parser.parse("daftar total attack list")
    assert p.wants_summary_only is False


def test_attack_list_parse_history_mode_requires_explicit_period():
    """'konversi' TANPA periode eksplisit -> tetap mode list (bukan history)."""
    p = parser.parse("attack list konversi")
    assert p.mode == "list"


def test_attack_list_parse_history_mode_with_explicit_period():
    p = parser.parse("attack list konversi bulan lalu")
    assert p.mode == "history"
    assert p.period is not None
    assert p.period.is_explicit is True


def test_attack_list_parse_sa_whitelist_ignores_non_sa_words():
    """Bug ditemukan sebelumnya: kata 'yg' (singkatan 'yang') salah
    tertangkap sebagai kode SA lewat regex generik. Diperbaiki dengan
    whitelist eksplisit (VALID_SA) -- tes ini reproduksi persis kasusnya."""
    p = parser.parse("attack list tcare yg expired bulan agustus")
    assert p.sa_terakhir is None


def test_attack_list_parse_sa_whitelist_recognizes_real_sa():
    p = parser.parse("attack list tcare sa bdr")
    assert p.sa_terakhir == "BDR"


def test_attack_list_parse_segment_whitelist():
    p = parser.parse("attack list crm segment champion")
    assert p.segment_rfm == "champion"


def test_attack_list_parse_segment_whitelist_multiword():
    p = parser.parse("attack list crm segment at risk")
    assert p.segment_rfm == "at risk"


def test_attack_list_parse_segment_not_recognized_returns_none():
    """Nilai di luar whitelist SENGAJA tidak ditebak (prinsip 'jangan
    menebak data/skema')."""
    p = parser.parse("attack list crm segment entah-apa")
    assert p.segment_rfm is None


def test_attack_list_parse_expired_mode_detected():
    p = parser.parse("attack list tcare expired bulan ini sa bdr")
    assert p.expired_mode is True
    assert p.sa_terakhir == "BDR"
    assert p.period is not None


def test_attack_list_parse_expired_mode_with_month_name_no_year():
    """'bulan agustus' (tanpa tahun) -- perbaikan gap di period_parser
    bersama (sebelumnya tidak terdeteksi eksplisit sama sekali)."""
    p = parser.parse("attack list tcare expired bulan agustus")
    assert p.expired_mode is True
    assert p.period.bulan == 8
    assert p.period.is_explicit is True


def test_attack_list_parse_not_expired_mode_period_is_none():
    """Tanpa kata 'expired', period TIDAK dipakai untuk filter list biasa
    (period tetap None di params) -- beda dari mode expired."""
    p = parser.parse("attack list tcare bulan ini")
    assert p.expired_mode is False
    assert p.period is None


def test_attack_list_match_missing_list_keyword_reproduces_known_gap():
    """'berapa tcare expired bulan ini' TIDAK match -- dikonfirmasi
    konsisten dengan tools/attack_list.py legacy (is_attack_list_query()
    juga butuh kata 'list'), jadi ini bukan gap baru, kemungkinan besar
    typo pengguna yang lupa menyebut 'list'."""
    assert parser.match("berapa tcare expired bulan ini") is False


# -- TCAREWebStatusParser --

web_status_parser = TCAREWebStatusParser()


def test_tcare_web_status_match_positive():
    assert web_status_parser.match("cek tcare web status") is True


def test_tcare_web_status_parse_no_rangka():
    p = web_status_parser.parse("status tcare web MHKA6GK6JSJ084260")
    assert p.no_rangka == "MHKA6GK6JSJ084260"
    assert p.wants_errors is False


def test_tcare_web_status_parse_wants_errors():
    p = web_status_parser.parse("tcare web status error terakhir")
    assert p.wants_errors is True


# -- TCARERealtimeParser --

realtime_parser = TCARERealtimeParser()


def test_tcare_realtime_match_positive():
    assert realtime_parser.match("cek tcare realtime MHKA6GK6JSJ084260") is True


def test_tcare_realtime_parse_single_vin():
    p = realtime_parser.parse("cek tcare realtime MHKA6GK6JSJ084260")
    assert p.vins == ["MHKA6GK6JSJ084260"]


def test_tcare_realtime_parse_multiple_vins():
    p = realtime_parser.parse(
        "cek tcare realtime MHKA6GK6JSJ084260 dan JF1ZD8K72RG010081"
    )
    assert p.vins == ["MHKA6GK6JSJ084260", "JF1ZD8K72RG010081"]


def test_tcare_realtime_parse_no_vin_detected():
    p = realtime_parser.parse("cek tcare realtime")
    assert p.vins == []

def test_tcare_realtime_parser_ignores_history_keyword():
    """ADR028: trigger Handler lain tidak boleh dianggap VIN."""
    p = realtime_parser.parse("history web tcare")
    assert p.vins == []


def test_tcare_realtime_parser_history_keyword_does_not_hide_real_vin():
    """Keyword HISTORY diabaikan, VIN asli tetap diparse."""
    p = realtime_parser.parse("history web tcare MHKA6GK6JSJ084260")
    assert p.vins == ["MHKA6GK6JSJ084260"]

