"""
handlers/tcare_web_status/handler.py — INT012 TCARE Web Status

Query Handler biasa (pola Room 4/5), extend BaseHandler. Tidak ada SQL/
business logic di sini (ADR003/ADR004).
"""

from db.base_repository import RepositoryError
from handlers.tcare_web_status import formatter
from handlers.tcare_web_status.parser import TCAREWebStatusParser
from handlers.tcare_web_status.service import TCAREWebStatusService, TCAREWebStatusServiceParams
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, SUFFIX_ERROR, SUFFIX_OK, make_code
from utils.logger import get_logger

logger = get_logger(__name__)


class TCAREWebStatusHandler(BaseHandler):
    intent_id = "INT012"
    name = "TCARE Web Status"

    def __init__(self, service: TCAREWebStatusService = None, parser: TCAREWebStatusParser = None):
        self.service = service or TCAREWebStatusService()
        self.parser = parser or TCAREWebStatusParser()

    def match(self, text: str) -> bool:
        return self.parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = self.parser.parse(text)
        service_params = TCAREWebStatusServiceParams(
            no_rangka=parsed.no_rangka,
            wants_errors=parsed.wants_errors,
        )

        try:
            result = self.service.execute(service_params)
        except RepositoryError as exc:
            logger.exception("Gagal mengambil data TCARE Web Status untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data TCARE Web Status: {exc}",
            )

        dataframe = result.get("service") if result.get("mode") == "detail" else result.get("errors")

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(result),
            dataframe=dataframe,
            summary=formatter.build_summary(result),
        )
