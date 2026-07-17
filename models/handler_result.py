"""
models/handler_result.py

Struktur hasil standar yang dikembalikan oleh setiap Handler.

Semua handler (Room 4+) WAJIB mengembalikan instance HandlerResult ini
dari method `execute()`, dengan `code` mengikuti Error Code Standard
di bawah.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Error Code Standard
# ---------------------------------------------------------------------------
# Setiap handler/domain punya prefix sendiri, misal "INT002" untuk
# handler intent tertentu. Kombinasikan dengan suffix di bawah, contoh:
#   INT002_OK, INT002_NOT_FOUND, INT002_AMBIGUOUS, INT002_ERROR
#
# Kode generik (tidak terikat prefix intent) dipakai untuk error
# infrastruktur/layer bawah:
#   E001 - Koneksi DB gagal
#   E002 - Query error
#   E003 - Parameter tidak valid

SUFFIX_OK = "OK"
SUFFIX_NOT_FOUND = "NOT_FOUND"
SUFFIX_AMBIGUOUS = "AMBIGUOUS"
SUFFIX_ERROR = "ERROR"

E001_CONNECTION_FAILED = "E001"
E002_QUERY_ERROR = "E002"
E003_INVALID_PARAMETER = "E003"


def make_code(intent_prefix: str, suffix: str) -> str:
    """
    Helper untuk membuat kode error konsisten, contoh:
        make_code("INT002", SUFFIX_OK) -> "INT002_OK"
    """
    return f"{intent_prefix}_{suffix}"


@dataclass
class HandlerResult:
    """
    Hasil standar dari sebuah Handler.

    Attributes:
        success: True jika operasi berhasil secara keseluruhan.
        code: kode status, contoh "INT002_OK", "INT002_NOT_FOUND", "E002".
        message: pesan human-readable, aman ditampilkan ke user/log.
        dataframe: hasil utama berupa pandas.DataFrame (opsional).
        summary: ringkasan hasil berupa data terstruktur (dict), bukan
                 teks jadi. Formatter (bukan Handler/Service) yang
                 bertanggung jawab mengubah dict ini menjadi teks
                 sesuai channel (ADR006, ADR019). Contoh:
                 {"customer": "Budi", "model": "Avanza",
                  "total_visit": 5}
        suggestions: daftar saran/opsi jika query ambigu (opsional).
        export: dict berisi data siap-export, misal
                {"excel": df, "csv": df} (opsional).
        metadata: dict bebas untuk info tambahan (opsional).
        execution_ms: waktu eksekusi dalam milidetik.
    """

    success: bool
    code: str
    message: str
    dataframe: Optional[pd.DataFrame] = None
    summary: Optional[dict] = None
    suggestions: Optional[list] = None
    export: Optional[dict] = None
    metadata: Optional[dict] = None
    execution_ms: float = 0.0

    def __post_init__(self):
        if self.summary is None:
            self.summary = {}
        if self.suggestions is None:
            self.suggestions = []
        if self.export is None:
            self.export = {}
        if self.metadata is None:
            self.metadata = {}
