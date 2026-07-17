"""
handlers/wip/parser.py

Ekstraksi entity dari raw text untuk INT007 (WIP -- Work In Progress).

Definisi WIP (dikonfirmasi eksplisit dengan user): unit yang belum
diinvoice. Breakdown kategori pakai kolom `kelompok`: SBE, GRP, WRT,
SBI, LUB, PDS (dikonfirmasi eksplisit dengan user, bukan `klp`).

Filter opsional yang bisa diekstrak dari text:
  - `kelompok` (mis. "wip SBE", "wip kelompok GRP")
  - kode SA (mis. "wip AGN")
  - `wants_summary_only` (mis. "total wip", "berapa jumlah wip") --
    PATCH Room 5: query yang cuma minta angka/ringkasan TIDAK perlu
    menyertakan tabel daftar unit penuh di HandlerResult.dataframe.
    "daftar"/"list"/"detail"/"rincian" selalu menang atas kata
    ringkasan (mis. "daftar total wip" tetap dianggap minta list).
"""

import re
from dataclasses import dataclass
from typing import Optional

from handlers._shared.sa_parser import SA_STOPWORDS
from repositories.wip_repository import KNOWN_KELOMPOK

WIP_KEYWORDS = (
    "wip", "belum invoice", "belum selesai", "in progress",
    "unit belum keluar", "progress",
)

SUMMARY_ONLY_KEYWORDS = ("total", "berapa", "jumlah")
LIST_KEYWORDS = ("list", "daftar", "detail", "rincian")

# Kata domain -- TIDAK BOLEH dianggap kandidat kode SA. Reuse stopword
# shared (sudah termasuk TOTAL/SEMUA/OUTLET, BR027-style, lihat bug
# "total wip" yang sempat salah tertangkap sebagai SA='TOTAL' sebelum
# fix ini) + tambahan kata khusus domain WIP.
_SA_STOPWORDS = {
    *SA_STOPWORDS,
    "WIP", "KELOMPOK", "UNIT", "BELUM", "INVOICE", "SELESAI", "PROGRESS",
    "BERAPA", "JUMLAH", "LIST", "DAFTAR", "RINCIAN",
    *KNOWN_KELOMPOK,
}

_SA_CANDIDATE_REGEX = re.compile(r"\b[A-Z]{2,6}\b")


@dataclass
class ParsedWIPQuery:
    kelompok: Optional[str]
    sa_candidate: Optional[str]
    wants_summary_only: bool = False


def match(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in WIP_KEYWORDS)


def parse(text: str) -> ParsedWIPQuery:
    text_upper = text.upper()
    t = text.lower()

    kelompok = None
    for code in KNOWN_KELOMPOK:
        if re.search(rf"\b{code}\b", text_upper):
            kelompok = code
            break

    sa_candidate = None
    for token in _SA_CANDIDATE_REGEX.findall(text_upper):
        if token in _SA_STOPWORDS:
            continue
        sa_candidate = token
        break

    wants_summary_only = any(k in t for k in SUMMARY_ONLY_KEYWORDS) and not any(
        k in t for k in LIST_KEYWORDS
    )

    return ParsedWIPQuery(
        kelompok=kelompok,
        sa_candidate=sa_candidate,
        wants_summary_only=wants_summary_only,
    )
