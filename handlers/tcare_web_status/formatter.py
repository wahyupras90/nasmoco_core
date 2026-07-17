"""
handlers/tcare_web_status/formatter.py — INT012 TCARE Web Status (ADR006)
"""


def build_summary(result: dict) -> dict:
    mode = result.get("mode")
    if mode == "errors":
        errors_df = result.get("errors")
        return {
            "mode": mode,
            "no_rangka_filter": result.get("no_rangka"),
            "total_error": 0 if errors_df is None else len(errors_df),
        }
    if mode == "detail":
        return {
            "mode": mode,
            "no_rangka": result.get("no_rangka"),
            "ditemukan": result.get("found", False),
            "total_kunjungan": 0 if result.get("service") is None else len(result["service"]),
        }
    return {"mode": mode}


def format_message(result: dict) -> str:
    mode = result.get("mode")

    if mode == "missing_no_rangka":
        return "Nomor rangka tidak terdeteksi. Sertakan nomor rangka untuk cek status TCARE Web."

    if mode == "errors":
        errors_df = result.get("errors")
        if errors_df is None or errors_df.empty:
            return "Tidak ada error scraping TCARE Web untuk filter ini."
        lines = [f"Ditemukan {len(errors_df)} unit gagal di-scrape terakhir kali:"]
        for _, row in errors_df.iterrows():
            lines.append(f"  {row.get('no_rangka')}: {row.get('error')}")
        return "\n".join(lines)

    # mode == "detail"
    no_rangka = result.get("no_rangka")
    if not result.get("found"):
        return f"Data TCARE Web untuk nomor rangka {no_rangka} tidak ditemukan."

    vehicle_df = result["vehicle"]
    service_df = result["service"]

    lines = [f"Status TCARE Web — {no_rangka}"]
    if not vehicle_df.empty:
        row = vehicle_df.iloc[0]
        lines.append(f"  Model: {_display(row.get('model'))}")
        lines.append(f"  Owner: {_display(row.get('owner'))}")
        lines.append(f"  Delivery date: {_display(row.get('delivery_date'))}")

    lines.append(f"  Total kunjungan tercatat: {len(service_df)}")
    if not service_df.empty:
        lines.append("  Kunjungan terakhir:")
        last = service_df.iloc[0]
        lines.append(
            f"    {_display(last.get('kunjungan'))} | {_display(last.get('service_date'))} | "
            f"{_display(last.get('dealer'))} | {_display(last.get('status'))}"
        )

    return "\n".join(lines)


def _display(value) -> str:
    """NULL/None/NaN/string kosong ditampilkan sebagai '-', bukan literal 'None'."""
    if value is None:
        return "-"
    try:
        import pandas as pd
        if pd.isna(value):
            return "-"
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else "-"
