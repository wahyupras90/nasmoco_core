# Room 2 — AI Agent Core (nasmoco_core)

Deliverable Room 2: `ai/router.py` (Router + FallbackProvider + NullFallbackProvider)
dan stub `app_v2.py`. Tidak ada handler/service produksi, tidak ada CLI/API penuh,
tidak ada perubahan pada file Room 1.

## Struktur

```
nasmoco_core/
├── ai/
│   └── router.py            # Router, FallbackProvider, NullFallbackProvider
├── app_v2.py                 # stub: create_router()
├── models/
│   ├── base_handler.py       # placeholder Room 1 (tidak diubah)
│   ├── base_service.py       # placeholder Room 1 (tidak diubah)
│   └── handler_result.py     # placeholder Room 1 (tidak diubah)
├── db/
│   ├── base_repository.py    # placeholder Room 1 (tidak diubah)
│   └── connection.py         # placeholder Room 1 (tidak diubah)
├── utils/
│   └── logger.py             # placeholder Room 1 (tidak diubah)
├── config/
│   └── settings.py           # placeholder Room 1 (tidak diubah)
└── tests/
    ├── mock_handlers.py       # MockHandler untuk testing Router saja
    └── test_router.py
```

> Catatan: file di `models/`, `db/`, `utils/`, `config/` di repo ini adalah
> **placeholder lokal** yang meniru kontrak Room 1 (persis seperti dijelaskan
> di brief Room 2), dibuat semata agar `ai/router.py` bisa diimport dan diuji
> secara terisolasi di lingkungan ini. Room 2 tidak mengubah isi kontrak
> tersebut (tanda tangan method & tipe tetap sama seperti spesifikasi ADR018–021).
> File asli yang sudah divalidasi ada di codebase Room 1.

## Parser Framework (ADR025 — patch additive)

Tambahan sejak brief patch kecil Room 2:

```
parsers/
├── base_parser.py   # BaseParser (abstract): parse(text) -> params
└── base_params.py   # BaseParams: base dataclass kosong untuk parser params
```

**Tujuan:** standardisasi struktur saja — setiap Parser (Room 6+) punya method
dengan nama sama (`parse()`), tanpa menyediakan logika parsing (regex,
keyword, dll) apa pun. Logika parsing tetap tanggung jawab tiap Room.

**Alur pemakaian (Room 6+):**

```
raw text  →  YourParser.parse(text)  →  YourParams(...)  →  diteruskan ke Service
```

Contoh minimal:

```python
from dataclasses import dataclass
from typing import Optional
from parsers.base_parser import BaseParser
from parsers.base_params import BaseParams


@dataclass
class AttackListParams(BaseParams):
    segment: Optional[str] = None


class AttackListParser(BaseParser):
    def parse(self, text: str) -> AttackListParams:
        # logika parsing spesifik Room 6 di sini
        ...
```

**Status berlaku — Final, terkunci (ADR025):**
- Berlaku **mulai Room 6** (Attack List + Extended Warranty) dan seterusnya.
- **Room 4 (History/TCARE) dan Room 5 (KPI/Ranking/WIP) di-grandfather** —
  parser mereka yang sudah ada TIDAK direfactor, TIDAK perlu extend
  `BaseParser`, TIDAK perlu validasi ulang.
- Konsolidasi Room 4/5 ke `BaseParser` (kalau nanti dilakukan) adalah
  pekerjaan terpisah **setelah Room 8 selesai**, bukan disisipkan di tengah
  Room 6/7/8 — dan kalau dikerjakan, harus refactor murni (nol perubahan
  perilaku, dibuktikan test pembanding sebelum-sesudah).

Parser mengikuti batasan layer yang sama seperti Handler/Service lain:
- Parser TIDAK BOLEH mengakses database / menjalankan SQL.
- Parser TIDAK BOLEH berisi business rule (itu tugas Service).
- Parser dipanggil dari Handler; hasilnya diteruskan ke Service.

Patch ini murni tambahan file baru — tidak menyentuh `ai/router.py`,
`BaseHandler`, `BaseService`, `BaseRepository`, `HandlerResult`, atau parser
Room 4/5 manapun.

## Decision Log

1. **Nama method Router: `route()`.**
   Dipilih `route()` alih-alih `execute()` karena secara semantik lebih jelas
   membedakan peran Router (orchestration/dispatch) dari Handler/Service/Repository
   (yang punya `execute()`). `route()` bukan nama yang dilarang oleh Room 0 (larangan
   `handle()/process()/run()/query()` hanya berlaku di layer Handler/Service/
   Repository), dan Room 0 secara eksplisit mendelegasikan keputusan gaya ini ke
   Room 2. Dengan `route()`, siapa pun yang membaca kode langsung tahu ini adalah
   titik masuk dispatch, bukan eksekusi bisnis.

