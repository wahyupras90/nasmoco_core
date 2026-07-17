# ROOM 6 — Attack List + TCARE Web Status + TCARE Realtime (nasmoco_core)

Status: **selesai**, tervalidasi terhadap sistem asli (bukan cuma dummy):
`nasmoco.db` untuk INT008/INT012, dan situs `aftersales.toyota.astra.co.id`
untuk INT013 (login + fetch VIN nyata berhasil, lihat bagian "Validasi
terhadap sistem asli").

**Angka test final (kondisi sekarang, semua fitur di bawah ini
terintegrasi jadi satu, bukan cabang terpisah): 254 test passed.**
Verifikasi ulang kapan saja dengan `python -m pytest tests/ -v`.

Section-section di bawah disusun **sesuai urutan kronologi pengerjaan
sebenarnya** (bukan urutan topik) — angka "hasil test" di tiap section
selalu melanjutkan dari angka section sebelumnya, supaya bisa ditelusuri:

| # | Section | Baseline → Hasil |
|---|---|---|
| ADR027 awal | Composite Handler pertama kali | — → 217 |
| Revisi ADR027 | Bug #1 (priority) + Bug #2 (kosong v1) | 217 → 227 |
| §7 | Mode "expired" Attack List | 227 → 244 |
| §8 | Fix urutan kata "web tcare" | 244 → 246 |
| §9 | Plat/nama NOT_FOUND — hint UX | 246 → 248 |
| §10 | Bug #3 (definisi "kosong" v2) | 248 → 253 |
| §11 | Fix "attacklist" tanpa spasi | 253 → **254 (final)** |

Room 6 adalah **room pertama** yang menerapkan `BaseParser` (ADR025) dan
`WebRepository` (ADR026, sumber HTTP bukan SQLite).

## Struktur yang ditambahkan

```
repositories/
├── attack_list_repository.py        # INT008, extend BaseRepository
├── tcare_web_status_repository.py    # INT012, extend BaseRepository
└── tcare_realtime_web_repository.py  # INT013, ADR026 -- TIDAK extend BaseRepository

handlers/
├── attack_list/       {handler.py, service.py, formatter.py, parser.py}   # INT008
├── tcare_web_status/  {sama}                                              # INT012
└── tcare_realtime/    {sama}                                              # INT013
    # parser.py ketiganya extend parsers.base_parser.BaseParser (ADR025)

tests/
├── fixtures_room6.py
├── test_room6_parsers.py
├── test_room6_repositories.py
├── test_room6_handlers.py            # INT008 & INT012 (SQLite, via Router)
└── test_room6_tcare_realtime.py      # INT013, HTTP di-mock (TIDAK hit TAM asli)

config/settings.py    # +TAM_EMAIL, TAM_PASSWORD, TAM_TIMEOUT_CONNECT/READ
app_v2.py              # +3 baris router.register() di titik ekstensi resmi
diagnose_tcare_realtime.py    # skrip diagnostik manual (bukan bagian aplikasi)
diagnose_tcare_dashboard.py   # skrip diagnostik manual (bukan bagian aplikasi)
```

`app_v2.py::create_router()` ditambah 3 baris `router.register(...)` —
tidak ada perubahan lain pada file Room 1-5.

## Skema tabel yang dipakai

| Tabel | Dipakai untuk | Kolom kunci | Boleh dibaca Room 6? |
|---|---|---|---|
| `attack_list` (10.348 baris) | INT008 | `source`, `no_rangka`, `sa_terakhir`, `segment_rfm`, `program_id`, `status`, `sawa_status`, `sawa_expiry`. Breakdown per source (dikonfirmasi): CR7=181, CRM=8657, TCARE=1510 | ✅ Master unified — sumber utama |
| `attack_list_history` (10.348 baris) | INT008 (mode histori konversi) | `bulan`, `source`, `no_rangka`, `tgl_konversi`, `bulan_konversi` | ✅ Untuk statistik konversi per bulan |
| `crm_attack_list` | — | — | ❌ Tabel SUMBER ETL, bukan tampilan — TIDAK PERNAH dibaca langsung |
| `attack_list_lama` | — | — | ❌ Artefak legacy tidak dipakai — TIDAK PERNAH dibaca |
| `tcare_schedule` | INT008 (`tcare_pending_count()`) | `no_rangka`, `bulan_jadwal`, `bulan_realisasi`, `expired` | ✅ Subset ~3.544 kendaraan AKTIF — dikonfirmasi Room 0 sengaja beda dari INT002/003 (ADR024, lihat bawah) |
| `tcare_web_vehicle` / `tcare_web_service` / `tcare_web_errors` | INT012 | `no_rangka`, `model`, `owner`, `kunjungan`, `service_date`, `dealer`, `status`, `error` | ✅ Di-refresh scheduler Windows Task Scheduler (`etl_tcare_web.py`), DI LUAR nasmoco_core |
| *(tidak ada — HTTP)* | INT013 | — | Live fetch ke `aftersales.toyota.astra.co.id/data`, TIDAK PERNAH baca/tulis `nasmoco.db` |

### Kenapa `crm_attack_list` dan `attack_list_lama` tidak dibaca langsung

`crm_attack_list` adalah tabel sumber yang dibaca `etl_attack_list.py` untuk
membangun bagian CRM di `attack_list` (yang sudah digabung dengan
`customer_profile`) — membaca ulang di Room 6 akan menduplikasi
data/logic ETL. `attack_list_lama` tidak dirujuk oleh proses apa pun
(ETL/evaluator/legacy handler) yang teridentifikasi — kemungkinan artefak
legacy, tidak dipakai kecuali ada konfirmasi Room 0 di masa depan.

## ADR024 — klarifikasi (bukan kontradiksi dengan Room 4)

- **INT003 (History TCARE, Room 4):** WAJIB `tcare_schedule_full_history`
  (populasi lengkap termasuk expired) — user bisa tanya riwayat kendaraan
  yang sudah lama tidak aktif.
- **INT008 (Attack List, Room 6):** WAJIB `tcare_schedule` (subset ~3.544
  kendaraan aktif) — kendaraan yang sudah lama expired harus DIKELUARKAN
  dari daftar follow-up (kalau tidak, sales disuruh follow-up unit yang
  sudah tidak relevan bertahun-tahun). Dikonfirmasi eksplisit Room 0,
  bukan kesalahan.

## ADR026 — `WebRepository` (pola baru, INT013)

`TCARERealtimeWebRepository` **tidak extend `BaseRepository`** (itu
khusus SQLite) — kontraknya tetap mengembalikan `pandas.DataFrame` supaya
Service/Handler/Formatter di atasnya tidak perlu tahu bedanya sumber
SQLite atau HTTP.

Beda dari Repository SQLite biasa:
- **Session-per-request** — instance baru dibuat tiap kali `Service`
  dipanggil (`TCARERealtimeService._default_repo_factory`), BUKAN
  di-reuse lintas request. Ini disengaja untuk thread-safety karena
  `app_v2.py` melayani request API via `ThreadingHTTPServer`.
- **Timeout wajib**: `(10, 20)` detik (connect, read) — dikonfirmasi.
  Script referensi lama (`tcare_realtime.py`) tidak punya timeout sama
  sekali (risiko hang selamanya kalau TAM lambat/down).
- **Tidak pernah `exit()`/crash** — semua kegagalan (login, timeout,
  parsing) ditangkap sebagai `TCARERealtimeError` di level Repository,
  lalu jadi `HandlerResult` dengan code `INT013_ERROR` di Handler.
- **Kegagalan per-VIN bukan error request** — kalau user minta banyak
  VIN sekaligus, satu VIN gagal (tidak ditemukan/timeout) tidak
  menggagalkan VIN lain. Ditangani lewat `VinFetchResult.error` per VIN,
  bukan exception yang menjalar (lihat `get_multiple()`).
- **Kredensial**: `TAM_EMAIL`/`TAM_PASSWORD` di `config/settings.py`,
  dibaca dari environment variable/`.env` (`python-dotenv`) — SENGAJA
  tidak ada default hardcode. Kalau kosong, Repository menolak jalan
  (`ValueError`), ditangkap Handler jadi `INT013_ERROR`, bukan crash.

## Validasi terhadap sistem asli

Ketiga intent sudah dites langsung terhadap sistem produksi (bukan cuma
dummy/mock), dengan hasil:

- **INT008**: `attack list source tcare` → 1.510 unit, breakdown per
  source cocok dengan angka asli (CR7=181, CRM=8657, TCARE=1510).
- **INT012**: `status tcare web <no_rangka>` → data kendaraan + histori
  kunjungan terbaca benar dari `tcare_web_vehicle`/`tcare_web_service`.
- **INT013**: login ke `aftersales.toyota.astra.co.id` berhasil, VIN
  `MHKA6GK6JSJ084260` (kendaraan CALYA nyata) berhasil di-fetch dan
  di-parse — ketiga tabel HTML (kendaraan, customer, histori 7 kunjungan)
  terbaca sesuai struktur asli, termasuk baris histori dengan nilai
  kosong (`-`).

### Temuan struktur HTML asli INT013 (bukan asumsi — hasil inspeksi langsung)

- `table[0]` (data kendaraan): format `key | : | value` per baris — cocok
  dengan asumsi awal, tidak perlu penyesuaian.
- `table[1]` (customer): **kalau customer belum registrasi**, dirender
  sebagai **SATU baris `<td colspan="3">`** berisi pesan teks ("Owners
  have not registered..."), BUKAN format key-value 3-kolom seperti
  kendaraan. Parser awal salah asumsi ini (baris seperti ini otomatis
  ter-skip, informasinya hilang senyap) — **sudah diperbaiki**:
  baris 1-kolom sekarang ditangkap sebagai `{"key": "catatan", "value": <pesan>}`.
- `table[2]` (histori service): format 6 kolom (`Service No`, `Service
  Date`, `Dealer`, `Tepat Waktu`, `Status`, `Ontime Service`) — cocok
  dengan asumsi awal.
- **VIN tidak terdaftar**: halaman redirect ke `/data/dashboard` (0 tabel
  ditemukan) — bukan error/404 terpisah. Ditangani sebagai
  `"Data tidak ditemukan"` per-VIN, bukan crash.

Dua skrip diagnostik manual (`diagnose_tcare_realtime.py`,
`diagnose_tcare_dashboard.py`) disertakan di root project — bukan bagian
aplikasi, tapi berguna kalau di masa depan situs TAM berubah struktur
lagi dan perlu debug ulang.

## Contoh query yang didukung

### INT008 — Attack List
- `"attack list"` — semua unit, semua source
- `"attack list source tcare"` — filter source
- `"attack list status pending"` — filter status
- `"attack list untuk AGN"` — filter SA
- `"berapa total attack list"` — ringkasan saja (dataframe kosong, summary tetap terisi — pola sama seperti WIP Room 5)
- `"attack list konversi bulan lalu"` — mode histori (statistik konversi)

### INT012 — TCARE Web Status
- `"status tcare web <no_rangka>"`
- `"tcare web status error terakhir"` — daftar unit gagal di-scrape

### INT013 — TCARE Realtime
- `"cek tcare realtime <VIN>"`
- `"cek tcare realtime <VIN1> dan <VIN2>"` — banyak VIN sekaligus, tidak ada batas jumlah

## Keputusan desain penting

### 1. Dedup & status konversi dibaca apa adanya (BR008, BR026)
`attack_list` sudah di-dedup ETL (`etl_attack_list.py`, prioritas
TCARE>CRM>CR7) dan status konversi sudah dihitung `evaluator_konversi.py`.
Room 6 **tidak mengimplementasikan ulang** logic ini — `AttackListService`
hanya membaca kolom `status`/`tgl_konversi`/`bulan_konversi` apa adanya.

### 2. Parameterized query, bukan f-string (keamanan)
`attack_list.py` legacy membangun SQL dengan f-string interpolation
langsung (rawan SQL injection). `AttackListRepository.find()` memakai
`?` placeholder lewat `BaseRepository.execute()`, konsisten dengan pola
aman Room 4/5. Logika filter dicontoh dari legacy, implementasinya tidak.

### 3. Ekstraksi kandidat SA — bug ditemukan & diperbaiki lewat unit test
`AttackListParser` awalnya memakai `extract_sa_candidate()` (helper Room 5)
lalu men-filter hasilnya dengan stopword tambahan Room 6. Ini **bug**:
`extract_sa_candidate()` berhenti di kandidat pertama pakai stopword-nya
SENDIRI (tidak tahu soal stopword Room 6), jadi kata domain seperti
"ATTACK"/"LIST" "mencuri" posisi kandidat pertama dan SA asli di
belakangnya (mis. "AGN") tidak pernah diperiksa. **Diperbaiki**: parser
sekarang melakukan loop sendiri memakai `SA_CANDIDATE_REGEX` +
stopword gabungan (`SA_STOPWORDS` Room 5 + stopword domain Room 6) sejak
awal, bukan sebagai post-filter.

### 4. Kata "list" sengaja dikeluarkan dari deteksi "mau daftar lengkap"
Trigger phrase intent ini sendiri (`"attack list"`) selalu mengandung
kata "list" — kalau dipakai sebagai sinyal "user minta daftar lengkap",
`wants_summary_only` akan SELALU `False` untuk semua query attack list
(bug ditemukan lewat unit test). Kata "daftar"/"detail"/"rincian" (Bahasa
Indonesia) sudah cukup mewakili niat ini di domain Attack List.

### 5. `segment_rfm` dan `program_id` — ekstraksi best-effort
Belum ada sample nilai `segment_rfm` asli dari data riil saat parser ini
ditulis, jadi ekstraksinya berbasis pola generik (`"segment <nilai>"` /
`"program <angka>"`), SENGAJA tidak menebak/whitelist nilai spesifik.
**Perlu sample data asli dari Room 0 untuk disempurnakan** — non-blocking,
tidak mempengaruhi filter source/status/SA yang sudah solid.

### 6. Formatter menangani NULL/None secara eksplisit
Ditemukan lewat test manual terhadap DB asli: kolom SQLite yang bernilai
`NULL` tampil sebagai literal `"None"` di pesan (bug formatting Python,
bukan bug data). Formatter INT012 sekarang punya helper `_display()` yang
mengubah `None`/`NaN`/string kosong jadi `"-"`.

## Error handling

- INT008/INT012: `RepositoryError` (E001/E002) ditangkap di Handler,
  jadi `{intent}_ERROR`. Tidak ada NOT_FOUND untuk 0 hasil filter — itu
  jawaban valid (sama seperti WIP Room 5).
- INT013: dua lapis penanganan error —
  1. **Level request**: kredensial kosong / kegagalan tak terduga →
     `INT013_ERROR`, ditangkap eksplisit di Handler.
  2. **Level per-VIN**: VIN tidak ditemukan / timeout / gagal parse →
     BUKAN error request, masuk sebagai bagian hasil normal
     (`VinFetchResult.error`), ditampilkan Formatter tanpa menggagalkan
     VIN lain yang diminta bersamaan.

## Dependency baru

`requests` dan `beautifulsoup4` (untuk INT013). Project belum punya
`requirements.txt` terpusat — instal manual:
```
pip install requests beautifulsoup4
```

## Definition of Done

- [x] INT008: Repository baca `attack_list`/`attack_list_history`, TIDAK
      PERNAH baca `crm_attack_list`/`attack_list_lama` langsung
- [x] INT008: semua query parameterized (`?`), tidak ada f-string SQL
- [x] INT008: dedup & status konversi dibaca apa adanya (BR026)
- [x] INT012: Query Handler biasa, extend `BaseRepository`
- [x] INT013: `TCARERealtimeWebRepository` dengan timeout eksplisit,
      error handling lengkap, tidak ada `exit()`/crash, tidak menulis ke
      `nasmoco.db`
- [x] INT013: kegagalan per-VIN dikembalikan sebagai bagian hasil, bukan
      menggagalkan seluruh request
- [x] Ketiga Parser extend `parsers.base_parser.BaseParser` (ADR025)
- [x] `intent_id`/`name` benar untuk ketiga Handler (INT008/012/013)
- [x] Parameter Service pakai dataclass typed (ADR020)
- [x] `HandlerResult.summary` dict terstruktur (ADR019)
- [x] Formatter dipanggil dari Handler, bukan Service (ADR006)
- [x] Unit test per layer — INT013 pakai HTTP di-mock (HTML asli hasil
      inspeksi, bukan hit web TAM di test)
- [x] Integrasi: `router.register(...)` untuk ketiga Handler di
      `app_v2.py::create_router()`
- [x] Tidak ada perubahan pada file Room 1-5 yang sudah validated selain
      3 baris register di titik ekstensi resmi
- [x] README Room 6 (dokumen ini)
- [x] Divalidasi terhadap sistem asli (bukan cuma dummy) — INT008/012
      terhadap `nasmoco.db`, INT013 terhadap situs TAM langsung

**Hasil test:** 195 test passed (Room 1-6 gabungan), termasuk 4 file test
baru Room 6 (`test_room6_parsers.py`, `test_room6_repositories.py`,
`test_room6_handlers.py`, `test_room6_tcare_realtime.py` — 51 test baru).

## ADR027 — Composite Handler (History TCARE + Web Fallback)

**Ditambahkan setelah diskusi Room 0** atas permintaan tambahan Wahyu:
kalau user tanya `"history tcare <X>"` (tanpa sebut web/realtime) dan hasil
di database lokal (INT003, Room 4) NOT_FOUND, sistem otomatis mencoba
fallback ke web TAM (INT013, Room 6) sebelum menyerah.

### Kenapa Composite Handler, bukan modifikasi langsung

Room 0 memilih pola **Composite Handler** (bukan memperluas Service Room 4,
bukan juga lapisan orkestrasi generik di Router) supaya:
- `handlers/history_tcare/*` (Room 4) dan `handlers/tcare_realtime/*`
  (Room 6) **tidak disentuh sama sekali** — dipakai apa adanya lewat
  import biasa, pola sama seperti `CustomerProfileRepository` shared
  (BR027). Satu-satunya penambahan aditif: dua method kecil di
  `TCARERealtimeService` (`credentials_configured()`, `get_single()`) —
  tidak mengubah `execute()`/perilaku yang sudah ada.
- Router (`ai/router.py`) tidak perlu tahu apa-apa soal fallback ini —
  dari sudut pandang Router, `CompositeHistoryTCAREHandler` tetap SATU
  Handler biasa yang `match()`/`execute()` seperti biasa. Tidak perlu ADR
  baru soal "Router chaining Handler berdasarkan hasil".

### Struktur

```
handlers/history_tcare_composite/
├── handler.py      # CompositeHistoryTCAREHandler(BaseHandler)
└── formatter.py     # format khusus utk hasil dari web (prefix sumber)

tests/
└── test_room6_composite_history_tcare.py   # 11 test, web service di-mock
```

`app_v2.py`: HANYA 1 baris registrasi diganti (`HistoryTCAREHandler` →
`CompositeHistoryTCAREHandler`), priority tetap sama (20).

### Alur

1. `CompositeHistoryTCAREHandler.execute()` panggil `HistoryTCAREHandler`
   (Room 4) **apa adanya** dulu.
2. Kalau hasilnya BUKAN `INT003_NOT_FOUND` (yaitu OK/AMBIGUOUS/ERROR) →
   dikembalikan **identik** tanpa perubahan apa pun — kasus normal tidak
   terpengaruh sama sekali.
3. Kalau `INT003_NOT_FOUND` → resolusi identifier di-reuse dari
   `handlers.history_tcare.parser.parse()` (Room 4, TIDAK ditulis ulang).
   Fallback ke web **HANYA** dicoba kalau `identifier_type == "no_rangka"`
   — pencarian by plate/nama yang NOT_FOUND di lokal tidak punya VIN untuk
   dicoba ke web sama sekali (itu justru yang gagal ditemukan).
4. Kalau kredensial TAM (`TAM_EMAIL`/`TAM_PASSWORD`) belum diisi →
   fallback di-skip diam-diam ke user (tetap tampilkan NOT_FOUND lokal),
   TAPI `logger.warning(...)` tercatat supaya ops tahu ini ter-skip karena
   config, bukan karena tidak ada datanya.
5. Fetch ke web (`TCARERealtimeService.get_single()`) dengan 3 kemungkinan
   hasil:
   - **Ditemukan** → `INT003_OK`, message diberi prefix
     `"[Realtime dari web TAM]"`, `metadata["source"] = "web_tam_realtime"`
     (transparansi wajib, dikonfirmasi Room 0).
   - **Tidak ditemukan di web juga** → `INT003_NOT_FOUND`, pesan
     eksplisit "tidak ditemukan di database lokal maupun di web TAM".
   - **Gagal teknis** (login/timeout/parsing) → `INT003_ERROR` — SENGAJA
     BUKAN `NOT_FOUND`, supaya tidak disimpulkan sebagai "datanya memang
     tidak ada" padahal cuma gagal teknis sementara.

### Catatan kopling yang perlu diperhatikan (dilaporkan, non-blocking)

Pembedaan "tidak ditemukan di web" vs "gagal teknis" saat ini dilakukan
dengan **mencocokkan teks** pesan error dari `TCARERealtimeWebRepository`
(marker `"tidak ditemukan"`, lihat `formatter.is_not_found_error()`) —
BUKAN lewat field/kategori error terpisah, supaya tidak perlu mengubah
file Room 6. Ini sengaja didokumentasikan sebagai kopling implisit:
kalau wording pesan error di `repositories/tcare_realtime_web_repository.py`
berubah di masa depan, klasifikasi ini bisa jadi tidak akurat lagi.
**Saran perbaikan non-blocking**: kalau Room 6 nanti menambah field
kategori error eksplisit di `VinFetchResult` (mis. `error_kind:
"not_found" | "technical"`), kopling ini bisa dihilangkan.

### Definition of Done (ADR027)

- [x] `CompositeHistoryTCAREHandler` dibuat, TIDAK mengubah
      `handlers/history_tcare/*` atau `handlers/tcare_realtime/*` (kecuali
      2 method aditif di `TCARERealtimeService`)
- [x] Kasus normal (ditemukan di lokal) — hasil IDENTIK dengan
      `HistoryTCAREHandler` asli (diuji lewat perbandingan langsung)
- [x] NOT_FOUND lokal + web BERHASIL → `INT003_OK`, prefix
      `"[Realtime dari web TAM]"`, `metadata["source"]`
- [x] NOT_FOUND lokal + web JUGA NOT_FOUND → `INT003_NOT_FOUND`, pesan
      sebut "maupun di web TAM"
- [x] NOT_FOUND lokal + web GAGAL TEKNIS → `INT003_ERROR`, bukan NOT_FOUND
- [x] Kredensial TAM kosong → skip diam-diam + `logger.warning`
- [x] Identifier bukan no_rangka (plate/nama) → fallback di-skip, tidak
      mencoba fetch web sama sekali
- [x] Tidak ada duplikasi regex/logic resolusi identifier — reuse
      `handlers.history_tcare.parser.parse()` apa adanya
- [x] `app_v2.py`: HANYA 1 baris registrasi diganti
- [x] Regresi: seluruh test suite Room 1-6 (217 test) tetap PASS
- [x] Test baru untuk semua skenario DoD, web service di-mock
- [x] README (bagian ini) mendokumentasikan pola Composite Handler
      sebagai preseden untuk kasus fallback lintas Room di masa depan

**Hasil test:** 217 test passed (Room 1-6 + Composite Handler gabungan),
termasuk 11 test baru (`test_room6_composite_history_tcare.py`).

### Revisi ADR027 — 2 bug kritis ditemukan & diperbaiki

Setelah sign-off awal, ditemukan 2 bug (root cause: keputusan ADR027 versi
awal kurang lengkap, BUKAN kesalahan implementasi):

**Bug #1 — permintaan eksplisit "web" tidak pernah sampai ke INT013.**
`CompositeHistoryTCAREHandler` (priority 20) dan `TCARERealtimeHandler`
(priority 10 lama) sama-sama `match()` untuk teks yang mengandung kata
"tcare web" DAN "history"/"riwayat" (mis. `"history tcare web <VIN>"`).
Tie-break ADR022 (highest priority wins) membuat Composite SELALU
menang, jadi INT013 tidak pernah kebagian giliran walau user eksplisit
minta "web". **Fix**: `TCARERealtimeHandler` priority dinaikkan ke **30**
di `app_v2.py` (satu-satunya perubahan untuk bug ini — tidak ada
perubahan logic).

**Bug #2 — "riwayat kosong tapi unit dikenal" tidak trigger fallback.**
`HistoryTCAREService` (Room 4, logic BENAR untuk tujuannya sendiri, TIDAK
diubah) sengaja mengembalikan `INT003_OK` (bukan `NOT_FOUND`) kalau
`unit_info` ADA tapi `schedule_df` kosong — supaya identitas kendaraan
tetap tampil walau riwayat TCARE-nya nol. `CompositeHistoryTCAREHandler`
versi awal cuma cek `code == INT003_NOT_FOUND`, jadi kasus ini lolos dari
kondisi fallback. **Fix**: definisi "kosong" diperluas mencakup
`success=True AND summary["total_riwayat_tcare"] == 0`. No_rangka untuk
fallback pada kasus ini diambil LANGSUNG dari `local_result.summary["no_rangka"]`
(sudah ter-resolve Room 4, apa pun cara user mencari — nama/plat/no_rangka),
BUKAN re-parse teks.

**Kasus baru yang muncul dari fix Bug #2**: kalau fallback dicoba dan web
JUGA tidak punya riwayat (VIN ditemukan tapi 0 kunjungan, ATAU VIN tidak
terdaftar di web sama sekali) — dikonfirmasi Wahyu: tampilkan **identitas
kendaraan** (dari hasil lokal asli) + keterangan **"bukan TCARE"**,
BUKAN NOT_FOUND/ERROR (kendaraan DITEMUKAN, cuma memang bukan peserta
TCARE — beda dari kasus "tidak dikenal sama sekali").

**Keputusan desain tambahan (dibuat sendiri, ditandai jelas karena tidak
eksplisit disebut di brief revisi):** kalau fallback untuk kasus
"OK-tapi-kosong" ini gagal TEKNIS (bukan "web juga kosong") — hasil
`local_result` dikembalikan apa adanya (BUKAN di-downgrade jadi ERROR),
karena identitas kendaraan dari lokal sudah valid dan bernilai; tidak
pantas dianggap gagal total hanya karena pengecekan tambahan (bersifat
suplementer) gagal. Ini beda dari kasus NOT_FOUND total, di mana
kegagalan teknis MEMANG jadi ERROR karena tidak ada apa pun lain untuk
ditampilkan.

**Test tambahan** (`test_room6_composite_history_tcare.py`, 10 test
baru): termasuk test negatif eksplisit yang sengaja memasang priority
versi LAMA untuk membuktikan bug memang nyata (bukan cuma klaim di
brief), test routing level-Router untuk Bug #1, dan fixture baru
(`db_path_with_empty_tcare_unit`, dibuat via INSERT tambahan langsung ke
temp DB — TIDAK mengubah `tests/fixtures_room4.py`) untuk kasus "unit
dikenal, riwayat TCARE nol baris" yang belum ada di fixture Room 4
sebelumnya.

**Hasil test setelah revisi:** 227 test passed (217 lama + 10 baru),
tidak ada regresi.

---

### 7. Mode "expired" ditambahkan setelah verifikasi terhadap script legacy

Wahyu menanyakan apakah query seperti `"attack list tcare expired bulan
agustus"` bisa jalan. Saat itu belum bisa — "expired" dan periode
diabaikan begitu saja. Setelah Wahyu kirim `tools/attack_list.py` dan
`tools/export_attack_list.py` (project legacy), ketahuan semantik
persisnya:

- **"expired" BUKAN nilai kolom `status`** (nilai asli cuma
  pending/converted/resolved) — ini **mode filter terpisah** berbasis
  `batas_tcare`:
  ```sql
  WHERE strftime('%Y-%m', batas_tcare) = <bulan>
    AND status NOT IN ('converted', 'resolved')
  ```
  Menggantikan filter status biasa, bukan ditambahkan ke atasnya —
  diimplementasikan persis begitu di
  `AttackListRepository.find(expired_mode=True, period_yyyymm=...)`.
- Kata "bulan ini"/"bulan agustus" HANYA memfilter dalam mode expired ini
  (reuse `extract_period()`). Di luar mode expired, periode tidak
  memfilter tabel `attack_list` sama sekali (cuma dipakai mode "history").

**Bug ditemukan & diperbaiki sekaligus:**

1. **Ekstraksi SA salah tangkap kata umum** — sebelumnya pakai regex
   generik + stopword (`SA_CANDIDATE_REGEX`), kata "yg" (singkatan
   "yang") salah tertangkap jadi kode SA. **Diperbaiki**: diganti ke
   **whitelist eksplisit** `VALID_SA = (AGN, ARIS, BDR, IND, NRK, SAID,
   ZKY, KHA)` — dikonfirmasi Wahyu masih akurat. Whitelist jauh lebih
   aman daripada blacklist/stopword untuk domain kode pendek begini.
2. **`segment_rfm` sekarang whitelist juga** — `VALID_SEGMENT = (at risk,
   lost, champion, loyal, potential, new)`, diambil dari
   `tools/attack_list.py` legacy. Ini jawaban dari item terbuka
   sebelumnya (dulu best-effort regex karena belum ada sample data
   asli).
3. **Gap di `handlers/_shared/period_parser.py` (modul lintas-Room,
   dipakai juga Room 5)**: nama bulan tanpa tahun (mis. "bulan agustus"
   tanpa "2026") sebelumnya TIDAK terdeteksi sebagai periode eksplisit
   sama sekali — jatuh ke default diam-diam (bulan berjalan,
   `is_explicit=False`). **Diperbaiki** (murni aditif, dikonfirmasi tidak
   ada test Room 5 yang bergantung pada perilaku lama untuk kasus ini):
   nama bulan tanpa tahun sekarang default ke tahun berjalan dengan
   `is_explicit=True` — meniru persis `_validate_bulan()` di
   `tools/attack_list.py` legacy.

**Item yang SENGAJA belum diimplementasikan (perlu konfirmasi dulu):**
`program_id` di skema `attack_list` bertipe INTEGER, tapi
`tools/attack_list.py` legacy membandingkan `program_id = 'P1'` (kode
teks via `PROGRAM_KEYWORD_MAP`, mis. "panggil pulang"→P1). Representasi
riil di tabel `attack_list` unified belum bisa diverifikasi (kemungkinan
sudah beda dari legacy, sudah pakai id numerik asli dari
`marketing_program`). Ekstraksi `program_id` di parser TETAP hanya
menerima angka literal (`"program 11"`) — alias teks seperti "panggil
pulang" TIDAK ditambahkan sampai representasi program_id riil
dikonfirmasi, supaya tidak salah filter tanpa ketahuan.

**Test tambahan**: 17 test baru (5 di `test_room6_parsers.py` untuk
whitelist SA/segment + expired_mode + gap period_parser, 5 di
`test_room6_repositories.py` untuk filter `batas_tcare`, 3 di
`test_room6_handlers.py` end-to-end). Fixture `attack_list` di
`tests/fixtures_room6.py` ditambah kolom `batas_tcare` dengan data uji.

**Hasil test setelah fitur ini:** 244 test passed (227 lama + 17 baru),
tidak ada regresi ke Room manapun (termasuk Room 5 yang berbagi
`period_parser.py`).

---

### 8. Fix kecil — urutan kata "web tcare" vs "tcare web"

Ditemukan Wahyu: `"history web tcare <plat>"` (kata "web" MENDAHULUI
"tcare") tidak ter-route ke INT013 — `TCARERealtimeHandler.match()`
sebelumnya cuma cek substring urutan tetap `"tcare web"` (satu arah
saja), jadi kalau dibalik ("web tcare") tidak ke-detect sama sekali,
akibatnya jatuh ke `CompositeHistoryTCAREHandler` (yang juga match untuk
teks yang sama, karena mengandung "history"+"tcare").

**Fix**: `TCARERealtimeParser.match()` (`handlers/tcare_realtime/parser.py`)
sekarang cek kata `"tcare"` + (`"web"` ATAU `"realtime"`) sebagai token
terpisah, urutan bebas — bukan substring berurutan tetap. Kata "tcare"
tetap WAJIB ada supaya tidak salah tangkap kalimat lain yang cuma
mengandung "web"/"realtime" tanpa konteks TCARE. 2 test baru
(`test_match_word_order_reversed_web_tcare`,
`test_match_web_without_tcare_still_rejected`).

**Hasil test:** 246 test passed (244 sebelumnya + 2 baru), tidak ada
regresi.

---

### 9. Keputusan Room 0 — plat/nama NOT_FOUND total TIDAK fallback ke web

Sempat ditanyakan: kalau user search History TCARE pakai plat/nama dan
itu NOT_FOUND total di lokal (bukan cuma "riwayat kosong"), apakah bisa
juga otomatis fallback ke web seperti kasus lain?

**Dikonfirmasi Wahyu**: web TAM (`aftersales.toyota.astra.co.id`) **hanya
bisa dicek pakai VIN** — tidak ada endpoint cari by plat/nama. Kalau
plat/nama NOT_FOUND total di lokal, tidak ada VIN yang bisa dikirim ke
web sama sekali — ini keterbatasan API pihak TAM, bukan gap coding.

Sempat diusulkan opsi cross-reference ke tabel Room 6 (`attack_list.no_polisi`
atau `tcare_web_vehicle`) untuk cari `no_rangka` alternatif kalau
`customer_profile` (Room 4) gagal. **Investigasi dulu** (bukan asumsi):
dicek `repositories/customer_profile_repository.py::get_by_no_polisi()` —
normalisasi plat (strip/spasi/case) **sudah benar** (`REPLACE(REPLACE(UPPER(no_polisi), '-', ''), ' ', '') = ?`),
jadi NOT_FOUND yang terjadi kemungkinan besar valid (datanya memang tidak
ada), bukan bug normalisasi.

**Keputusan Room 0**: opsi cross-reference **ditolak** berdasarkan bukti
investigasi di atas. Perilaku existing (plat/nama NOT_FOUND total = tetap
NOT_FOUND, tidak ada fallback web) **final, tidak perlu kode baru**.

**Satu penambahan kecil disetujui** (non-blocking, murni UX): pesan
NOT_FOUND untuk kasus ini sekarang diberi petunjuk kenapa fallback web
tidak dicoba, supaya user tidak bingung:

```
"<pesan NOT_FOUND asli dari Room 4>

Catatan: Web TAM hanya bisa dicek pakai nomor rangka (VIN) -- kalau
kamu punya VIN kendaraan ini, coba tanya lagi pakai VIN-nya."
```

Implementasi: `CompositeHistoryTCAREHandler._add_no_web_lookup_hint()`.
Murni tambahan teks — `success`/`code`/`dataframe`/`summary` semuanya
sama persis dengan `local_result` asli, tidak ada logic yang berubah.
2 test baru (`test_identifier_type_name_not_found_gets_vin_hint`,
`test_identifier_type_plate_not_found_gets_vin_hint`).

**Hasil test:** 248 test passed (246 sebelumnya + 2 baru), tidak ada
regresi.

---

### 10. Bug #3 (revisi kedua ADR027) — jumlah baris jadwal ≠ riwayat efektif

Ditemukan Wahyu (2026-07-16) lewat kasus nyata: `MHKE8FB3JNK077471`
punya `total_riwayat_tcare: 7` (7 baris milestone 1K-60K), sehingga
Bug #2 (definisi "kosong" = `total_riwayat_tcare == 0`) tidak
menganggapnya kosong dan fallback tidak dicoba. Tapi diperiksa lagi
isinya: **ketujuh baris itu `status='pending'`, `bulan_realisasi=None`,
`expired=1` — tidak ada SATU pun yang benar-benar terjadi.** Customer ini
punya jadwal, tapi riwayat *efektif*-nya nol.

**Root cause**: `total_riwayat_tcare` menghitung JUMLAH BARIS JADWAL,
bukan jumlah kunjungan yang benar-benar terealisasi.

**Fix** (dikonfirmasi Wahyu): definisi "kosong" diperluas lagi lewat
`CompositeHistoryTCAREHandler._is_effectively_empty(schedule_df)` —
dataframe kosong (0 baris) **ATAU** semua baris punya `bulan_realisasi`
kosong/None (tidak ada satupun yang benar-benar terealisasi). Kalau
**minimal satu** baris punya `bulan_realisasi` terisi, TIDAK dianggap
kosong — tetap pakai data lokal, tidak fallback (walau baris lain masih
pending).

```python
@staticmethod
def _is_effectively_empty(schedule_df) -> bool:
    if schedule_df is None or schedule_df.empty:
        return True
    if "bulan_realisasi" not in schedule_df.columns:
        return False  # fail-safe: tidak bisa pastikan, jangan anggap kosong
    col = schedule_df["bulan_realisasi"]
    is_blank = col.isna() | (col.astype(str).str.strip() == "") | (col.astype(str).str.lower() == "none")
    return bool(is_blank.all())
```

**Test tambahan**: 5 test baru di `test_room6_composite_history_tcare.py`
(`test_bug3_*`), termasuk test regresi penting
`test_bug3_partial_realization_not_treated_as_empty` — unit dengan
**minimal satu** baris sudah realisasi TIDAK BOLEH fallback ke web, meski
baris lain masih pending. Fixture baru
(`UNREALIZED_TCARE_NO_RANGKA`/`PARTIAL_REALIZED_NO_RANGKA`) ditambahkan
ke `db_path_with_empty_tcare_unit`, tetap tidak mengubah
`tests/fixtures_room4.py`.

**Hasil test:** 253 test passed (248 sebelumnya + 5 baru), tidak ada
regresi.

---

### 11. Fix kecil — "attacklist" (tanpa spasi) belum didukung

Wahyu sempat konfirmasi eksplisit ("Iya, tanpa spasi didukung") bahwa
`"attacklist"` (satu kata) harus jadi trigger yang sah, sama seperti
`"attack list"`. Sempat tertunda tanpa sengaja (percakapan teralihkan ke
debugging cache bytecode). Ditemukan lagi lewat query nyata
(`"attacklist tcare expired agustus sa bdr"` — `match()` return `False`).

**Fix**: tambah `"attacklist"` ke `ATTACK_LIST_KEYWORDS`
(`handlers/attack_list/parser.py`). 1 test baru
(`test_attack_list_match_no_space_variant`).

**Hasil test:** 254 test passed (253 sebelumnya + 1 baru), tidak ada
regresi.

---

## Catatan untuk Room 0 / Room 7-8

1. **Perlu sample nilai `segment_rfm` asli** untuk menyempurnakan
   ekstraksi filter di `AttackListParser` (saat ini best-effort, lihat
   poin desain #5 di atas).
2. **Pola `WebRepository` (ADR026)** relevan kalau Room 7/8 juga butuh
   integrasi ke sumber non-SQLite — pertimbangkan reuse pola
   session-per-request + timeout eksplisit + error-per-item, bukan
   menulis ulang dari nol.
3. Extended Warranty (INT009) tetap ditunda sesuai brief — butuh
   `BaseAction`/`JobStore` yang belum didesain, TIDAK dikerjakan di Room 6.
4. Dua skrip diagnostik (`diagnose_tcare_realtime.py`,
   `diagnose_tcare_dashboard.py`) sengaja ditinggalkan di root project —
   bukan bagian aplikasi produksi, tapi berguna untuk debug cepat kalau
   struktur situs TAM berubah lagi di masa depan.
