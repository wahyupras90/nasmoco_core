"""
tests/test_room4_formatters.py

Unit test langsung untuk formatter.py Room 4 (tanpa perlu DB), fokus ke
perbaikan yang disepakati user: "jumlah kunjungan" dihitung per WO unik
(`no_wo`), BUKAN per baris di `history_df` — karena `unitmasuk`
menyimpan satu baris PER ITEM PEKERJAAN, jadi 1 WO dengan beberapa
pekerjaan bisa muncul sebagai beberapa baris dengan `no_wo` yang sama.
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers.history_service import formatter


class TestHistoryServiceFormatterVisitCount(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "customer": "DENISA APRILIAWATI",
            "no_rangka": "MHKAB1BC6PJ024535",
            "no_polisi": "AB-1899-GM",
            "model": "AGYA 1.2 G CVT",
            "segment": "New Entry",
        }

    def test_counts_unique_wo_not_rows(self):
        """
        Kasus nyata dari smoke test: WO 2243864 muncul 2 baris (2 item
        pekerjaan: DIAGNOSA/INSPECTION + NITROGEN), WO 2236285 muncul 1
        baris -> 3 baris total, tapi cuma 2 kunjungan/WO unik.
        """
        history_df = pd.DataFrame(
            {
                "no_wo": [2243864, 2243864, 2236285],
                "pekerjaan": ["DIAGNOSA/INSPECTION", "NITROGEN", "CLAIM PART"],
            }
        )

        summary = formatter.build_summary(self.profile, history_df, ro_total=1)
        self.assertEqual(summary["visit_in_range"], 2)  # BUKAN 3

        message = formatter.format_message(self.profile, history_df, ro_total=1)
        self.assertIn("Jumlah kunjungan pada rentang yang diminta: 2", message)

    def test_counts_zero_for_empty_history(self):
        history_df = pd.DataFrame(columns=["no_wo", "pekerjaan"])
        summary = formatter.build_summary(self.profile, history_df, ro_total=0)
        self.assertEqual(summary["visit_in_range"], 0)

    def test_all_rows_unique_wo_counts_same_as_row_count(self):
        """Kasus normal (tidak ada WO berulang) -- hasil tetap sama seperti sebelumnya."""
        history_df = pd.DataFrame({"no_wo": [1001, 1002], "pekerjaan": ["A", "B"]})
        summary = formatter.build_summary(self.profile, history_df, ro_total=5)
        self.assertEqual(summary["visit_in_range"], 2)


if __name__ == "__main__":
    unittest.main()
