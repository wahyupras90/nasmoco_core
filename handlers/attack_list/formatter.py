"""
handlers/attack_list/formatter.py — INT008 Attack List (ADR006)
"""


def build_summary(result: dict) -> dict:
    if result["mode"] == "history":
        return {
            "mode": "history",
            "bulan": result["bulan"],
            "bulan_label": result["bulan_label"],
            "periode_diasumsikan": not result["period_is_explicit"],
            "filter_source": result.get("source_filter"),
            "filter_program": result.get("program_filter"),
            "filter_sa": result.get("sa_filter"),
            "total_tercatat": result["total_tercatat"],
            "total_konversi": result["total_konversi"],
            "program_breakdown": result.get("program_breakdown", []),
        }

    if result["mode"] == "all":
        return {
            "mode": "all",
            "filter_sa": result.get("sa_filter"),
            "filter_segment_rfm": result.get("segment_rfm_filter"),
            "filter_program_id": result.get("program_id_filter"),
            "tcare_unit_pending": result["tcare_unit_pending"],
            "tcare_pekerjaan_pending": result["tcare_pekerjaan_pending"],
            "tcare_unit_converted": result["tcare_unit_converted"],
            "tcare_pekerjaan_converted": result["tcare_pekerjaan_converted"],
            "crm_total": result["crm_total"],
            "crm_converted": result["crm_converted"],
            "crm_pending": result["crm_pending"],
            "crm_program_breakdown": result.get("crm_program_breakdown", []),
            "cr7_total": result["cr7_total"],
            "cr7_converted": result["cr7_converted"],
            "cr7_pending": result["cr7_pending"],
        }

    summary_per_source_df = result.get("summary_per_source")
    per_source = (
        dict(zip(summary_per_source_df["source"], summary_per_source_df["jumlah_unit"]))
        if summary_per_source_df is not None and not summary_per_source_df.empty
        else {}
    )

    return {
        "mode": "list",
        "filter_source": result.get("source_filter"),
        "filter_status": result.get("status_filter"),
        "filter_sa": result.get("sa_filter"),
        "filter_segment_rfm": result.get("segment_rfm_filter"),
        "filter_program_id": result.get("program_id_filter"),
        "expired_mode": result.get("expired_mode", False),
        "period_yyyymm": result.get("period_yyyymm"),
        "period_label": result.get("period_label"),
        "period_is_explicit": result.get("period_is_explicit"),
        "total_unit": result["total_unit"],
        "total_gabungan": result.get("total_gabungan", 0),
        "total_converted": result.get("total_converted", 0),
        "total_pending": result.get("total_pending", 0),
        "jumlah_per_source": per_source,
        "wants_conversion_summary": result.get("wants_conversion_summary", False),
    }


