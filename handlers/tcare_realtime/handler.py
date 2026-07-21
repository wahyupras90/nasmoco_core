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

## Dukungan pencarian by-nama (brief Wahyu via Room 0)

Kalau parser tidak menemukan VIN langsung TAPI menemukan nama customer,
Handler resolve nama itu dulu (reuse `CustomerNameResolver`, yang reuse
Repository Room 4 -- lihat `name_resolver.py`) SEBELUM lanjut ke
WebRepository:
- 0 kandidat -> NOT_FOUND (pesan spesifik nama, beda dari NOT_FOUND
  "tidak ada VIN terdeteksi" untuk kasus tidak ada input sama sekali).
- >1 kandidat -> AMBIGUOUS, tampilkan daftar, TIDAK lanjut ke web TAM
  sama sekali (keputusan eksplisit Wahyu -- jangan otomatis pilih satu).
- 1 kandidat -> lanjut ke alur VIN biasa (tidak ada percabangan lagi
  setelah titik ini, sama seperti kalau user ketik VIN langsung).

Input VIN langsung (perilaku lama) TIDAK berubah sama sekali -- kondisi
`if parsed.vins:` di awal `execute()` identik dengan sebelum fitur ini.
"""

import pandas as pd

from handlers.tcare_realtime import formatter
from handlers.tcare_realtime.name_resolver import CustomerNameResolver
from handlers.tcare_realtime.parser import TCARERealtimeParser
from handlers.tcare_realtime.service import TCARERealtimeParams, TCARERealtimeService
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, SUFFIX_AMBIGUOUS, SUFFIX_ERROR, SUFFIX_NOT_FOUND, SUFFIX_OK, make_code
from utils.logger import get_logger

logger = get_logger(__name__)


class TCARERealtimeHandler(BaseHandler):
    intent_id = "INT013"
    name = "TCARE Realtime"

    def __init__(
        self,
        service: TCARERealtimeService = None,
        parser: TCARERealtimeParser = None,
        name_resolver: CustomerNameResolver = None,
    ):
        self.service = service or TCARERealtimeService()
        self.parser = parser or TCARERealtimeParser()
        self.name_resolver = name_resolver or CustomerNameResolver()

    def match(self, text: str) -> bool:
        return self.parser.match(text)

    def execute(self, text: str) -> HandlerResult:
        parsed = self.parser.parse(text)

        vins = parsed.vins

        if not vins and parsed.customer_name:
            # Fitur baru: resolusi by-nama SEBELUM ke WebRepository.
            resolution = self.name_resolver.resolve(parsed.customer_name)

            if resolution.count == 0:
                return HandlerResult(
                    success=False,
                    code=make_code(self.intent_id, SUFFIX_NOT_FOUND),
                    message=formatter.format_name_not_found_message(parsed.customer_name),
                )

            if resolution.count > 1:
                return HandlerResult(
                    success=False,
                    code=make_code(self.intent_id, SUFFIX_AMBIGUOUS),
                    message=formatter.format_ambiguous_message(
                        parsed.customer_name, resolution.candidates
                    ),
                    suggestions=formatter.build_ambiguous_suggestions(resolution.candidates),
                )

            # Tepat 1 kandidat -- lanjut ke alur VIN biasa, tidak ada
            # percabangan lagi setelah titik ini.
            vins = [resolution.candidates.iloc[0]["no_rangka"]]

        if not vins:
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_NOT_FOUND),
                message="Tidak ada nomor rangka/VIN yang terdeteksi pada permintaan ini.",
            )

        service_params = TCARERealtimeParams(vins=vins)

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