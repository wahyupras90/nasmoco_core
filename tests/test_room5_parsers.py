"""tests/test_room5_parsers.py"""

from handlers._shared.period_parser import extract_period, month_date_range
from handlers.kpi_detail import parser as kpi_detail_parser
from handlers.kpi_summary import parser as kpi_summary_parser
from handlers.ranking import parser as ranking_parser
from handlers.wip import parser as wip_parser


# -- period_parser --

def test_extract_period_nama_bulan_tahun():
    p = extract_period("kpi AGN Januari 2026")
    assert p.tahun == 2026 and p.bulan == 1 and p.is_explicit


def test_extract_period_iso():
    p = extract_period("kpi outlet 2026-03")
    assert p.tahun == 2026 and p.bulan == 3


def test_extract_period_nama_bulan_tahun_2_digit():
    """
    Regresi: "kpi outlet juni 26" sempat gagal dikenali (jatuh ke default
    bulan berjalan) karena regex hanya menerima tahun 4 digit.
    """
    p = extract_period("kpi outlet juni 26")
    assert p.tahun == 2026 and p.bulan == 6 and p.is_explicit is True


def test_extract_period_default_bulan_berjalan():
    p = extract_period("kpi AGN")
    assert p.is_explicit is False


def test_month_date_range_desember():
    date_from, date_to = month_date_range(2026, 12)
    assert date_from == "2026-12-01"
    assert date_to == "2026-12-31"


# -- kpi_summary parser vs kpi_detail parser: harus saling eksklusif --

def test_kpi_summary_match_rejects_detail_keyword():
    assert kpi_summary_parser.match("kpi detail AGN") is False
    assert kpi_summary_parser.match("kpi AGN bulan ini") is True


def test_kpi_detail_match_requires_detail_keyword():
    assert kpi_detail_parser.match("kpi AGN bulan ini") is False
    assert kpi_detail_parser.match("kpi detail AGN") is True


def test_kpi_summary_match_rejects_ranking_and_wip():
    assert kpi_summary_parser.match("ranking kpi bulan ini") is False
    assert kpi_summary_parser.match("kpi wip AGN") is False


def test_kpi_summary_parse_extracts_sa_candidate():
    parsed = kpi_summary_parser.parse("kpi AGN Januari 2026")
    assert parsed.sa_candidate == "AGN"


def test_kpi_summary_parse_outlet_keyword_gives_none_sa():
    parsed = kpi_summary_parser.parse("kpi outlet Januari 2026")
    assert parsed.sa_candidate is None


# -- ranking parser --

def test_ranking_match():
    assert ranking_parser.match("ranking revenue bulan ini") is True
    assert ranking_parser.match("peringkat cpus Januari 2026") is True
    assert ranking_parser.match("kpi AGN") is False


def test_ranking_parse_metric_default_revenue():
    parsed = ranking_parser.parse("ranking bulan ini")
    assert parsed.metric == "revenue"


def test_ranking_parse_metric_cpus():
    parsed = ranking_parser.parse("ranking cpus Januari 2026")
    assert parsed.metric == "cpus"


# -- wip parser --

def test_wip_match():
    assert wip_parser.match("wip") is True
    assert wip_parser.match("unit belum invoice") is True
    assert wip_parser.match("kpi AGN") is False


def test_wip_parse_extracts_kelompok():
    parsed = wip_parser.parse("wip SBE")
    assert parsed.kelompok == "SBE"


def test_wip_parse_extracts_sa_not_confused_with_kelompok():
    parsed = wip_parser.parse("wip AGN kelompok GRP")
    assert parsed.sa_candidate == "AGN"
    assert parsed.kelompok == "GRP"


def test_wip_parse_total_keyword_not_treated_as_sa():
    """
    Regresi: "total wip" sempat salah menangkap 'TOTAL' sebagai kandidat
    kode SA (karena stopword list WIP dulu terpisah dari shared
    SA_STOPWORDS dan lupa memasukkan kata ini).
    """
    parsed = wip_parser.parse("total wip")
    assert parsed.sa_candidate is None

    parsed2 = wip_parser.parse("berapa jumlah unit wip semua SA")
    assert parsed2.sa_candidate is None


def test_wip_parse_summary_only_keywords():
    """Patch Room 5: 'total'/'berapa'/'jumlah' -> wants_summary_only=True."""
    assert wip_parser.parse("total wip").wants_summary_only is True
    assert wip_parser.parse("berapa jumlah wip").wants_summary_only is True
    assert wip_parser.parse("wip").wants_summary_only is False


def test_wip_parse_list_keyword_wins_over_summary_only():
    """'daftar total wip' tetap dianggap minta list, bukan summary_only."""
    parsed = wip_parser.parse("daftar total wip")
    assert parsed.wants_summary_only is False

    parsed2 = wip_parser.parse("list wip SBE")
    assert parsed2.wants_summary_only is False