2. **Aturan tie-break: Highest Priority Wins, lalu First Registered Wins (ADR022).**
   Diimplementasikan dengan menyimpan setiap registrasi sebagai tuple
   `(priority, registration_order, handler)` dan mengurutkan
   `sorted(registrations, key=lambda r: (-priority, registration_order))`
   sebelum mencoba `match()` satu per satu. Ini eksplisit di kode (bukan
   kebetulan urutan list) dan diuji lewat:
   - `test_higher_priority_wins_when_both_match` — priority berbeda menang
     meski handler priority rendah didaftarkan lebih dulu.
   - `test_first_registered_wins_when_priority_equal` /
     `test_first_registered_wins_regardless_of_definition_order` — kalau
     priority sama, handler yang `register()`-nya dipanggil duluan menang,
     terlepas dari urutan variabel didefinisikan di kode pemanggil.

3. **Router bergantung pada `FallbackProvider` abstrak (Dependency Inversion, ADR023).**
   `ai/router.py` hanya mengimpor `FallbackProvider` (abstract base class) dan
   `NullFallbackProvider` (implementasi testing). Tidak ada import, nama kelas,
   string, atau komentar apa pun di `Router` yang menyebut "Analysis" atau
   "SQL Agent" secara konkret. Ketika Room 8 membuat `AnalysisProvider(FallbackProvider)`,
   Router tidak perlu diubah sama sekali — cukup `Router(fallback=AnalysisProvider(...))`
   di `app_v2.py`/`create_router()` saat wiring produksi.

4. **Kode error `NullFallbackProvider` mengikuti Error Code Standard Room 1.**
   Semula memakai string hardcode `"E999_NO_HANDLER_MATCHED"` yang tidak
   mengikuti format `{intent_prefix}_{suffix}` dari `models/handler_result.py`.
   Diperbaiki (masukan review Room 0) menjadi
   `make_code("INT999", SUFFIX_ERROR)` -> `"INT999_ERROR"`, memakai prefix
   `INT999` sebagai penanda "tidak ada intent yang match" (bukan intent
   produksi manapun milik Room 4–8) dan suffix standar `SUFFIX_ERROR`. Ini
   supaya pola kode error konsisten sebelum ditiru handler-handler produksi.

## Batasan yang dipatuhi

- Router murni dispatch: tidak ada SQL atau business logic di `ai/router.py`
  maupun `app_v2.py`.
- Tidak ada perubahan pada kontrak Room 1 (`HandlerResult`, `BaseHandler`,
  `BaseService`, `BaseRepository`, `get_logger`).
- `NullFallbackProvider` hanya untuk testing Router — bukan implementasi
  Analysis/SQL Agent asli.
- `app_v2.py` hanya stub: `create_router()` bisa dipanggil tanpa error, tidak
  ada CLI loop lengkap atau port binding (itu scope Room 3).
- Tidak menulis ke `nasmoco.db` dengan cara apa pun.

## Menjalankan test

```bash
cd nasmoco_core
python3 -m unittest discover -s tests -v
```

Semua 7 test lulus, mencakup 4 skenario wajib di DoD:
1. Router memilih Handler yang benar dari beberapa mock Handler
2. Tie-break priority (priority beda, priority tinggi menang)
3. Tie-break registration order (priority sama, register duluan menang)
4. Router memanggil `FallbackProvider.execute()` saat tidak ada yang match

## Untuk Room 3 / Room 4–8

- Room 4–8: panggil `router.register(YourHandler(), priority=...)` di
  `create_router()` (`app_v2.py`) atau di titik wiring produksi masing-masing.
  `YourHandler` harus punya `intent_id`, `name`, `match()`, `execute()` sesuai
  `BaseHandler` dari Room 1 — Router akan otomatis memakainya untuk logging
  (`"Matched %s %s"`), tanpa hardcode apa pun di Router.
- Room 8: implementasikan `AnalysisProvider(FallbackProvider)` dan inject ke
  `Router(fallback=AnalysisProvider(...))` saat wiring produksi, menggantikan
  `NullFallbackProvider`.
- Room 3: lengkapi `app_v2.py` jadi CLI/API penuh (port 8001), tanpa perlu
  menyentuh `ai/router.py`.
