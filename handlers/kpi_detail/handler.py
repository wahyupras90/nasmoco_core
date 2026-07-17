"""
handlers/kpi_detail/handler.py

KPIDetailHandler (INT005). Alur sama seperti INT004, hanya
Service/Formatter yang berbeda (rincian harian, bukan agregat).
"""

from db.base_repository import RepositoryError
from handlers.kpi_detail import formatter, parser
from handlers.kpi_detail.service import KPIDetailParams, KPIDetailService
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


class KPIDetailHandler(BaseHandler):
    intent_id = "INT005"
    name = "KPI Detail"

    def __init__(self, service: KPIDetailService = None):
        self.service = service or KPIDetailService()

    def match(self, text: str) -> bool:
        return parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = parser.parse(text)
        service_params = KPIDetailParams(
            sa_candidate=parsed.sa_candidate, period=parsed.period
        )

        try:
            result = self.service.execute(service_params)
        except RepositoryError as exc:
            logger.exception("Gagal mengambil KPI detail untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data KPI detail: {exc}",
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
            dataframe=result["daily"],
            summary=formatter.build_summary(result),
        )
