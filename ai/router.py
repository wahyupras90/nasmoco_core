"""
ROOM 2 — Router (ai/router.py)

Tanggung jawab (lihat README_room2.md untuk Decision Log lengkap):
  - register(handler, priority=0): pendaftaran Handler satu per satu (ADR022).
  - route(text): coba setiap Handler terdaftar via handler.match(text); Handler
    pertama yang match (sesuai tie-break) dipanggil execute()-nya.
  - Tie-break saat >1 Handler match (ADR022):
        1) Highest Priority Wins
        2) First Registered Wins
  - Kalau tidak ada yang match -> panggil FallbackProvider.execute(text) (ADR023).

Batasan keras:
  - Router TIDAK BOLEH berisi SQL atau business logic apa pun. Murni dispatch.
  - Router TIDAK BOLEH import/reference apa pun yang menyebut "Analysis" atau
    "SQL Agent" secara konkret. Satu-satunya ketergantungan fallback adalah
    interface abstrak FallbackProvider di bawah (Dependency Inversion, ADR023).
  - Router TIDAK BOLEH hardcode nama/intent handler manapun untuk logging;
    semua diambil dari handler.intent_id / handler.name (ADR021).
"""

from abc import ABC, abstractmethod
from itertools import count
from typing import List, Tuple

from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, make_code, SUFFIX_ERROR
from utils.logger import get_logger

logger = get_logger(__name__)


class FallbackProvider(ABC):
    """
    Interface abstrak untuk penanganan query yang tidak match Handler manapun.

    Room 2 HANYA mendefinisikan interface ini. Implementasi konkret (mis.
    AnalysisProvider yang di dalamnya mungkin chain ke SQL Generator) adalah
    tanggung jawab Room 8. Router tidak pernah tahu, dan tidak boleh tahu,
    apa yang terjadi di dalam execute() ini.
    """

    @abstractmethod
    def execute(self, text: str) -> HandlerResult:
        raise NotImplementedError(
            "FallbackProvider wajib diimplementasikan oleh subclass."
        )


class NullFallbackProvider(FallbackProvider):
    """
    Fallback sederhana untuk testing Router di Room 2.

    BUKAN implementasi Analysis/SQL Agent asli. Room 8 akan membuat
    AnalysisProvider(FallbackProvider) sungguhan dan meng-inject-nya ke
    Router lewat app_v2.py / create_router() saat wiring produksi.
    """

    # Prefix "INT999" dipakai sebagai penanda "tidak ada intent yang match".
    # Bukan intent produksi (INT001-INT998 milik Room 4-8) -- khusus untuk
    # kondisi no-match di NullFallbackProvider testing ini.
    NO_MATCH_INTENT_PREFIX = "INT999"

    def execute(self, text: str) -> HandlerResult:
        return HandlerResult(
            success=False,
            code=make_code(self.NO_MATCH_INTENT_PREFIX, SUFFIX_ERROR),  # "INT999_ERROR"
            message=(
                "Tidak ada handler yang cocok, dan tidak ada fallback produksi "
                "yang terpasang (masih memakai NullFallbackProvider)."
            ),
            summary={"query": text},
        )


class Router:
    """
    Orchestration layer murni: register Handler, dispatch ke Handler yang
    match sesuai aturan tie-break, atau jatuh ke FallbackProvider.
    """

    def __init__(self, fallback: FallbackProvider):
        self._fallback = fallback
        # setiap entri: (priority, registration_order, handler)
        self._registrations: List[Tuple[int, int, BaseHandler]] = []
        self._order_counter = count()

    def register(self, handler: BaseHandler, priority: int = 0) -> None:
        """
        Daftarkan satu Handler. Dipanggil satu per satu oleh Room 4-8 saat
        wiring (bukan lewat constructor list) -- ADR022.
        """
        order = next(self._order_counter)
        self._registrations.append((priority, order, handler))

    def _sorted_handlers(self) -> List[BaseHandler]:
        """
        Urutkan handler sesuai aturan tie-break (ADR022):
          1) priority tertinggi lebih dulu
          2) kalau priority sama, urutan register() lebih awal lebih dulu
        """
        ordered = sorted(self._registrations, key=lambda entry: (-entry[0], entry[1]))
        return [handler for (_priority, _order, handler) in ordered]

    def route(self, text: str) -> HandlerResult:
        """
        Coba setiap Handler terdaftar sesuai urutan tie-break. Handler
        pertama yang match() == True akan dipanggil execute()-nya. Kalau
        tidak ada yang match, delegasikan ke FallbackProvider.
        """
        for handler in self._sorted_handlers():
            if handler.match(text):
                logger.info(
                    "Matched %s %s",
                    getattr(handler, "intent_id", "<no-intent_id>"),
                    getattr(handler, "name", "<no-name>"),
                )
                return handler.execute(text)
        return self._fallback.execute(text)
