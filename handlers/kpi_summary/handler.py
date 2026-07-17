"""
handlers/kpi_summary/handler.py

KPISummaryHandler (INT004). Alur wajib (pola Room 4):

    Router.route(text)
      -> Handler.match(text) / Handler.execute(text)
           -> parser: ekstrak SA candidate + periode dari text
           -> Service.execute(params: KPISummaryParams)
                -> Repository -> SQLite (read-only)
           -> formatter: bentuk message + summary
      -> HandlerResult

Tidak ada SQL/business logic di file ini (ADR003/ADR004).
"""

from db.base_repository import RepositoryError
from handlers.kpi_summary import formatter, parser
from handlers.kpi_summary.service import KPISummaryParams, KPISummaryService
from models.base_handler import BaseHandler
from models.handler_result import (
    HandlerResult,
    SUFFIX_ERROR,
    SUFFIX_NOT_FOUND,
    SUFFIX_OK,
    make_code,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class KPISummaryHandler(BaseHandler):
    intent_id = "INT004"
    name = "KPI Summary"

    def __init__(self, service: KPISummaryService = None):
        self.service = service or KPISummaryService()

    def match(self, text: str) -> bool:
        return parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = parser.parse(text)
        service_params = KPISummaryParams(
            sa_candidate=parsed.sa_candidate, period=parsed.period
        )

        try:
            result = self.service.execute(service_params)
        except RepositoryError as exc:
            logger.exception("Gagal mengambil KPI summary untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data KPI summary: {exc}",
            )

        if result["status"] == "not_found":
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_NOT_FOUND),
                message=formatter.format_not_found_message(result["sa_candidate"]),
                summary={"query": result["sa_candidate"]},
            )

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(result),
            summary=formatter.build_summary(result),
        )
