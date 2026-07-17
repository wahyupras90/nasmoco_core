"""
handlers/history_tcare/parser.py

Ekstraksi entity dari raw text untuk INT003 (History TCARE).

Sama seperti parser INT002: murni pattern-matching, tidak ada query DB
atau business rule di sini (itu tugas Service/Repository).

Legacy (`tools/history_tcare.py`) hanya mendukung identifier VIN 17
karakter strict. Room 4 memperluas ke plat nomor & nama customer juga
(konsisten dengan INT002), DAN memperbaiki regex no_rangka supaya cocok
data nyata — contoh di brief sendiri ("01S208014054") cuma 12 karakter,
tidak match VIN_REGEX legacy sama sekali. Lihat parser INT002 untuk
penjelasan lengkap kenapa regex diperlonggar jadi 8-17 karakter
alfanumerik campuran huruf+digit.
"""

import re
from dataclasses import dataclass
from typing import Optional

HISTORY_KEYWORDS = ("history", "histori", "riwayat")
TCARE_KEYWORD = "tcare"

# no_rangka: sama seperti parser INT002 — alfanumerik 8-17 karakter,
# wajib campuran huruf+digit, tanpa spasi internal (lebih longgar dari
# VIN_REGEX legacy yang strict 17 karakter dan tidak menangkap contoh
# nyata seperti "01S208014054").
NO_RANGKA_REGEX = re.compile(
    r"\b(?=[A-Z0-9]{8,17}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+\b"
)

# Plat nomor Indonesia DENGAN spasi — sama seperti parser INT002.
PLATE_REGEX = re.compile(r"\b[A-Z]{1,2}\s\d{1,4}\s?[A-Z]{0,3}\b")

# Plat nomor TANPA spasi — pola ketat & anchored, dicek duluan sebelum
# NO_RANGKA_REGEX (ditemukan lewat smoke test nyata: "AB1930GG"
# sebelumnya salah tertangkap sebagai no_rangka). Lihat parser INT002
# untuk penjelasan lengkap kenapa ini aman diprioritaskan.
PLATE_NO_SPACE_REGEX = re.compile(r"^[A-Z]{1,2}\d{1,4}[A-Z]{0,3}$")

# Plat nomor dengan STRIP (format ASLI database, mis. "G-1576-DF") —
# sama seperti parser INT002, lihat penjelasan lengkap di sana.
PLATE_DASH_REGEX = re.compile(r"^[A-Z]{1,2}-\d{1,4}-[A-Z]{0,3}$")

_STOPWORDS = (
    "history",
    "histori",
    "riwayat",
    "tcare",
    "punya",
    "dari",
    "atas",
    "nama",
    "customer",
    "pelanggan",
    "untuk",
    "milik",
    "mobil",
    "unit",
    "kendaraan",
    "dong",
    "ya",
    "yah",
    "sih",
    "nih",
    "deh",
    "lah",
    "kah",
    "kok",
    "gitu",
    "aja",
    "dulu",
    "tolong",
    "coba",
    "cek",
)

_MIN_NAME_TOKEN_LENGTH = 3


@dataclass
class ParsedHistoryTCAREQuery:
    customer_identifier: str
    identifier_type: str  # "no_rangka" | "plate" | "name"


def match(text: str) -> bool:
    """
    Cek apakah `text` relevan untuk INT003.

    Berbeda dari INT002: WAJIB mengandung kata "tcare" secara eksplisit
    (bukan menolaknya) supaya kedua intent yang sama-sama pakai kata
    "history"/"riwayat" tidak saling menyerobot.
    """
    t = text.lower()
    if TCARE_KEYWORD not in t:
        return False
    has_history_word = any(k in t for k in HISTORY_KEYWORDS)
    if not has_history_word:
        return False
    return _extract_identifier(text) is not None


def parse(text: str) -> Optional[ParsedHistoryTCAREQuery]:
    identifier = _extract_identifier(text)
    if identifier is None:
        return None
    identifier_value, identifier_type = identifier
    return ParsedHistoryTCAREQuery(
        customer_identifier=identifier_value,
        identifier_type=identifier_type,
    )


def extract_all_no_rangka(text: str) -> list:
    """
    Dipertahankan dari legacy (`extract_all_no_rangka`) sebagai utility
    (mis. kalau di masa depan Room lain butuh dukungan multi-no_rangka
    sekaligus dalam satu query, seperti legacy) — TIDAK dipakai oleh
    alur single-identifier saat ini di `parse()`.
    """
    matches = NO_RANGKA_REGEX.findall(text.upper())
    seen = []
    for m in matches:
        if m not in seen:
            seen.append(m)
    return seen


def _extract_identifier(text: str):
    text_upper = text.upper()

    plate = _extract_plate(text_upper)
    if plate:
        return plate, "plate"

    no_rangka_matches = NO_RANGKA_REGEX.findall(text_upper)
    if no_rangka_matches:
        return no_rangka_matches[0], "no_rangka"

    name = _extract_name_fallback(text)
    if name:
        return name, "name"

    return None


def _extract_plate(text_upper: str) -> Optional[str]:
    spaced = PLATE_REGEX.search(text_upper)
    if spaced:
        return spaced.group(0)

    for token in re.findall(r"\b[A-Z0-9-]+\b", text_upper):
        if PLATE_NO_SPACE_REGEX.fullmatch(token) or PLATE_DASH_REGEX.fullmatch(token):
            return token

    return None


def _extract_name_fallback(text: str) -> Optional[str]:
    tokens = re.findall(r"[A-Za-z]+", text)
    name_tokens = [t for t in tokens if t.lower() not in _STOPWORDS]
    if not any(len(t) >= _MIN_NAME_TOKEN_LENGTH for t in name_tokens):
        return None
    name = " ".join(name_tokens).strip()
    return name or None