"""
tests/test_room4_services.py

Unit test Service layer Room 4 (business logic, ADR004):
  - HistoryServiceService (INT002)
  - HistoryTCAREService (INT003) — termasuk kasus wajib DoD: no_rangka
    yang tcare_unit-nya kosong tapi riwayatnya lama-expired (01S208014054)
    tetap harus "ok", bukan "not_found" (anti bug legacy, ADR024).
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import close_connection

from tests.fixtures_room4 import make_temp_db

from handlers.history_service.service import HistoryServiceParams, HistoryServiceService
from handlers.history_tcare.service import HistoryTCAREParams, HistoryTCAREService
from repositories.history_service_repository import HistoryServiceRepository
from repositories.history_tcare_repository import HistoryTCARERepository


class TestHistoryServiceService(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.service = HistoryServiceService(HistoryServiceRepository(self.db_path))

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_ok_by_vin_includes_ro_from_br020(self):
        params = HistoryServiceParams(
            customer_identifier="MHFXX1JGK000BUDI1", identifier_type="no_rangka"
        )
        result = self.service.execute(params)
        self.assertEqual(result["status"], "ok")
        # BR020: RO wajib dari customer_profile.total_kunjungan_fisik (=5),
        # BUKAN len(history) yang cuma 2 baris di fixture.
        self.assertEqual(result["ro_total"], 5)
        self.assertEqual(len(result["history"]), 2)

    def test_ok_by_plate(self):
        params = HistoryServiceParams(
            customer_identifier="B 1234 XYZ", identifier_type="plate"
        )
        result = self.service.execute(params)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["profile"]["no_rangka"], "MHFXX1JGK000BUDI1")

    def test_ambiguous_by_name(self):
        params = HistoryServiceParams(customer_identifier="budi", identifier_type="name")
        result = self.service.execute(params)
        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(len(result["candidates"]), 2)

    def test_not_found(self):
        params = HistoryServiceParams(
            customer_identifier="TIDAK_ADA_SAMA_SEKALI", identifier_type="name"
        )
        result = self.service.execute(params)
        self.assertEqual(result["status"], "not_found")

    def test_name_fallback_to_unitmasuk_when_customer_profile_empty(self):
        """
        Keputusan Room 0 (Opsi A): kalau customer_profile 0 hasil untuk
        pencarian by-nama, fallback ke unitmasuk. Meniru kasus nyata
        "PT. LONG WELL INTERNATIONAL" (ada di unitmasuk, tidak ada di
        customer_profile -- lag ETL bulanan yang wajar, bukan data cacat).
        """
        params = HistoryServiceParams(
            customer_identifier="UNTESTED WELL", identifier_type="name"
        )
        result = self.service.execute(params)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["profile"]["customer"], "PT UNTESTED WELL SEJAHTERA")
        self.assertEqual(result["profile"]["no_rangka"], "MHUNTESTED0000001")
        # BR020/BR026: RO/segment TIDAK dihitung ulang dari unitmasuk,
        # sengaja None -- bukan cuma hilang diam-diam.
        self.assertIsNone(result["ro_total"])
        self.assertIsNone(result["profile"]["segment"])
        self.assertEqual(result["identity_source"], "unitmasuk_fallback")

    def test_customer_profile_stays_priority_even_if_it_could_also_match_unitmasuk(self):
        """
        Keputusan Room 0: customer_profile PRIORITAS MUTLAK -- kalau
        sudah ada hasil di customer_profile, unitmasuk TIDAK PERNAH
        dicek sama sekali (walau namanya juga match di unitmasuk).
        """
        params = HistoryServiceParams(
            customer_identifier="MHFXX1JGK000BUDI1", identifier_type="no_rangka"
        )
        result = self.service.execute(params)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result.get("identity_source", "customer_profile"), "customer_profile")

    def test_revenue_attached_from_rekapbulanan_br003(self):
        params = HistoryServiceParams(
            customer_identifier="MHFXX1JGK000BUDI1", identifier_type="no_rangka"
        )
        result = self.service.execute(params)
        history = result["history"]
        self.assertIn("invoice", history.columns)
        row_1001 = history[history["no_wo"] == 1001].iloc[0]
        self.assertEqual(row_1001["invoice"], 350_000.0)


class TestHistoryTCAREService(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.service = HistoryTCAREService(HistoryTCARERepository(self.db_path))

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_ok_normal_active_unit(self):
        params = HistoryTCAREParams(
            customer_identifier="MHFXX1JGK000BUDI1", identifier_type="no_rangka"
        )
        result = self.service.execute(params)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["unit_info"]["customer"], "BUDI SANTOSO")
        self.assertEqual(result["ro_total"], 5)

    def test_old_expired_unit_does_not_inherit_legacy_bug_adr024(self):
        """
        DoD wajib: no_rangka dengan riwayat TCARE lama-expired (2008-2011,
        pola seperti 01S208014054) HARUS tetap mengembalikan status "ok",
        BUKAN "not_found" — walaupun tcare_unit tidak punya baris untuk
        no_rangka ini (sengaja dikosongkan di fixture).
        """
        params = HistoryTCAREParams(
            customer_identifier="01S208014054", identifier_type="no_rangka"
        )
        result = self.service.execute(params)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["schedule"]), 7)
        # Identitas fallback datang dari customer_profile (BR027, repo
        # yang sama dipakai HistoryServiceService).
        self.assertEqual(result["unit_info"]["customer"], "SITI AMINAH")
        self.assertIsNone(result["unit_info"]["tcare_type"])
        # BR020: RO tetap dari customer_profile walau tcare_unit kosong.
        self.assertEqual(result["ro_total"], 7)

    def test_not_found_when_neither_table_has_data(self):
        params = HistoryTCAREParams(
            customer_identifier="ZZ99NOTFOUND99ZZ", identifier_type="no_rangka"
        )
        result = self.service.execute(params)
        self.assertEqual(result["status"], "not_found")

    def test_ambiguous_by_name(self):
        params = HistoryTCAREParams(customer_identifier="budi", identifier_type="name")
        result = self.service.execute(params)
        self.assertEqual(result["status"], "ambiguous")


if __name__ == "__main__":
    unittest.main()