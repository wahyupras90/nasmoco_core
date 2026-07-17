"""
Mock Handler untuk keperluan unit test Router (Room 2).

Ini BUKAN handler produksi (INT001-INT999) -- itu tugas Room 4+. Mock ini
hanya mengimplementasikan kontrak BaseHandler (match/execute + intent_id/name)
seminimal mungkin agar Router bisa diuji secara terisolasi.
"""

from models.base_handler import BaseHandler
from models.handler_result import HandlerResult


class MockHandler(BaseHandler):
    def __init__(self, intent_id: str, name: str, keyword: str, tag: str = ""):
        self.intent_id = intent_id
        self.name = name
        self._keyword = keyword
        self._tag = tag or name

    def match(self, text: str) -> bool:
        return self._keyword.lower() in text.lower()

    def execute(self, text: str) -> HandlerResult:
        return HandlerResult(
            success=True,
            code="OK",
            message=f"Handled by {self._tag}",
            summary={"matched_by": self._tag, "query": text},
        )
