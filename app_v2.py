"""
app_v2.py — Room 3.

Melengkapi stub Room 2 menjadi aplikasi yang bisa benar-benar dipakai:
- CLI interaktif (default): `python app_v2.py`
- API endpoint di port 8001: `python app_v2.py --mode api`

Kontrak yang TIDAK diubah dari Room 2:
- `create_router()` dipertahankan sebagai titik ekstensi resmi untuk Room 4-8
  memanggil `router.register(handler, priority)`.
- Fallback tetap `NullFallbackProvider()` (ADR023) sampai Room 8 selesai.
  Room 3 TIDAK membuat implementasi Analysis/SQL Agent apa pun di sini.

Aturan yang dijaga di file ini:
- Tidak ada SQL/business logic di sini — semua request lewat Router -> Handler
  (ADR016), tidak ada shortcut ke Repository.
- Exception tak terduga dari Handler/Service/Repository tidak boleh membuat
  CLI/API crash — ditangkap di `_safe_route`, dilog via `get_logger()`, dan
  dikembalikan sebagai `HandlerResult` error dengan kode `{PREFIX}_ERROR`
  via `make_code()`.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ai.router import Router, NullFallbackProvider
from models.handler_result import HandlerResult, make_code, SUFFIX_ERROR
from utils.logger import get_logger

logger = get_logger(__name__)

API_PORT = 8001


def create_router() -> Router:
    """
    Titik ekstensi resmi untuk Room 4-8.

    Fallback tetap NullFallbackProvider() sampai Room 8 (Analysis/SQL Agent)
    selesai — ini kontrak yang disengaja (ADR023), bukan bug.
    """
    router = Router(fallback=NullFallbackProvider())

    # Room 4: History Service (INT002) & History TCARE (INT003, via
    # CompositeHistoryTCAREHandler -- ADR027). Priority INT003 > INT002
    # sekadar jaga-jaga; kedua match() sudah saling menolak kata "tcare"
    # di parser masing-masing sehingga tidak seharusnya pernah match
    # bersamaan pada teks yang sama.
    #
    # PENTING (ADR027 Bug #1 fix): priority CompositeHistoryTCAREHandler
    # (20) HARUS lebih rendah dari TCARERealtimeHandler (Room 6, 30 --
    # lihat blok registrasi Room 6 di bawah) supaya permintaan eksplisit
    # "tcare web"/"tcare realtime" menang tie-break dan langsung ke
    # INT013, bukan tercegat Composite ini.
    from handlers.history_service.handler import HistoryServiceHandler
    from handlers.history_tcare_composite.handler import CompositeHistoryTCAREHandler

    router.register(HistoryServiceHandler(), priority=10)
    router.register(CompositeHistoryTCAREHandler(), priority=20)

    # Room 5: KPI Summary (INT004), KPI Detail (INT005), Ranking (INT006),
    # WIP (INT007). Priority KPI Detail > KPI Summary sekadar jaga-jaga;
    # kedua match() sudah saling menolak (KPI Summary menolak kata
    # detail/harian/per hari/rincian, KPI Detail mewajibkannya) sehingga
    # tidak seharusnya pernah match bersamaan pada teks yang sama.
    from handlers.kpi_summary.handler import KPISummaryHandler
    from handlers.kpi_detail.handler import KPIDetailHandler
    from handlers.ranking.handler import RankingHandler
    from handlers.wip.handler import WIPHandler

    router.register(KPISummaryHandler(), priority=10)
    router.register(KPIDetailHandler(), priority=20)
    router.register(RankingHandler(), priority=10)
    router.register(WIPHandler(), priority=10)

    # Room 6: Attack List (INT008), TCARE Web Status (INT012),
    # TCARE Realtime (INT013).
    #
    # ADR027 Bug #1 fix: TCARERealtimeHandler priority DINAIKKAN ke 30
    # (bukan 10) -- match()-nya ("tcare web"/"tcare realtime") overlap
    # dengan CompositeHistoryTCAREHandler (Room4+Room6, priority 20,
    # match() juga menangkap "tcare web" lewat delegasi ke parser Room 4).
    # Tanpa ini, tie-break ADR022 (highest priority wins) membuat Composite
    # SELALU menang, jadi permintaan eksplisit "web"/"realtime" tidak
    # pernah sampai ke INT013. AttackListHandler/TCAREWebStatusHandler
    # tetap 10 (tidak ada overlap match() dengan Handler lain).
    from handlers.attack_list.handler import AttackListHandler
    from handlers.tcare_web_status.handler import TCAREWebStatusHandler
    from handlers.tcare_realtime.handler import TCARERealtimeHandler

    router.register(AttackListHandler(), priority=10)
    router.register(TCAREWebStatusHandler(), priority=10)
    router.register(TCARERealtimeHandler(), priority=30)

    # Room 7-8 mendaftarkan handler produksi masing-masing di sini.
    return router


def _safe_route(router: Router, text: str) -> HandlerResult:
    """
    Bungkus router.route() supaya exception tak terduga dari
    Handler/Service/Repository tidak membuat aplikasi crash total.
    """
    try:
        return router.route(text)
    except Exception as exc:  # noqa: BLE001 — sengaja luas, ini boundary aplikasi
        logger.exception("Unhandled exception saat routing text=%r", text)
        return HandlerResult(
            success=False,
            code=make_code("APP", SUFFIX_ERROR),
            message=f"Terjadi kesalahan tak terduga saat memproses permintaan: {exc}",
        )


def handler_result_to_dict(result: HandlerResult) -> dict:
    """
    Konversi HandlerResult ke bentuk JSON-serializable.

    `dataframe` (pandas.DataFrame) dikonversi eksplisit ke list-of-records.
    `summary`/`suggestions`/`metadata` sudah dict/list (lihat __post_init__
    HandlerResult), aman langsung disertakan.
    `export` sengaja TIDAK disertakan di response /query biasa — itu untuk
    endpoint export terpisah, di luar scope Room 3 saat ini.
    """
    return {
        "success": result.success,
        "code": result.code,
        "message": result.message,
        "summary": result.summary,
        "suggestions": result.suggestions,
        "dataframe": (
            result.dataframe.to_dict(orient="records")
            if result.dataframe is not None else None
        ),
        "metadata": result.metadata,
        "execution_ms": result.execution_ms,
    }


def format_result_for_cli(result: HandlerResult) -> str:
    """Format HandlerResult supaya mudah dibaca di terminal."""
    lines = [f"[{result.code}] {result.message}"]

    if result.summary:
        lines.append("summary:")
        for key, value in result.summary.items():
            lines.append(f"  {key}: {value}")

    if result.dataframe is not None and not result.dataframe.empty:
        lines.append("dataframe:")
        lines.append(result.dataframe.to_string(index=False))

    if result.suggestions:
        lines.append("suggestions:")
        for suggestion in result.suggestions:
            lines.append(f"  - {suggestion}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# A. CLI interaktif
# ---------------------------------------------------------------------------

def run_cli(router: Router) -> None:
    print("nasmoco_core CLI — ketik 'exit' atau 'quit' untuk keluar.")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            print("Bye.")
            break

        result = _safe_route(router, text)
        print(format_result_for_cli(result))


# ---------------------------------------------------------------------------
# B. API endpoint (port 8001)
# ---------------------------------------------------------------------------

class _QueryAPIHandler(BaseHTTPRequestHandler):
    """
    HTTP handler minimal berbasis stdlib (tanpa dependency tambahan):
      GET  /health -> {"status": "ok"}
      POST /query  -> {"text": "..."} -> HandlerResult sebagai JSON
    """

    router: Router = None  # di-set per instance server via subclass dinamis

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (nama method ditentukan BaseHTTPRequestHandler)
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/query":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b""
            payload = json.loads(raw_body) if raw_body else {}
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": f"invalid JSON body: {exc}"})
            return

        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            self._send_json(400, {"error": "field 'text' (string, non-empty) wajib diisi"})
            return

        result = _safe_route(self.router, text)
        self._send_json(200, handler_result_to_dict(result))

    def log_message(self, fmt, *args):  # redirect log bawaan http.server ke logger aplikasi
        logger.info("%s - %s", self.address_string(), fmt % args)


def build_api_server(router: Router, port: int = API_PORT) -> ThreadingHTTPServer:
    """Factory terpisah dari serve_forever() supaya mudah ditest."""
    handler_cls = type("QueryAPIHandler", (_QueryAPIHandler,), {"router": router})
    return ThreadingHTTPServer(("0.0.0.0", port), handler_cls)


def run_api(router: Router, port: int = API_PORT) -> None:
    server = build_api_server(router, port=port)
    logger.info("API listening on port %d", port)
    print(f"nasmoco_core API listening on http://0.0.0.0:{port}  (POST /query, GET /health)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="nasmoco_core app_v2")
    parser.add_argument(
        "--mode", choices=["cli", "api"], default="cli",
        help="cli: loop interaktif terminal (default). api: HTTP server di port 8001.",
    )
    parser.add_argument("--port", type=int, default=API_PORT, help="port untuk --mode api")
    args = parser.parse_args()

    router = create_router()

    if args.mode == "api":
        run_api(router, port=args.port)
    else:
        run_cli(router)


if __name__ == "__main__":
    main()
