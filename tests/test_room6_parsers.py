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


# -- INT010: whitelist VALID_PROGRAM & trigger natural --

def test_int010_extract_program_sets_source_crm_automatically():
    """Nama program (whitelist) terdeteksi -> source otomatis 'CRM',
    TANPA perlu user sebut kata 'crm' secara eksplisit."""
    p = parser.parse("konversi program Panggil Pulang - Lost bulan juli")
    assert p.program == "panggil pulang - lost"
    assert p.source == "CRM"
    assert p.mode == "history"


def test_int010_program_name_not_leaked_into_dynamic_px_source():
    """BUGFIX ditemukan saat implementasi: nama program CRM (mengandung
    spasi & tanda hubung) sempat bocor sebagian ke _extract_dynamic_source
    dan salah tertangkap sebagai nama source PX. Diperbaiki dengan
    mengecek whitelist program LEBIH DULU, skip ekstraksi source dinamis
    kalau program sudah ketemu."""
    p = parser.parse("berapa yang datang dari program Aktivasi New & Potential")
    assert p.source == "CRM"
    assert p.program == "aktivasi new & potential"


def test_int010_natural_trigger_datang_requires_domain_context():
    """'datang' SENDIRIAN (tanpa source/program/kata konversi) TIDAK boleh
    memicu match() -- terlalu generik, berpotensi salah tangkap query
    domain lain (ADR028 checklist)."""
    assert parser.match("berapa yang datang") is False
    assert parser.match("berapa yang datang bulan ini") is False
    assert parser.match("mobil pelanggan sudah datang belum ya") is False


def test_int010_natural_trigger_datang_with_source_matches():
    """'datang' + source eksplisit (tcare/crm/cr7) dianggap niat history
    natural, walau tidak ada kata 'attack list' atau 'konversi'."""
    assert parser.match("berapa yang datang dari tcare bulan ini") is True
    p = parser.parse("berapa yang datang dari tcare bulan ini")
    assert p.mode == "history"
    assert p.source == "TCARE"


def test_int010_dynamic_px_source_unaffected_by_program_whitelist():
    """Regresi negatif: ekstraksi source dinamis PX (nama custom dari
    Excel) tetap bekerja seperti sebelumnya -- whitelist program CRM
    tidak mengganggu jalur ini sama sekali kalau program tidak disebut."""
    p = parser.parse("attack list Recall_Rem_2026")
    assert p.source == "Recall_Rem_2026"
    assert p.program is None
    assert p.mode == "list"


def test_dynamic_px_source_rejects_pure_punctuation():
    """BUGFIX (2026-07-23, ditemukan Wahyu): sisa teks yang cuma tanda
    baca (artefak copy-paste prompt CLI, mis. '>' ikut ke-input) TIDAK
    BOLEH dianggap nama source PX yang valid. Sebelumnya
    '> berapa attack list juli' menghasilkan source='>' secara harfiah."""
    p = parser.parse("> berapa attack list juli")
    assert p.source is None

    # Pastikan source PX asli (ada huruf/angka) TETAP jalan seperti biasa.
    p2 = parser.parse("attack list Recall_Rem_2026")
    assert p2.source == "Recall_Rem_2026"


def test_int010_source_check_uses_word_boundary_not_substring():
    """Permintaan verifikasi eksplisit Room 0 (ADR028 checklist, kasus
    lintas-domain): source (tcare/crm/cr7) di trigger natural HARUS dicek
    word-boundary, BUKAN substring biasa.

    BUG DITEMUKAN & DIPERBAIKI: sebelum fix, VIN yang mengandung kata
    "tcare" sebagai substring (mis. "MHTCARE0000001") membuat kalimat
    riwayat servis biasa salah match ke attack_list -- padahal domainnya
    History Service/History TCARE, bukan attack list/konversi sama
    sekali. Kalimat ini TIDAK boleh match, supaya tidak "mencuri" query
    dari history_service/history_tcare (checklist wajib ADR028)."""
    assert parser.match("MHTCARE0000001 kapan terakhir datang service") is False
    assert parser.match("customer ini kapan terakhir datang service?") is False


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


def test_attack_list_parse_period_always_captured_regardless_of_expired_mode():
    """FIX (2026-07-23): period SEKARANG SELALU diisi (bukan cuma saat
    expired_mode seperti sebelumnya) -- dibutuhkan mode "all" ("Attack
    List Semua") untuk scoping TCARE pending/converted ke periode yang
    diminta user. `expired_mode` sendiri TETAP False untuk query tanpa
    kata "expired" -- dua field ini independen."""
    p = parser.parse("attack list tcare bulan ini")
    assert p.expired_mode is False
    assert p.period is not None
    assert p.period.is_explicit is True


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