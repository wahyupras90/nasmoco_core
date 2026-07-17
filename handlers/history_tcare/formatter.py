"""
handlers/history_tcare/formatter.py

ADR006: Formatter bertanggung jawab pada output, dipanggil dari Handler
(bukan Service). Struktur pesan mengadaptasi gaya legacy
(`tools/history_tcare.py::format_history_tcare`), tapi field yang
ditampilkan disesuaikan dengan skema `tcare_unit` aktual.
"""

from typing import Optional

import pandas as pd

PEKERJAAN_ORDER = ["1K", "10K", "20K", "30K", "40K", "50K", "60K"]
MAX_SUGGESTIONS = 10


def build_summary(unit_info: dict, schedule_df: pd.DataFrame, ro_total: Optional[int]) -> dict:
    return {
        "no_rangka": unit_info.get("no_rangka"),
        "customer": unit_info.get("customer"),
        "no_polisi": unit_info.get("no_polisi"),
        "model": unit_info.get("model"),
        "tcare_type": unit_info.get("tcare_type"),
        "batas_tcare": unit_info.get("batas_tcare"),
        "total_visit": ro_total,  # BR020
        "total_riwayat_tcare": 0 if schedule_df is None else len(schedule_df),
    }


def format_message(unit_info: dict, schedule_df: pd.DataFrame, ro_total: Optional[int]) -> str:
    total_riwayat = 0 if schedule_df is None else len(schedule_df)
    lines = [
        f"History TCARE — {unit_info.get('no_rangka', '-')}",
        f"Customer     : {unit_info.get('customer', '-')}",
        f"Model        : {unit_info.get('model', '-')}",
        f"No Polisi    : {unit_info.get('no_polisi', '-')}",
        f"Kategori     : {unit_info.get('dealer_kategori', '-')}",
        f"Tipe TCARE   : {unit_info.get('tcare_type', '-')}",
        f"SA Terakhir  : {unit_info.get('sa_terakhir', '-')}",
        f"Tgl DO       : {unit_info.get('tgl_do', '-')}",
        f"Batas TCARE  : {unit_info.get('batas_tcare', '-')}",
        f"Sisa Service : {unit_info.get('sisa_detail', '-')}",
        f"Total RO     : {ro_total if ro_total is not None else '-'}",
        "",
        f"Riwayat Kunjungan TCARE : {total_riwayat}",
    ]
    if total_riwayat:
        lines.append("Lihat tabel di bawah untuk detail per milestone (1K-60K).")
    return "\n".join(lines)


def format_not_found_message(identifier: str) -> str:
    return f"Data history TCARE tidak ditemukan untuk '{identifier}'."


def build_ambiguous_suggestions(candidates_df: pd.DataFrame) -> list:
    suggestions = []
    for _, row in candidates_df.head(MAX_SUGGESTIONS).iterrows():
        suggestions.append(
            {
                "no_rangka": row.get("no_rangka"),
                "customer": row.get("customer"),
                "no_polisi": row.get("no_polisi"),
                "model": row.get("model"),
            }
        )
    return suggestions


def format_ambiguous_message(candidates_df: pd.DataFrame) -> str:
    count = len(candidates_df)
    return (
        f"Ditemukan {count} kemungkinan unit yang cocok. "
        "Mohon perjelas dengan no_rangka (VIN) atau no_polisi (lihat suggestions)."
    )
