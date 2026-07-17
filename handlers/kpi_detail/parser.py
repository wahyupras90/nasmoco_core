"""
handlers/kpi_detail/parser.py

Ekstraksi entity dari raw text untuk INT005 (KPI Detail — rincian harian).

Beda dengan INT004 (KPI Summary): parser ini MEWAJIBKAN kata domain
Detail (`detail`/`harian`/`per hari`/`rincian`) supaya match() tidak
bentrok dengan INT004 (yang justru menolak kata-kata ini). SA-candidate
dan period extraction pakai modul shared yang sama dengan INT004
(BR027-style sharing).
"""

from dataclasses import dataclass
from typing import Optional

from handlers._shared.period_parser import ParsedPeriod, extract_period
from handlers._shared.sa_parser import extract_sa_candidate

KPI_KEYWORDS = ("kpi",)
DETAIL_KEYWORDS = ("detail", "harian", "per hari", "rincian")
RANKING_KEYWORDS = ("ranking", "rank", "peringkat")
WIP_KEYWORDS = ("wip", "belum invoice", "belum selesai", "in progress")


@dataclass
class ParsedKPIDetailQuery:
    sa_candidate: Optional[str]
    period: ParsedPeriod


def match(text: str) -> bool:
    t = text.lower()
    if not any(k in t for k in KPI_KEYWORDS):
        return False
    if not any(k in t for k in DETAIL_KEYWORDS):
        return False
    if any(k in t for k in RANKING_KEYWORDS):
        return False
    if any(k in t for k in WIP_KEYWORDS):
        return False
    return True


def parse(text: str) -> ParsedKPIDetailQuery:
    period = extract_period(text)
    sa_candidate = extract_sa_candidate(text)
    return ParsedKPIDetailQuery(sa_candidate=sa_candidate, period=period)
