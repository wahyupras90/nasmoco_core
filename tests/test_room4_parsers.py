"""
tests/test_room4_parsers.py

Unit test khusus parser.py Room 4 (ekstraksi identifier), termasuk
kasus regresi yang ditemukan lewat smoke test nyata terhadap
`nasmoco.db`: plat nomor tanpa spasi (mis. "AB1930GG") sebelumnya salah
tertangkap sebagai no_rangka karena kebetulan juga alfanumerik 8
karakter campuran huruf+digit.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers.history_service import parser as service_parser
from handlers.history_tcare import parser as tcare_parser


class TestHistoryServiceParserIdentifier(unittest.TestCase):
    def test_plate_without_space_classified_as_plate_not_no_rangka(self):
        """Regresi: kasus nyata 'riwayat service Wahyu AB1930GG'."""
        parsed = service_parser.parse("riwayat service Wahyu AB1930GG")
        self.assertEqual(parsed.identifier_type, "plate")
        self.assertEqual(parsed.customer_identifier, "AB1930GG")

    def test_plate_with_space_still_classified_as_plate(self):
        parsed = service_parser.parse("riwayat service B 1234 XYZ")
        self.assertEqual(parsed.identifier_type, "plate")
        self.assertEqual(parsed.customer_identifier, "B 1234 XYZ")

    def test_plate_with_dash_classified_as_plate(self):
        """
        Regresi bug report Room 0: plat format strip (format ASLI yang
        tersimpan di kolom no_polisi database, mis. "G-1576-DF")
        sebelumnya gagal total dikenali sebagai identifier apa pun.
        """
        parsed = service_parser.parse("history G-8095-CG")
        self.assertEqual(parsed.identifier_type, "plate")
        self.assertEqual(parsed.customer_identifier, "G-8095-CG")

    def test_match_true_for_dash_plate(self):
        self.assertTrue(service_parser.match("history G-8095-CG"))

    def test_real_no_rangka_17_char_still_classified_as_no_rangka(self):
        parsed = service_parser.parse("riwayat service MHKA6GJ3JPJ608788")
        self.assertEqual(parsed.identifier_type, "no_rangka")
        self.assertEqual(parsed.customer_identifier, "MHKA6GJ3JPJ608788")

    def test_short_legacy_no_rangka_still_classified_as_no_rangka(self):
        parsed = service_parser.parse("riwayat service 01S208014054")
        self.assertEqual(parsed.identifier_type, "no_rangka")
        self.assertEqual(parsed.customer_identifier, "01S208014054")

    def test_plate_takes_priority_when_both_could_match_in_same_text(self):
        parsed = service_parser.parse("riwayat service AB1930GG")
        self.assertEqual(parsed.identifier_type, "plate")


class TestHistoryTCAREParserIdentifier(unittest.TestCase):
    def test_plate_without_space_classified_as_plate_not_no_rangka(self):
        parsed = tcare_parser.parse("history tcare AB1930GG")
        self.assertEqual(parsed.identifier_type, "plate")
        self.assertEqual(parsed.customer_identifier, "AB1930GG")

    def test_plate_with_dash_classified_as_plate(self):
        """Regresi bug report Room 0 (lihat parser INT002 untuk detail)."""
        parsed = tcare_parser.parse("history tcare G-8095-CG")
        self.assertEqual(parsed.identifier_type, "plate")
        self.assertEqual(parsed.customer_identifier, "G-8095-CG")

    def test_match_true_for_dash_plate(self):
        self.assertTrue(tcare_parser.match("history tcare G-8095-CG"))

    def test_real_no_rangka_17_char_still_classified_as_no_rangka(self):
        parsed = tcare_parser.parse("history tcare MHKA6GJ3JPJ608788")
        self.assertEqual(parsed.identifier_type, "no_rangka")

    def test_short_legacy_no_rangka_still_classified_as_no_rangka(self):
        parsed = tcare_parser.parse("history tcare 01S208014054")
        self.assertEqual(parsed.identifier_type, "no_rangka")


if __name__ == "__main__":
    unittest.main()