"""
handlers/wip/formatter.py

ADR006: Formatter dipanggil dari Handler, bukan Service.
"""

from typing import Optional

import pandas as pd


def build_summary(result: dict) -> dict:
    return {
        "filter_kelompok": result.get("kelompok_filter"),
        "filter_sa": result.get("sa_filter"),
        "total_unit_wip": result["total_unit_wip"],
        "breakdown_per_kelompok": result.get("breakdown_per_kelompok") or None,
    }


def format_message(result: dict) -> str:
    total = result["total_unit_wip"]
    kelompok_filter = result.get("kelompok_filter")
    sa_filter = result.get("sa_filter")
    breakdown = result.get("breakdown_per_kelompok") or {}

    filter_desc = []
    if sa_filter:
        filter_desc.append(f"SA={sa_filter}")
    if kelompok_filter:
        filter_desc.append(f"kelompok={kelompok_filter}")
    filter_text = f" ({', '.join(filter_desc)})" if filter_desc else ""

    lines = [
        f"WIP (Work In Progress) — unit belum diinvoice{filter_text}",
        f"Total unit WIP: {total}",
    ]

    if breakdown:
        lines.append("")
        lines.append("Breakdown per kelompok (satu unit bisa masuk >1 kelompok):")
        for code, count in breakdown.items():
            if count:
                lines.append(f"  {code}: {count}")

    units_df = result.get("units")
    units_returned = units_df is not None and not units_df.empty

    if total == 0:
        lines.append("")
        lines.append("Tidak ada unit WIP untuk filter ini saat ini.")
    elif units_returned:
        lines.append("")
        lines.append("Lihat tabel di bawah untuk daftar unit.")
    # else: total > 0 tapi dataframe sengaja dikosongkan (query
    # "total"/"berapa"/"jumlah" tanpa kata list/daftar/detail/rincian) --
    # tidak perlu baris tambahan, angka di atas sudah cukup menjawab.

    return "\n".join(lines)
