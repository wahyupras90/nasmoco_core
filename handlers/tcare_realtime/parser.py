"""
handlers/tcare_realtime/parser.py — INT013 TCARE Realtime per VIN

Parser PERTAMA di Room 6, extend BaseParser (ADR025) langsung -- bukan
grandfathered function-based seperti Room 4/5.

Ekstraksi murni teks -> parameter terstruktur. TIDAK ADA akses DB/HTTP
di sini -- fetch live ke web TAM adalah tugas Service/Repository.

Definisi VIN di project ini (ADR024/Room 4 findings): `no_rangka` TIDAK
selalu 17 karakter VIN standar -- jadi parser ini SENGAJA tidak memvalidasi
panjang/format VIN secara ketat, hanya ekstraksi token alfanumerik yang
"terlihat seperti" nomor rangka. Validasi keberadaan sebenarnya baru
diketahui setelah fetch ke web TAM (kalau tidak ketemu, itu tanggung jawab
Service/Handler untuk melaporkan sebagai error per-VIN, bukan Parser yang
menebak valid/tidaknya).

Mendukung banyak VIN sekaligus (sesuai keputusan Room 0: tidak ada batas
jumlah) -- dipisah dengan koma, spasi, "dan", atau baris baru.
"""

import re
from dataclasses import dataclass, field
from typing import List

from parsers.base_params import BaseParams
from parsers.base_parser import BaseParser

TCARE_REALTIME_KEYWORDS = (
    "tcare realtime", "tcare live", "cek tcare", "status tcare online",
    "tcare web", "cek rangka", "cek vin",
)

# Token kandidat no_rangka/VIN: alfanumerik, minimal 5 karakter (longgar --
# no_rangka di project ini TIDAK selalu 17 char, lihat ADR024 Room 4
# findings), maksimal 17 (VIN standar) supaya tidak menangkap kata biasa.
_VIN_CANDIDATE_REGEX = re.compile(r"\b[A-Z0-9]{5,17}\b")

# Kata domain yang kebetulan alfanumerik pendek -- TIDAK BOLEH dianggap VIN.
_STOPWORDS = {
    "TCARE", "REALTIME", "LIVE", "STATUS", "ONLINE", "WEB", "CEK", "RANGKA",
    "VIN", "HISTORY", "SERVICE", "RIWAYAT", "ATTACK", "KPI", "RANKING", "WIP", "TOLONG", "COBA", "DONG", "UNTUK", "DARI", "DAN", "ATAU",
}


@dataclass
class TCARERealtimeParams(BaseParams):
    vins: List[str] = field(default_factory=list)


class TCARERealtimeParser(BaseParser):
    """Parser untuk INT013. `match()` dipanggil Handler sebelum `parse()`,
    mengikuti pola Router -> Handler yang sudah ada (bukan bagian kontrak
    BaseParser, tapi konvensi tiap Room 4/5/6 menaruh match() di Parser)."""

    def match(self, text: str) -> bool:
        t = text.lower()
        if any(k in t for k in TCARE_REALTIME_KEYWORDS):
            return True
        # PATCH: "tcare"+"web" atau "tcare"+"realtime" sebagai kata terpisah,
        # URUTAN BEBAS -- ditemukan Wahyu: "history web tcare <plat>" tidak
        # match karena TCARE_REALTIME_KEYWORDS di atas cuma substring
        # berurutan tetap ("tcare web"), sedangkan user menulis "web tcare"
        # (terbalik). Kata "tcare" WAJIB ada supaya tidak match sembarang
        # kalimat yang cuma mengandung "web"/"realtime" tanpa konteks TCARE.
        return "tcare" in t and ("web" in t or "realtime" in t)

    def parse(self, text: str) -> TCARERealtimeParams:
        text_upper = text.upper()
        vins: List[str] = []
        seen = set()

        for token in _VIN_CANDIDATE_REGEX.findall(text_upper):
            if token in _STOPWORDS:
                continue
            if token in seen:
                continue
            seen.add(token)
            vins.append(token)

        return TCARERealtimeParams(vins=vins)

