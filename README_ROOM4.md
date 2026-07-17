# Room 4 — History Service (INT002) + History TCARE (INT003)

Room 4 mengisi Handler/Service/Repository produksi pertama di atas fondasi
Room 1-3. Tidak ada perubahan pada `models/`, `db/`, `utils/`, `config/`,
atau `ai/router.py`. Satu-satunya perubahan di `app_v2.py` adalah dua baris
`router.register(...)` di `create_router()` — titik ekstensi resmi yang
memang disediakan Room 2/3 untuk Room 4-8.

## Struktur yang ditambahkan

```
repositories/
├── customer_profile_repository.py   # shared: customer_profile (BR020, BR027)
├── history_service_repository.py    # INT002: unitmasuk + rekapbulanan
└── history_tcare_repository.py      # INT003: unit_tcare (VIEW) + tcare_schedule_full_history

handlers/
├── history_service/
│   ├── parser.py       # ekstrak no_rangka/plat/nama + rentang tanggal
│   ├── service.py       # HistoryServiceService (business logic, ADR004)
│   ├── formatter.py       # summary dict + message (ADR006)
│   ├── handler.py         # HistoryServiceHandler (INT002)
│   └── prompt.md           # dokumentasi pola pattern-matching
└── history_tcare/
    ├── parser.py
    ├── service.py
    ├── formatter.py
    ├── handler.py
    └── prompt.md

tests/
├── fixtures_room4.py             # SQLite temp db sintetis (skema mini 5 tabel)
├── test_room4_repositories.py
├── test_room4_services.py
└── test_room4_handlers.py
```

## Skema tabel yang dipakai (subset kolom, sesuai brief Room 4)

| Tabel | Dipakai oleh | Kolom kunci |
|---|---|---|
| `customer_profile` (PK `no_rangka`) | INT002 & INT003 (shared, `CustomerProfileRepository`) | `total_kunjungan_fisik` (BR020), `customer`, `model`, `no_polisi`, `segment`, `dealer_kategori` |
| `unitmasuk` | INT002 | `no_wo` (INTEGER), `no_rangka`, `tanggal`, `pekerjaan`, `sa`, `mech` |
| `rekapbulanan` | INT002 (revenue, BR003) | `no_wo` (REAL — beda tipe dari `unitmasuk.no_wo`!), `invoice` |
| `unit_tcare` (VIEW = `rs` LEFT JOIN `tcare_unit`) | INT003 (info unit) | identitas dari `rs` (`model`, `no_polisi`, `customer`, `dealer_kategori`, `batas_tcare`, `tgl_do`); operasional dari `tcare_unit` (`tcare_type`, `sisa_detail`, `sa_terakhir`) |
| `tcare_schedule_full_history` | INT003 (riwayat, ADR024 final) | `no_rangka`, `kunjungan`, `pekerjaan`, `status`, `expired` |

`tcare_schedule`, `tcare_schedule_v1_backup`, `tcare_monthly_v1_backup`,
`tcare_monthly_full_history` **tidak pernah** direferensikan di kode Room 4
(lihat `test_no_query_ever_touches_tcare_schedule_short_table`).

## Contoh query yang didukung

### INT002 — History Service

```
riwayat service Budi Santoso
history servis mobil nopol B 1234 XYZ
histori wo untuk MHFXXKF3JGK012345
cek riwayat kunjungan customer atas nama Ahmad 3 bulan terakhir
riwayat service 2024-01-01 sampai 2024-03-31 Budi
history Budi Santoso                      (polos, tanpa kata domain — lihat bagian A di bawah)
history MHFXXKF3JGK012345                 (polos, no_rangka langsung)
```

### INT003 — History TCARE

```
history tcare MHFXXKF3JGK012345
riwayat tcare mobil nopol B 1234 XYZ
cek tcare punya Budi Santoso
```

Kedua `match()` saling menolak berdasarkan kata "tcare": INT002 menolak
teks yang mengandung "tcare", INT003 mewajibkannya. Ini mencegah kedua
intent (yang sama-sama pakai kata "history"/"riwayat") saling menyerobot.
`Router` tetap didaftarkan dengan priority INT003=20 > INT002=10 sebagai
jaga-jaga tambahan (bukan pembeda utama).

