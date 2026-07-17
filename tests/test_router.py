"""
Unit tests untuk Router (Room 2), sesuai Definition of Done:
  1. Router memilih Handler yang benar dari beberapa mock Handler
  2. Tie-break priority: dua Handler match, priority beda -> yang lebih tinggi menang
  3. Tie-break registration order: dua Handler match, priority sama ->
     yang register duluan menang
  4. Router memanggil FallbackProvider.execute() ketika tidak ada Handler yang match
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from ai.router import Router, NullFallbackProvider
from tests.mock_handlers import MockHandler


class TestRouterBasicMatching(unittest.TestCase):
    def test_router_selects_correct_handler(self):
        router = Router(fallback=NullFallbackProvider())
        history_handler = MockHandler("INT001", "HistoryHandler", "riwayat", tag="history")
        stock_handler = MockHandler("INT002", "StockHandler", "stok", tag="stock")

        router.register(history_handler, priority=5)
        router.register(stock_handler, priority=5)

        result = router.route("cek riwayat transaksi bulan ini")

        self.assertTrue(result.success)
        self.assertEqual(result.summary["matched_by"], "history")

    def test_router_selects_correct_handler_second_case(self):
        router = Router(fallback=NullFallbackProvider())
        history_handler = MockHandler("INT001", "HistoryHandler", "riwayat", tag="history")
        stock_handler = MockHandler("INT002", "StockHandler", "stok", tag="stock")

        router.register(history_handler, priority=5)
        router.register(stock_handler, priority=5)

        result = router.route("berapa stok barang A?")

        self.assertTrue(result.success)
        self.assertEqual(result.summary["matched_by"], "stock")


class TestRouterTieBreakPriority(unittest.TestCase):
    def test_higher_priority_wins_when_both_match(self):
        router = Router(fallback=NullFallbackProvider())
        low_priority = MockHandler("INT001", "LowPriorityHandler", "barang", tag="low")
        high_priority = MockHandler("INT002", "HighPriorityHandler", "barang", tag="high")

        # Register low priority first, high priority second --
        # priority must still decide, not registration order.
        router.register(low_priority, priority=1)
        router.register(high_priority, priority=10)

        result = router.route("info barang X")

        self.assertEqual(result.summary["matched_by"], "high")


class TestRouterTieBreakRegistrationOrder(unittest.TestCase):
    def test_first_registered_wins_when_priority_equal(self):
        router = Router(fallback=NullFallbackProvider())
        first = MockHandler("INT001", "FirstHandler", "barang", tag="first")
        second = MockHandler("INT002", "SecondHandler", "barang", tag="second")

        router.register(first, priority=5)
        router.register(second, priority=5)

        result = router.route("info barang X")

        self.assertEqual(result.summary["matched_by"], "first")

    def test_first_registered_wins_regardless_of_definition_order(self):
        router = Router(fallback=NullFallbackProvider())
        second = MockHandler("INT002", "SecondHandler", "barang", tag="second")
        first = MockHandler("INT001", "FirstHandler", "barang", tag="first")

        # register() call order is what matters, not variable name/definition order
        router.register(second, priority=5)
        router.register(first, priority=5)

        result = router.route("info barang X")

        self.assertEqual(result.summary["matched_by"], "second")


class TestRouterFallback(unittest.TestCase):
    def test_fallback_called_when_no_handler_matches(self):
        router = Router(fallback=NullFallbackProvider())
        handler = MockHandler("INT001", "OnlyHandler", "riwayat", tag="history")
        router.register(handler, priority=1)

        result = router.route("query yang tidak dikenal sama sekali")

        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT999_ERROR")

    def test_fallback_called_with_no_handlers_registered(self):
        router = Router(fallback=NullFallbackProvider())

        result = router.route("apapun")

        self.assertFalse(result.success)
        self.assertEqual(result.code, "INT999_ERROR")


if __name__ == "__main__":
    unittest.main()
