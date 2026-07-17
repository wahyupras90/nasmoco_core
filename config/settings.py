"""
config/settings.py

Konfigurasi terpusat untuk nasmoco_core.

Nilai default mengikuti spesifikasi Room 0. Semua nilai bisa di-override
melalui environment variable, atau melalui file `.env` di root project
(jika package `python-dotenv` tersedia).

Override yang didukung:
    NASMOCO_DB_PATH
    NASMOCO_LOG_PATH
    NASMOCO_LOG_LEVEL
    TAM_EMAIL              (Room 6, INT013 TCARE Realtime -- WAJIB diisi via
                             env var/.env, TIDAK ADA default hardcode)
    TAM_PASSWORD           (sama seperti di atas)
    TAM_TIMEOUT_CONNECT    (detik, default 10)
    TAM_TIMEOUT_READ       (detik, default 20)
"""

import os

# Muat file .env jika python-dotenv tersedia. Ini opsional — jika package
# tidak terpasang, kita lanjut memakai environment variable OS / default.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv tidak wajib
    pass


def _get_env(key: str, default: str) -> str:
    value = os.environ.get(key)
    return value if value else default


# Path ke database SQLite milik project lama (D:\AI_nasmoco).
# nasmoco_core HANYA membaca database ini — tidak pernah menulis.
DB_PATH = _get_env(
    "NASMOCO_DB_PATH",
    r"D:\AI_nasmoco\db\nasmoco.db",
)

# Path file log untuk nasmoco_core.
LOG_PATH = _get_env(
    "NASMOCO_LOG_PATH",
    r"D:\nasmoco_core\logs\nasmoco.log",
)

# Level logging default: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL = _get_env("NASMOCO_LOG_LEVEL", "INFO")


# ---------------------------------------------------------------------------
# Room 6 — INT013 TCARE Realtime (ADR026, WebRepository)
# ---------------------------------------------------------------------------
# Kredensial login web TAM (aftersales.toyota.astra.co.id). SENGAJA TIDAK ADA
# default hardcode -- kalau tidak diisi lewat env var/.env, nilainya "" dan
# TCARERealtimeWebRepository akan menolak login (lihat ValueError di
# repositories/tcare_realtime_web_repository.py), bukan diam-diam gagal.
TAM_EMAIL = _get_env("TAM_EMAIL", "")
TAM_PASSWORD = _get_env("TAM_PASSWORD", "")

# Timeout (detik) untuk request ke web TAM -- dikonfirmasi Wahyu: 10s connect
# / 20s read. Script referensi lama TIDAK punya timeout sama sekali (risiko
# hang selamanya kalau TAM lambat/down) -- Room 6 wajib set ini.
TAM_TIMEOUT_CONNECT = int(_get_env("TAM_TIMEOUT_CONNECT", "10"))
TAM_TIMEOUT_READ = int(_get_env("TAM_TIMEOUT_READ", "20"))