def format_message(result: dict) -> str:
    if result["mode"] == "history":
        label = result["bulan_label"]
        assumed = "" if result["period_is_explicit"] else " (diasumsikan)"
        lines = [
            f"Statistik konversi Attack List — {label}{assumed}",
            f"Total tercatat: {result['total_tercatat']}",
            f"Sudah konversi: {result['total_konversi']}",
        ]
        if result.get("source_filter"):
            lines.append(f"Filter source: {result['source_filter']}")
        if result.get("program_filter"):
            lines.append(f"Filter program: {result['program_filter']}")
        if result.get("sa_filter"):
            lines.append(f"Filter SA (konversi): {result['sa_filter']}")
        # INT010: breakdown per program CRM (dinamis, DISTINCT dari data)
        program_breakdown = result.get("program_breakdown") or []
        if program_breakdown:
            lines.append("Breakdown per program CRM:")
            for row in program_breakdown:
                lines.append(
                    f"  - {row['program']}: {row['konversi']}/{row['total']} konversi"
                )
        return "\n".join(lines)

    if result["mode"] == "all":
        return _format_all(result)

    total = result["total_unit"]
    filters = []
    for label, key in (
        ("source", "source_filter"), ("status", "status_filter"),
        ("SA", "sa_filter"), ("segment_rfm", "segment_rfm_filter"),
        ("program_id", "program_id_filter"),
    ):
        if result.get(key):
            filters.append(f"{label}={result[key]}")
    filter_text = f" ({', '.join(filters)})" if filters else ""

    if result.get("expired_mode"):
        assumed = "" if result.get("period_is_explicit") else " (diasumsikan)"
        mode_label = f"EXPIRED — {result['period_label']}{assumed}"
    else:
        mode_label = "Attack List"

    lines = [f"{mode_label}{filter_text}"]

    # KEPUTUSAN ROOM 0 (REVISI KEDUA, 2026-07-24): breakdown converted/
    # pending SEKARANG juga ditampilkan untuk mode expired -- populasi
    # expired sekarang bisa berisi campuran keduanya (definisi baru:
    # berbasis batas_tcare semata, bukan exclude status), jadi breakdown
    # ini penting supaya user langsung lihat komposisinya tanpa menerka
    # (sebelumnya sengaja disembunyikan untuk expired karena breakdown
    # itu percuma -- selalu 0 converted dengan definisi lama).
    if "total_converted" in result:
        gabungan = result["total_gabungan"]
        conv = result["total_converted"]
        pend = result["total_pending"]
        lines.append(f"Total unit: {gabungan:,} ({conv:,} converted, {pend:,} pending)")
    else:
        lines.append(f"Total unit: {total:,}")

    # KEPUTUSAN ROOM 0 (REVISI KEDUA, 2026-07-24): kata trigger konversi/
    # history disebut BERSAMA "expired" -> tonjolkan angka konversi
    # secara eksplisit (bukan lagi pesan penolakan seperti Opsi A yang
    # DIBATALKAN). Populasi tetap sama seperti mode list expired biasa
    # (baris "Total unit" di atas), baris ini cuma menegaskan makna
    # pertanyaan yang ditanyakan user.
    if result.get("wants_conversion_summary") and "total_converted" in result:
        lines.append(
            f"Sudah konversi: {result['total_converted']:,} dari "
            f"{result['total_gabungan']:,} unit yang batas waktunya jatuh "
            "di periode ini."
        )

    if total == 0:
        if result.get("total_gabungan", 0) > 0:
            lines.append(f"Tidak ada daftar antrean untuk status '{result.get('status_filter')}'.")
        else:
            lines.append("Tidak ada unit attack list untuk filter ini.")
    elif result["units"] is not None and not result["units"].empty:
        lines.append("Lihat tabel di bawah untuk daftar unit.")
    # else: total > 0 tapi DataFrame sengaja dikosongkan (query
    # total/berapa/jumlah tanpa kata list/daftar/detail/rincian).

    summary_per_source_df = result.get("summary_per_source")
    if summary_per_source_df is not None and not summary_per_source_df.empty:
        lines.append("")
        lines.append("Breakdown per source:")
        for _, row in summary_per_source_df.iterrows():
            lines.append(f"  {row['source']}: {row['jumlah_unit']}")

    return "\n".join(lines)


def _format_all(result: dict) -> str:
    """View 'Attack List Semua' -- format persis disepakati Wahyu
    (2026-07-16): resolved dikecualikan total, total per kategori/segmen
    = pending+converted, breakdown (x converted, y pending) di tiap baris.
    Source of truth tunggal: tabel attack_list (termasuk untuk TCARE)."""
    sa_label = f" SA {result['sa_filter']}" if result.get("sa_filter") else ""

    lines = [f"Attack List Semua{sa_label}"]

    lines.append(
        f"  TCARE Pending  : {result['tcare_unit_pending']:,} unit "
        f"({result['tcare_pekerjaan_pending']:,} pekerjaan)  "
        f"({result['tcare_unit_converted']:,} unit converted "
        f"({result['tcare_pekerjaan_converted']:,} pekerjaan))"
    )

    lines.append(
        f"  CRM Total      : {result['crm_total']:,} unit "
        f"({result['crm_converted']:,} converted, {result['crm_pending']:,} pending)"
    )
    for seg in result["crm_segment_breakdown"]:
        lines.append(
            f"    {seg['segment']:<18} : {seg['total']:,} "
            f"({seg['converted']:,} converted, {seg['pending']:,} pending)"
        )

    # INT010: breakdown per program CRM (P1-P4), dinamis dari data
    program_breakdown = result.get("crm_program_breakdown") or []
    if program_breakdown:
        lines.append("  CRM per Program:")
        for prog in program_breakdown:
            lines.append(
                f"    {prog['program']:<35}: {prog['total']:,} "
                f"({prog['converted']:,} converted, {prog['pending']:,} pending)"
            )

    lines.append(
        f"  CR7 Aktif      : {result['cr7_total']:,} unit "
        f"({result['cr7_converted']:,} converted, {result['cr7_pending']:,} pending)"
    )

    for src in result.get("other_source_breakdown", []):
        lines.append(
            f"  {src['source']:<14}: "
            f"{src['total']:,} unit "
            f"({src['converted']:,} converted, "
            f"{src['pending']:,} pending)"
        )

    return "\n".join(lines)