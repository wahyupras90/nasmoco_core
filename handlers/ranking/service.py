"""
handlers/ranking/service.py

Business logic INT006 (Ranking). ADR004.

Alur:
  1. Ambil agregat `daily_kpi` per SA pada rentang bulan (Repository
     sudah exclude `sa='Counter'`, BR027/keputusan bisnis dikonfirmasi).
  2. Urutkan menurun berdasarkan metrik yang diminta (default revenue),
     beri nomor rank 1..N.
  3. Kalau target tersedia untuk (tahun,bulan) -- JOIN target per SA
     (Repository sudah exclude `sa='TOTAL'`) untuk menampilkan capaian
     (%), tapi urutan rank TETAP berdasarkan angka aktual, BUKAN %
     capaian (keputusan default; belum ada permintaan eksplisit untuk
     rank berdasarkan % capaian).
  4. Baris agregat outlet (`sa='TOTAL'`) DITAMPILKAN TERPISAH di akhir,
     TIDAK diberi nomor rank (dikonfirmasi eksplisit user: "jangan
     dimasukkan ke rank, jadikan di terakhir karena jumlah").
"""

from dataclasses import dataclass

import pandas as pd

from handlers._shared.period_parser import ParsedPeriod, month_date_range
from models.base_service import BaseService
from repositories.ranking_repository import RankingRepository


@dataclass
class RankingParams:
    metric: str
    period: ParsedPeriod


class RankingService(BaseService):
    def __init__(self, repo: RankingRepository = None):
        self.repo = repo or RankingRepository()

    def execute(self, params: RankingParams) -> dict:
        date_from, date_to = month_date_range(params.period.tahun, params.period.bulan)
        source_df = self.repo.get_ranking_source(date_from, date_to)

        target_available_for_year = self.repo.has_target_for_year(params.period.tahun)
        targets_df = pd.DataFrame()
        if target_available_for_year:
            targets_df = self.repo.get_targets_for_ranking(
                params.period.tahun, params.period.bulan
            )

        ranked_df = _build_ranking(source_df, targets_df, params.metric)

        outlet_total = self.repo.get_outlet_total(params.period.tahun, params.period.bulan)

        return {
            "status": "ok",
            "metric": params.metric,
            "period": params.period,
            "ranking": ranked_df,
            "outlet_total": outlet_total,
            "target_year_covered": target_available_for_year,
        }


def _build_ranking(source_df: pd.DataFrame, targets_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    if source_df.empty:
        return source_df

    df = source_df.copy()

    if not targets_df.empty:
        target_col_map = {
            "revenue": "target_revenue",
            "cpus": "target_cpus",
            "total_liter": "target_liter",
        }
        target_col = target_col_map.get(metric)
        if target_col and target_col in targets_df.columns:
            df = df.merge(
                targets_df[["sa", target_col]], on="sa", how="left"
            )
            df["pct_capaian"] = df.apply(
                lambda row: round((row[metric] / row[target_col]) * 100, 1)
                if row.get(target_col) else None,
                axis=1,
            )

    df = df.sort_values(by=metric, ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df
