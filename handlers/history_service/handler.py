"""
handlers/history_service/handler.py

HistoryServiceHandler (INT002). Alur wajib (brief Room 4):

    Router.route(text)
      -> Handler.match(text) / Handler.execute(text)
           -> parser: ekstrak identifier + rentang tanggal dari text
           -> Service.execute(params: HistoryServiceParams)
                -> Repository -> SQLite (read-only)
           -> formatter: bentuk message + summary
      -> HandlerResult

Tidak ada SQL/business logic di file ini (ADR003/ADR004). Semua error
dari layer bawah (RepositoryError) ditangkap di sini supaya
HandlerResult yang dikembalikan konsisten `{INT002}_ERROR`, bukan
exception mentah yang menembus ke `_safe_route` di app_v2.py.
"""

from db.base_repository import RepositoryError
from handlers.history_service import formatter, parser
from handlers.history_service.service import HistoryServiceService
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


class HistoryServiceHandler(BaseHandler):
    intent_id = "INT002"
    name = "History Service"

    def __init__(self, service: HistoryServiceService = None):
        self.service = service or HistoryServiceService()

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
            logger.exception("Gagal mengambil history service untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data history service: {exc}",
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

        profile = result["profile"]
        history_df = result["history"]
        ro_total = result["ro_total"]
        has_tcare_history = result.get("has_tcare_history", False)
        identity_source = result.get("identity_source", "customer_profile")

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(
                profile, history_df, ro_total, has_tcare_history, identity_source
            ),
            dataframe=history_df,
            summary=formatter.build_summary(
                profile, history_df, ro_total, has_tcare_history, identity_source
            ),
        )


def _to_service_params(parsed: "parser.ParsedHistoryServiceQuery"):
    from handlers.history_service.service import HistoryServiceParams

    return HistoryServiceParams(
        customer_identifier=parsed.customer_identifier,
        identifier_type=parsed.identifier_type,
        date_from=parsed.date_from,
        date_to=parsed.date_to,
    )