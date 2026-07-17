"""
handlers/wip/handler.py

WIPHandler (INT007). Alur sama seperti intent lain (pola Room 4):

    Router.route(text)
      -> Handler.match(text) / Handler.execute(text)
           -> parser: ekstrak filter kelompok + SA dari text
           -> Service.execute(params: WIPParams)
                -> Repository -> SQLite (read-only)
           -> formatter: bentuk message + summary
      -> HandlerResult

Tidak ada SQL/business logic di file ini (ADR003/ADR004). Tidak ada
kasus NOT_FOUND untuk INT007 -- 0 unit WIP untuk filter tertentu adalah
jawaban valid, bukan error (lihat docstring service.py).
"""

from db.base_repository import RepositoryError
from handlers.wip import formatter, parser
from handlers.wip.service import WIPParams, WIPService
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, SUFFIX_ERROR, SUFFIX_OK, make_code
from utils.logger import get_logger

logger = get_logger(__name__)


class WIPHandler(BaseHandler):
    intent_id = "INT007"
    name = "WIP"

    def __init__(self, service: WIPService = None):
        self.service = service or WIPService()

    def match(self, text: str) -> bool:
        return parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = parser.parse(text)
        service_params = WIPParams(
            kelompok=parsed.kelompok,
            sa_candidate=parsed.sa_candidate,
            wants_summary_only=parsed.wants_summary_only,
        )

        try:
            result = self.service.execute(service_params)
        except RepositoryError as exc:
            logger.exception("Gagal mengambil data WIP untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data WIP: {exc}",
            )

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(result),
            dataframe=result["units"],
            summary=formatter.build_summary(result),
        )
