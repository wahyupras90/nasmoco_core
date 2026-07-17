"""
handlers/attack_list/parser.py — INT008 Attack List

Extend BaseParser (ADR025). Tiga mode:
  - "list"            : query attack_list saat ini, dengan filter opsional
                         (source/status/sa_terakhir/segment_rfm/program_id).
  - "list" + expired   : sub-mode "expired" (lihat di bawah) -- BUKAN nilai
                         status, tapi mode filter berbeda berbasis
                         `batas_tcare` per periode.
  - "history"          : statistik konversi dari attack_list_history untuk
                         bulan tertentu -- reuse handlers._shared.period_parser
                         (BR027-style sharing, sama seperti Room 5).

Disambiguasi mode: kata "konversi"/"histori" DIKOMBINASIKAN dengan
penyebutan periode eksplisit (bulan ini/lalu/nama bulan/ISO) -> mode
history. Tanpa penyebutan periode eksplisit, "konversi" dianggap filter
status='converted' di mode list saja (bukan histori).

## Mode "expired" (ditambahkan setelah verifikasi terhadap
`tools/attack_list.py` versi legacy, dikirim Wahyu)

"expired" BUKAN nilai kolom `status` (nilai status yang ada hanya
pending/converted/resolved) -- ini MODE FILTER TERPISAH yang menggantikan
filter status biasa, persis logic legacy:

    kalau expired_mode:
        WHERE strftime('%Y-%m', batas_tcare) = <bulan>
          AND status NOT IN ('converted', 'resolved')

Kata "bulan ini"/"bulan agustus" dkk HANYA dipakai untuk memfilter
`batas_tcare` dalam mode expired ini (reuse `extract_period()`, default ke
bulan berjalan kalau tidak disebutkan eksplisit -- sama seperti
`_validate_bulan()` di legacy). Di luar mode expired, periode TIDAK
memfilter tabel `attack_list` (hanya dipakai untuk mode "history").

## Ekstraksi SA & segment_rfm (whitelist, BUKAN regex generik lagi)

Sebelumnya best-effort regex -- ditemukan bug: kata umum seperti "yg"
(singkatan "yang") salah tertangkap sebagai kandidat SA. Diperbaiki
dengan whitelist eksplisit (VALID_SA, dikonfirmasi Wahyu masih akurat;
VALID_SEGMENT, dari `tools/attack_list.py` legacy) -- jauh lebih aman
daripada pendekatan stopword/blacklist.

## CATATAN TERBUKA untuk Room 0 (belum diimplementasikan, sengaja ditunda)

`program_id` di skema `attack_list` bertipe INTEGER (dikonfirmasi PRAGMA),
tapi `tools/attack_list.py` legacy membandingkan `program_id = 'P1'` (kode
teks) lewat `PROGRAM_KEYWORD_MAP` ("panggil pulang"->P1, dst). Belum bisa
diverifikasi apakah representasi ini masih berlaku di tabel `attack_list`
unified sekarang (kemungkinan sudah berubah jadi id numerik asli dari
`marketing_program`). Ekstraksi `program_id` di sini TETAP hanya menerima
angka literal (`"program 11"`), TIDAK menambahkan alias teks seperti
"panggil pulang" sampai representasi program_id riil dikonfirmasi --
supaya tidak salah filter tanpa ketahuan.
"""

import re
from dataclasses import dataclass
from typing import Optional

from handlers._shared.period_parser import ParsedPeriod, extract_period
from parsers.base_params import BaseParams
from parsers.base_parser import BaseParser

ATTACK_LIST_KEYWORDS = (
    "attack list", "attack-list", "attacklist", "sasaran follow up",
    "unit follow up", "daftar attack",
)

_SOURCE_MAP = {
    "tcare": "TCARE",
    "crm": "CRM",
    "cr7": "CR7",
}

_STATUS_KEYWORDS = {
    "pending": "pending",
    "resolved": "resolved",
    "converted": "converted",
}

_HISTORY_TRIGGER_WORDS = ("konversi", "histori", "history")

