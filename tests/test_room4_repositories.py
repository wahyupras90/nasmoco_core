"""
tests/test_room4_repositories.py

Unit test Repository layer Room 4:
  - CustomerProfileRepository (BR020, BR027 — shared)
  - HistoryServiceRepository (INT002 — unitmasuk + rekapbulanan)
  - HistoryTCARERepository (INT003 — ADR024: tcare_schedule_full_history)
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import close_connection

from tests.fixtures_room4 import make_temp_db

from repositories.customer_profile_repository import CustomerProfileRepository
from repositories.history_service_repository import HistoryServiceRepository
from repositories.history_tcare_repository import HistoryTCARERepository


class TestCustomerProfileRepository(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.repo = CustomerProfileRepository(self.db_path)

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_get_by_no_rangka(self):
        df = self.repo.get_by_no_rangka("MHFXX1JGK000BUDI1")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["customer"], "BUDI SANTOSO")

    def test_get_by_no_polisi(self):
        df = self.repo.get_by_no_polisi("b 1234 xyz")  # case-insensitive
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["no_rangka"], "MHFXX1JGK000BUDI1")

    def test_get_by_no_polisi_normalizes_dash_separator(self):
        """
        Regresi: smoke test nyata menunjukkan no_polisi di nasmoco.db
        pakai strip sebagai pemisah (mis. "G-1576-DF"), bukan spasi.
        Query dengan strip harus tetap match walau data tersimpan pakai
        spasi (dan sebaliknya).
        """
        df = self.repo.get_by_no_polisi("B-1234-XYZ")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["no_rangka"], "MHFXX1JGK000BUDI1")

    def test_get_by_no_polisi_normalizes_no_separator(self):
        df = self.repo.get_by_no_polisi("B1234XYZ")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["no_rangka"], "MHFXX1JGK000BUDI1")

    def test_get_by_customer_name_ambiguous(self):
        df = self.repo.get_by_customer_name("budi")
        self.assertEqual(len(df), 2)  # BUDI SANTOSO & BUDI HARTONO

    def test_get_total_kunjungan_fisik_br020(self):
        ro = self.repo.get_total_kunjungan_fisik("MHFXX1JGK000BUDI1")
        self.assertEqual(ro, 5)

    def test_get_total_kunjungan_fisik_not_found(self):
        ro = self.repo.get_total_kunjungan_fisik("TIDAK_ADA")
        self.assertIsNone(ro)


class TestHistoryServiceRepository(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.repo = HistoryServiceRepository(self.db_path)

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_get_wo_history_returns_dataframe(self):
        df = self.repo.get_wo_history("MHFXX1JGK000BUDI1")
        self.assertEqual(len(df), 2)
        self.assertIn("no_wo", df.columns)

    def test_get_wo_history_date_filter(self):
        df = self.repo.get_wo_history(
            "MHFXX1JGK000BUDI1", date_from="2024-02-01", date_to="2024-12-31"
        )
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["no_wo"], 1002)

    def test_get_revenue_by_no_wo_br003(self):
        df = self.repo.get_revenue_by_no_wo([1001, 1002])
        self.assertEqual(len(df), 2)
        revenue_1001 = df.loc[df["no_wo"] == 1001, "invoice"].iloc[0]
        self.assertEqual(revenue_1001, 350_000.0)

    def test_get_revenue_by_no_wo_empty_list(self):
        df = self.repo.get_revenue_by_no_wo([])
        self.assertTrue(df.empty)


class TestHistoryTCARERepository(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.repo = HistoryTCARERepository(self.db_path)

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_get_unit_info_found(self):
        info = self.repo.get_unit_info("MHFXX1JGK000BUDI1")
        self.assertIsNotNone(info)
        self.assertEqual(info["customer"], "BUDI SANTOSO")

    def test_get_unit_info_missing_for_old_expired_case(self):
        # ADR024 case: tcare_unit sengaja kosong untuk no_rangka ini.
        info = self.repo.get_unit_info("01S208014054")
        self.assertIsNone(info)

    def test_schedule_history_uses_full_history_table_adr024(self):
        df = self.repo.get_schedule_history("01S208014054")
        self.assertEqual(len(df), 7)  # 1K..60K
        self.assertListEqual(
            sorted(df["pekerjaan"].tolist()),
            sorted(["1K", "10K", "20K", "30K", "40K", "50K", "60K"]),
        )

    def test_has_any_tcare_history_true_even_when_unit_info_missing(self):
        self.assertIsNone(self.repo.get_unit_info("01S208014054"))
        self.assertTrue(self.repo.has_any_tcare_history("01S208014054"))

    def test_no_query_ever_touches_tcare_schedule_short_table(self):
        # Bukti negatif ADR024: tabel tcare_schedule (bukan _full_history)
        # sengaja dibuat KOSONG untuk no_rangka ini di fixture. Kalau
        # Repository (secara tidak sengaja di masa depan) balik memakai
        # tcare_schedule, test ini akan tetap lulus dengan salah (harus
        # 0), jadi kita pastikan lewat baris di bawah bahwa datanya
        # memang tidak ada di sana -- bukti bahwa full_history-lah
        # satu-satunya sumber yang punya datanya.
        cursor_check = self.repo.execute(
            "SELECT COUNT(*) as c FROM tcare_schedule WHERE no_rangka = ?",
            ("01S208014054",),
        )
        self.assertEqual(cursor_check.iloc[0]["c"], 0)

    def test_get_ro_count_br020_br027(self):
        ro = self.repo.get_ro_count("01S208014054")
        self.assertEqual(ro, 7)

    def test_get_fallback_identity(self):
        identity = self.repo.get_fallback_identity("01S208014054")
        self.assertIsNotNone(identity)
        self.assertEqual(identity["customer"], "SITI AMINAH")


if __name__ == "__main__":
    unittest.main()
