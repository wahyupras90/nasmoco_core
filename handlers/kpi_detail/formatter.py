"""
handlers/kpi_detail/formatter.py

ADR006: Formatter dipanggil dari Handler, bukan Service.
"""

from typing import Optional

import pandas as pd

from handlers._shared.period_parser import ParsedPeriod, display_period


def build_summary(result: dict) -> dict:
    period: ParsedPeriod = result["period"]
    sa = result["sa"]
    daily_df: pd.DataFrame = result["daily"]

    return {
        "sa": sa if sa is not None else "OUTLET (semua SA)",
        "periode": display_period(period.tahun, period.bulan),
        "periode_diasumsikan": not period.is_explicit,
        "jumlah_baris": int(len(daily_df)),
        "hari_terisi_data": 0 if daily_df.empty else int(daily_df["tanggal"].nunique()),
    }


def format_message(result: dict) -> str:
    period: ParsedPeriod = result["period"]
    sa = result["sa"]
    daily_df: pd.DataFrame = result["daily"]

    label = sa if sa is not None else "Outlet (semua SA)"
    lines = [
        f"KPI Detail (harian) — {label}",
        f"Periode : {display_period(period.tahun, period.bulan)}"
        + ("" if period.is_explicit else " (diasumsikan bulan berjalan)"),
        f"Jumlah baris: {len(daily_df)}",
    ]
    if daily_df.empty:
        lines.append("")
        lines.append("Tidak ada data KPI harian untuk periode ini.")
    else:
        lines.append("Lihat tabel di bawah untuk rincian per hari.")
    return "\n".join(lines)


def format_not_found_message(sa_candidate: Optional[str]) -> str:
    return f"SA '{sa_candidate}' tidak ditemukan di data KPI (daily_kpi)."
