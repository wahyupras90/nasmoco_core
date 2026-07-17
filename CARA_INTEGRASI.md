# PENTING — Cara integrasi delta ini ke project kamu

Zip ini HANYA berisi file/folder BARU untuk Room 5. Tidak ada satu pun
file Room 1-4 yang di-include, supaya perubahan lokal kamu di Room 4
tidak ketimpa.

## 1. Extract & salin folder/file berikut ke project kamu

Salin (copy-paste / merge) folder-folder dan file berikut ke lokasi
yang sama persis di `D:\nasmoco_core\`:

```
repositories/kpi_repository.py         -> BARU, taruh di repositories/
repositories/ranking_repository.py     -> BARU, taruh di repositories/
repositories/wip_repository.py         -> BARU, taruh di repositories/

handlers/_shared/                       -> BARU, folder utuh
handlers/kpi_summary/                   -> BARU, folder utuh
handlers/kpi_detail/                    -> BARU, folder utuh
handlers/ranking/                       -> BARU, folder utuh
handlers/wip/                           -> BARU, folder utuh

tests/fixtures_room5.py                -> BARU
tests/test_room5_repositories.py       -> BARU
tests/test_room5_services.py           -> BARU
tests/test_room5_parsers.py            -> BARU
tests/test_room5_handlers.py           -> BARU

README_ROOM5.md                         -> BARU, taruh di root project
```

Semua ini nama file/foldernya BARU (tidak ada di Room 1-4), jadi aman
di-copy langsung tanpa risiko menimpa apa pun.

## 2. SATU-SATUNYA file lama yang perlu disentuh: `app_v2.py`

Saya TIDAK mengirim file `app_v2.py` utuh supaya tidak menimpa
perubahan Room 4 kamu di file itu. Sebagai gantinya, cari fungsi
`create_router()` di `app_v2.py` kamu, lalu **tambahkan manual** baris
berikut (jangan hapus baris registrasi Room 4 yang sudah ada):

```python
    # Room 5: KPI Summary (INT004), KPI Detail (INT005), Ranking (INT006),
    # WIP (INT007).
    from handlers.kpi_summary.handler import KPISummaryHandler
    from handlers.kpi_detail.handler import KPIDetailHandler
    from handlers.ranking.handler import RankingHandler
    from handlers.wip.handler import WIPHandler

    router.register(KPISummaryHandler(), priority=10)
    router.register(KPIDetailHandler(), priority=20)
    router.register(RankingHandler(), priority=10)
    router.register(WIPHandler(), priority=10)
```

Taruh blok ini di `create_router()`, SEBELUM baris `return router`,
setelah baris-baris registrasi Room 4 (`HistoryServiceHandler`,
`HistoryTCAREHandler`) yang sudah ada di file kamu sekarang.

## 3. Verifikasi

Setelah kedua langkah di atas, jalankan:

```powershell
python -m pytest tests\ -v
```

Harusnya `151 passed` (kalau test Room 1-4 kamu sekarang berjumlah beda
karena ada perubahan lokal, tinggal tambah 8 test Room 5 dari delta ini
ke total yang sudah ada).