## Keputusan desain penting

### 1. Identifier customer: `no_rangka` / `plate` / `name`

Tiga jenis identifier didukung di kedua intent, diekstrak `parser.py`
lalu di-resolve ke `customer_profile` (INT002 selalu; INT003 hanya untuk
`plate`/`name` — untuk `no_rangka`, nilainya itu sendiri IS the no_rangka).

**Regex `no_rangka` sengaja lebih longgar dari VIN 17-karakter standar
dunia yang dipakai kode legacy.** Contoh nyata di brief Room 4 sendiri
(`01S208014054`) cuma 12 karakter — tidak match sama sekali dengan
`VIN_REGEX` legacy (`[A-HJ-NPR-Z0-9]{17}`). Karena itu Room 4 memakai
pola alfanumerik 8-17 karakter yang wajib mengandung minimal satu huruf
dan satu digit, tanpa spasi internal. Ini ditemukan lewat testing nyata
saat DoD test case ADR024 (`01S208014054`) awalnya salah diklasifikasi
sebagai nama customer alih-alih no_rangka — sudah diperbaiki dan
dibuktikan lewat `test_old_expired_unit_does_not_inherit_legacy_bug_adr024`.

**Keterbatasan yang diketahui (bukan bug, didokumentasikan secara
sadar):** plat nomor tanpa spasi (mis. "B1234XYZ", 8 karakter berisi
huruf+digit) bisa salah tertangkap sebagai `no_rangka` alih-alih
`plate`, karena regex plat mewajibkan spasi setelah huruf wilayah untuk
menghindari tumpang-tindih dengan regex `no_rangka` (yang tidak
mengizinkan spasi internal). Dampak: kalau ini terjadi, resolusi akan
gagal (NOT_FOUND) alih-alih salah root cause — tidak fatal, tapi kalau
pola input user di lapangan banyak memakai plat tanpa spasi, ini perlu
disempurnakan (linked ke prosedur "lapor ke Room 0" di brief kalau
ternyata jadi masalah nyata di produksi).

Fallback nama customer memakai daftar stopword (termasuk partikel
kasual seperti "dong", "sih", "deh") dan syarat panjang token minimum,
supaya frasa seperti "riwayat service dong" tidak salah dianggap
sebagai nama customer "dong" (`match()` mengembalikan `False`, jatuh ke
fallback provider — bukan `False` positif yang berujung `NOT_FOUND`).

### 2. `CustomerProfileRepository` dibagi (BR027)

`HistoryServiceRepository` dan `HistoryTCARERepository` sama-sama
memakai `CustomerProfileRepository` lewat komposisi (has-a), bukan
menyalin query. Ini satu-satunya implementasi untuk:
- Resolusi identifier (`no_rangka`/`no_polisi`/`customer`) -> baris
  `customer_profile`.
- BR020: `get_total_kunjungan_fisik()` — RO dibaca apa adanya dari
  `total_kunjungan_fisik`, tidak pernah dihitung ulang.

### 3. ADR024 — anti-warisan bug legacy di `HistoryTCAREService`

Kode legacy (`tools/history_tcare.py`) menganggap unit "tidak
ditemukan" hanya berdasarkan `unit_tcare` (VIEW gabungan `rs` +
`tcare_unit`, lihat "Diperbaiki #3" di atas) kosong. Room 4
mengidentifikasi ini sebagai **kelas bug yang sama** dengan alasan
`tcare_schedule` ditolak jadi source of truth: satu sumber info yang
tidak mencakup semua `no_rangka` bisa membuat unit salah dilaporkan
"tidak ditemukan" padahal riwayat TCARE-nya ada.

`HistoryTCAREService` karena itu HANYA menganggap `NOT_FOUND` kalau
**kedua** sumber kosong (`unit_tcare` DAN `tcare_schedule_full_history`).
Kalau `unit_tcare` kosong tapi riwayat ada, Service memakai identitas
fallback dari `customer_profile` (nama, model, no_polisi) dan tetap
mengembalikan `INT003_OK` dengan field spesifik TCARE (`tcare_type`,
`batas_tcare`, `sisa_detail`) berisi `None`.

