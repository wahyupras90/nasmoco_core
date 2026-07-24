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


# -- INT010 (extend): trigger history untuk nama program PX --

def test_int010_px_history_trigger_extracts_source_no_program():
    """DoD #1: kata pemicu + nama PX -> mode history, source=nama PX,
    program tetap None (PX tidak granular per program, sesuai desain)."""
    p = parser.parse("konversi T-CARE LITE FREE 2LT bulan juli")
    assert p.mode == "history"
    assert p.source == "T-CARE LITE FREE 2LT"
    assert p.program is None


def test_int010_history_mode_no_longer_drops_sa_terakhir():
    """BUG DITEMUKAN & DIPERBAIKI (test manual chatbot production): sebelum
    fix, sa_terakhir berhasil diekstrak (_extract_sa) tapi DIBUANG diam-diam
    saat return AttackListParams(mode="history", ...) -- kata "sa bdr" di
    query "konversi ... sa bdr" silently ignored, filter tidak pernah
    diterapkan. Sekarang sa_terakhir disertakan untuk SEMUA mode."""
    p = parser.parse("konversi T-CARE LITE FREE 2LT bulan juli sa bdr")
    assert p.mode == "history"
    assert p.sa_terakhir == "BDR"


def test_int010_px_history_trigger_requires_trigger_word():
    """DoD #3 (ADR028): nama PX sendirian, TANPA kata pemicu apa pun,
    TIDAK boleh match -- beda dari whitelist CRM yang sudah pasti unik/
    terbatas, nama PX bebas sehingga wajib ada penanda niat eksplisit."""
    assert parser.match("T-CARE LITE FREE 2LT") is False
    assert parser.match("T-CARE LITE FREE 2LT bulan juli") is False


def test_int010_px_history_trigger_word_is_konversi_only_not_history():
    """BUG DITEMUKAN & DIPERBAIKI (test manual dengan chatbot production):
    kata pemicu PX untuk mode history HARUS HANYA "konversi", BUKAN
    "histori"/"history" -- sebelum fix, "history <nama PX> bulan juli"
    match attack_list.match()==True, TAPI di router kalimat ini KALAH
    tie-break dari HistoryServiceHandler (priority sama, registrasi
    lebih dulu), sehingga query salah dijawab "data tidak ditemukan" oleh
    domain yang salah alih-alih statistik konversi attack list. "konversi"
    tidak overlap dengan handler manapun, aman jadi satu-satunya pemicu."""
    assert parser.match("history T-CARE LITE FREE 2LT bulan juli") is False
    assert parser.match("histori T-CARE LITE FREE 2LT bulan juli") is False
    # "konversi" TETAP harus match (regresi negatif untuk fix ini)
    assert parser.match("konversi T-CARE LITE FREE 2LT bulan juli") is True


def test_int010_crm_whitelist_wins_over_px_fallback_same_trigger_word():
    """DoD #2: dibuktikan eksplisit (bukan asumsi) -- whitelist VALID_PROGRAM
    (CRM) dicek LEBIH DULU dari fallback PX, meski sama-sama dipicu kata
    'konversi'. Nama program CRM resmi TIDAK PERNAH bocor ke jalur PX."""
    p = parser.parse("konversi Aktivasi New & Potential bulan juli")
    assert p.source == "CRM"
    assert p.program == "aktivasi new & potential"


def test_int010_px_name_not_matching_whitelist_falls_back_correctly():
    """DoD #2 (sisi sebaliknya): nama yang TIDAK match whitelist CRM utuh
    (walau mengandung kata yang mirip) diproses BENAR sebagai PX, bukan
    salah ke CRM atau gagal total."""
    p = parser.parse("konversi Percepat bulan juli")
    assert p.program is None
    assert p.source == "Percepat"


