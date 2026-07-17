"""
handlers/history_tcare_composite/handler.py — ADR027 (+ REVISI 2 bug)

Composite Handler: menggantikan registrasi HistoryTCAREHandler polos di
create_router(). Perilaku untuk kasus normal (riwayat TCARE lokal ADA)
IDENTIK dengan HistoryTCAREHandler asli (Room 4) -- dipanggil apa adanya,
TIDAK dimodifikasi sama sekali.

## Riwayat revisi (jangan dihapus, ini keputusan Room 0 -- lihat brief)

**Bug #1 (fixed di app_v2.py, BUKAN di file ini):** `TCARERealtimeHandler`
(match "tcare web"/"tcare realtime") dan Composite ini sama-sama match()
untuk teks yang mengandung "tcare web" -- tie-break ADR022 (highest
priority wins) membuat Composite selalu menang walau user eksplisit minta
"web". Fix: `TCARERealtimeHandler` dinaikkan ke priority 30 (dari 10),
Composite tetap 20 -- permintaan eksplisit "web" langsung ke INT013,
independen dari Composite.

**Bug #2 (fixed di file ini):** Definisi "kosong" ADR027 versi awal cuma
cek `code == INT003_NOT_FOUND`. Tapi `HistoryTCAREService` (Room 4, LOGIC
BENAR untuk tujuannya sendiri, TIDAK diubah) sengaja mengembalikan
`INT003_OK` (bukan NOT_FOUND) kalau `unit_info` ADA tapi riwayat TCARE-nya
nol baris -- supaya identitas kendaraan tetap tampil. Kasus ini lolos dari
kondisi lama, fallback tidak pernah dicoba. Definisi "kosong" diperluas
mencakup `success=True` + `summary["total_riwayat_tcare"] == 0`.

Untuk kasus ini, kalau web JUGA tidak punya riwayat (dikonfirmasi Wahyu):
tampilkan identitas kendaraan (dari hasil lokal asli) + keterangan
"bukan TCARE", BUKAN NOT_FOUND/ERROR -- kendaraan DITEMUKAN, cuma memang
bukan peserta TCARE. Beda dari kasus NOT_FOUND total (kendaraan benar-benar
tidak dikenal sama sekali).

**Bug #3 (fixed di file ini, ditemukan Wahyu 2026-07-16):** Definisi
"kosong" versi Bug #2 (`total_riwayat_tcare == 0`) ternyata masih kurang
tepat. `total_riwayat_tcare` menghitung JUMLAH BARIS JADWAL (mis. 7 baris
untuk milestone 1K-60K), BUKAN jumlah kunjungan yang BENAR-BENAR terjadi.
Kasus nyata: unit dengan 7 baris jadwal, tapi SEMUANYA `status='pending'`,
`bulan_realisasi=None` (tidak pernah direalisasi), dan `expired=1` (semua
sudah lewat batas) -- `total_riwayat_tcare` tetap 7 (bukan 0), jadi
fallback TIDAK pernah dicoba, padahal secara bisnis customer ini belum
pernah sekalipun menyelesaikan TCARE (riwayat efektifnya kosong).

**Definisi "kosong" DIPERBAIKI** (dikonfirmasi Wahyu): bukan cuma
`total_riwayat_tcare == 0`, tapi diperluas mencakup juga "SEMUA baris
jadwal punya `bulan_realisasi` kosong/None" (tidak ada satupun yang
benar-benar terealisasi) -- lihat `_is_effectively_empty()`. Kalau
minimal SATU baris punya `bulan_realisasi` terisi, dianggap ADA riwayat
nyata, TIDAK fallback ke web (meski baris lain masih pending).


disebutkan di brief revisi, ditandai jelas supaya Room 0 bisa koreksi):
kalau fallback untuk kasus "OK-tapi-kosong" ini gagal TEKNIS (bukan
"web juga kosong"), saya kembalikan `local_result` apa adanya (bukan
error) -- karena identitas kendaraan dari lokal sudah valid dan bernilai,
tidak pantas di-downgrade jadi error hanya karena pengecekan tambahan
(yang sifatnya suplementer) gagal. Ini beda dari kasus NOT_FOUND total,
di mana kegagalan teknis MEMANG jadi ERROR karena tidak ada apa pun lain
untuk ditampilkan ke user.
"""

from handlers.history_tcare import parser as room4_parser
from handlers.history_tcare.handler import HistoryTCAREHandler
from handlers.history_tcare_composite import formatter as composite_formatter
from handlers.tcare_realtime.service import TCARERealtimeService
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, SUFFIX_ERROR, SUFFIX_NOT_FOUND, SUFFIX_OK, make_code
from utils.logger import get_logger

logger = get_logger(__name__)

_INTENT_ID = "INT003"
_LOCAL_NOT_FOUND_CODE = make_code(_INTENT_ID, SUFFIX_NOT_FOUND)
_LOCAL_OK_CODE = make_code(_INTENT_ID, SUFFIX_OK)


