"""
handlers/ranking/formatter.py

ADR006: Formatter dipanggil dari Handler, bukan Service.
"""

import pandas as pd

from handlers._shared.period_parser import ParsedPeriod, display_period

_METRIC_LABELS = {
    "revenue": "Revenue",
    "cpus": "CPUS",
    "unit_entry": "Unit Entry",
    "total_liter": "Total Liter",
    "jasa": "Jasa",
    "tgp": "TGP",
}


def build_summary(result: dict) -> dict:
    period: ParsedPeriod = result["period"]
    ranking_df: pd.DataFrame = result["ranking"]
    outlet_total = result.get("outlet_total")

    return {
        "metric": _METRIC_LABELS.get(result["metric"], result["metric"]),
        "periode": display_period(period.tahun, period.bulan),
        "periode_diasumsikan": not period.is_explicit,
        "jumlah_sa": int(len(ranking_df)),
        "target_tersedia": result.get("target_year_covered", False),
        "outlet_total_tersedia": outlet_total is not None,
    }


def format_message(result: dict) -> str:
    period: ParsedPeriod = result["period"]
    ranking_df: pd.DataFrame = result["ranking"]
    metric = result["metric"]
    metric_label = _METRIC_LABELS.get(metric, metric)
    outlet_total = result.get("outlet_total")

    lines = [
        f"Ranking SA berdasarkan {metric_label}",
        f"Periode : {display_period(period.tahun, period.bulan)}"
        + ("" if period.is_explicit else " (diasumsikan bulan berjalan)"),
        "",
    ]

    if ranking_df.empty:
        lines.append("Tidak ada data untuk periode ini.")
        return "\n".join(lines)

    for _, row in ranking_df.iterrows():
        pct_text = ""
        if "pct_capaian" in ranking_df.columns and pd.notna(row.get("pct_capaian")):
            pct_text = f" ({row['pct_capaian']:.1f}% dari target)"
        lines.append(
            f"{int(row['rank'])}. {row['sa']} — {_fmt_number(row[metric])}{pct_text}"
        )

    if not result.get("target_year_covered", False):
        lines.append("")
        lines.append(
            f"Catatan: target tidak tersedia untuk tahun {period.tahun} "
            "(data target_bulanan hanya mencakup tahun 2026), ranking "
            "murni berdasarkan angka aktual."
        )

    actual_total = float(ranking_df[metric].sum()) if metric in ranking_df.columns else None
    lines.append("")
    lines.append(
        f"Total seluruh SA (tidak termasuk transaksi Counter, tidak diberi "
        f"nomor rank): {_fmt_number(actual_total)}"
    )

    target_col_map = {"revenue": "target_revenue", "cpus": "target_cpus", "total_liter": "target_liter"}
    target_col = target_col_map.get(metric)
    if outlet_total is not None and target_col:
        target_val = outlet_total.get(target_col)
        if target_val and actual_total is not None:
            pct = (actual_total / target_val) * 100
            lines.append(f"  vs Target Outlet: {_fmt_number(target_val)} ({pct:.1f}%)")

    return "\n".join(lines)


def _fmt_number(value) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}".replace(",", ".")
