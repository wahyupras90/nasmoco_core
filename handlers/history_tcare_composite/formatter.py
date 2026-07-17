"""
handlers/history_tcare_composite/formatter.py — ADR027

Format khusus untuk hasil yang datang dari fallback web TAM (INT013).
Hasil dari database lokal TIDAK lewat sini sama sekali -- itu pakai
formatter Room 4 (`handlers/history_tcare/formatter.py`) apa adanya,
lewat `HistoryTCAREHandler.execute()` yang di-reuse utuh.
"""

from repositories.tcare_realtime_web_repository import VinFetchResult

SOURCE_PREFIX = "[Realtime dari web TAM] "

# Marker untuk membedakan "VIN memang tidak terdaftar di web TAM" (NOT_FOUND)
# vs kegagalan teknis (login/timeout/parsing, ERROR). Dikopel ke wording
# persis yang dipakai TCARERealtimeWebRepository._parse_vin_page() --
# TIDAK mengubah file Room 6, jadi klasifikasi ini dilakukan di sisi
# Composite Handler lewat pencocokan teks. Kalau Room 6 nanti menambah
# field terpisah untuk kategori error, ini bisa disederhanakan -- catat
# sebagai potensi improvement non-blocking, lapor ke Room 0 kalau wording
# Room 6 berubah dan pencocokan ini jadi tidak akurat.
NOT_FOUND_MARKER = "tidak ditemukan"


def is_not_found_error(error_message: str) -> bool:
    return NOT_FOUND_MARKER in (error_message or "").lower()


def format_web_message(web_result: VinFetchResult) -> str:
    from handlers.tcare_realtime import formatter as realtime_formatter

    base_message = realtime_formatter.format_message([web_result])
    return f"{SOURCE_PREFIX}{base_message}"


def build_web_summary(no_rangka: str, web_result: VinFetchResult) -> dict:
    total_kunjungan = 0 if web_result.services is None else len(web_result.services)
    return {
        "no_rangka": no_rangka,
        "source": "web_tam_realtime",
        "total_kunjungan": total_kunjungan,
    }
