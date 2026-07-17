"""
handlers/history_service/parser.py

Ekstraksi entity dari raw text untuk INT002 (History Service).

Tugas parser HANYA ekstraksi teks -> nilai (no business rule, no query
DB). Ini murni layer Handler (bukan Service/Repository), sesuai brief
Room 4: "Parser tidak boleh berada di Service atau Repository."

Identifier customer bisa berupa salah satu dari:
  - no_rangka (nomor rangka/chassis). PENTING: no_rangka di data nyata
    TIDAK selalu VIN 17-karakter standar dunia — contoh di brief Room 4
    sendiri ("01S208014054") cuma 12 karakter. Karena itu regex di sini
    SENGAJA lebih longgar dari VIN_REGEX versi legacy (yang strict 17
    karakter): alfanumerik 8-17 karakter, wajib mengandung minimal satu
    huruf dan minimal satu digit (supaya tidak menangkap kata biasa atau
    angka polos), tanpa spasi internal.
  - No polisi (plat nomor Indonesia, mis. "B 1234 XYZ" ATAU "B1234XYZ"
    tanpa spasi). Dicek LEBIH DULU daripada no_rangka lewat pola ketat
    (anchored, seluruh token: 1-2 huruf + 1-4 digit + 0-3 huruf) —
    ditemukan lewat smoke test nyata bahwa plat tanpa spasi (mis.
    "AB1930GG") sebelumnya salah tertangkap sebagai no_rangka karena
    kebetulan juga alfanumerik 8 karakter. Pola ketat ini aman dipakai
    duluan karena no_rangka asli (VIN 17 karakter atau chassis legacy)
    tidak pernah berbentuk "huruf-blok, lalu digit-blok, lalu
    huruf-blok" yang rapi seperti itu — hurufnya berselang-seling
    dengan digit di seluruh panjang string.
  - Nama customer (fallback kalau no_rangka/plat tidak ketemu)

Rentang tanggal (opsional) mendukung dua bentuk:
  - Eksplisit ISO: "2024-01-01 sampai 2024-03-31"
  - Relatif: "N bulan terakhir" / "N bulan belakangan"
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

HISTORY_KEYWORDS = ("history", "histori", "riwayat")
SERVICE_KEYWORDS = ("service", "servis", "kunjungan", "wo", "bengkel")
TCARE_KEYWORD = "tcare"

# no_rangka: alfanumerik 8-17 karakter, wajib campuran huruf+digit, TANPA
# spasi internal. Lihat catatan modul di atas soal kenapa ini lebih
# longgar dari VIN_REGEX legacy yang strict 17 karakter.
NO_RANGKA_REGEX = re.compile(
    r"\b(?=[A-Z0-9]{8,17}\b)(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*[0-9])[A-Z0-9]+\b"
)

# Plat nomor Indonesia DENGAN spasi: 1-2 huruf, WAJIB spasi, 1-4 digit,
# spasi opsional, 0-3 huruf.
PLATE_REGEX = re.compile(r"\b[A-Z]{1,2}\s\d{1,4}\s?[A-Z]{0,3}\b")

# Plat nomor TANPA spasi: pola ketat & anchored ke SATU TOKEN penuh
# (huruf-blok, digit-blok, huruf-blok — tanpa segmen lain). Dicek
# duluan sebelum NO_RANGKA_REGEX (lihat docstring modul).
PLATE_NO_SPACE_REGEX = re.compile(r"^[A-Z]{1,2}\d{1,4}[A-Z]{0,3}$")

# Plat nomor dengan STRIP (format ASLI yang tersimpan di kolom
# no_polisi database, mis. "G-1576-DF") — ditemukan lewat bug report
# Room 0: fix normalisasi strip di CustomerProfileRepository sempat
# lupa diterapkan juga di sisi Parser, jadi query dengan format strip
# gagal total sebelum sempat sampai ke Repository sama sekali.
PLATE_DASH_REGEX = re.compile(r"^[A-Z]{1,2}-\d{1,4}-[A-Z]{0,3}$")

DATE_RANGE_REGEX = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s*(?:s(?:ampai|/d)|-|hingga)\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
RELATIVE_MONTHS_REGEX = re.compile(
    r"(\d+)\s*bulan\s*(?:terakhir|belakangan|kebelakang)", re.IGNORECASE
)

_STOPWORDS = (
    "history",
    "histori",
    "riwayat",
    "service",
    "servis",
    "kunjungan",
    "wo",
    "bengkel",
    "punya",
    "dari",
    "atas",
    "nama",
    "customer",
    "pelanggan",
    "untuk",
    "milik",
    # Kata pengisi/partikel kasual Indonesia — bukan nama, sering
    # nyangkut di ujung kalimat percakapan ("riwayat service dong").
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

# Token hasil fallback nama harus punya minimal satu kata dengan panjang
# ini supaya tidak menganggap sisa kata pendek acak sebagai nama valid.
_MIN_NAME_TOKEN_LENGTH = 3


@dataclass
class ParsedHistoryServiceQuery:
    customer_identifier: str
    identifier_type: str  # "no_rangka" | "plate" | "name"
    date_from: Optional[str] = None
    date_to: Optional[str] = None


def match(text: str) -> bool:
    """
    Cek apakah `text` relevan untuk INT002.

    Sengaja MENOLAK teks yang menyebut "tcare" secara eksplisit supaya
    tidak bentrok dengan INT003 (History TCARE) — kedua intent sama-sama
    memakai kata "history"/"riwayat".

    KEPUTUSAN (disepakati eksplisit, bukan diputuskan sepihak): kata
    domain servis (`service`/`servis`/`kunjungan`/`wo`/`bengkel`) TIDAK
    wajib ada. Query polos seperti "history <nama>" atau
    "riwayat <nama>" (tanpa kata domain apa pun) DEFAULT ke History
    Service, selama tidak menyebut "tcare" dan ada identifier yang bisa
    diekstrak. Kalau user memang menyebut kata domain servis secara
    eksplisit, itu tetap match seperti biasa (SERVICE_KEYWORDS dipakai
    di Handler untuk keputusan notifikasi TCARE, bukan lagi syarat
    match() di sini).
    """
    t = text.lower()
    if TCARE_KEYWORD in t:
        return False
    has_history_word = any(k in t for k in HISTORY_KEYWORDS)
    if not has_history_word:
        return False
    return _extract_identifier(text) is not None


def parse(text: str) -> Optional[ParsedHistoryServiceQuery]:
    """
    Parse `text` jadi ParsedHistoryServiceQuery, atau None kalau tidak
    ada identifier customer yang bisa diekstrak sama sekali.
    """
    identifier = _extract_identifier(text)
    if identifier is None:
        return None

    identifier_value, identifier_type = identifier
    date_from, date_to = _extract_date_range(text)

    return ParsedHistoryServiceQuery(
        customer_identifier=identifier_value,
        identifier_type=identifier_type,
        date_from=date_from,
        date_to=date_to,
    )


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
    """
    Cek plat dengan spasi dulu (tidak ambigu sama sekali), lalu plat
    dengan strip atau tanpa pemisah (pola ketat per-token, lihat
    docstring modul untuk kenapa ini aman diprioritaskan sebelum
    NO_RANGKA_REGEX).

    Tokenizer sengaja pakai `[A-Z0-9-]+` (bukan `[A-Z0-9]+`) supaya
    strip ikut jadi satu token utuh (mis. "G-8095-CG"), bukan terpecah
    jadi 3 token terpisah oleh `\b` di sekitar strip.
    """
    spaced = PLATE_REGEX.search(text_upper)
    if spaced:
        return spaced.group(0)

    for token in re.findall(r"\b[A-Z0-9-]+\b", text_upper):
        if PLATE_NO_SPACE_REGEX.fullmatch(token) or PLATE_DASH_REGEX.fullmatch(token):
            return token

    return None


def _extract_name_fallback(text: str) -> Optional[str]:
    """
    Fallback kasar: buang stopwords/keyword domain/partikel kasual,
    sisanya dianggap nama customer — TAPI hanya kalau minimal satu token
    yang tersisa cukup panjang (`_MIN_NAME_TOKEN_LENGTH`), supaya sisa
    kata pendek acak (typo, partikel yang tidak masuk stopword list)
    tidak dianggap nama valid. Kasus yang tetap ambigu/tidak jelas
    berujung AMBIGUOUS atau NOT_FOUND di layer Service (bukan diputuskan
    di sini).
    """
    cleaned = DATE_RANGE_REGEX.sub(" ", text)
    cleaned = RELATIVE_MONTHS_REGEX.sub(" ", cleaned)

    tokens = re.findall(r"[A-Za-z]+", cleaned)
    name_tokens = [t for t in tokens if t.lower() not in _STOPWORDS]
    if not any(len(t) >= _MIN_NAME_TOKEN_LENGTH for t in name_tokens):
        return None
    name = " ".join(name_tokens).strip()
    return name or None


def _extract_date_range(text: str):
    explicit = DATE_RANGE_REGEX.search(text)
    if explicit:
        return explicit.group(1), explicit.group(2)

    relative = RELATIVE_MONTHS_REGEX.search(text)
    if relative:
        months = int(relative.group(1))
        today = date.today()
        # Pendekatan sederhana bebas dependency tambahan (dateutil):
        # mundur `months` bulan dengan aritmatika manual pada year/month.
        total_month_index = today.month - 1 - months
        year = today.year + total_month_index // 12
        month = total_month_index % 12 + 1
        day = min(today.day, 28)  # hindari overflow tanggal (mis. 31 Feb)
        date_from = date(year, month, day).isoformat()
        return date_from, today.isoformat()

    return None, None