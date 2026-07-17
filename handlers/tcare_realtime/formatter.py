"""
handlers/tcare_realtime/formatter.py — INT013 TCARE Realtime per VIN (ADR006)

Formatter dipanggil dari Handler, bukan Service. Menerima list[VinFetchResult]
dan membentuk message + summary. Setiap VIN gagal ditampilkan apa adanya
(pesan error-nya), tidak menghentikan penampilan VIN lain yang berhasil.
"""

from typing import List

from repositories.tcare_realtime_web_repository import VinFetchResult


def build_summary(results: List[VinFetchResult]) -> dict:
    ok_vins = [r.vin for r in results if r.ok]
    failed = [{"vin": r.vin, "error": r.error} for r in results if not r.ok]
    return {
        "total_diminta": len(results),
        "berhasil": len(ok_vins),
        "gagal": len(failed),
        "vin_gagal": failed,
    }


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
