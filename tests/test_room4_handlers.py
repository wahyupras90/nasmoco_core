"""
tests/test_room4_handlers.py

Unit test Handler layer Room 4:
  - match() mengenali pola teks yang relevan, dan HistoryService vs
    HistoryTCARE saling menolak sesuai kata "tcare".
  - execute() mengembalikan HandlerResult dengan `code` sesuai format
    {INT}_OK / {INT}_NOT_FOUND / {INT}_AMBIGUOUS / {INT}_ERROR.
  - Router.route() memilih Handler yang tepat berdasarkan match().
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import close_connection

from tests.fixtures_room4 import make_temp_db

from ai.router import Router, NullFallbackProvider
from db.base_repository import RepositoryError
from handlers.history_service.handler import HistoryServiceHandler
from handlers.history_service.service import HistoryServiceService
from handlers.history_tcare.handler import HistoryTCAREHandler
from handlers.history_tcare.service import HistoryTCAREService
from repositories.history_service_repository import HistoryServiceRepository
from repositories.history_tcare_repository import HistoryTCARERepository


class TestHistoryServiceHandler(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        service = HistoryServiceService(HistoryServiceRepository(self.db_path))
        self.handler = HistoryServiceHandler(service)

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_intent_id_and_name(self):
        self.assertEqual(self.handler.intent_id, "INT002")
        self.assertEqual(self.handler.name, "History Service")

    def test_match_true_for_relevant_text(self):
        self.assertTrue(self.handler.match("riwayat service Budi Santoso"))

    def test_match_false_when_mentions_tcare(self):
        # Harus ditolak supaya tidak bentrok dengan INT003.
        self.assertFalse(self.handler.match("riwayat tcare Budi Santoso"))

    def test_match_false_when_no_identifier(self):
        self.assertFalse(self.handler.match("riwayat service dong"))

    def test_execute_ok(self):
        result = self.handler.execute("riwayat service MHFXX1JGK000BUDI1")
        self.assertTrue(result.success)
        self.assertEqual(result.code, "INT002_OK")
        self.assertEqual(result.summary["total_visit"], 5)  # BR020
        self.assertIsNotNone(result.dataframe)

    def test_execute_not_found(self):
        result = self.handler.execute("riwayat service TIDAKADASAMASEKALINAMA")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT002_NOT_FOUND")

    def test_execute_ok_via_unitmasuk_fallback_shows_transparency_note(self):
        """
        Keputusan Room 0 (Opsi A): customer yang belum ke-ETL ke
        customer_profile tetap OK lewat fallback unitmasuk, dengan
        catatan transparansi bahwa RO/segment belum tersedia.
        """
        result = self.handler.execute("riwayat service UNTESTED WELL")
        self.assertTrue(result.success)
        self.assertEqual(result.code, "INT002_OK")
        self.assertEqual(result.summary["identity_source"], "unitmasuk_fallback")
        self.assertIsNone(result.summary["total_visit"])
        self.assertIn("belum tersedia di data profil resmi", result.message)

    def test_execute_ambiguous(self):
        result = self.handler.execute("riwayat service budi")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT002_AMBIGUOUS")
        self.assertEqual(len(result.suggestions), 2)

    def test_execute_error_when_no_identifier_parsed(self):
        result = self.handler.execute("riwayat service dong")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT002_ERROR")

    def test_execute_wraps_repository_error(self):
        class BoomRepo(HistoryServiceRepository):
            def get_wo_history(self, *a, **kw):
                raise RepositoryError("E002: query error - simulated")

        service = HistoryServiceService(BoomRepo(self.db_path))
        handler = HistoryServiceHandler(service)
        result = handler.execute("riwayat service MHFXX1JGK000BUDI1")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT002_ERROR")


class TestHistoryTCAREHandler(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        service = HistoryTCAREService(HistoryTCARERepository(self.db_path))
        self.handler = HistoryTCAREHandler(service)

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_intent_id_and_name(self):
        self.assertEqual(self.handler.intent_id, "INT003")
        self.assertEqual(self.handler.name, "History TCARE")

    def test_match_true_for_relevant_text(self):
        self.assertTrue(self.handler.match("history tcare MHFXX1JGK000BUDI1"))

    def test_match_false_without_tcare_keyword(self):
        self.assertFalse(self.handler.match("riwayat service MHFXX1JGK000BUDI1"))

    def test_execute_ok_old_expired_case_not_lost_adr024(self):
        """
        Test wajib DoD: no_rangka lama-expired tetap OK, bukan NOT_FOUND,
        walau tcare_unit kosong untuk no_rangka ini.
        """
        result = self.handler.execute("history tcare 01S208014054")
        self.assertTrue(result.success)
        self.assertEqual(result.code, "INT003_OK")
        self.assertEqual(len(result.dataframe), 7)
        self.assertEqual(result.summary["customer"], "SITI AMINAH")

    def test_execute_not_found(self):
        result = self.handler.execute("history tcare VINTIDAKADASAMASEKALI1")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT003_NOT_FOUND")

    def test_execute_ambiguous(self):
        result = self.handler.execute("history tcare budi")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT003_AMBIGUOUS")


class TestRouterIntegration(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        service_history = HistoryServiceService(HistoryServiceRepository(self.db_path))
        service_tcare = HistoryTCAREService(HistoryTCARERepository(self.db_path))
        self.router = Router(fallback=NullFallbackProvider())
        self.router.register(HistoryServiceHandler(service_history), priority=10)
        self.router.register(HistoryTCAREHandler(service_tcare), priority=20)

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def test_router_picks_history_service_for_service_text(self):
        result = self.router.route("riwayat service MHFXX1JGK000BUDI1")
        self.assertEqual(result.code, "INT002_OK")

    def test_router_picks_history_tcare_for_tcare_text(self):
        result = self.router.route("history tcare 01S208014054")
        self.assertEqual(result.code, "INT003_OK")

    def test_router_falls_back_when_nothing_matches(self):
        result = self.router.route("berapa kurs dollar hari ini")
        self.assertEqual(result.code, "INT999_ERROR")


if __name__ == "__main__":
    unittest.main()