"""
handlers/kpi_summary/parser.py

Ekstraksi entity dari raw text untuk INT004 (KPI Summary).

Tugas parser HANYA ekstraksi teks -> nilai (no business rule, no query
DB) -- sama seperti prinsip Room 4. Resolusi apakah SA yang diekstrak
benar-benar ada di `daily_kpi` adalah tanggung jawab Service (verifikasi
ke Repository), BUKAN parser ini -- supaya tidak menebak/hardcode daftar
SA yang bisa berubah.

Sengaja MENOLAK teks yang mengandung kata domain Detail/Ranking/WIP
supaya tidak bentrok dengan INT005/INT006/INT007 (pola sama seperti
History Service menolak kata "tcare").
"""

from dataclasses import dataclass
from typing import Optional

from handlers._shared.period_parser import ParsedPeriod, extract_period
from handlers._shared.sa_parser import extract_sa_candidate

KPI_KEYWORDS = ("kpi",)

# Kata yang menandakan ini SEHARUSNYA ditangani intent lain, bukan
# KPI Summary -- dicek lebih dulu untuk menghindari overlap match().
DETAIL_KEYWORDS = ("detail", "harian", "per hari", "rincian")
RANKING_KEYWORDS = ("ranking", "rank", "peringkat")
WIP_KEYWORDS = ("wip", "belum invoice", "belum selesai", "in progress")


@dataclass
class ParsedKPISummaryQuery:
    sa_candidate: Optional[str]  # None -> level outlet
    period: ParsedPeriod


def match(text: str) -> bool:
    t = text.lower()
    if not any(k in t for k in KPI_KEYWORDS):
        return False
    if any(k in t for k in DETAIL_KEYWORDS):
        return False
    if any(k in t for k in RANKING_KEYWORDS):
        return False
    if any(k in t for k in WIP_KEYWORDS):
        return False
    return True


def parse(text: str) -> ParsedKPISummaryQuery:
    period = extract_period(text)
    sa_candidate = extract_sa_candidate(text)
    return ParsedKPISummaryQuery(sa_candidate=sa_candidate, period=period)
