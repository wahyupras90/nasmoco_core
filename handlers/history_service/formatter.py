"""
handlers/history_service/formatter.py

ADR006: Formatter bertanggung jawab pada output. Handler memanggil
fungsi-fungsi di sini untuk mengubah dict/DataFrame mentah dari Service
menjadi `message` (teks) dan `summary` (dict terstruktur, ADR019).

Formatter TIDAK dipanggil dari Service (brief Room 4) — hanya dari
Handler.
"""

from typing import Optional

import pandas as pd

MAX_SUGGESTIONS = 10


def _count_unique_visits(history_df: pd.DataFrame) -> int:
    """
    Jumlah KUNJUNGAN/WO unik, BUKAN jumlah baris di `history_df`.

    Ditemukan lewat smoke test nyata: `unitmasuk` menyimpan satu baris
    PER ITEM PEKERJAAN, bukan satu baris per kunjungan — jadi 1 WO
    dengan beberapa pekerjaan bisa muncul sebagai beberapa baris dengan
    `no_wo` yang sama persis. Kalau dihitung `len(history_df)` langsung,
    "jumlah kunjungan" jadi salah (menghitung jumlah item pekerjaan,
    bukan jumlah kunjungan). Keputusan ini disepakati eksplisit dengan
    user setelah temuan tersebut.
    """
    if history_df is None or history_df.empty or "no_wo" not in history_df.columns:
        return 0
    return int(history_df["no_wo"].dropna().nunique())


def build_summary(
    profile: dict,
    history_df: pd.DataFrame,
    ro_total: Optional[int],
    has_tcare_history: bool = False,
) -> dict:
    """Ringkasan data terstruktur (ADR019) — bukan teks jadi."""
    return {
        "customer": profile.get("customer"),
        "no_rangka": profile.get("no_rangka"),
        "no_polisi": profile.get("no_polisi"),
        "model": profile.get("model"),
        "segment": profile.get("segment"),
        "total_visit": ro_total,  # BR020 — dari customer_profile, bukan hitung ulang
        "visit_in_range": _count_unique_visits(history_df),
        "has_tcare_history": has_tcare_history,
    }


def format_message(
    profile: dict,
    history_df: pd.DataFrame,
    ro_total: Optional[int],
    has_tcare_history: bool = False,
) -> str:
    visit_in_range = _count_unique_visits(history_df)
    lines = [
        f"Riwayat Service — {profile.get('customer', '-')}",
        f"No Rangka    : {profile.get('no_rangka', '-')}",
        f"No Polisi    : {profile.get('no_polisi', '-')}",
        f"Model        : {profile.get('model', '-')}",
        f"Segment      : {profile.get('segment', '-')}",
        f"Total RO     : {ro_total if ro_total is not None else '-'}",
        "",
        f"Jumlah kunjungan pada rentang yang diminta: {visit_in_range}",
    ]
    if visit_in_range:
        lines.append("Lihat tabel di bawah untuk detail per kunjungan.")
    if has_tcare_history:
        lines.append("")
        lines.append(
            '💡 Unit ini juga punya data TCARE. Ketik "history tcare '
            f"{profile.get('no_rangka', '')}\" untuk detail lengkap."
        )
    return "\n".join(lines)


def format_not_found_message(identifier: str) -> str:
    return f"Data history service tidak ditemukan untuk '{identifier}'."


def build_ambiguous_suggestions(candidates_df: pd.DataFrame) -> list:
    """
    Daftar saran untuk HandlerResult.suggestions saat identifier ambigu
    (>1 baris customer_profile cocok).
    """
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
        f"Ditemukan {count} kemungkinan customer yang cocok. "
        "Mohon perjelas dengan no_rangka atau no_polisi (lihat suggestions)."
    )