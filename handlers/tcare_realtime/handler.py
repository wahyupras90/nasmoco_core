"""
handlers/tcare_realtime/handler.py — INT013 TCARE Realtime per VIN

Alur: Router -> Handler.match/execute -> Parser -> Service -> WebRepository
(HTTP, ADR026) -> Formatter -> HandlerResult.

Aturan wajib (brief Room 6, beda dari Handler SQLite biasa):
- Kegagalan login/timeout/parsing HARUS ditangkap di sini dan dikembalikan
  sebagai HandlerResult code INT013_ERROR -- TIDAK BOLEH membuat app_v2.py
  crash (konsisten dengan _safe_route Room 3, ini lapis pertahanan kedua).
- Kegagalan PER-VIN (VIN tidak ditemukan, halaman gagal di-parse) BUKAN
  error di level Handler -- itu bagian hasil normal (lihat formatter.py),
  karena satu VIN gagal tidak boleh menggagalkan VIN lain yang diminta
  bersamaan.
"""

import pandas as pd

from handlers.tcare_realtime import formatter
from handlers.tcare_realtime.parser import TCARERealtimeParser
from handlers.tcare_realtime.service import TCARERealtimeParams, TCARERealtimeService
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, SUFFIX_ERROR, SUFFIX_OK, make_code
from utils.logger import get_logger

logger = get_logger(__name__)


class TCARERealtimeHandler(BaseHandler):
    intent_id = "INT013"
    name = "TCARE Realtime"

    def __init__(self, service: TCARERealtimeService = None, parser: TCARERealtimeParser = None):
        self.service = service or TCARERealtimeService()
        self.parser = parser or TCARERealtimeParser()

    def match(self, text: str) -> bool:
        return self.parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = self.parser.parse(text)

        if not parsed.vins:
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, "NOT_FOUND"),
                message="Tidak ada nomor rangka/VIN yang terdeteksi pada permintaan ini.",
            )

        service_params = TCARERealtimeParams(vins=parsed.vins)

        try:
            results = self.service.execute(service_params)
        except ValueError as exc:
            # Kredensial TAM_EMAIL/TAM_PASSWORD belum diisi di config -- ini
            # error konfigurasi, bukan kegagalan network/parsing per-VIN.
            logger.error("Konfigurasi TCARE Realtime tidak lengkap: %s", exc)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Konfigurasi TCARE Realtime belum lengkap: {exc}",
            )
        except Exception as exc:  # noqa: BLE001 -- lapis pertahanan wajib, lihat docstring
            logger.exception("Gagal menjalankan TCARE Realtime untuk %r", text)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=f"Terjadi kesalahan saat mengambil data TCARE Realtime: {exc}",
            )

        combined_services = _combine_services(results)

        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=formatter.format_message(results),
            dataframe=combined_services,
            summary=formatter.build_summary(results),
            metadata={
                "vehicle_customer_per_vin": [
                    {
                        "vin": r.vin,
                        "vehicle": r.vehicle.to_dict("records") if r.ok and r.vehicle is not None else None,
                        "customer": r.customer.to_dict("records") if r.ok and r.customer is not None else None,
                    }
                    for r in results
                ]
            },
        )


def _combine_services(results) -> pd.DataFrame:
    """Gabungkan histori service semua VIN yang berhasil jadi satu DataFrame
    (kolom `vin` ditambahkan di depan) -- ini yang jadi HandlerResult.dataframe
    utama, cocok untuk export/tabel di UI."""
    frames = []
    for r in results:
        if r.ok and r.services is not None and not r.services.empty:
            df = r.services.copy()
            df.insert(0, "vin", r.vin)
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["vin", "kunjungan", "tanggal", "dealer", "tepat", "status", "ontime_service"])

    return pd.concat(frames, ignore_index=True)
