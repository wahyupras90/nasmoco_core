# nasmoco_core

Fondasi **Database Layer** untuk proyek AI Nasmoco (Room 1).

Project ini **hanya membaca** database SQLite milik project lama
(`D:\AI_nasmoco\db\nasmoco.db`). ETL dan penulisan data tetap berjalan
di project lama — tidak disentuh oleh `nasmoco_core`.

Room 4+ (handler/service/repository spesifik) dibangun di atas fondasi
ini: `db/`, `models/`, `utils/`, `config/`.

---

## Struktur Folder

```
nasmoco_core/
├── ai/                     # kosong — reserved
├── config/
│   └── settings.py         # konfigurasi (DB_PATH, LOG_PATH, LOG_LEVEL)
├── db/
│   ├── connection.py       # koneksi SQLite read-only, per-thread reuse
│   └── base_repository.py  # interface wajib untuk semua repository
├── docs/                   # kosong — reserved
├── etl/                    # kosong — ETL masih di project lama
├── handlers/                # kosong — diisi Room 4+
├── models/
│   ├── handler_result.py   # dataclass HandlerResult + error code standard
│   ├── base_handler.py     # interface wajib untuk semua handler
│   └── base_service.py     # interface wajib untuk semua service
├── repositories/           # kosong — diisi Room 4+
├── services/                # kosong — diisi Room 4+
├── tests/
│   ├── test_base_repository.py
│   └── test_handler_result.py
├── tools/                   # kosong — reserved
├── utils/
│   └── logger.py            # get_logger(name) standar
└── main.py                  # stub entrypoint, wiring diisi Room 4+
```

---

## Setup

1. Python 3.9+ direkomendasikan.
2. Install dependency:

   ```bash
   pip install pandas
   # opsional, jika ingin override config lewat file .env:
   pip install python-dotenv
   ```

3. (Opsional) Jalankan dengan environment variable untuk override
   konfigurasi default, alih-alih mengedit `config/settings.py`:

   ```bash
   set NASMOCO_DB_PATH=D:\AI_nasmoco\db\nasmoco.db
   set NASMOCO_LOG_PATH=D:\nasmoco_core\logs\nasmoco.log
   set NASMOCO_LOG_LEVEL=INFO
   ```

   Atau buat file `.env` di root `nasmoco_core\`:

   ```
   NASMOCO_DB_PATH=D:\AI_nasmoco\db\nasmoco.db
   NASMOCO_LOG_PATH=D:\nasmoco_core\logs\nasmoco.log
   NASMOCO_LOG_LEVEL=INFO
   ```

4. Jalankan test:

   ```bash
   pip install pytest
   python -m pytest tests/ -v
   ```

   Test `BaseRepository` menggunakan database SQLite sementara
   (dibuat di runtime), **bukan** `nasmoco.db` asli — jadi test bisa
   dijalankan di mesin manapun tanpa perlu akses ke project lama.

5. Verifikasi kontrak import (Definition of Done Room 1):

   ```bash
   python -c "
   from db.base_repository import BaseRepository
   from models.handler_result import HandlerResult
   from models.base_handler import BaseHandler
   from models.base_service import BaseService
   from utils.logger import get_logger
   print('OK')
   "
   ```

---

## Cara Pakai (untuk Room 4+)

```python
from dataclasses import dataclass

from db.base_repository import BaseRepository
from models.handler_result import HandlerResult, make_code, SUFFIX_OK
from models.base_handler import BaseHandler
from models.base_service import BaseService
from utils.logger import get_logger

logger = get_logger(__name__)


class UnitRepository(BaseRepository):
    def get_by_code(self, unit_code: str):
        return self.execute(
            "SELECT * FROM units WHERE code = ?", (unit_code,)
        )

    def unit_exists(self, unit_code: str) -> bool:
        # Pakai exists() (ADR018) kalau cuma perlu tahu ada/tidak,
        # tanpa menarik seluruh row.
        return self.exists(
            "SELECT 1 FROM units WHERE code = ?", (unit_code,)
        )


# Params Service pakai dataclass sendiri (ADR020), bukan **kwargs bebas.
@dataclass
class UnitParams:
    unit_code: str


class UnitService(BaseService):
    def __init__(self):
        self.repo = UnitRepository()

    def execute(self, params: UnitParams):
        return self.repo.get_by_code(params.unit_code)


class UnitHandler(BaseHandler):
    intent_id = "INT001"
    name = "Unit Lookup"

    def __init__(self):
        self.service = UnitService()

    def match(self, text: str) -> bool:
        return "unit" in text.lower()

    def execute(self, text: str) -> HandlerResult:
        df = self.service.execute(UnitParams(unit_code="X123"))
        if df.empty:
            return HandlerResult(
                success=False,
                code=make_code("INT001", "NOT_FOUND"),
                message="Unit tidak ditemukan.",
            )
        return HandlerResult(
            success=True,
            code=make_code("INT001", SUFFIX_OK),
            message="Unit ditemukan.",
            dataframe=df,
            # summary berupa dict data terstruktur (ADR019) — Formatter
            # yang mengubahnya jadi teks sesuai channel (CLI/API/dsb).
            summary={"unit_code": "X123", "total_rows": len(df)},
        )
```

---

## Aturan yang Wajib Dipatuhi Room 4+

- **Repository**: tidak boleh ada business rule / formatting, hanya
  query dan return DataFrame. Tidak boleh ada statement selain SELECT
  (`BaseRepository` akan menolak dan raise `RepositoryError` dengan
  kode `E003`).
- **Handler**: tidak boleh ada SQL, tidak boleh ada business rule,
  tidak boleh membuka koneksi DB langsung.
- **Service**: tempat business rule berada — satu-satunya jembatan
  antara Handler dan Repository.
- **Logging**: selalu pakai `get_logger(__name__)` dari
  `utils/logger.py`, jangan buat logger sendiri, supaya format dan
  handler (file + console) konsisten.

---

## Catatan untuk Room 0 (ketidaksesuaian arsitektur yang ditemukan)

Tidak ada perubahan arsitektur yang dilakukan. Satu catatan non-blocking
untuk dipertimbangkan Room 0:

1. **Path Windows hardcoded (`D:\...`) di `config/settings.py`.**
   Nilai default (`DB_PATH`, `LOG_PATH`) memakai path absolut Windows
   sesuai spesifikasi. Ini sudah dibuat overridable lewat environment
   variable (`NASMOCO_DB_PATH`, `NASMOCO_LOG_PATH`) atau `.env`, dan
   `utils/logger.py` sudah dibuat fail-safe (fallback ke console-only
   jika path log tidak bisa dibuat/ditulis — misalnya saat dijalankan
   sementara di lingkungan non-Windows untuk testing). Tidak
   mengimplementasikan perubahan lebih jauh dari ini karena berpotensi
   mengubah kontrak konfigurasi — hanya melaporkan sebagai catatan,
   sesuai instruksi.

Tidak ada usulan kolom tambahan di `HandlerResult` atau helper function
baru di luar yang diminta — semua kebutuhan di spesifikasi Room 0 sudah
tercover.
