"""
utils/logger.py

Logging standard untuk seluruh project nasmoco_core.

Semua modul WAJIB mengambil logger lewat `get_logger(__name__)`,
bukan membuat `logging.getLogger` sendiri, supaya format dan
handler (file + console) konsisten di seluruh project.

Format:
    [TIMESTAMP] [LEVEL] [MODULE] message
"""

import logging
import os
import sys

from config import settings

_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Flag supaya kita hanya memasang root handler sekali per proses,
# meskipun get_logger() dipanggil berkali-kali dari banyak modul.
_configured = False


def _ensure_log_dir(log_path: str) -> None:
    log_dir = os.path.dirname(log_path)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            # Jika path Windows (D:\...) dijalankan di lingkungan non-Windows,
            # atau folder tidak bisa dibuat karena permission, jangan crash —
            # cukup fallback ke console-only logging.
            pass


def _configure_root_logger() -> None:
    global _configured
    if _configured:
        return

    level_name = getattr(settings, "LOG_LEVEL", "INFO")
    level = getattr(logging, str(level_name).upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — selalu dipasang.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler — best-effort. Jika LOG_PATH tidak bisa ditulis
    # (misalnya path Windows dijalankan di OS lain), kita skip diam-diam
    # dan tetap log ke console saja.
    log_path = getattr(settings, "LOG_PATH", None)
    if log_path:
        _ensure_log_dir(log_path)
        try:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError:
            pass

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Ambil logger standar untuk modul `name`.

    Contoh:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("pesan info")
    """
    _configure_root_logger()
    return logging.getLogger(name)
