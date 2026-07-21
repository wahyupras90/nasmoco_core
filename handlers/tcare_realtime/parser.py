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

## Dukungan pencarian by-nama (ditambahkan setelah brief Wahyu via Room 0)

Kalau TIDAK ada VIN yang terdeteksi, parser coba deteksi apakah teks
mengandung NAMA customer -- REUSE `handlers.history_tcare.parser`
(Room 4, fungsi `parse()`, TIDAK diubah/dimodifikasi) untuk klasifikasi
no_rangka/plate/name yang sudah teruji, bukan menulis ulang logic serupa.

Sebelum delegasi ke parser Room 4, kata-kata trigger domain INT013
sendiri ("web", "realtime", "live", "online", "rangka", "vin", "status")
DIHILANGKAN dulu dari teks -- supaya tidak ikut mencemari hasil ekstraksi
nama (Room 4 punya stopword sendiri untuk kata-katanya, tapi wajar tidak
tahu soal kata-kata spesifik INT013; membersihkan teks di sisi Room 6
ini TIDAK mengubah file Room 4 sama sekali).
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from handlers.history_tcare import parser as room4_history_tcare_parser
from parsers.base_params import BaseParams
from parsers.base_parser import BaseParser

TCARE_REALTIME_KEYWORDS = (
    "tcare realtime", "tcare live", "cek tcare", "status tcare online",
    "tcare web", "cek rangka", "cek vin",
)

# Token kandidat no_rangka/VIN: alfanumerik, 5-17 karakter (longgar --
# no_rangka di project ini TIDAK selalu 17 char, lihat ADR024 Room 4
# findings), WAJIB campuran huruf+angka (pola sama seperti Room 4
# `NO_RANGKA_REGEX` di handlers/history_tcare/parser.py).
#
# PENTING (ditemukan lewat testing fitur pencarian by-nama, 2026-07-21):
# versi awal regex ini (`\b[A-Z0-9]{5,17}\b`, TANPA syarat campuran
# huruf+angka) menangkap KATA APA PUN 5-17 huruf sebagai "VIN" -- bukan
# cuma "HISTORY" (sudah diperbaiki via stopword sebelumnya), tapi juga
# nama orang biasa seperti "SANTOSO" (bagian dari pencarian by-nama).
# Menambah stopword satu-satu tidak akan pernah cukup (tidak mungkin
# daftar semua kemungkinan nama orang) -- akar masalahnya diperbaiki di
# sini: WAJIB ada minimal 1 huruf DAN 1 angka, sama seperti VIN asli.
_VIN_CANDIDATE_REGEX = re.compile(
    r"\b(?=[A-Z0-9]{5,17}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+\b"
)

# Kata domain yang kebetulan alfanumerik pendek -- TIDAK BOLEH dianggap VIN.
_STOPWORDS = {
    "TCARE", "REALTIME", "LIVE", "STATUS", "ONLINE", "WEB", "CEK", "RANGKA",
    "VIN", "HISTORY", "SERVICE", "RIWAYAT", "ATTACK", "KPI", "RANKING", "WIP", "TOLONG", "COBA", "DONG", "UNTUK", "DARI", "DAN", "ATAU",
}

# Kata trigger domain INT013 sendiri -- dibersihkan dari teks SEBELUM
# didelegasikan ke parser Room 4 untuk ekstraksi nama (lihat docstring
# modul). Bukan stopword Room 4 -- ini murni pembersihan di sisi Room 6.
_OWN_TRIGGER_WORDS_TO_STRIP = ("realtime", "web", "live", "online", "rangka", "vin", "status")
_STRIP_REGEX = re.compile(
    r"\b(" + "|".join(_OWN_TRIGGER_WORDS_TO_STRIP) + r")\b",
    re.IGNORECASE,
)


def _strip_own_trigger_words(text: str) -> str:
    return _STRIP_REGEX.sub(" ", text)


@dataclass
class TCARERealtimeParams(BaseParams):
    vins: List[str] = field(default_factory=list)
    customer_name: Optional[str] = None


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

        if vins:
            # VIN terdeteksi -- perilaku LAMA, tidak berubah sama sekali
            # (wajib regresi PASS, lihat brief).
            return TCARERealtimeParams(vins=vins)

        # Tidak ada VIN -- coba deteksi nama customer (fitur baru).
        cleaned = _strip_own_trigger_words(text)
        parsed_room4 = room4_history_tcare_parser.parse(cleaned)
        if parsed_room4 is not None and parsed_room4.identifier_type == "name":
            return TCARERealtimeParams(vins=[], customer_name=parsed_room4.customer_identifier)

        return TCARERealtimeParams(vins=[])