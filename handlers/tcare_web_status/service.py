"""
handlers/tcare_web_status/service.py — INT012 TCARE Web Status

Query Handler biasa (pola Room 4/5) -- tidak ada business rule khusus,
Repository sudah membaca tabel yang sudah bersih hasil scraping scheduler.
"""

from dataclasses import dataclass
from typing import Optional

from models.base_service import BaseService
from repositories.tcare_web_status_repository import TCAREWebStatusRepository


@dataclass
class TCAREWebStatusServiceParams:
    no_rangka: Optional[str] = None
    wants_errors: bool = False


class TCAREWebStatusService(BaseService):
    def __init__(self, repo: TCAREWebStatusRepository = None):
        self.repo = repo or TCAREWebStatusRepository()

    def execute(self, params: TCAREWebStatusServiceParams) -> dict:
        if params.wants_errors:
            errors_df = self.repo.find_error(no_rangka=params.no_rangka)
            return {"mode": "errors", "no_rangka": params.no_rangka, "errors": errors_df}

        if not params.no_rangka:
            return {"mode": "missing_no_rangka"}

        vehicle_df = self.repo.find_vehicle(params.no_rangka)
        service_df = self.repo.find_service(params.no_rangka)

        return {
            "mode": "detail",
            "no_rangka": params.no_rangka,
            "vehicle": vehicle_df,
            "service": service_df,
            "found": not vehicle_df.empty,
        }
