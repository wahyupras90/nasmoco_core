"""
handlers/kpi_summary/formatter.py

ADR006: Formatter bertanggung jawab pada output. Dipanggil dari Handler
saja, bukan Service.
"""

from typing import Optional

from handlers._shared.period_parser import ParsedPeriod, display_period

_METRIC_LABELS = {
    "unit_entry": "Unit Entry",
    "cpus": "CPUS",
    "revenue": "Revenue",
    "jasa": "Jasa",
    "tgp": "TGP",
    "adt": "ADT",
    "sublet": "Sublet",
    "upselling": "Upselling",
    "total_liter": "Total Liter",
}

_TARGET_METRIC_MAP = {
    "cpus": "target_cpus",
    "revenue": "target_revenue",
    "total_liter": "target_liter",
}


def build_summary(result: dict) -> dict:
    period: ParsedPeriod = result["period"]
    sa = result["sa"]
    totals = result["totals"]
    target = result.get("target")

    summary = {
        "sa": sa if sa is not None else "OUTLET (semua SA)",
        "periode": display_period(period.tahun, period.bulan),
        "periode_diasumsikan": not period.is_explicit,
        "hari_terisi_data": result["hari_terisi"],
        "totals": totals,
    }

    if target:
        capaian = {}
        for metric, target_col in _TARGET_METRIC_MAP.items():
            target_val = target.get(target_col)
            actual_val = totals.get(metric)
            if target_val:
                capaian[metric] = {
                    "target": target_val,
                    "actual": actual_val,
                    "pct": round((actual_val / target_val) * 100, 1) if target_val else None,
                }
        summary["vs_target"] = capaian
    else:
        summary["vs_target"] = None
        summary["target_tersedia"] = result.get("target_year_covered", False)

    return summary


def format_message(result: dict) -> str:
    period: ParsedPeriod = result["period"]
    sa = result["sa"]
    totals = result["totals"]
    target = result.get("target")

    label = sa if sa is not None else "Outlet (semua SA)"
    lines = [
        f"KPI Summary — {label}",
        f"Periode : {display_period(period.tahun, period.bulan)}"
        + ("" if period.is_explicit else " (diasumsikan bulan berjalan)"),
        f"Hari terisi data: {result['hari_terisi']}",
        "",
    ]
    for col, label_metric in _METRIC_LABELS.items():
        val = totals.get(col, 0.0)
        lines.append(f"{label_metric:<12}: {_fmt_number(val)}")

    if target:
        lines.append("")
        lines.append("vs Target:")
        for metric, target_col in _TARGET_METRIC_MAP.items():
            target_val = target.get(target_col)
            actual_val = totals.get(metric)
            if target_val:
                pct = (actual_val / target_val) * 100 if target_val else 0
                lines.append(
                    f"  {_METRIC_LABELS[metric]:<12}: {_fmt_number(actual_val)} / "
                    f"{_fmt_number(target_val)} ({pct:.1f}%)"
                )
    else:
        if result.get("target_year_covered", False):
            lines.append("")
            lines.append(
                f"Target untuk {label} pada periode ini tidak tersedia di data target_bulanan."
            )
        else:
            lines.append("")
            lines.append(
                f"Target tidak tersedia untuk tahun {period.tahun} "
                "(data target_bulanan hanya mencakup tahun 2026)."
            )

    return "\n".join(lines)


def format_not_found_message(sa_candidate: Optional[str]) -> str:
    return f"SA '{sa_candidate}' tidak ditemukan di data KPI (daily_kpi)."


def _fmt_number(value) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}".replace(",", ".")
