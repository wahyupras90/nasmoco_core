"""
tests/fixtures_room4.py

Helper untuk membuat SQLite database sementara berisi skema mini
(subset kolom) dari tabel-tabel yang dipakai Room 4, sesuai skema
aktual `nasmoco.db` yang sudah diverifikasi langsung (`PRAGMA
table_info` + definisi VIEW). Bukan `nasmoco.db` asli — supaya test
bisa jalan di mesin manapun (pola sama seperti
`tests/test_base_repository.py` Room 1).

PENTING soal `unit_tcare`: ini VIEW, bukan tabel, hasil gabungan
`rs` (identitas unit: model, no_polisi, customer, dealer_kategori,
batas_tcare, tgl_do) LEFT JOIN `tcare_unit` (operasional TCARE:
tcare_type, sisa_service, sisa_detail, sa_terakhir) — dikonfirmasi
lewat `sqlite_master.sql` terhadap database produksi. Fixture ini
meniru struktur itu persis, BUKAN tabel `tcare_unit` mentah yang tidak
punya kolom identitas sama sekali.

Data uji sengaja menyertakan kasus ADR024: no_rangka
"01S208014054" ADA di `tcare_schedule_full_history` (riwayat lama,
2008-2011, semua expired) tapi SENGAJA TIDAK diberi baris di `rs`
maupun `tcare_unit` (sehingga VIEW `unit_tcare` kosong untuknya), untuk
membuktikan Service/Repository Room 4 tidak mewarisi bug legacy
"unit_tcare kosong -> dianggap tidak ditemukan". Juga TIDAK ADA di
`tcare_schedule` (memang tidak pernah dipakai Room 4, tapi ditambahkan
sebagai bukti tabel itu memang bukan populasi yang sama).
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
        CREATE TABLE customer_profile (
            no_rangka TEXT PRIMARY KEY,
            customer TEXT,
            model TEXT,
            segment TEXT,
            dealer_kategori TEXT,
            no_polisi TEXT,
            sa_terakhir TEXT,
            total_kunjungan_fisik INTEGER,
            total_revenue_lifetime REAL
        );

        CREATE TABLE unitmasuk (
            no_polisi TEXT,
            no_wo INTEGER,
            no_invoice TEXT,
            customer TEXT,
            no_rangka TEXT,
            model TEXT,
            sa TEXT,
            mech TEXT,
            pekerjaan TEXT,
            klp TEXT,
            kelompok TEXT,
            tanggal TEXT,
            tgl_invoice TEXT,
            kategori TEXT,
            tcare TEXT
        );

        CREATE TABLE rekapbulanan (
            tanggal TEXT,
            no_wo REAL,
            sa TEXT,
            model TEXT,
            no_invoice TEXT,
            invoice REAL,
            total_revenue REAL
        );

        CREATE TABLE tcare_schedule_full_history (
            no_rangka TEXT,
            dealer_kategori TEXT,
            tgl_do TEXT,
            kunjungan INTEGER,
            pekerjaan TEXT,
            bulan_jadwal TEXT,
            bulan_realisasi TEXT,
            status TEXT,
            no_wo_real TEXT,
            sa_realisasi TEXT,
            expired INTEGER,
            batas_tcare TEXT
        );

        CREATE TABLE tcare_schedule (
            no_rangka TEXT,
            kunjungan INTEGER,
            pekerjaan TEXT,
            bulan_jadwal TEXT,
            bulan_realisasi TEXT,
            status TEXT,
            no_wo_real TEXT,
            sa_realisasi TEXT,
            expired INTEGER
        );

        CREATE TABLE rs (
            no_rangka TEXT,
            model TEXT,
            no_polisi TEXT,
            customer TEXT,
            dealer_kategori TEXT,
            batas_tcare TEXT,
            tgl_do TEXT
        );

        CREATE TABLE tcare_unit (
            no_rangka TEXT,
            tcare_type TEXT,
            sisa_service INTEGER,
            sisa_detail TEXT,
            sa_terakhir TEXT
        );

        CREATE VIEW unit_tcare AS
            SELECT r.*, t.tcare_type, t.sisa_service, t.sisa_detail, t.sa_terakhir
            FROM rs r
            LEFT JOIN tcare_unit t ON r.no_rangka = t.no_rangka;
        """
    )

    # -- customer_profile --
    conn.executemany(
        "INSERT INTO customer_profile (no_rangka, customer, model, segment, "
        "dealer_kategori, no_polisi, sa_terakhir, total_kunjungan_fisik, "
        "total_revenue_lifetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "MHFXX1JGK000BUDI1",
                "BUDI SANTOSO",
                "Avanza",
                "Retail",
                "A",
                "B 1234 XYZ",
                "SA01",
                5,
                12_500_000.0,
            ),
            (
                # namesake kedua supaya nama "Budi" ambigu di test
                "MHFXX1JGK000BUDI2",
                "BUDI HARTONO",
                "Innova",
                "Retail",
                "B",
                "D 5678 ABC",
                "SA02",
                3,
                8_000_000.0,
            ),
            (
                "01S208014054",
                "SITI AMINAH",
                "Xenia",
                "Retail",
                "A",
                "F 9999 OLD",
                "SA03",
                7,
                20_000_000.0,
            ),
            (
                "MHAGGTEST0000001",
                "AGUNG PRATAMA",
                "Fortuner",
                "Retail",
                "A",
                "H 7777 AG",
                "SA05",
                3,
                5_000_000.0,
            ),
        ],
    )

    # -- unitmasuk (riwayat WO untuk Budi Santoso) --
    conn.executemany(
        "INSERT INTO unitmasuk (no_polisi, no_wo, no_invoice, customer, "
        "no_rangka, model, sa, mech, pekerjaan, klp, kelompok, tanggal, "
        "tgl_invoice, kategori, tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "B 1234 XYZ",
                1001,
                "INV-1001",
                "BUDI SANTOSO",
                "MHFXX1JGK000BUDI1",
                "Avanza",
                "SA01",
                "MECH1",
                "Ganti Oli",
                "SBE",
                "SBE",
                "2024-01-10",
                "2024-01-10",
                "Reguler",
                "N",
            ),
            (
                "B 1234 XYZ",
                1002,
                "INV-1002",
                "BUDI SANTOSO",
                "MHFXX1JGK000BUDI1",
                "Avanza",
                "SA01",
                "MECH2",
                "Servis Berkala",
                "SBE",
                "SBE",
                "2024-03-15",
                "2024-03-15",
                "Reguler",
                "N",
            ),
        ],
    )

    # -- unitmasuk: kasus uji agregasi jenis_pekerjaan (disepakati eksplisit
    # dengan user) untuk customer terpisah "AGUNG PRATAMA", supaya tidak
    # mengganggu data Budi Santoso yang sudah dipakai test lain --
    conn.executemany(
        "INSERT INTO unitmasuk (no_polisi, no_wo, no_invoice, customer, "
        "no_rangka, model, sa, mech, pekerjaan, klp, kelompok, tanggal, "
        "tgl_invoice, kategori, tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # WO 2001: kombinasi SBE+GRP+SUB tanpa WRT -> "SBE (Ganti Oli
            # Mesin), GRP, SUB"
            (
                "H 7777 AG", 2001, "INV-2001", "AGUNG PRATAMA",
                "MHAGGTEST0000001", "Fortuner", "SA05", "MECH1",
                "Ganti Oli Mesin", "SBE", "SBE",
                "2024-05-01", "2024-05-01", "Reguler", "N",
            ),
            (
                "H 7777 AG", 2001, "INV-2001", "AGUNG PRATAMA",
                "MHAGGTEST0000001", "Fortuner", "SA05", "MECH1",
                "Ganti Filter Oli", "GRP", "SBE",
                "2024-05-01", "2024-05-01", "Reguler", "N",
            ),
            (
                "H 7777 AG", 2001, "INV-2001", "AGUNG PRATAMA",
                "MHAGGTEST0000001", "Fortuner", "SA05", "MECH1",
                "Ban Luar", "SUB", "SBE",
                "2024-05-01", "2024-05-01", "Reguler", "N",
            ),
            # WO 2002: kelompok=WRT (warranty) -> label HANYA "WRT"
            (
                "H 7777 AG", 2002, "INV-2002", "AGUNG PRATAMA",
                "MHAGGTEST0000001", "Fortuner", "SA05", "MECH2",
                "Headlight Assy R&R", "GRP", "WRT",
                "2024-06-01", "2024-06-01", "non CPUS", "N",
            ),
            (
                "H 7777 AG", 2002, "INV-2002", "AGUNG PRATAMA",
                "MHAGGTEST0000001", "Fortuner", "SA05", "MECH2",
                "Mirror Assy", "SUB", "WRT",
                "2024-06-01", "2024-06-01", "non CPUS", "N",
            ),
            # WO 2003: SBI+SUB -> "SBI, SUB" (SBI TIDAK disertai teks
            # pekerjaan, beda dari SBE)
            (
                "H 7777 AG", 2003, "INV-2003", "AGUNG PRATAMA",
                "MHAGGTEST0000001", "Fortuner", "SA05", "MECH3",
                "Ganti Battery", "SBI", "SBI",
                "2024-07-01", "2024-07-01", "Reguler", "N",
            ),
            (
                "H 7777 AG", 2003, "INV-2003", "AGUNG PRATAMA",
                "MHAGGTEST0000001", "Fortuner", "SA05", "MECH3",
                "Busi", "SUB", "SBI",
                "2024-07-01", "2024-07-01", "Reguler", "N",
            ),
        ],
    )

    # -- rekapbulanan (revenue resmi, no_wo bertipe REAL) --
    conn.executemany(
        "INSERT INTO rekapbulanan (tanggal, no_wo, sa, model, no_invoice, "
        "invoice, total_revenue) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("2024-01-10", 1001.0, "SA01", "Avanza", "INV-1001", 350_000.0, 999_999.0),
            ("2024-03-15", 1002.0, "SA01", "Avanza", "INV-1002", 1_200_000.0, 999_999.0),
        ],
    )

    # -- tcare_schedule_full_history: kasus lama-expired (01S208014054) --
    old_expired_rows = [
        ("01S208014054", "A", "2008-05-01", 1, "1K", "2008-06", "2008-06", "DONE", "WO-1", "SA10", 1, "2011-05-01"),
        ("01S208014054", "A", "2008-05-01", 2, "10K", "2008-11", "2008-12", "DONE", "WO-2", "SA10", 1, "2011-05-01"),
        ("01S208014054", "A", "2008-05-01", 3, "20K", "2009-05", "2009-06", "DONE", "WO-3", "SA10", 1, "2011-05-01"),
        ("01S208014054", "A", "2008-05-01", 4, "30K", "2009-11", "2009-12", "DONE", "WO-4", "SA10", 1, "2011-05-01"),
        ("01S208014054", "A", "2008-05-01", 5, "40K", "2010-05", "2010-06", "DONE", "WO-5", "SA10", 1, "2011-05-01"),
        ("01S208014054", "A", "2008-05-01", 6, "50K", "2010-11", "2010-12", "DONE", "WO-6", "SA10", 1, "2011-05-01"),
        ("01S208014054", "A", "2008-05-01", 7, "60K", "2011-05", "2011-05", "DONE", "WO-7", "SA10", 1, "2011-05-01"),
    ]
    conn.executemany(
        "INSERT INTO tcare_schedule_full_history (no_rangka, dealer_kategori, "
        "tgl_do, kunjungan, pekerjaan, bulan_jadwal, bulan_realisasi, status, "
        "no_wo_real, sa_realisasi, expired, batas_tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        old_expired_rows,
    )
    # Sengaja TIDAK ada baris untuk 01S208014054 di tcare_schedule (bukti
    # empiris ADR024: 92% kendaraan hilang dari tabel ini).

    # -- kasus overlap TCARE untuk INT002 (opsi 3, disepakati user):
    # Budi Santoso juga punya riwayat TCARE, dipakai untuk membuktikan
    # notifikasi "unit ini juga punya data TCARE" muncul di History
    # Service. Budi Hartono (MHFXX1JGK000BUDI2) SENGAJA tidak diberi
    # baris di sini -- dipakai sebagai kasus "tidak ada overlap".
    conn.execute(
        "INSERT INTO tcare_schedule_full_history (no_rangka, dealer_kategori, "
        "tgl_do, kunjungan, pekerjaan, bulan_jadwal, bulan_realisasi, status, "
        "no_wo_real, sa_realisasi, expired, batas_tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("MHFXX1JGK000BUDI1", "A", "2023-01-10", 1, "1K", "2023-02", "2023-02", "DONE", "WO-100", "SA01", 0, "2026-01-10"),
    )

    # -- rs (identitas unit) + tcare_unit (operasional TCARE), digabung
    # VIEW unit_tcare -- kasus aktif normal (Budi Santoso) --
    conn.execute(
        "INSERT INTO rs (no_rangka, model, no_polisi, customer, "
        "dealer_kategori, batas_tcare, tgl_do) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "MHFXX1JGK000BUDI1",
            "Avanza",
            "B 1234 XYZ",
            "BUDI SANTOSO",
            "A",
            "2026-01-10",
            "2023-01-10",
        ),
    )
    conn.execute(
        "INSERT INTO tcare_unit (no_rangka, tcare_type, sisa_service, "
        "sisa_detail, sa_terakhir) VALUES (?, ?, ?, ?, ?)",
        ("MHFXX1JGK000BUDI1", "Reguler", 4, "3 dari 7", "SA01"),
    )
    # Sengaja TIDAK ada baris untuk 01S208014054 di `rs` maupun
    # `tcare_unit` -- ini kasus DoD wajib: VIEW unit_tcare kosong untuk
    # no_rangka ini (LEFT JOIN dari `rs` tidak akan menghasilkan baris
    # sama sekali kalau `rs` sendiri tidak punya baris untuk no_rangka
    # itu), tapi riwayat ADA di tcare_schedule_full_history -- Service
    # harus tetap OK (bukan NOT_FOUND).

    # -- Kasus fallback pencarian nama (keputusan Room 0, Opsi A):
    # "PT UNTESTED WELL SEJAHTERA" ada di unitmasuk (riwayat WO nyata),
    # tapi SENGAJA TIDAK diberi baris di customer_profile maupun rs --
    # meniru persis kasus nyata "PT. LONG WELL INTERNATIONAL" yang
    # ditemukan lewat smoke test (lag ETL bulanan yang wajar).
    conn.executemany(
        "INSERT INTO unitmasuk (no_polisi, no_wo, no_invoice, customer, "
        "no_rangka, model, sa, mech, pekerjaan, klp, kelompok, tanggal, "
        "tgl_invoice, kategori, tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "K 9999 UW", 3001, "INV-3001", "PT UNTESTED WELL SEJAHTERA",
                "MHUNTESTED0000001", "Hilux", "SA07", "MECH4",
                "Ganti Oli Mesin", "SBE", "SBE",
                "2024-08-01", "2024-08-01", "Reguler", "N",
            ),
        ],
    )

    conn.commit()
    conn.close()
    return path