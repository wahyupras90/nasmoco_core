# Room 3 — Application Layer

`app_v2.py` melengkapi stub Room 2 menjadi aplikasi yang bisa dipakai: CLI
interaktif dan API endpoint di port **8001**. Tidak ada SQL/business logic di
sini — semua request lewat `Router -> Handler` (ADR016).

## Menjalankan

### CLI (default)

```bash
python app_v2.py
# atau eksplisit:
python app_v2.py --mode cli
```

Contoh sesi:

```
nasmoco_core CLI — ketik 'exit' atau 'quit' untuk keluar.
> berapa total visit Budi bulan ini
[INT999_ERROR] Tidak ada handler yang cocok untuk permintaan ini.
> exit
Bye.
```

(`INT999_ERROR` muncul karena belum ada Handler produksi terdaftar — ini
`NullFallbackProvider`, kontrak sementara ADR023 sampai Room 8 selesai.)

### API (port 8001)

```bash
python app_v2.py --mode api
# port custom, kalau perlu:
python app_v2.py --mode api --port 8001
```

Endpoint:

| Method | Path      | Body                    | Response                      |
|--------|-----------|--------------------------|--------------------------------|
| GET    | `/health` | -                        | `{"status": "ok"}`            |
| POST   | `/query`  | `{"text": "..."}`       | `HandlerResult` sebagai JSON  |

Contoh:

```bash
curl -s http://localhost:8001/health

curl -s -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"text": "berapa total visit Budi bulan ini"}'
```

Response `/query` (`HandlerResult` terserialisasi — lihat `handler_result_to_dict`
di `app_v2.py`):

```json
{
  "success": false,
  "code": "INT999_ERROR",
  "message": "Tidak ada handler yang cocok untuk permintaan ini.",
  "summary": {},
  "suggestions": [],
  "dataframe": null,
  "metadata": {},
  "execution_ms": 0.33
}
```

Catatan: `dataframe` dikonversi eksplisit (`to_dict(orient="records")`) sebelum
di-serialize. `export` sengaja tidak disertakan di response `/query` biasa —
di luar scope Room 3 saat ini.

## Cara Room 4–8 mendaftarkan Handler produksi

Buka `create_router()` di `app_v2.py` — **titik ekstensi resmi**, tidak perlu
menyentuh bagian lain file ini. Tambahkan satu baris `router.register(...)`
per handler:

```python
def create_router() -> Router:
    router = Router(fallback=NullFallbackProvider())
    # Room 4-8 mendaftarkan handler produksi masing-masing di sini, contoh:
    from handlers.history_handler import HistoryServiceHandler
    router.register(HistoryServiceHandler(), priority=10)

    from handlers.kpi_handler import KPIHandler
    router.register(KPIHandler(), priority=10)
    return router
```

Aturan tie-break (ADR022): priority lebih tinggi menang; kalau sama, yang lebih
dulu `register()` menang.

**Jangan** mengganti `NullFallbackProvider()` di `create_router()` sampai
Room 8 (Analysis/SQL Agent) selesai dan tervalidasi — itu kontrak yang
disengaja (ADR023), bukan sesuatu yang perlu "diperbaiki" di Room 3/4-8.

## Error handling

- Exception tak terduga dari Handler/Service/Repository ditangkap di
  `_safe_route()` (dipakai baik oleh CLI maupun API) — tidak pernah membuat
  aplikasi crash. Hasilnya dikembalikan sebagai `HandlerResult` dengan
  `success=False`, kode `{PREFIX}_ERROR` (via `make_code()`), dan dilog lewat
  `get_logger()` (termasuk stack trace).
- Log intent match tetap datang dari `ai/router.py` (ADR021) — Room 3 tidak
  menduplikasi log ini.

## Test

```bash
PYTHONPATH=. python -m pytest tests/test_app_v2.py -v
```

Mencakup:
- `create_router()` menghasilkan `Router` yang bisa `register()`/`route()`
  tanpa error.
- Query yang tidak match apa pun tetap menghasilkan response wajar lewat
  `NullFallbackProvider` (bukan crash).
- Exception tak terduga dari Handler tertangkap (`_safe_route`), baik di
  jalur langsung maupun lewat endpoint `/query` (tetap HTTP 200 dengan
  `success: false` di body, bukan 500/crash).
- Konversi `HandlerResult` (termasuk `dataframe`) ke JSON aman untuk
  `json.dumps`.
- Endpoint `/health` dan `/query` (sukses, exception, dan `text` field
  hilang → 400).

## Yang tidak dikerjakan di Room 3 (sesuai brief)

- Tidak ada Handler/Service spesifik (INT001–INT999) — itu scope Room 4–8.
- Tidak ada implementasi `AnalysisProvider`/SQL Agent — itu scope Room 8.
- Tidak ada perubahan pada `ai/router.py`, `HandlerResult`, `BaseHandler`,
  `BaseService`, `BaseRepository`.
- Tidak menulis ke `nasmoco.db`.
- Tidak membuka port selain 8001 (port 8000 dipakai project lama).
