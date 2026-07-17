"""
repositories/tcare_web_status_repository.py — INT012 TCARE Web Status

Query Handler biasa (pola Room 4/5) -- tidak ada yang baru secara arsitektur,
cuma domain data baru. Tabel di-refresh scheduler Windows Task Scheduler
(etl_tcare_web.py), DI LUAR nasmoco_core -- Repository ini hanya membaca.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from db.base_repository import BaseRepository


class TCAREWebStatusRepository(BaseRepository):

    def find_vehicle(self, no_rangka: str) -> pd.DataFrame:
        sql = """
            SELECT *
            FROM tcare_web_vehicle
            WHERE no_rangka = ?
        """
        return self.execute(sql, [no_rangka])

    def find_service(self, no_rangka: str) -> pd.DataFrame:
        sql = """
            SELECT *
            FROM tcare_web_service
            WHERE no_rangka = ?
            ORDER BY service_date DESC
        """
        return self.execute(sql, [no_rangka])

    def find_error(self, no_rangka: Optional[str] = None) -> pd.DataFrame:
        """Unit yang gagal di-scrape terakhir kali. Kalau no_rangka None,
        kembalikan semua error terbaru."""
        if no_rangka is not None:
            sql = "SELECT * FROM tcare_web_errors WHERE no_rangka = ?"
            params = [no_rangka]
        else:
            sql = "SELECT * FROM tcare_web_errors"
            params = []
        return self.execute(sql, params)
