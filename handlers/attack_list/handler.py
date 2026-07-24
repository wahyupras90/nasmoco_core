"""
handlers/attack_list/handler.py — INT008 Attack List

Alur sama seperti Room 4/5: Router -> Handler.match/execute -> Parser
(BaseParser, ADR025) -> Service.execute(params) -> Repository -> SQLite
-> Formatter -> HandlerResult. Tidak ada SQL/business logic di file ini
(ADR003/ADR004).
"""

from db.base_repository import RepositoryError
from handlers.attack_list import formatter
from handlers.attack_list.parser import AttackListParser
from handlers.attack_list.service import AttackListService, AttackListServiceParams
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, SUFFIX_ERROR, SUFFIX_OK, make_code
from utils.logger import get_logger

logger = get_logger(__name__)


class AttackListHandler(BaseHandler):
    intent_id = "INT008"
    name = "Attack List"

    def __init__(self, service: AttackListService = None, parser: AttackListParser = None):
        self.service = service or AttackListService()
        self.parser = parser or AttackListParser()

    def match(self, text: str) -> bool:
        return self.parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = self.parser.parse(text)
        service_params = AttackListServiceParams(
            mode=parsed.mode,
            source=parsed.source,
            status=parsed.status,
            sa_terakhir=parsed.sa_terakhir,
            segment_rfm=parsed.segment_rfm,
            program_id=parsed.program_id,
            program=parsed.program,
            period=parsed.period,
            expired_mode=parsed.expired_mode,
            wants_summary_only=parsed.wants_summary_only,
            wants_conversion_summary=parsed.wants_conversion_summary,
        )

        try:
            result = self.service.execute(service_params)
        except RepositoryError as exc:
            logger.exception("Gagal mengambil data Attack List untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data Attack List: {exc}",
            )

        if result["mode"] == "history":
            dataframe = result["history"]
        elif result["mode"] == "all":
            dataframe = result["raw_df"]
        else:
            dataframe = result["units"]

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(result),
            dataframe=dataframe,
            summary=formatter.build_summary(result),
        )