class CompositeHistoryTCAREHandler(BaseHandler):
    """Menggantikan registrasi HistoryTCAREHandler polos di create_router().

    TIDAK mengubah handlers/history_tcare/* (Room 4) atau
    handlers/tcare_realtime/* (Room 6) -- keduanya dipakai apa adanya lewat
    import biasa (read-only usage, pola sama seperti CustomerProfileRepository
    shared di BR027).

    PENTING (Bug #1): priority registrasi handler ini di app_v2.py HARUS
    lebih rendah dari TCARERealtimeHandler (20 vs 30) supaya permintaan
    eksplisit "tcare web"/"tcare realtime" langsung ke INT013, tidak
    "tercegat" Composite ini lewat tie-break Router.
    """

    intent_id = _INTENT_ID
    name = "History TCARE (+ Web Fallback)"

    def __init__(
        self,
        local_handler: HistoryTCAREHandler = None,
        web_service: TCARERealtimeService = None,
    ):
        self._local_handler = local_handler or HistoryTCAREHandler()
        self._web_service = web_service or TCARERealtimeService()

    def match(self, text: str) -> bool:
        # Delegasikan match() ke handler lokal apa adanya -- kriteria
        # "apakah ini query History TCARE" tidak berubah sama sekali.
        return self._local_handler.match(text)

    def execute(self, text: str) -> HandlerResult:
        local_result = self._local_handler.execute(text)

        is_local_not_found = local_result.code == _LOCAL_NOT_FOUND_CODE
        is_local_ok_but_empty = (
            local_result.success
            and local_result.code == _LOCAL_OK_CODE
            and self._is_effectively_empty(local_result.dataframe)
        )

        if not is_local_not_found and not is_local_ok_but_empty:
            return local_result  # kasus normal (riwayat ADA) -- tidak berubah sama sekali

        no_rangka = self._resolve_no_rangka(text, local_result, is_local_not_found)
        if no_rangka is None:
            if is_local_not_found:
                # UX hint (disetujui Room 0, non-blocking): user tidak tahu
                # kenapa fallback web tidak dicoba untuk pencarian plat/nama
                # -- beri petunjuk, bukan diam saja. Ini MURNI tambahan teks
                # pesan, TIDAK mengubah success/code/logic apa pun.
                return self._add_no_web_lookup_hint(local_result)
            return local_result

        if not self._web_service.credentials_configured():
            logger.warning(
                "Fallback web TAM di-skip: kredensial TAM_EMAIL/TAM_PASSWORD "
                "belum diisi. text=%r", text
            )
            return local_result

        try:
            web_result = self._web_service.get_single(no_rangka)
        except Exception as exc:  # noqa: BLE001 -- lapis pertahanan wajib, ADR021
            logger.exception("Fallback web TAM gagal teknis (exception) untuk %r", no_rangka)
            return self._handle_web_technical_failure(local_result, is_local_not_found, str(exc))

        web_has_history = (
            web_result.ok
            and web_result.services is not None
            and not web_result.services.empty
        )

        if is_local_not_found:
            # -- Alur lama, TIDAK berubah dari ADR027 versi awal --
            if web_result.ok:
                return self._build_success_from_web(no_rangka, web_result)

            if composite_formatter.is_not_found_error(web_result.error):
                return HandlerResult(
                    success=False,
                    code=make_code(self.intent_id, SUFFIX_NOT_FOUND),
                    message="Tidak ditemukan di database lokal maupun di web TAM.",
                )

            logger.warning("Fallback web TAM gagal teknis untuk %r: %s", no_rangka, web_result.error)
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=(
                    f"Tidak ditemukan di database lokal. Percobaan cek realtime "
                    f"ke web TAM gagal: {web_result.error}. Coba lagi nanti."
                ),
            )

        # -- is_local_ok_but_empty (BARU, fix Bug #2) --
        if web_has_history:
            # Web ternyata punya riwayat yang lokal tidak punya -> pakai
            # data web, sama seperti kasus NOT_FOUND (prefix transparansi).
            return self._build_success_from_web(no_rangka, web_result)

        if web_result.ok or composite_formatter.is_not_found_error(web_result.error):
            # Web juga tidak punya riwayat (baik VIN ditemukan tapi 0
            # kunjungan, ATAU VIN memang tidak terdaftar di web) -> unit
            # ini memang BUKAN peserta TCARE. Identitas kendaraan (dari
            # hasil lokal ASLI) tetap ditampilkan -- BUKAN NOT_FOUND/ERROR,
            # karena kendaraannya DITEMUKAN dan diketahui identitasnya.
            return self._build_bukan_tcare_result(local_result)

        # Kegagalan teknis saat mengecek "OK-tapi-kosong" -- keputusan
        # desain saya sendiri (lihat catatan di docstring modul): kembalikan
        # local_result apa adanya, JANGAN di-downgrade jadi ERROR, karena
        # identitas kendaraan dari lokal sudah valid dan bernilai.
        return self._handle_web_technical_failure(local_result, is_local_not_found, web_result.error)

    def _add_no_web_lookup_hint(self, local_result: HandlerResult) -> HandlerResult:
        """Kasus NOT_FOUND lokal dengan identifier plat/nama (bukan
        no_rangka) -- fallback ke web TIDAK mungkin (web TAM cuma bisa
        lookup per VIN, lihat docstring `_resolve_no_rangka`). Disetujui
        Room 0: beri petunjuk ke user kenapa tidak coba ke web, bukan
        diam saja -- murni tambahan teks, success/code/data tidak berubah."""
        hint = (
            "\n\nCatatan: Web TAM hanya bisa dicek pakai nomor rangka (VIN) "
            "-- kalau kamu punya VIN kendaraan ini, coba tanya lagi pakai "
            "VIN-nya."
        )
        return HandlerResult(
            success=local_result.success,
            code=local_result.code,
            message=f"{local_result.message}{hint}",
            dataframe=local_result.dataframe,
            summary=local_result.summary,
            metadata=local_result.metadata,
        )

    @staticmethod
    def _is_effectively_empty(schedule_df) -> bool:
        """Definisi "kosong" untuk trigger fallback web (Bug #3, dikonfirmasi
        Wahyu 2026-07-16): dataframe kosong (0 baris) ATAU semua baris
        jadwal punya `bulan_realisasi` kosong/None (tidak ada satupun yang
        benar-benar terealisasi). Bukan sekadar jumlah baris jadwal --
        unit bisa punya banyak baris jadwal (mis. 7 milestone 1K-60K) tapi
        SEMUANYA masih pending & sudah expired, tetap dianggap "kosong"
        secara efektif."""
        if schedule_df is None or schedule_df.empty:
            return True
        if "bulan_realisasi" not in schedule_df.columns:
            # Kolom tidak ada -- tidak bisa dipastikan, JANGAN anggap
            # kosong (fail-safe) supaya tidak salah trigger fallback.
            return False
        col = schedule_df["bulan_realisasi"]
        is_blank = col.isna() | (col.astype(str).str.strip() == "") | (col.astype(str).str.lower() == "none")
        return bool(is_blank.all())

    def _handle_web_technical_failure(self, local_result, is_local_not_found: bool, error_text: str) -> HandlerResult:
        if is_local_not_found:
            return HandlerResult(
                success=False,
                code=make_code(self.intent_id, SUFFIX_ERROR),
                message=(
                    f"Tidak ditemukan di database lokal. Percobaan cek "
                    f"realtime ke web TAM gagal: {error_text}. Coba lagi nanti."
                ),
            )
        logger.warning(
            "Pengecekan fallback web TAM gagal teknis untuk unit yang sudah "
            "dikenal lokal (riwayat kosong): %s. Mengembalikan hasil lokal apa adanya.",
            error_text,
        )
        return local_result

    def _build_success_from_web(self, no_rangka: str, web_result) -> HandlerResult:
        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=composite_formatter.format_web_message(web_result),
            dataframe=web_result.services,
            summary=composite_formatter.build_web_summary(no_rangka, web_result),
            metadata={"source": "web_tam_realtime"},
        )

    def _build_bukan_tcare_result(self, local_result: HandlerResult) -> HandlerResult:
        message = (
            f"{local_result.message}\n\n"
            f"Keterangan: Kendaraan ini tidak memiliki riwayat TCARE "
            f"(bukan peserta program TCARE, atau belum pernah dijadwalkan)."
        )
        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message=message,
            dataframe=local_result.dataframe,
            summary=local_result.summary,
            metadata={"source": "local", "tcare_history_checked_web": True},
        )

    @staticmethod
    def _resolve_no_rangka(text: str, local_result: HandlerResult, is_local_not_found: bool):
        """Resolusi no_rangka untuk lookup web -- BEDA sumber tergantung kasus:

        - NOT_FOUND lokal: belum ada resolusi apa pun dari Room 4, jadi
          reuse parser Room 4 (`room4_parser.parse()`) langsung dari teks.
          HANYA kalau identifier_type == "no_rangka" -- web TAM cuma bisa
          lookup per VIN, dan kalau lokal NOT_FOUND untuk pencarian
          plate/nama, kita tidak punya VIN untuk dicoba (itu justru yang
          gagal ditemukan).
        - OK-tapi-kosong: Room 4 SUDAH berhasil resolve unit secara unik
          (apa pun cara user mencari -- nama/plat/no_rangka), no_rangka
          hasil resolusi itu ada di `local_result.summary["no_rangka"]`
          (lihat `handlers/history_tcare/formatter.py::build_summary`).
          Pakai itu langsung, TIDAK perlu re-parse teks atau batasan
          identifier_type -- karena unitnya sudah pasti diketahui.
        """
        if is_local_not_found:
            parsed = room4_parser.parse(text)
            if parsed is None or parsed.identifier_type != "no_rangka":
                return None
            return parsed.customer_identifier

        return local_result.summary.get("no_rangka")