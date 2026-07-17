"""
handlers/tcare_web_status/parser.py — INT012 TCARE Web Status

Query Handler biasa (pola Room 4/5), extend BaseParser (ADR025, wajib mulai
Room 6). Tidak ada yang baru secara arsitektur -- cuma domain data baru
(tcare_web_vehicle/tcare_web_service/tcare_web_errors, di-refresh scheduler
Windows Task Scheduler di luar nasmoco_core).
"""

import re
from dataclasses import dataclass
from typing import Optional

from parsers.base_params import BaseParams
from parsers.base_parser import BaseParser

TCARE_WEB_KEYWORDS = (
    "tcare web", "status tcare web", "tcare web status", "cek tcare web",
)

ERROR_KEYWORDS = ("error", "gagal scrape", "gagal di-scrape", "gagal ambil")

_RANGKA_CANDIDATE_REGEX = re.compile(r"\b[A-Z0-9]{5,17}\b")
_STOPWORDS = {
    "TCARE", "WEB", "STATUS", "CEK", "ERROR", "GAGAL", "SCRAPE", "UNTUK",
    "DARI", "DAN", "ATAU", "TOLONG", "COBA", "DONG",
    # Kata umum lain yang kebetulan 5-17 huruf -- ditemukan lewat unit test
    # (mis. "terakhir" salah tertangkap jadi no_rangka pada query
    # "tcare web status error terakhir").
    "TERAKHIR", "SEMUA", "SUDAH", "BELUM", "SEKARANG", "TOLONGKAH",
}


@dataclass
class TCAREWebStatusParams(BaseParams):
    no_rangka: Optional[str] = None
    wants_errors: bool = False


class TCAREWebStatusParser(BaseParser):

    def match(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in TCARE_WEB_KEYWORDS)

    def parse(self, text: str) -> TCAREWebStatusParams:
        t = text.lower()
        text_upper = text.upper()

        wants_errors = any(k in t for k in ERROR_KEYWORDS)

        no_rangka = None
        for token in _RANGKA_CANDIDATE_REGEX.findall(text_upper):
            if token in _STOPWORDS:
                continue
            no_rangka = token
            break

        return TCAREWebStatusParams(no_rangka=no_rangka, wants_errors=wants_errors)
