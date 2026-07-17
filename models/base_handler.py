"""
models/base_handler.py

Interface wajib untuk semua Handler di nasmoco_core.

Aturan:
    - Semua handler spesifik (Room 4+) WAJIB extend BaseHandler.
    - Handler TIDAK BOLEH berisi SQL.
    - Handler TIDAK BOLEH berisi business rule (itu tugas Service).
    - Handler TIDAK BOLEH membuka koneksi DB langsung
      (harus lewat Service -> Repository).
    - Handler WAJIB mendefinisikan `intent_id` dan `name` sebagai
      class attribute (ADR021). Router (Room 2) memakainya untuk
      logging/debugging ("Matched INT002 HistoryServiceHandler")
      tanpa perlu hardcode nama handler apa pun.

Alur:
    Router -> Handler (match/execute) -> Service -> Repository -> SQLite
"""

from models.handler_result import HandlerResult


class BaseHandler:
    """
    Base class untuk semua handler.

    Subclass WAJIB override `intent_id` dan `name`, contoh:

        class HistoryServiceHandler(BaseHandler):
            intent_id = "INT002"
            name = "History Service"

    Keduanya dipakai Router untuk logging dan (nanti) statistik
    penggunaan intent — bukan untuk logic apa pun di Handler sendiri.
    """

    intent_id: str = ""
    name: str = ""

    def match(self, text: str) -> bool:
        """
        Cek apakah `text` (input user) cocok ditangani handler ini.

        Harus dioverride oleh subclass.
        """
        raise NotImplementedError("Handler wajib mengimplementasikan match().")

    def execute(self, text: str) -> HandlerResult:
        """
        Proses `text` dan kembalikan HandlerResult.

        Harus dioverride oleh subclass. Implementasi TIDAK BOLEH
        menulis SQL langsung atau membuka koneksi DB di sini —
        delegasikan ke Service.
        """
        raise NotImplementedError("Handler wajib mengimplementasikan execute().")
