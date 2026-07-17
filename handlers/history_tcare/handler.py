"""
handlers/history_tcare/handler.py

HistoryTCAREHandler (INT003). Alur sama seperti HistoryServiceHandler
(brief Room 4, konsisten BR027/ADR006): Parser -> Service -> Formatter
-> HandlerResult. Tidak ada SQL/business logic di file ini.
"""

from db.base_repository import RepositoryError
from handlers.history_tcare import formatter, parser
from handlers.history_tcare.service import HistoryTCAREService
from models.base_handler import BaseHandler
from models.handler_result import (
    HandlerResult,
    SUFFIX_AMBIGUOUS,
    SUFFIX_ERROR,
    SUFFIX_NOT_FOUND,
    SUFFIX_OK,
    make_code,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class HistoryTCAREHandler(BaseHandler):
    intent_id = "INT003"
    name = "History TCARE"

    def __init__(self, service: HistoryTCAREService = None):
        self.service = service or HistoryTCAREService()

    def match(self, text: str) -> bool:
        return parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        params = parser.parse(text)
        if params is None:
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=(
                    "Tidak bisa mengenali customer/kendaraan dari permintaan ini. "
                    "Sertakan nama customer, no polisi, atau no rangka (VIN)."
                ),
            )

        service_params = _to_service_params(params)

        try:
            result = self.service.execute(service_params)
        except RepositoryError as exc:
            logger.exception("Gagal mengambil history TCARE untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data history TCARE: {exc}",
            )

        status = result["status"]

        if status == "not_found":
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_NOT_FOUND),
                message=formatter.format_not_found_message(params.customer_identifier),
                summary={"query": params.customer_identifier},
            )

        if status == "ambiguous":
            candidates = result["candidates"]
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_AMBIGUOUS),
                message=formatter.format_ambiguous_message(candidates),
                suggestions=formatter.build_ambiguous_suggestions(candidates),
            )

        unit_info = result["unit_info"]
        schedule_df = result["schedule"]
        ro_total = result["ro_total"]

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(unit_info, schedule_df, ro_total),
            dataframe=schedule_df,
            summary=formatter.build_summary(unit_info, schedule_df, ro_total),
        )


def _to_service_params(parsed: "parser.ParsedHistoryTCAREQuery"):
    from handlers.history_tcare.service import HistoryTCAREParams

    return HistoryTCAREParams(
        customer_identifier=parsed.customer_identifier,
        identifier_type=parsed.identifier_type,
    )
