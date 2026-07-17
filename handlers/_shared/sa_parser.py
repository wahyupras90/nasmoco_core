"""
handlers/_shared/sa_parser.py

Helper ekstraksi kandidat kode SA dari raw text, dipakai bersama oleh
parser INT004 (KPI Summary) dan INT005 (KPI Detail) -- BR027-style
sharing di dalam Room 5 sendiri, satu implementasi bukan disalin.

Murni ekstraksi teks -> string kandidat (atau None untuk level outlet).
TIDAK ADA query DB di sini -- verifikasi apakah kandidat ini benar-benar
ada di `daily_kpi` adalah tanggung jawab Service (Repository), sesuai
prinsip "jangan menebak daftar SA" (brief Room 5 melarang menebak skema/
data, kita perluas prinsipnya: jangan hardcode daftar SA juga, karena SA
baru bisa muncul di masa depan -- lihat kasus ARDI/SUPP yang dikonfirmasi
user diperlakukan apa adanya tanpa whitelist).
"""

import re
from typing import Optional

OUTLET_KEYWORDS = (
    "outlet", "semua sa", "semua advisor", "keseluruhan", "seluruh sa",
)

# Kata domain/kata umum yang kebetulan berupa huruf kapital pendek --
# TIDAK BOLEH dianggap kandidat kode SA.
SA_STOPWORDS = {
    "KPI", "SUMMARY", "DETAIL", "HARIAN", "RANKING", "RANK", "WIP",
    "BULAN", "INI", "LALU", "TAHUN", "DAN", "ATAU", "UNTUK", "DARI",
    "TOLONG", "COBA", "CEK", "DONG", "YA", "SIH", "NIH", "OUTLET",
    "TOTAL", "SEMUA", "ADVISOR", "PER", "HARI", "SA",
}

SA_CANDIDATE_REGEX = re.compile(r"\b[A-Z]{2,6}\b")


def extract_sa_candidate(text: str) -> Optional[str]:
    """
    Kandidat kode SA pertama yang ditemukan di `text`, atau None kalau
    tidak ada / user menyebut kata level-outlet secara eksplisit.
    """
    t = text.lower()
    if any(k in t for k in OUTLET_KEYWORDS):
        return None

    for token in SA_CANDIDATE_REGEX.findall(text.upper()):
        if token in SA_STOPWORDS:
            continue
        return token
    return None