Dibuktikan lewat:
- `test_old_expired_unit_does_not_inherit_legacy_bug_adr024` (Service)
- `test_execute_ok_old_expired_case_not_lost_adr024` (Handler)
- Fixture `01S208014054`: 7 baris riwayat 2008-2011 di
  `tcare_schedule_full_history`, TIDAK ADA baris di `rs`/`tcare_unit`
  (sehingga VIEW `unit_tcare` kosong untuknya) maupun `tcare_schedule`
  — mengulang persis kondisi bukti empiris di brief.

### 4. Revenue (BR003) — JOIN tipe data berbeda

`unitmasuk.no_wo` adalah `INTEGER`, `rekapbulanan.no_wo` adalah `REAL`.
`HistoryServiceRepository.get_revenue_by_no_wo()` melakukan
`CAST(no_wo AS INTEGER)` di sisi SQL (tetap parameterized, bukan
string-concat nilai) supaya JOIN manual di Python (`DataFrame.merge`)
match dengan benar. Kolom yang dipakai selalu `rekapbulanan.invoice`,
tidak pernah `rekapbulanan.total_revenue` atau tabel `invoice` mentah.

### 5. Ambiguitas

Kalau identifier "plate"/"name" (INT002) atau "plate"/"name" (INT003)
me-resolve ke >1 baris `customer_profile`, Handler mengembalikan
`{INT}_AMBIGUOUS` dengan `suggestions` berisi kandidat (`no_rangka`,
`customer`, `no_polisi`, `model`) supaya user bisa memperjelas. Identifier
`no_rangka` tidak pernah ambigu (PK).

## Error handling

`RepositoryError` (E001/E002/E003 dari `BaseRepository`) ditangkap di
Handler (bukan dibiarkan menembus ke `_safe_route` di `app_v2.py`),
dikembalikan sebagai `HandlerResult(success=False, code={INT}_ERROR)`.
`_safe_route` di `app_v2.py` tetap jadi jaring pengaman terakhir untuk
exception tak terduga yang tidak sengaja lolos dari Handler.

## Update setelah smoke test terhadap `nasmoco.db` asli

Tiga temuan dari smoke test nyata (bukan cuma data sintetis) — dua sudah
diperbaiki, satu masih **blocking** dan butuh konfirmasi:

### Diperbaiki #1 — plat tanpa spasi salah diklasifikasi sebagai `no_rangka`

Kasus nyata: `"riwayat service Wahyu AB1930GG"` — "AB1930GG" (8 karakter,
campuran huruf+digit) awalnya tertangkap oleh `NO_RANGKA_REGEX`
(sengaja longgar untuk kasus ADR024), padahal itu plat nomor.

**Perbaikan:** ditambahkan `PLATE_NO_SPACE_REGEX` (anchored, `^[A-Z]{1,2}\d{1,4}[A-Z]{0,3}$`)
yang dicek **lebih dulu** daripada `NO_RANGKA_REGEX`. Ini aman dilakukan
karena no_rangka asli (VIN 17 karakter maupun chassis legacy) tidak
pernah berbentuk rapi "blok huruf, blok digit, blok huruf" — hurufnya
berselang-seling dengan digit di sepanjang string (dibuktikan lewat
`tests/test_room4_parsers.py`, termasuk terhadap sampel no_rangka nyata
dari smoke test seperti `MHKA6GJ3JPJ608788`).

### Diperbaiki #2 — format pemisah `no_polisi` di data asli pakai strip, bukan spasi

Hasil suggestions nyata menunjukkan `no_polisi` tersimpan sebagai
`"G-1576-DF"` (strip), bukan `"G 1576 DF"` (spasi) seperti asumsi awal.

**Perbaikan:** `CustomerProfileRepository.get_by_no_polisi()` sekarang
menormalisasi KEDUA sisi (kolom di database maupun parameter query)
dengan menghilangkan spasi dan strip sebelum dibandingkan (`REPLACE`
di SQL). Jadi `"G1576DF"`, `"G 1576 DF"`, dan `"G-1576-DF"` semuanya
dianggap identifier yang sama.

### Diperbaiki #3 (sebelumnya dilaporkan sebagai BLOCKING) — `unit_tcare` adalah VIEW, bukan tabel `tcare_unit`

