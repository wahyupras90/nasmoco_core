"""
handlers/tcare_realtime/service.py — INT013 TCARE Realtime per VIN

ADR026: Service ini memakai TCARERealtimeWebRepository (HTTP source), BUKAN
BaseRepository/SQLite. Kontrak Service (execute(params) -> Any) tidak
berubah -- Handler di atasnya tidak perlu tahu bedanya.

TIDAK menulis ke nasmoco.db sama sekali (brief Room 6). TIDAK ada retry
otomatis di sini -- satu percobaan per VIN, kegagalan dikembalikan sebagai
bagian hasil (lihat VinFetchResult.error), bukan exception yang menjalar.

Repository dibuat BARU per pemanggilan execute() (bukan disimpan sebagai
instance state jangka panjang di Service) supaya sesuai keputusan
session-per-request -- lihat __init__ untuk detail.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from config import settings
from models.base_service import BaseService
from repositories.tcare_realtime_web_repository import (
    TCARERealtimeWebRepository,
    VinFetchResult,
)


@dataclass
class TCARERealtimeParams:
    vins: List[str] = field(default_factory=list)


class TCARERealtimeService(BaseService):
    def __init__(self, repo_factory=None):
        """
        `repo_factory`: callable tanpa argumen yang mengembalikan instance
        TCARERealtimeWebRepository baru. Default-nya membuat instance baru
        dari kredensial di config.settings setiap kali dipanggil --
        session-per-request (thread-safety untuk ThreadingHTTPServer
        app_v2.py, disetujui Room 0). Injectable untuk unit test (mock).
        """
        self._repo_factory = repo_factory or self._default_repo_factory

    @staticmethod
    def _default_repo_factory() -> TCARERealtimeWebRepository:
        return TCARERealtimeWebRepository(
            email=settings.TAM_EMAIL,
            password=settings.TAM_PASSWORD,
            timeout=(settings.TAM_TIMEOUT_CONNECT, settings.TAM_TIMEOUT_READ),
        )

    def execute(self, params: TCARERealtimeParams) -> List[VinFetchResult]:
        if not params.vins:
            return []

        repo = self._repo_factory()
        return repo.get_multiple(params.vins)

    # ------------------------------------------------------------------
    # ADR027 — method aditif untuk CompositeHistoryTCAREHandler.
    # TIDAK mengubah execute()/_default_repo_factory di atas sama sekali.
    # ------------------------------------------------------------------

    def credentials_configured(self) -> bool:
        """Cek TAM_EMAIL/TAM_PASSWORD terisi TANPA mencoba login sungguhan
        -- dipakai CompositeHistoryTCAREHandler untuk skip fallback diam-diam
        kalau kredensial belum diisi (ADR027, poin keputusan #6)."""
        return bool(settings.TAM_EMAIL) and bool(settings.TAM_PASSWORD)

    def get_single(self, no_rangka: str) -> VinFetchResult:
        """Fetch satu VIN, dipakai CompositeHistoryTCAREHandler (ADR027).
        Session-per-request tetap berlaku (repo baru dibuat lewat
        _repo_factory, sama seperti execute())."""
        repo = self._repo_factory()
        return repo.get_vin_data(no_rangka)
