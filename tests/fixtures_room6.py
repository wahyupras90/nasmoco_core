"""
tests/fixtures_room6.py

Helper untuk membuat SQLite database sementara berisi skema mini (subset
kolom) dari tabel-tabel yang dipakai Room 6, sesuai skema aktual
`nasmoco.db` yang sudah dikonfirmasi Room 0 (PRAGMA table_info + sample
data, lihat brief Room 6 dan jawaban Room 0). Pola sama seperti
`tests/fixtures_room4.py` / `tests/fixtures_room5.py`.

Catatan: `unit_tcare` di database asli adalah VIEW (ADR024) -- di fixture
ini dibuat sebagai TABLE biasa (cukup untuk keperluan test JOIN, Repository
tidak peduli VIEW vs TABLE selama bisa di-SELECT).
"""

import os
import sqlite3
import tempfile


def make_temp_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)

    conn.executescript(
        """
        CREATE TABLE attack_list (
            id INTEGER,
            source TEXT,
            no_rangka TEXT,
            customer TEXT,
            model TEXT,
            segment TEXT,
            segment_rfm TEXT,
            no_polisi TEXT,
            dealer_kategori TEXT,
            nama_sales TEXT,
            sa_terakhir TEXT,
            program_id INTEGER,
            program TEXT,
            kategori TEXT,
            pekerjaan TEXT,
            bulan_jadwal TEXT,
            batas_tcare TEXT,
            alasan TEXT,
            tgl_kunjungan_terakhir TEXT,
            hari_sejak_kunjungan INTEGER,
            interval_avg_hari REAL,
            avg_revenue_per_wo REAL,
            last_sbe_km INTEGER,
            last_sbe_date TEXT,
            sawa_status TEXT,
            sawa_expiry TEXT,
            status TEXT,
            tgl_followup TEXT,
            tgl_generate TEXT
        );

        CREATE TABLE attack_list_history (
            id INTEGER,
            bulan TEXT,
            source TEXT,
            no_rangka TEXT,
            tgl_konversi TEXT,
            bulan_konversi TEXT,
            segment_rfm TEXT,
            program TEXT
        );

        CREATE TABLE tcare_web_vehicle (
            no_rangka TEXT,
            vin TEXT,
            model TEXT,
            owner TEXT,
            delivery_date TEXT
        );

        CREATE TABLE tcare_web_service (
            no_rangka TEXT,
            kunjungan TEXT,
            pekerjaan TEXT,
            service_date TEXT,
            dealer TEXT,
            status TEXT,
            ontime_service TEXT
        );

        CREATE TABLE tcare_web_errors (
            no_rangka TEXT,
            error TEXT
        );

        CREATE TABLE tcare_schedule (
            no_rangka TEXT,
            bulan_jadwal TEXT,
            bulan_realisasi TEXT,
            expired INTEGER
        );

        -- Substitusi VIEW unit_tcare (ADR024) untuk keperluan test JOIN.
        -- Kolom sa_terakhir WAJIB ada (skema asli, dikonfirmasi Room 4
        -- lewat get_unit_info()) -- dipakai tcare_pending_count()/
        -- tcare_converted_count() untuk filter SA konsisten (ADR027 Bug#1).
        CREATE TABLE unit_tcare (
            no_rangka TEXT,
            sa_terakhir TEXT
        );
        """
    )

    # -- attack_list: 3 source berbeda, status berbeda --
    conn.executemany(
        "INSERT INTO attack_list (id, source, no_rangka, sa_terakhir, "
        "segment_rfm, program_id, program, status, batas_tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "TCARE", "MHTCARE0000001", "AGN", "Champions", 10, "PROG A", "pending", "2026-07-15"),
            (2, "CRM", "MHCRM00000001", "BUD", "At Risk", 11, "PROG B", "pending", "2026-08-01"),
            (3, "CRM", "MHCRM00000002", "AGN", "At Risk", 11, "PROG B", "converted", "2026-07-20"),
            (4, "CR7", "MHCR700000001", "AGN", None, None, None, "pending", None),
        ],
    )

    # -- attack_list_history: histori konversi bulan Juni 2026 --
    # Baris CRM (id=2) sengaja punya `program` terisi -- skema production
    # tidak pernah NULL untuk source=CRM (dikonfirmasi Wahyu via query
    # langsung, 0 rows NULL), jadi fixture ikut konsisten.
    #
    # Baris id=3,4 (bulan sama, program BEDA) ditambahkan khusus untuk
    # INT010 -- uji breakdown per program dalam satu bulan/source yang
    # sama (Panggil Pulang - At Risk vs Aktivasi New & Potential).
    conn.executemany(
        "INSERT INTO attack_list_history (id, bulan, source, no_rangka, "
        "tgl_konversi, bulan_konversi, segment_rfm, program) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "2026-06", "TCARE", "MHTCARE0000001", "2026-06-15", "2026-06", "Champions", None),
            (2, "2026-06", "CRM", "MHCRM00000001", None, None, "At Risk", "Panggil Pulang - At Risk"),
            (3, "2026-06", "CRM", "MHCRM00000003", "2026-06-20", "2026-06", "At Risk", "Panggil Pulang - At Risk"),
            (4, "2026-06", "CRM", "MHCRM00000004", None, None, "New", "Aktivasi New & Potential"),
        ],
    )

    # -- tcare_web_vehicle / service / errors --
    conn.execute(
        "INSERT INTO tcare_web_vehicle (no_rangka, vin, model, owner, delivery_date) "
        "VALUES (?, ?, ?, ?, ?)",
        ("MHKA6GK6JSJ084260", "MHKA6GK6JSJ084260", "CALYA", None, "2025-08-14"),
    )
    conn.executemany(
        "INSERT INTO tcare_web_service (no_rangka, kunjungan, pekerjaan, "
        "service_date, dealer, status, ontime_service) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("MHKA6GK6JSJ084260", "1/1 bln", "Servis Berkala", "04-Nov-25", "-", "No", "30 Sep 2025"),
            ("MHKA6GK6JSJ084260", "2/6 bln", "Servis Berkala", "12-Feb-26", "NASMOCO - TEGAL", "Approve Claim", "28 Feb 2026"),
        ],
    )
    conn.execute(
        "INSERT INTO tcare_web_errors (no_rangka, error) VALUES (?, ?)",
        ("MHERROR000000001", "Timeout saat scraping"),
    )

    # -- tcare_schedule + unit_tcare: untuk tcare_pending_count/tcare_converted_count --
    # MHTCARE0000004 (BARU): baris yang SUDAH direalisasi (bulan_realisasi
    # terisi) -- dipakai test tcare_converted_count(), sebelumnya tidak
    # ada satupun baris converted di fixture ini (gap ditemukan lewat
    # bug report "TCARE pekerjaan selalu=unit", 2026-07-22).
    conn.executemany(
        "INSERT INTO tcare_schedule (no_rangka, bulan_jadwal, bulan_realisasi, expired) "
        "VALUES (?, ?, ?, ?)",
        [
            ("MHTCARE0000001", "2026-07", None, 0),
            ("MHTCARE0000002", "2026-06", None, 0),
            ("MHTCARE0000003", "2026-01", None, 1),  # expired, tidak boleh terhitung
            ("MHTCARE0000004", "2026-07", "2026-07", 0),  # SUDAH direalisasi -> converted (format YYYY-MM, sama seperti data asli)
        ],
    )
    conn.executemany(
        "INSERT INTO unit_tcare (no_rangka, sa_terakhir) VALUES (?, ?)",
        [
            ("MHTCARE0000001", "AGN"),
            ("MHTCARE0000002", "BUD"),
            ("MHTCARE0000003", "AGN"),
            ("MHTCARE0000004", "AGN"),
        ],
    )

    conn.commit()
    conn.close()
    return path