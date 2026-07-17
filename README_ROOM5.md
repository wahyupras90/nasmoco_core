# ROOM 5 — KPI + Ranking + WIP (nasmoco_core)

Status: **selesai**, mengikuti pola arsitektur Room 4 (Parser → Service →
Repository → Formatter, ADR001-024) persis seperti yang diwajibkan brief.

## Struktur yang ditambahkan

```
repositories/
├── kpi_repository.py        # shared INT004 & INT005 (BR027)
├── ranking_repository.py    # INT006
└── wip_repository.py        # INT007

handlers/
├── _shared/                  # helper Room 5 internal (BR027-style sharing)
│   ├── period_parser.py      # ekstraksi "Januari 2026" / "2026-01" / "bulan ini" dst
│   └── sa_parser.py          # ekstraksi kandidat kode SA dari raw text
├── kpi_summary/   {handler.py, service.py, formatter.py, parser.py, prompt.md}   # INT004
├── kpi_detail/    {sama}                                                         # INT005
├── ranking/       {sama}                                                         # INT006
└── wip/           {sama}                                                         # INT007

tests/
├── fixtures_room5.py
├── test_room5_repositories.py
├── test_room5_services.py
├── test_room5_parsers.py
└── test_room5_handlers.py
```

`app_v2.py::create_router()` ditambah 4 baris `router.register(...)` di
titik ekstensi resmi — tidak ada perubahan lain pada file Room 1-4.

## Skema tabel yang dipakai (dikonfirmasi lewat inspeksi langsung ke `nasmoco.db`)

| Tabel | Dipakai untuk | Kolom kunci |
|---|---|---|
| `daily_kpi` (6.593 baris) | INT004, INT005, INT006 | `tanggal`, `sa`, `unit_entry`, `cpus`, `revenue`, `jasa`, `tgp`, `adt`, `sublet`, `upselling`, `total_liter`. Hasil ETL, dibaca apa adanya (BR026). `revenue` dikonfirmasi konsisten dengan `rekapbulanan.invoice` (BR003) — tidak perlu JOIN. |
| `target_bulanan` (96 baris, **HANYA tahun 2026**) | INT004, INT006 | `tahun`, `bulan`, `sa`, `target_cpus`, `target_revenue`, `target_liter`, `tipe`. `sa='TOTAL'` (`tipe='ALL'`) = baris agregat outlet, bukan entitas rank. |
| `unitmasuk` (114.328 baris) | INT007 | `no_wo`, `no_invoice`, `tgl_invoice`, `sa`, `kelompok`, `pekerjaan`, dst. 1 baris = 1 item pekerjaan (bukan 1 unit) — sama seperti temuan Room 4. |

## Contoh query yang didukung

### INT004 — KPI Summary
- `"kpi AGN bulan ini"`
- `"kpi IND Januari 2026"`
- `"kpi outlet 2026-03"`

### INT005 — KPI Detail
- `"kpi detail AGN bulan ini"`
- `"rincian kpi harian IND Januari 2026"`

### INT006 — Ranking
- `"ranking revenue bulan ini"`
- `"peringkat cpus Januari 2026"`

### INT007 — WIP
- `"wip"`
- `"wip SBE"`
- `"wip AGN"`

## Keputusan desain penting (dikonfirmasi eksplisit dengan user, bukan asumsi sepihak)

### 1. `sa='Counter'` di `daily_kpi`
Transaksi tanpa WO (walk-in). **Exclude dari Ranking** (`RankingRepository`
selalu `WHERE sa NOT IN ('Counter')`), tapi **tetap masuk** agregat KPI
vs Target level outlet (INT004 outlet-level tidak melakukan exclude apa
pun — semua `sa` termasuk Counter dijumlahkan).

### 2. `sa='TOTAL'` (`tipe='ALL'`) di `target_bulanan`
Baris agregat (jumlah semua SA), bukan entitas yang bisa di-rank.
`RankingRepository.get_targets_for_ranking()` selalu exclude baris ini;
diambil terpisah lewat `get_outlet_total()` dan ditampilkan di akhir
hasil ranking tanpa nomor rank.

### 3. `ARDI` dan `SUPP` di `daily_kpi.sa`
Diperlakukan sebagai SA biasa apa adanya sesuai data yang ada — **tidak
ada whitelist/blacklist hardcoded** untuk kode SA di mana pun di Room 5.
Semua resolusi SA (`KPISummaryService`, `KPIDetailService`) memverifikasi
kandidat terhadap `KPIRepository.get_distinct_sa()` (data nyata), bukan
daftar statis — supaya SA baru di masa depan otomatis ter-cover tanpa
perlu ubah kode.

### 4. Definisi WIP
Unit yang **belum diinvoice**: `tgl_invoice` ATAU `no_invoice`
kosong/NULL (dikonfirmasi eksplisit user). Diimplementasikan sebagai satu
filter SQL di `WIPRepository` (`_WIP_FILTER_SQL`), dipakai konsisten oleh
semua method repository — bukan disalin ulang di Service.

### 5. Agregasi `unitmasuk` ke level unit/WO (WIP)
Sama seperti temuan Room 4: 1 baris `unitmasuk` = 1 item pekerjaan, BUKAN
1 unit. `WIPService._aggregate_to_unit()` mengelompokkan berdasarkan
`no_wo` sebelum menghitung "N unit WIP" — diverifikasi ulang lewat query
langsung ke `nasmoco.db` (238 `no_wo` unik dari 262 baris WIP mentah,
membuktikan ada WO dengan >1 item pekerjaan).