def test_int010_word_program_not_leaked_into_px_source():
    """BUG DITEMUKAN & DIPERBAIKI (test manual dengan chatbot production):
    kata "program" (tanpa angka setelahnya, TIDAK match
    _PROGRAM_ID_REGEX yang cuma menghapus pola "program 11") sebelumnya
    tidak pernah masuk _DYNAMIC_SOURCE_IGNORE_WORDS, sehingga kalau nama
    program CRM ditulis TANPA tanda hubung ("Panggil Pulang At Risk",
    bukan "Panggil Pulang - At Risk") -- gagal match whitelist
    VALID_PROGRAM (exact match), fallback ke ekstraksi PX, dan kata
    "program" ikut kebawa masuk jadi bagian source
    ("program Panggil Pulang", bukan "Panggil Pulang" saja). Diperbaiki
    dengan menambahkan "program" ke _DYNAMIC_SOURCE_IGNORE_WORDS."""
    p = parser.parse("konversi program Panggil Pulang At Risk bulan juli")
    assert p.source == "Panggil Pulang"
    assert "program" not in p.source.lower()
    # Regresi negatif: program_id literal ("program 11") tetap harus
    # berfungsi seperti biasa, tidak terganggu oleh fix ini.
    p2 = parser.parse("attack list program 11")
    assert p2.program_id == 11
    assert p2.source is None


def test_int010_px_list_mode_unaffected_by_history_trigger_extension():
    """DoD #4: mode 'list' PX (fungsi lama Room 6) tidak berubah sama
    sekali oleh penambahan jalur trigger history natural PX."""
    p = parser.parse("attack list T-CARE LITE FREE 2LT")
    assert p.mode == "list"
    assert p.source == "T-CARE LITE FREE 2LT"
    assert p.program is None


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


# -- Room 7a: bug "expired diabaikan di mode history" --
# KEPUTUSAN FINAL ROOM 0 (2026-07-24, Opsi A): kata trigger konversi/
# history + "expired" TIDAK PERNAH masuk mode="history" -- "expired"
# adalah status akhir final (unit gugur dari follow-up), jadi
# "konversi dari unit yang sudah expired" secara konsep tidak valid.
# Parser HARUS tetap mode="list" (expired_mode=True, TIDAK berubah dari
# perilaku lama) dan menandai wants_conversion_summary=True sebagai
# sinyal ke Service untuk menolak dengan pesan penjelasan (BUKAN
# menghitung angka apa pun).

def test_room7a_expired_plus_konversi_stays_mode_list_not_history():
    """BUG DITEMUKAN & DIPERBAIKI: sebelumnya 'konversi attack list tcare
    expired juli sa bdr' salah masuk mode='history' (attack_list_history
    tidak mengenal konsep expired sama sekali, kata 'expired' diam-diam
    diabaikan). Sekarang WAJIB tetap mode='list'."""
    p = parser.parse("konversi attack list tcare expired juli sa bdr")
    assert p.mode == "list"
    assert p.expired_mode is True
    assert p.wants_conversion_summary is True


def test_room7a_expired_plus_history_keyword_stays_mode_list():
    """Sama seperti kata 'konversi', kata 'histori'/'history' + 'expired'
    juga TIDAK boleh masuk mode history."""
    p = parser.parse("histori attack list tcare expired juli")
    assert p.mode == "list"
    assert p.expired_mode is True
    assert p.wants_conversion_summary is True


def test_room7a_expired_plus_px_konversi_trigger_stays_mode_list():
    """Regresi khusus: trigger PX history ('konversi' + nama source
    dinamis, lihat _PX_HISTORY_TRIGGER_WORDS) juga HARUS tunduk pada
    aturan yang sama -- begitu 'expired' disebut, tetap mode='list',
    bukan mode='history' untuk source PX apa pun."""
    p = parser.parse("konversi T-CARE LITE FREE 2LT expired juli")
    assert p.mode == "list"
    assert p.expired_mode is True
    assert p.wants_conversion_summary is True


def test_room7a_konversi_without_expired_still_mode_history():
    """Regresi wajib PASS: 'konversi' TANPA kata 'expired' TIDAK berubah
    -- tetap mode='history' seperti sebelum fix ini (room7-int010-full-
    validated)."""
    p = parser.parse("konversi attack list tcare juli sa bdr")
    assert p.mode == "history"
    assert p.wants_conversion_summary is False


def test_room7a_expired_without_konversi_still_mode_list_unaffected():
    """Regresi wajib PASS: mode list 'expired' TANPA kata trigger
    konversi/history sama sekali TIDAK terpengaruh -- wants_conversion_summary
    tetap False, perilaku sama persis seperti sebelum fix ini."""
    p = parser.parse("attack list tcare expired juli sa bdr")
    assert p.mode == "list"
    assert p.expired_mode is True
    assert p.wants_conversion_summary is False


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