EXPIRED_KEYWORD = "expired"

# Whitelist kode SA -- dikonfirmasi Wahyu (2026-07) masih akurat. Kalau
# roster SA berubah di masa depan, cukup update daftar ini (satu titik).
VALID_SA = ("AGN", "ARIS", "BDR", "IND", "NRK", "SAID", "ZKY", "KHA")

# Whitelist segment_rfm -- dari tools/attack_list.py legacy (VALID_SEGMENT).
# Nilai asli lowercase di database ("at risk", "champion", dst).
VALID_SEGMENT = ("at risk", "lost", "champion", "loyal", "potential", "new")

_PROGRAM_ID_REGEX = re.compile(r"\bprogram\s*(?:id\s*)?[:#]?\s*(\d+)\b", re.IGNORECASE)

SUMMARY_ONLY_KEYWORDS = ("total", "berapa", "jumlah")
# CATATAN: "list" SENGAJA TIDAK dimasukkan di sini -- trigger phrase intent
# ini sendiri ("attack list") selalu mengandung kata "list", jadi kalau
# dipakai sebagai LIST_KEYWORDS, wants_summary_only akan SELALU False untuk
# semua query attack list (bug ditemukan lewat unit test). "daftar" cukup
# mewakili niat "tampilkan daftar" dalam Bahasa Indonesia di domain ini.
LIST_KEYWORDS = ("daftar", "detail", "rincian")


@dataclass
class AttackListParams(BaseParams):
    mode: str = "list"  # "list" | "history"
    source: Optional[str] = None
    status: Optional[str] = None
    sa_terakhir: Optional[str] = None
    segment_rfm: Optional[str] = None
    program_id: Optional[int] = None
    period: Optional[ParsedPeriod] = None  # mode=="history" ATAU expired_mode=True
    expired_mode: bool = False
    wants_summary_only: bool = False


def _extract_sa(text_upper: str) -> Optional[str]:
    """Whitelist-based -- cari token VALID_SA yang berdiri sendiri (word
    boundary), BUKAN regex generik + stopword (rawan false-positive, mis.
    'yg' tertangkap jadi SA -- bug yang sudah ditemukan & diperbaiki)."""
    for sa in VALID_SA:
        if re.search(rf"\b{sa}\b", text_upper):
            return sa
    return None


def _extract_segment(text_lower: str) -> Optional[str]:
    """Whitelist-based, dari VALID_SEGMENT (tools/attack_list.py legacy)."""
    for seg in VALID_SEGMENT:
        if seg in text_lower:
            return seg
    return None


class AttackListParser(BaseParser):

    def match(self, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ATTACK_LIST_KEYWORDS)

    def parse(self, text: str) -> AttackListParams:
        t = text.lower()
        text_upper = text.upper()

        source = None
        for key, value in _SOURCE_MAP.items():
            if re.search(rf"\b{key}\b", t):
                source = value
                break

        status = None
        for key, value in _STATUS_KEYWORDS.items():
            if key in t:
                status = value
                break

        period = extract_period(text)
        wants_history = period.is_explicit and any(w in t for w in _HISTORY_TRIGGER_WORDS)
        expired_mode = EXPIRED_KEYWORD in t

        sa_terakhir = _extract_sa(text_upper)
        segment_rfm = _extract_segment(t)

        program_id = None
        m = _PROGRAM_ID_REGEX.search(text)
        if m:
            program_id = int(m.group(1))

        wants_summary_only = any(k in t for k in SUMMARY_ONLY_KEYWORDS) and not any(
            k in t for k in LIST_KEYWORDS
        )

        if wants_history:
            return AttackListParams(mode="history", source=source, period=period)

        return AttackListParams(
            mode="list",
            source=source,
            status=status,
            sa_terakhir=sa_terakhir,
            segment_rfm=segment_rfm,
            program_id=program_id,
            period=period if expired_mode else None,
            expired_mode=expired_mode,
            wants_summary_only=wants_summary_only,
        )