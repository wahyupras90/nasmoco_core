"""
tests/test_room4_aggregation.py

Unit test agregasi `jenis_pekerjaan` per WO di HistoryServiceService
(disepakati eksplisit dengan user, lihat docstring
handlers/history_service/service.py):

  1. Kombinasi SBE+GRP+SUB (tanpa WRT) -> "SBE (<pekerjaan>), GRP, SUB"
  2. Ada kelompok=WRT -> HANYA "WRT" (tidak digabung kode lain)
  3. Kombinasi SBI+SUB -> "SBI, SUB" (SBI TIDAK disertai teks pekerjaan,
     beda dari SBE)

Dites lewat customer terpisah "AGUNG PRATAMA" (no_rangka
MHAGGTEST0000001) supaya tidak mengganggu fixture Budi Santoso yang
dipakai test lain.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import close_connection
from tests.fixtures_room4 import make_temp_db

from handlers.history_service.service import HistoryServiceParams, HistoryServiceService
from repositories.history_service_repository import HistoryServiceRepository


class TestJenisPekerjaanAggregation(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.service = HistoryServiceService(HistoryServiceRepository(self.db_path))

    def tearDown(self):
        close_connection()
        os.remove(self.db_path)

    def _get_history(self):
        params = HistoryServiceParams(
            customer_identifier="MHAGGTEST0000001", identifier_type="no_rangka"
        )
        result = self.service.execute(params)
        self.assertEqual(result["status"], "ok")
        return result["history"]

    def test_aggregates_one_row_per_wo(self):
        history = self._get_history()
        # 3 WO (2001, 2002, 2003), walau totalnya 7 baris mentah di unitmasuk.
        self.assertEqual(len(history), 3)
        self.assertEqual(sorted(history["no_wo"].tolist()), [2001, 2002, 2003])

    def test_sbe_grp_sub_combo_includes_sbe_pekerjaan_text(self):
        history = self._get_history()
        row = history[history["no_wo"] == 2001].iloc[0]
        self.assertEqual(row["jenis_pekerjaan"], "SBE (Ganti Oli Mesin), GRP, SUB")

    def test_wrt_overrides_to_single_label(self):
        history = self._get_history()
        row = history[history["no_wo"] == 2002].iloc[0]
        self.assertEqual(row["jenis_pekerjaan"], "WRT")

    def test_sbi_sub_combo_without_pekerjaan_text(self):
        history = self._get_history()
        row = history[history["no_wo"] == 2003].iloc[0]
        self.assertEqual(row["jenis_pekerjaan"], "SBI, SUB")

    def test_raw_pekerjaan_klp_kelompok_columns_removed(self):
        history = self._get_history()
        for col in ("pekerjaan", "klp", "kelompok"):
            self.assertNotIn(col, history.columns)

    def test_visit_count_matches_unique_wo_after_aggregation(self):
        from handlers.history_service import formatter

        history = self._get_history()
        summary = formatter.build_summary(
            {"customer": "AGUNG PRATAMA"}, history, ro_total=3
        )
        self.assertEqual(summary["visit_in_range"], 3)


if __name__ == "__main__":
    unittest.main()
