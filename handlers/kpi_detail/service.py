"""
handlers/kpi_detail/service.py

Business logic INT005 (KPI Detail -- rincian per hari). ADR004.

Beda dengan INT004 (KPI Summary): tidak menjumlahkan `daily_kpi`, tapi
mengembalikan baris per-hari apa adanya (BR026) supaya user bisa lihat
tren harian, plus ringkasan kecil (total & rata-rata) sebagai konteks.

Resolusi SA sama seperti INT004: verifikasi ke Repository, BUKAN
whitelist hardcoded (KPIRepository dipakai BERSAMA, BR027).
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from handlers._shared.period_parser import ParsedPeriod, month_date_range
from models.base_service import BaseService
from repositories.kpi_repository import KPIRepository


@dataclass
class KPIDetailParams:
    sa_candidate: Optional[str]
    period: ParsedPeriod


class KPIDetailService(BaseService):
    def __init__(self, repo: KPIRepository = None):
        self.repo = repo or KPIRepository()

    def execute(self, params: KPIDetailParams) -> dict:
        sa = None
        if params.sa_candidate is not None:
            known_sa = self.repo.get_distinct_sa()
            if params.sa_candidate not in known_sa:
                return {"status": "not_found", "sa_candidate": params.sa_candidate}
            sa = params.sa_candidate

        date_from, date_to = month_date_range(params.period.tahun, params.period.bulan)
        daily_df = self.repo.get_daily(date_from, date_to, sa=sa)

        return {
            "status": "ok",
            "sa": sa,
            "period": params.period,
            "daily": daily_df,
        }
