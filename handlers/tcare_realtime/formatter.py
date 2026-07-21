"""
handlers/tcare_realtime/formatter.py — INT013 TCARE Realtime per VIN (ADR006)

Formatter dipanggil dari Handler, bukan Service. Menerima list[VinFetchResult]
dan membentuk message + summary. Setiap VIN gagal ditampilkan apa adanya
(pesan error-nya), tidak menghentikan penampilan VIN lain yang berhasil.
"""

from typing import List

import pandas as pd

from repositories.tcare_realtime_web_repository import VinFetchResult

MAX_AMBIGUOUS_SUGGESTIONS = 10


def build_summary(results: List[VinFetchResult]) -> dict:
    ok_vins = [r.vin for r in results if r.ok]
    failed = [{"vin": r.vin, "error": r.error} for r in results if not r.ok]
    return {
        "total_diminta": len(results),
        "berhasil": len(ok_vins),
        "gagal": len(failed),
        "vin_gagal": failed,
    }


def build_ambiguous_suggestions(candidates_df: pd.DataFrame) -> list:
    """Daftar kandidat kendaraan untuk pencarian by-nama yang AMBIGUOUS
    (>1 hasil) -- gaya konsisten dengan `handlers/history_tcare/formatter.py`
    (Room 4), ditulis sendiri di sini (bukan import silang file Room 4)
    supaya Room 6 tetap independen dari perubahan internal Room 4."""
    suggestions = []
    for _, row in candidates_df.head(MAX_AMBIGUOUS_SUGGESTIONS).iterrows():
        suggestions.append(
            {
                "no_rangka": row.get("no_rangka"),
                "customer": row.get("customer"),
                "no_polisi": row.get("no_polisi"),
                "model": row.get("model"),
            }
        )
    return suggestions


def format_ambiguous_message(customer_name: str, candidates_df: pd.DataFrame) -> str:
    count = len(candidates_df)
    lines = [
        f"Ditemukan {count} kendaraan untuk nama '{customer_name}'. "
        "Mohon perjelas dengan nomor rangka (VIN) atau no_polisi:",
        "",
    ]
    for _, row in candidates_df.head(MAX_AMBIGUOUS_SUGGESTIONS).iterrows():
        lines.append(
            f"  {row.get('no_rangka')} | {row.get('no_polisi') or '-'} | "
            f"{row.get('model') or '-'} | {row.get('customer')}"
        )
    return "\n".join(lines)


def format_name_not_found_message(customer_name: str) -> str:
    return f"Tidak ditemukan kendaraan untuk nama '{customer_name}'."


def format_message(results: List[VinFetchResult]) -> str:
    if not results:
        return "Tidak ada nomor rangka/VIN yang terdeteksi pada permintaan ini."

    lines: List[str] = []

    for r in results:
        lines.append("=" * 60)
        lines.append(f"VIN: {r.vin}")
        lines.append("=" * 60)

        if not r.ok:
            lines.append(f"  Gagal: {r.error}")
            lines.append("")
            continue

        if r.vehicle is not None and not r.vehicle.empty:
            lines.append("-- Data Kendaraan --")
            for _, row in r.vehicle.iterrows():
                lines.append(f"  {row['key']}: {row['value']}")

        if r.customer is not None and not r.customer.empty:
            lines.append("-- Customer --")
            for _, row in r.customer.iterrows():
                lines.append(f"  {row['key']}: {row['value']}")

        if r.services is not None and not r.services.empty:
            lines.append("-- Histori TCARE --")
            for _, row in r.services.iterrows():
                lines.append(
                    f"  {row['kunjungan']} | {row['tanggal']} | {row['dealer']} | "
                    f"{row['tepat']} | {row['status']} | {row['ontime_service']}"
                )

        lines.append("")

    return "\n".join(lines)