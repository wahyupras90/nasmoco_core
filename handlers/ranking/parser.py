"""
handlers/ranking/parser.py

Ekstraksi entity dari raw text untuk INT006 (Ranking SA).

Metrik yang bisa diranking (default: revenue kalau tidak disebut):
  revenue, cpus, unit_entry, total_liter, jasa, tgp

Tidak butuh SA-candidate (ranking selalu untuk SEMUA SA, exclude
'Counter' -- keputusan bisnis dikonfirmasi user, diterapkan di
RankingRepository).
"""

from dataclasses import dataclass

from handlers._shared.period_parser import ParsedPeriod, extract_period

RANKING_KEYWORDS = ("ranking", "rank", "peringkat")

_METRIC_KEYWORDS = {
    "revenue": "revenue",
    "cpus": "cpus",
    "unit entry": "unit_entry",
    "unit masuk": "unit_entry",
    "liter": "total_liter",
    "jasa": "jasa",
    "tgp": "tgp",
}
DEFAULT_METRIC = "revenue"


@dataclass
class ParsedRankingQuery:
    metric: str
    period: ParsedPeriod


def match(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in RANKING_KEYWORDS)


def parse(text: str) -> ParsedRankingQuery:
    period = extract_period(text)
    metric = _extract_metric(text)
    return ParsedRankingQuery(metric=metric, period=period)


def _extract_metric(text: str) -> str:
    t = text.lower()
    for keyword, column in _METRIC_KEYWORDS.items():
        if keyword in t:
            return column
    return DEFAULT_METRIC
