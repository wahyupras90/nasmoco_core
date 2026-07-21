"""
handlers/tcare_realtime/name_resolver.py — INT013 TCARE Realtime, resolusi
identitas by-nama customer.

Ditambahkan setelah brief permintaan Wahyu (via Room 0): user harus bisa
cari TCARE web pakai nama customer, bukan cuma VIN langsung.

REUSE MURNI dari Room 4, TIDAK ADA file Room 4 yang diubah:
- `repositories.customer_profile_repository.CustomerProfileRepository`
  (prioritas mutlak, dipakai bersama lintas Room sejak awal -- ADR008)
- `repositories.history_service_repository.HistoryServiceRepository`
  (method `find_identity_by_customer_name_in_unitmasuk()`, fallback
  kalau `customer_profile` 0 hasil)

Pola persis sama dengan `handlers/history_service/service.py` (INT002,
sudah di-approve Room 0): `customer_profile` dicoba dulu SELALU;
`unitmasuk` HANYA dicoba kalau `customer_profile` benar-benar 0 hasil.
TIDAK ADA penggabungan kandidat dari dua sumber sekaligus.

Root cause fallback ini (dikonfirmasi Room 0 lewat kasus INT002): lag
ETL bulanan yang wajar -- customer baru "belum ada" di `customer_profile`
sampai siklus ETL berikutnya, bukan data cacat.
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from repositories.customer_profile_repository import CustomerProfileRepository
from repositories.history_service_repository import HistoryServiceRepository


@dataclass
class NameResolutionResult:
    candidates: pd.DataFrame  # kolom minimal: no_rangka, customer, model, no_polisi
    used_fallback: bool = False

    @property
    def count(self) -> int:
        return len(self.candidates)


class CustomerNameResolver:
    """Resolusi nama customer -> kandidat no_rangka, reuse Repository Room 4."""

    def __init__(
        self,
        customer_profile_repo: CustomerProfileRepository = None,
        history_service_repo: HistoryServiceRepository = None,
    ):
        self._customer_profile_repo = customer_profile_repo or CustomerProfileRepository()
        self._history_service_repo = history_service_repo or HistoryServiceRepository()

    def resolve(self, customer_name: str) -> NameResolutionResult:
        profiles = self._customer_profile_repo.get_by_customer_name(customer_name)

        if not profiles.empty:
            return NameResolutionResult(candidates=profiles, used_fallback=False)

        # customer_profile 0 hasil -> fallback ke unitmasuk (persis pola INT002).
        fallback_profiles = self._history_service_repo.find_identity_by_customer_name_in_unitmasuk(
            customer_name
        )
        return NameResolutionResult(candidates=fallback_profiles, used_fallback=True)