### 6. Breakdown WIP pakai `kelompok`, bukan `klp`
Dikonfirmasi eksplisit user. `unitmasuk` punya dua kolom mirip (`klp` dan
`kelompok`) yang TIDAK selalu sama nilainya untuk baris yang sama — hanya
`kelompok` yang dipakai untuk kategori resmi (SBE/GRP/WRT/SBI/LUB/PDS),
sama seperti pola agregasi `jenis_pekerjaan` di Room 4.

Breakdown per kelompok **tidak saling eksklusif** — satu unit/WO bisa
mengandung item pekerjaan dari lebih dari satu kelompok sekaligus
(`WIPService._count_unique_wo_per_kelompok()` menghitung ulang per
kelompok dari `no_wo` unik, bukan dari jumlah baris mentah).

### 7. Target hanya tersedia untuk tahun 2026
`target_bulanan` dikonfirmasi HANYA berisi data tahun 2026. Query KPI
Summary/Ranking untuk periode 2024/2025 tetap menampilkan angka aktual
dari `daily_kpi`, tapi bagian "vs Target" secara eksplisit menyatakan
"target tidak tersedia untuk tahun X" — bukan menampilkan 0% diam-diam.

### 8. Shared helper internal Room 5 (`handlers/_shared/`)
`period_parser.py` (ekstraksi bulan/tahun) dan `sa_parser.py` (ekstraksi
kandidat kode SA) dipakai bersama oleh parser INT004/INT005 (dan
`period_parser` juga oleh INT006) — satu implementasi, bukan disalin 3x,
mengikuti semangat BR027 diterapkan di dalam Room 5 sendiri (analog
dengan `CustomerProfileRepository` di Room 4).

### 9. `match()` antar 4 intent Room 5 saling eksklusif
- KPI Summary (INT004) MENOLAK teks yang mengandung kata domain
  Detail/Ranking/WIP.
- KPI Detail (INT005) MEWAJIBKAN kata domain Detail
  (`detail`/`harian`/`per hari`/`rincian`).
- Ranking (INT006) & WIP (INT007) masing-masing punya kata kunci unik
  sendiri yang tidak overlap dengan intent lain.
Diverifikasi lewat `test_room5_handlers.py::test_router_dispatches_to_correct_intent_no_overlap`.

## Error handling

- INT004/INT005: `{intent}_NOT_FOUND` kalau SA yang diketik tidak ada di
  `daily_kpi` (diverifikasi ke Repository, bukan ditebak).
- INT006: tidak ada NOT_FOUND (ranking selalu untuk semua SA); kalau
  tidak ada data untuk periode, `ranking` DataFrame kosong dan message
  menyatakan itu secara eksplisit.
- INT007: tidak ada NOT_FOUND — 0 unit WIP untuk filter tertentu adalah
  jawaban valid, bukan error.
- Semua `RepositoryError` (E001/E002) ditangkap di Handler, dikembalikan
  sebagai `{intent}_ERROR`, konsisten dengan pola Room 4.

## Definition of Done

- [x] Skema `daily_kpi`, `target_bulanan`, `unitmasuk` diinspeksi &
      dikonfirmasi eksplisit dengan user SEBELUM coding dimulai
- [x] Empat intent (INT004-007) lengkap: `handler.py`, `service.py`,
      `formatter.py`, `parser.py`, `prompt.md` masing-masing
- [x] Repository extend `BaseRepository`, read-only, tanpa business logic
- [x] `intent_id`/`name` benar untuk keempat Handler (INT004-INT007)
- [x] Parameter Service pakai dataclass typed (ADR020)
- [x] `HandlerResult.summary` dict terstruktur (ADR019)
- [x] `kpi_repository.py` di-share antara INT004 & INT005 (BR027)
- [x] Revenue KPI dari `daily_kpi.revenue` (dikonfirmasi konsisten dengan
      `rekapbulanan.invoice`, BR003) — tidak perlu JOIN tambahan
- [x] Angka dari `daily_kpi` dibaca apa adanya, hanya di-SUM (BR026)
- [x] Formatter dipanggil dari Handler, bukan Service (ADR006)
- [x] Unit test per layer (Repository/Service/Parser/Handler), termasuk
      NOT_FOUND (INT004/005) dan kasus tanpa target (2024/2025)
- [x] Integrasi: `router.register(...)` untuk keempat Handler di
      `app_v2.py::create_router()`
- [x] Tidak ada perubahan pada file Room 1-4 yang sudah validated selain
      4 baris register di titik ekstensi resmi
- [x] README Room 5 (dokumen ini)

**Hasil test:** 141 test passed (Room 1-5 gabungan), termasuk 4 file test
baru Room 5 (`test_room5_repositories.py`, `test_room5_services.py`,
`test_room5_parsers.py`, `test_room5_handlers.py`).

## Catatan untuk Room 0 / Room 6-8

Tidak ada perubahan arsitektur yang dilakukan sepihak. Satu observasi
non-blocking untuk dipertimbangkan Room lain yang mungkin punya
kebutuhan serupa:

1. Pola ekstraksi periode (`handlers/_shared/period_parser.py`) dan
   kandidat SA (`handlers/_shared/sa_parser.py`) kemungkinan relevan
   kalau Room 6-8 juga butuh parsing bulan/tahun atau kode SA dari raw
   text — pertimbangkan reuse alih-alih menulis ulang.
2. `daily_kpi` dan `target_bulanan` HANYA tersedia mulai tahun 2026 untuk
   target — kalau ada Room lain yang butuh data target historis
   (2024/2025), itu memang tidak tersedia di skema saat ini (bukan bug
   Room 5, dikonfirmasi lewat inspeksi langsung ke `nasmoco.db`).
