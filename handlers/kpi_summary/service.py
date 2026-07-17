"""
handlers/kpi_summary/service.py

Business logic INT004 (KPI Summary). ADR004: business rule ADA di sini,
BUKAN di Repository/Handler.

Alur:
  1. Resolve `sa_candidate` (dari parser) terhadap daftar SA nyata di
     `daily_kpi` (Repository) -- BUKAN daftar hardcoded. `None` berarti
     level outlet (semua SA + Counter, sesuai konfirmasi user bahwa
     Counter tetap masuk agregat KPI vs target level outlet).
       - candidate None -> level outlet, tidak perlu resolusi.
       - candidate ada tapi TIDAK match -> NOT_FOUND.
       - candidate match -> level SA tersebut.
  2. Ambil & jumlahkan baris `daily_kpi` pada rentang bulan yang diminta
     (BR026: revenue dkk dibaca apa adanya dari kolom hasil ETL, hanya
     di-SUM, tidak dihitung ulang formulanya).
  3. Ambil target (`target_bulanan`) untuk (tahun, bulan, sa-atau-TOTAL).
     Kalau tahun di luar cakupan data target (dikonfirmasi: HANYA ada
     2026) -> tandai `target_available=False`, BUKAN 0 diam-diam.
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from handlers._shared.period_parser import ParsedPeriod, month_date_range
from models.base_service import BaseService
from repositories.kpi_repository import KPIRepository

_SUM_COLUMNS = [
    "unit_entry", "cpus", "revenue", "jasa", "tgp", "adt", "sublet",
    "upselling", "total_liter",
]


@dataclass
class KPISummaryParams:
    sa_candidate: Optional[str]
    period: ParsedPeriod


class KPISummaryService(BaseService):
    def __init__(self, repo: KPIRepository = None):
        self.repo = repo or KPIRepository()

    def execute(self, params: KPISummaryParams) -> dict:
        sa = None
        if params.sa_candidate is not None:
            known_sa = self.repo.get_distinct_sa()
            if params.sa_candidate not in known_sa:
                return {"status": "not_found", "sa_candidate": params.sa_candidate}
            sa = params.sa_candidate

        date_from, date_to = month_date_range(params.period.tahun, params.period.bulan)
        daily_df = self.repo.get_daily(date_from, date_to, sa=sa)

        totals = _sum_columns(daily_df)

        target_key = sa if sa is not None else "TOTAL"
        target_row = self.repo.get_target(params.period.tahun, params.period.bulan, target_key)
        target_available = target_row is not None
        if not target_available:
            target_available = self.repo.has_target_for_year(params.period.tahun)
            # has_target_for_year True tapi baris spesifik None berarti
            # SA/bulan itu memang tidak ada di target_bulanan (bukan
            # keterbatasan tahun) -- tetap target_available dianggap
            # False untuk baris ini, tapi dibedakan di formatter lewat
            # `target_year_covered`.
        year_covered = self.repo.has_target_for_year(params.period.tahun)

        return {
            "status": "ok",
            "sa": sa,
            "period": params.period,
            "totals": totals,
            "hari_terisi": 0 if daily_df.empty else int(daily_df["tanggal"].nunique()),
            "target": target_row,
            "target_year_covered": year_covered,
        }


def _sum_columns(df: pd.DataFrame) -> dict:
    if df.empty:
        return {col: 0.0 for col in _SUM_COLUMNS}
    return {col: float(df[col].fillna(0).sum()) for col in _SUM_COLUMNS if col in df.columns}
