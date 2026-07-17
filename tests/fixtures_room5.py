"""
tests/fixtures_room5.py

Helper untuk membuat SQLite database sementara berisi skema mini (subset
kolom) dari tabel-tabel yang dipakai Room 5, sesuai skema aktual
`nasmoco.db` yang sudah diverifikasi langsung (PRAGMA table_info +
sample data). Pola sama seperti `tests/fixtures_room4.py`.
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
        CREATE TABLE daily_kpi (
            tanggal TEXT,
            sa TEXT,
            is_counter INTEGER,
            unit_entry INTEGER,
            cpus INTEGER,
            revenue REAL,
            jasa REAL,
            tgp REAL,
            adt REAL,
            sublet REAL,
            upselling REAL,
            total_liter REAL
        );

        CREATE TABLE target_bulanan (
            tahun INTEGER,
            bulan INTEGER,
            bulan_nama TEXT,
            sa TEXT,
            target_cpus REAL,
            target_revenue REAL,
            target_liter REAL,
            tipe TEXT
        );

        CREATE TABLE unitmasuk (
            no_polisi TEXT,
            no_wo INTEGER,
            no_invoice TEXT,
            customer TEXT,
            jam TEXT,
            serah TEXT,
            no_rangka TEXT,
            model TEXT,
            tunggu TEXT,
            sa TEXT,
            mech TEXT,
            klp TEXT,
            pekerjaan TEXT,
            rate REAL,
            arate REAL,
            stat TEXT,
            ket TEXT,
            tanggal TEXT,
            tgl_invoice TEXT,
            sublet_type TEXT,
            kategori TEXT,
            kelompok TEXT,
            tcare TEXT,
            is_own INTEGER,
            tgl_bpk TEXT,
            batas_tcare TEXT,
            in_tcare INTEGER,
            nama_sales TEXT
        );
        """
    )

    # -- daily_kpi: dua SA (AGN, IND) + Counter, bulan Januari 2026 --
    conn.executemany(
        "INSERT INTO daily_kpi (tanggal, sa, is_counter, unit_entry, cpus, "
        "revenue, jasa, tgp, adt, sublet, upselling, total_liter) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("2026-01-01", "AGN", 0, 2, 2, 3_000_000.0, 700_000.0, 1_600_000.0, 0.0, 700_000.0, 700_000.0, 4.0),
            ("2026-01-02", "AGN", 0, 3, 3, 4_000_000.0, 900_000.0, 2_000_000.0, 0.0, 1_100_000.0, 1_100_000.0, 6.0),
            ("2026-01-01", "IND", 0, 1, 1, 1_500_000.0, 400_000.0, 800_000.0, 0.0, 300_000.0, 300_000.0, 2.0),
            ("2026-01-02", "IND", 0, 4, 4, 6_000_000.0, 1_500_000.0, 2_500_000.0, 100_000.0, 1_900_000.0, 2_000_000.0, 10.0),
            ("2026-01-01", "Counter", 1, 0, 0, 200_000.0, 0.0, 200_000.0, 0.0, 0.0, 0.0, 0.0),
            # Bulan Februari untuk memastikan filter bulan bekerja
            ("2026-02-01", "AGN", 0, 5, 5, 5_000_000.0, 1_000_000.0, 2_000_000.0, 0.0, 2_000_000.0, 2_000_000.0, 8.0),
        ],
    )

    # -- target_bulanan: hanya tahun 2026, termasuk baris TOTAL --
    conn.executemany(
        "INSERT INTO target_bulanan (tahun, bulan, bulan_nama, sa, "
        "target_cpus, target_revenue, target_liter, tipe) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (2026, 1, "JAN", "AGN", 4.0, 6_000_000.0, 8.0, "GR"),
            (2026, 1, "JAN", "IND", 4.0, 6_000_000.0, 10.0, "GR"),
            (2026, 1, "JAN", "TOTAL", 8.0, 12_000_000.0, 18.0, "ALL"),
        ],
    )

    # -- unitmasuk: kasus WIP (belum invoice) + kasus sudah invoice --
    conn.executemany(
        "INSERT INTO unitmasuk (no_polisi, no_wo, no_invoice, customer, "
        "jam, serah, no_rangka, model, tunggu, sa, mech, klp, pekerjaan, "
        "rate, arate, stat, ket, tanggal, tgl_invoice, sublet_type, "
        "kategori, kelompok, tcare, is_own, tgl_bpk, batas_tcare, "
        "in_tcare, nama_sales) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # WO 5001: WIP, 2 item pekerjaan (SBE + GRP), belum invoice
            ("B 1111 AA", 5001, None, "CUST WIP 1", "08:00", None,
             "MHWIP0000000001", "Avanza", "Tidak", "AGN", "MECH1", "SBE",
             "Servis Berkala", 2.0, 2.0, "", "", "2026-07-13", None,
             None, "CPUS", "SBE", "REGULER", 0, None, None, 0, None),
            ("B 1111 AA", 5001, None, "CUST WIP 1", "08:00", None,
             "MHWIP0000000001", "Avanza", "Tidak", "AGN", "MECH1", "GRP",
             "Ganti Filter", 0.5, 0.5, "", "", "2026-07-13", None,
             None, "CPUS", "GRP", "REGULER", 0, None, None, 0, None),
            # WO 5002: WIP juga (no_invoice ada tapi tgl_invoice kosong)
            ("B 2222 BB", 5002, "INV-5002", "CUST WIP 2", "09:00", None,
             "MHWIP0000000002", "Innova", "Ya", "IND", "MECH2", "SBI",
             "Ganti Battery", 0.3, 0.3, "", "", "2026-07-13", "",
             None, "CPUS", "SBI", "REGULER", 0, None, None, 0, None),
            # WO 6001: SUDAH invoice, bukan WIP
            ("B 3333 CC", 6001, "INV-6001", "CUST DONE", "07:00", "12:00",
             "MHDONE000000001", "Fortuner", "Tidak", "AGN", "MECH1", "SBE",
             "Servis Berkala", 2.5, 2.4, "", "K", "2026-07-01", "2026-07-01",
             None, "CPUS", "SBE", "REGULER", 0, None, None, 0, None),
        ],
    )

    conn.commit()
    conn.close()
    return path
