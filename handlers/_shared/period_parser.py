"""
handlers/_shared/period_parser.py

Helper ekstraksi PERIODE (bulan/tahun) dari raw text, dipakai bersama oleh
parser INT004 (KPI Summary), INT005 (KPI Detail), dan INT006 (Ranking) --
ketiganya butuh logic identik untuk mengenali "Januari 2026", "2026-01",
"bulan ini", "bulan lalu", dsb. Satu implementasi (BR027-style sharing di
dalam Room 5 sendiri, sama seperti CustomerProfileRepository di Room 4),
bukan disalin 3x ke masing-masing parser.

Murni ekstraksi teks -> nilai. TIDAK ADA query DB dan TIDAK ADA business
rule (evaluasi target/ranking dsb.) di sini -- itu tugas Service.

`target_bulanan` hanya berisi data tahun 2026 (dikonfirmasi lewat inspeksi
skema) tapi modul ini SENGAJA tidak membatasi tahun yang bisa diekstrak --
pembatasan "target tidak tersedia untuk tahun X" adalah keputusan Service
saat query ke Repository, bukan keputusan Parser.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

_BULAN_NAMA = {
    "januari": 1, "jan": 1,
    "februari": 2, "feb": 2,
    "maret": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "agustus": 8, "agu": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12, "dec": 12,
}

# Dipakai sa_parser.py (dan siapa pun yang ekstrak kandidat kode SA) untuk
# MENGECUALIKAN nama/singkatan bulan dari kandidat SA -- satu sumber
# kebenaran (BR027), supaya daftar bulan tidak disalin ulang dan berisiko
# tidak sinkron. Lihat BUG REPORT 2026-07-22: "kpi juli"/"wip juli" sempat
# salah mengambil "JULI" sebagai kandidat SA karena nama bulan tidak ada
# di stopword ekstraksi SA.
MONTH_NAME_TOKENS_UPPER = frozenset(k.upper() for k in _BULAN_NAMA)

# "Januari 2026" / "Jan 2026" / "Juni 26" (tahun 2 ATAU 4 digit)
_NAMA_BULAN_TAHUN_REGEX = re.compile(
    r"\b(" + "|".join(sorted(_BULAN_NAMA.keys(), key=len, reverse=True)) + r")\s+(\d{2}|\d{4})\b",
    re.IGNORECASE,
)

# "Agustus" TANPA tahun -- default ke tahun berjalan, is_explicit=True.
# Ditambahkan setelah ditemukan gap lewat pengujian Room 6 (Attack List):
# "bulan agustus" (tanpa tahun) sebelumnya TIDAK terdeteksi sama sekali,
# jatuh ke default diam-diam (is_explicit=False, bulan berjalan) --
# padahal user JELAS menyebut bulan tertentu. Perilaku ini meniru
# `_validate_bulan()` di tools/attack_list.py legacy: nama bulan disebut
# tanpa tahun -> asumsikan tahun berjalan, BUKAN dianggap tidak menyebut
# periode sama sekali. Murni ADITIF -- dicoba setelah pola nama+tahun di
# atas (lebih spesifik menang duluan), tidak mengubah hasil untuk teks
# yang sudah match pola lain manapun sebelumnya (dikonfirmasi tidak ada
# test Room 5 yang bergantung pada perilaku lama untuk kasus ini).
_NAMA_BULAN_SAJA_REGEX = re.compile(
    r"\b(" + "|".join(sorted(_BULAN_NAMA.keys(), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# "2026-01" (ISO year-month)
_ISO_YM_REGEX = re.compile(r"\b(\d{4})-(\d{1,2})\b")

# "01/2026" atau "1/2026" (bulan/tahun gaya umum Indonesia)
_SLASH_MY_REGEX = re.compile(r"\b(\d{1,2})/(\d{4})\b")

_RELATIVE_THIS_MONTH = re.compile(r"\bbulan\s+ini\b", re.IGNORECASE)
_RELATIVE_LAST_MONTH = re.compile(
    r"\bbulan\s+(?:lalu|kemarin|kemaren|sebelumnya)\b", re.IGNORECASE
)


def _normalize_year(raw_year: str) -> int:
    """
    Terima tahun 2 ATAU 4 digit dan kembalikan tahun 4 digit penuh.

    Tahun 2 digit (mis. "26") diasumsikan abad 2000-an ("2026") --
    keputusan wajar untuk konteks aplikasi ini (data `daily_kpi` dan
    `target_bulanan` hanya mencakup 2024-2026), bukan tebakan
    sembarangan terhadap skema data (murni interpretasi format tanggal
    umum, tidak menyentuh asumsi skema tabel).
    """
    year = int(raw_year)
    if len(raw_year) == 2:
        return 2000 + year
    return year


@dataclass
class ParsedPeriod:
    tahun: int
    bulan: int  # 1-12
    is_explicit: bool  # False kalau hasil default (tidak disebut user sama sekali)


def extract_period(text: str, today: Optional[date] = None) -> ParsedPeriod:
    """
    Ekstrak (tahun, bulan) dari `text`. Kalau tidak ada penyebutan periode
    sama sekali, default ke bulan berjalan (`is_explicit=False`) supaya
    Handler/Formatter bisa memberi tahu user bahwa periode diasumsikan,
    bukan diam-diam menganggap itu permintaan eksplisit.
    """
    today = today or date.today()

    m = _NAMA_BULAN_TAHUN_REGEX.search(text)
    if m:
        bulan = _BULAN_NAMA[m.group(1).lower()]
        tahun = _normalize_year(m.group(2))
        return ParsedPeriod(tahun=tahun, bulan=bulan, is_explicit=True)

    m = _NAMA_BULAN_SAJA_REGEX.search(text)
    if m:
        bulan = _BULAN_NAMA[m.group(1).lower()]
        return ParsedPeriod(tahun=today.year, bulan=bulan, is_explicit=True)

    m = _ISO_YM_REGEX.search(text)
    if m:
        tahun = int(m.group(1))
        bulan = int(m.group(2))
        if 1 <= bulan <= 12:
            return ParsedPeriod(tahun=tahun, bulan=bulan, is_explicit=True)

    m = _SLASH_MY_REGEX.search(text)
    if m:
        bulan = int(m.group(1))
        tahun = int(m.group(2))
        if 1 <= bulan <= 12:
            return ParsedPeriod(tahun=tahun, bulan=bulan, is_explicit=True)

    if _RELATIVE_LAST_MONTH.search(text):
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        return ParsedPeriod(tahun=year, bulan=month, is_explicit=True)

    if _RELATIVE_THIS_MONTH.search(text):
        return ParsedPeriod(tahun=today.year, bulan=today.month, is_explicit=True)

    # Default diam-diam: bulan berjalan, ditandai is_explicit=False supaya
    # formatter bisa menampilkan "(diasumsikan bulan berjalan)".
    return ParsedPeriod(tahun=today.year, bulan=today.month, is_explicit=False)


def month_date_range(tahun: int, bulan: int) -> tuple:
    """
    Rentang tanggal awal & akhir bulan (string ISO "YYYY-MM-DD"), aman
    dipakai untuk perbandingan string terhadap kolom `tanggal` TEXT di
    `daily_kpi` (format ISO konsisten, sama seperti asumsi Room 4 untuk
    `unitmasuk.tanggal`).
    """
    date_from = date(tahun, bulan, 1)
    if bulan == 12:
        next_month_first = date(tahun + 1, 1, 1)
    else:
        next_month_first = date(tahun, bulan + 1, 1)
    date_to = next_month_first.fromordinal(next_month_first.toordinal() - 1)
    return date_from.isoformat(), date_to.isoformat()


_BULAN_NAMA_DISPLAY = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November",
    12: "Desember",
}


def display_period(tahun: int, bulan: int) -> str:
    """Label periode yang enak dibaca, contoh: 'Januari 2026'."""
    return f"{_BULAN_NAMA_DISPLAY.get(bulan, bulan)} {tahun}"