Query awal ke tabel `tcare_unit` gagal:

```
sqlite3.OperationalError: no such column: model
```

**Root cause yang terkonfirmasi** (lewat `PRAGMA table_info` + inspeksi
`sqlite_master.sql` terhadap `nasmoco.db` produksi): brief Room 4 salah
menyimpulkan bahwa `unit_tcare` (nama yang dipakai legacy) itu
"typo/nama lama" dari tabel `tcare_unit`. Yang benar:

```sql
CREATE VIEW unit_tcare AS
    SELECT r.*, t.tcare_type, t.sisa_service, t.sisa_detail,
           t.next_service, t.last_sbe_km, t.last_sbe_date,
           t.last_sbe_dealer, t.last_sbe_source,
           t.sa_terakhir, t.tgl_sa_terakhir,
           t.flag_pending_sbe, t.flag_sa,
           t.flag_tgl_kunjungan, t.flag_wo_type,
           t.next_sbe_expected, t.last_updated
    FROM rs r
    LEFT JOIN tcare_unit t ON r.no_rangka = t.no_rangka
```

`unit_tcare` adalah VIEW ASLI yang sungguh ada, menggabungkan identitas
unit dari tabel `rs` (`model`, `no_polisi`, `customer`,
`dealer_kategori`, `batas_tcare`, `tgl_do`) dengan field operasional
TCARE dari tabel `tcare_unit` (`tcare_type`, `sisa_service`,
`sisa_detail`, dst — tabel `tcare_unit` mentah memang TIDAK punya
kolom identitas sama sekali, makanya query langsung ke situ gagal).

**Perbaikan:** `HistoryTCARERepository.get_unit_info()` sekarang query
ke `FROM unit_tcare` (VIEW), dengan daftar kolom yang sama seperti versi
awal (`no_rangka, model, no_polisi, customer, dealer_kategori,
sa_terakhir, tcare_type, batas_tcare, sisa_detail, tgl_do`) — terbukti
benar lewat smoke test nyata (screenshot hasil query legacy terhadap
`no_rangka` yang sama, menampilkan Customer/Model/No Polisi/Batas TCARE
lengkap).

**Pelajaran untuk Room 5-8:** kalau brief bilang sebuah nama tabel
legacy adalah "salah sebut/typo", jangan langsung dipercaya — cek dulu
`SELECT name, type FROM sqlite_master` (termasuk `type='view'`, bukan
cuma `type='table'`) sebelum mengganti ke nama yang "dianggap benar".


### Observasi non-blocking — pencarian nama parsial bisa sangat ambigu

`"riwayat service Wahyu"` menghasilkan 327 kandidat (dibatasi tampil 10
lewat `MAX_SUGGESTIONS`). Ini sesuai desain (LIKE partial match harus
didisambiguasi, BUKAN bug), tapi dicatat sebagai pertimbangan UX kalau
ternyata pola pemakaian nyata lebih sering pakai nama depan pendek —
bisa dipertimbangkan menaikkan bar (mis. wajib ≥2 kata) di iterasi
berikutnya kalau dirasa perlu.



```bash
cd nasmoco_core
pip install pytest pandas
PYTHONPATH=. python -m pytest tests/ -v
```

100 test lulus, termasuk seluruh test Room 1-3 yang sudah ada (tidak ada
regresi) + 65 test baru Room 4 (repository, service, handler, parser,
formatter, router/integrasi, agregasi `jenis_pekerjaan`).

## Perubahan disepakati setelah validasi produksi (pasca smoke test)

Tiga keputusan besar berikut disepakati eksplisit dengan user (bukan
keputusan sepihak) setelah menguji Room 4 langsung terhadap
`nasmoco.db` produksi. Ini mengubah perilaku INT002 secara signifikan
dibanding versi awal — didokumentasikan di sini karena Room 5-8
kemungkinan menemukan pola serupa.

### A. `match()` INT002 dilonggarkan — kata domain servis tidak wajib

Awalnya INT002 mensyaratkan kata `history`/`riwayat` **DAN**
`service`/`servis`/`kunjungan`/`wo`/`bengkel`. Ternyata user sering
mengetik `history <nama>` polos tanpa kata domain sama sekali.

