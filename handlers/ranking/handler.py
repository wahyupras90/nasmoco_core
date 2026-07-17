"""
handlers/ranking/handler.py

RankingHandler (INT006).
"""

from db.base_repository import RepositoryError
from handlers.ranking import formatter, parser
from handlers.ranking.service import RankingParams, RankingService
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, SUFFIX_ERROR, SUFFIX_OK, make_code
from utils.logger import get_logger

logger = get_logger(__name__)


class RankingHandler(BaseHandler):
    intent_id = "INT006"
    name = "Ranking"

    def __init__(self, service: RankingService = None):
        self.service = service or RankingService()

    def match(self, text: str) -> bool:
        return parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = parser.parse(text)
        service_params = RankingParams(metric=parsed.metric, period=parsed.period)

        try:
            result = self.service.execute(service_params)
        except RepositoryError as exc:
            logger.exception("Gagal mengambil ranking untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data ranking: {exc}",
            )

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(result),
            dataframe=result["ranking"],
            summary=formatter.build_summary(result),
        )