**Keputusan:** `history <nama>` / `riwayat <nama>` polos (tanpa kata
domain, tanpa kata "tcare") sekarang DEFAULT ke History Service.
`SERVICE_KEYWORDS` tidak lagi jadi syarat `match()`, cuma
dipertahankan sebagai konstanta (bisa dipakai kalau nanti butuh
disambiguasi tambahan). Lihat `handlers/history_service/parser.py::match()`.

### B. Notifikasi overlap TCARE

Karena INT002 sekarang bisa match tanpa user secara eksplisit
menyebut domain, ada risiko user tidak sadar unit yang dia tanya juga
punya data TCARE. Solusinya (opsi yang dipilih dari 3 opsi yang
diajukan ke user): **INT002 tetap hanya menampilkan data History
Service**, tapi menambahkan notifikasi satu baris di akhir `message`
kalau `HistoryServiceRepository.has_any_tcare_history(no_rangka)`
bernilai `True`:

```
💡 Unit ini juga punya data TCARE. Ketik "history tcare <no_rangka>" untuk detail lengkap.
```

`summary["has_tcare_history"]` (bool) juga ditambahkan untuk konsumen
terprogram. Query EXISTS ini sengaja diduplikasi kecil di
`HistoryServiceRepository` dari `HistoryTCARERepository` (bukan lewat
BR027, karena ini cuma EXISTS satu baris, bukan rumus bisnis) supaya
tidak ada dependency silang antar Repository dua intent berbeda.

### C. Agregasi `jenis_pekerjaan` per WO — `unitmasuk` 1 baris = 1 item pekerjaan, BUKAN 1 kunjungan

**Temuan kritis** (lewat smoke test nyata): `unitmasuk` menyimpan SATU
BARIS PER ITEM PEKERJAAN, bukan satu baris per kunjungan/WO. Kalau 1 WO
punya 2 item pekerjaan (mis. "DIAGNOSA/INSPECTION" + "NITROGEN"), itu 2
baris dengan `no_wo` yang identik. Ini berarti:

- "Jumlah kunjungan" **tidak boleh** dihitung dari `len(history_df)`
  langsung — itu menghitung jumlah *baris/item pekerjaan*, bukan jumlah
  kunjungan. Diperbaiki jadi hitung `no_wo` UNIK
  (`formatter._count_unique_visits()`).
- Dataframe yang ditampilkan ke user sekarang **diagregasi ke level
  WO** (satu baris per kunjungan, bukan satu baris per item pekerjaan)
  lewat `HistoryServiceService._aggregate_by_wo()`, dengan kolom baru
  **`jenis_pekerjaan`** yang merangkum kode `klp`/`kelompok` dari
  seluruh item pekerjaan dalam WO itu. Kolom mentah `pekerjaan`/`klp`/
  `kelompok` DIHAPUS dari hasil akhir (digantikan `jenis_pekerjaan`).

**Aturan `jenis_pekerjaan`** (disepakati eksplisit lewat beberapa
putaran klarifikasi dengan bukti data nyata, lihat
`handlers/history_service/service.py::_build_jenis_pekerjaan()`):

1. Kalau ADA baris dengan `kelompok == "WRT"` (warranty — bisa
   menaungi `klp` GRP maupun SUB) → `jenis_pekerjaan` untuk WO itu
   **HANYA "WRT"**, tidak digabung kode lain sama sekali sekalipun ada
   baris `SUB` di WO yang sama.
2. Kalau TIDAK ADA WRT → ambil kode `klp` UNIK dalam WO itu, urutkan
   prioritas **`SBE > GRP > LUB > SBI > PDS > SUB`**, gabung dengan
   `", "`. Khusus kode **SBE**, sertakan teks `pekerjaan` asli dari
   baris SBE **pertama** yang muncul di WO itu, format
   `"SBE (<pekerjaan>)"`. Kode lain (`GRP`/`LUB`/`SBI`/`PDS`/`SUB`)
   ditampilkan sebagai kode polos saja (TANPA teks pekerjaan — ini
   yang membedakan SBE dari SBI, walau sekilas mirip).

Contoh nyata (dari data produksi, no_rangka `MHKAB1BC6PJ024535`):

| WO | Baris asli (pekerjaan; klp; kelompok) | `jenis_pekerjaan` hasil |
|---|---|---|
| 2243864 | DIAGNOSA/INSPECTION; GRP; GRP · NITROGEN; SUB; GRP | `GRP, SUB` |
| 2236285 | CLAIM PART T-CARE LITE; SBI; SBI | `SBI` |

(Catatan: contoh di atas WO nyata tidak mengandung SBE atau WRT — untuk
kasus SBE/WRT lihat data uji sintetis di `tests/fixtures_room4.py`,
customer "AGUNG PRATAMA".)

**Kolom sumber yang belum pernah dipakai sebelumnya:** `unitmasuk.klp`
dan `unitmasuk.kelompok` — dua kolom berbeda yang **bisa punya nilai
berbeda untuk baris yang sama** (mis. `klp=SUB` tapi `kelompok=GRP`
untuk baris yang sama persis, dibuktikan lewat data nyata). Room 5-8
yang menyentuh `unitmasuk` perlu tahu ini: jangan asumsikan `klp` dan
`kelompok` selalu identik.



- [x] `handlers/history_service/` & `handlers/history_tcare/` lengkap
      (`handler.py`, `service.py`, `formatter.py`, `parser.py`, `prompt.md`)
- [x] `repositories/history_service_repository.py` &
      `repositories/history_tcare_repository.py`, extend `BaseRepository`,
      tanpa business logic
- [x] `intent_id`/`name` benar (`INT002`/"History Service",
      `INT003`/"History TCARE")
- [x] Parameter Service pakai dataclass typed (`HistoryServiceParams`,
      `HistoryTCAREParams`), bukan `**kwargs`
- [x] `HandlerResult.summary` dict terstruktur, bukan string jadi
- [x] RO diambil dari `customer_profile.total_kunjungan_fisik` (BR020),
      via `CustomerProfileRepository` yang di-share (BR027)
- [x] `HistoryTCARERepository` hanya query `unit_tcare` (VIEW) +
      `tcare_schedule_full_history`; TIDAK ADA query ke `tcare_schedule`,
      `tcare_schedule_v1_backup`, `tcare_monthly_v1_backup`,
      `tcare_monthly_full_history` di mana pun (ADR024)
- [x] Unit test kasus `no_rangka` lama-expired (`01S208014054`) tetap OK,
      bukan NOT_FOUND
- [x] Revenue dari `rekapbulanan.invoice` (BR003), bukan tabel `invoice`
      mentah atau `total_revenue`
- [x] Formatter dipanggil dari Handler, bukan dari Service
- [x] Unit test per layer (Repository/Service/Handler), termasuk
      NOT_FOUND, AMBIGUOUS + suggestions
- [x] Integrasi: `router.register(...)` di `app_v2.py::create_router()`
      berjalan, `router.route(text)` memilih Handler yang tepat
- [x] Tidak ada perubahan pada file Room 1-3 selain dua baris register
      di titik ekstensi resmi `create_router()`
- [x] README Room 4 (dokumen ini)

## Catatan untuk Room 0 / Room 5-8

Tidak ada perubahan arsitektur yang dilakukan sepihak. Satu catatan
non-blocking (bukan penyimpangan kontrak, murni observasi desain untuk
dipertimbangkan Room 5-8 yang mungkin punya kebutuhan serupa):

1. **Regex identifier "no_rangka" yang diperlonggar** (lihat "Keputusan
   desain #1") kemungkinan relevan untuk Room lain yang juga perlu
   mengekstrak no_rangka dari raw text — pertimbangkan memakai pola yang
   sama (`8-17 karakter alfanumerik, wajib huruf+digit, tanpa spasi`)
   daripada regex VIN 17-karakter strict dari legacy, supaya konsisten
   dan tidak mengulang masalah yang sama dengan contoh nyata
   (`01S208014054`).
2. Keterbatasan plat-tanpa-spasi (lihat "Keputusan desain #1") — kalau di
   praktiknya user sering mengetik plat tanpa spasi, ini layak
   disempurnakan di iterasi berikutnya (bukan blocker untuk Room 4 saat
   ini karena semua kasus di DoD/test terpenuhi).
