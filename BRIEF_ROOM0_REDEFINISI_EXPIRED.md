# BRIEF ROOM 7a → ROOM 0 — Usulan Perubahan Definisi "Expired": Populasi Berdasar Periode Saja, Bukan Exclude Status

**Konteks:** Klarifikasi langsung dari Wahyu (chat CLI production, 2026-07-24)
setelah melihat hasil `konversi attack list tcare expired bulan juli sa
bdr` yang ditolak (Opsi A, sudah di-tag `room7a-expired-history-validated`,
334 test). Ternyata definisi "expired" yang Wahyu maksud **berbeda** dari
definisi yang sudah berjalan di sistem — bukan revisi dari keputusan Opsi A
(itu tetap benar untuk definisi LAMA), tapi usulan **definisi baru**.

---

## Definisi LAMA (sistem sekarang, `repositories/attack_list_repository.py::find()`)

```sql
WHERE strftime('%Y-%m', batas_tcare) = <bulan>
  AND status NOT IN ('converted', 'resolved')
```

"Expired" = batas waktu lewat **DAN** unit itu **belum pernah convert**.
Begitu status berubah jadi `converted`, unit itu **otomatis dibuang** dari
hasil populasi "expired" — dianggap sudah selesai, tidak relevan lagi.

Konsekuensinya (root cause bug sebelumnya): pertanyaan "berapa yang
converted dari yang expired" secara struktural SELALU 0, karena populasi
"expired" sudah dijamin 100% berisi unit `pending` saja.

## Definisi BARU yang diusulkan (dikonfirmasi langsung Wahyu, 2026-07-24)

**"Expired bulan X"** = semua unit yang `batas_tcare`-nya jatuh di bulan X,
**apa pun status unit itu sekarang** (pending ATAU converted). Populasi
tidak lagi dikecualikan berdasarkan status — filter HANYA berbasis waktu
(`batas_tcare`).

Dengan definisi ini, query `attack list tcare expired juli sa bdr` bisa
menghasilkan populasi LEBIH BESAR dari 6 unit (bisa jadi 6 pending + N
converted = total lebih dari 6), dan pertanyaan lanjutan `konversi ...
expired ...` jadi bermakna: **dari total populasi itu, berapa yang sudah
convert** — bukan lagi pertanyaan yang secara struktural pasti 0.

## Contoh konkret (angka ilustrasi, BUKAN data asli)

| | Definisi LAMA | Definisi BARU |
|---|---|---|
| Filter SQL | `batas_tcare=Juli AND status NOT IN (converted,resolved)` | `batas_tcare=Juli` saja |
| Hasil "attack list ... expired ..." | 6 unit (semua pasti pending) | Misal 10 unit (6 pending + 4 converted) |
| Hasil "konversi ... expired ..." | Tidak valid ditanya (Opsi A, pesan penjelasan) | 4 dari 10 (bermakna, bisa dihitung) |

## Dampak ke bagian lain sistem — sudah dicek, TERISOLASI

Saya grep seluruh codebase untuk `expired_mode`/`status NOT IN`:

- `status NOT IN ('converted', 'resolved')` **HANYA muncul satu kali**,
  di `AttackListRepository.find()`.
- `expired_mode` **HANYA dipakai di jalur `attack_list` mode "list"**.
  Mode "Attack List Semua" (`_execute_all_summary`) secara eksplisit
  TIDAK mendukung `expired_mode` sama sekali (dikonfirmasi komentar
  service.py: *"Mode `expired` TIDAK didukung sama sekali di view
  ini... persis legacy"*) — jadi TIDAK terdampak perubahan ini.
  Mode "history" (`attack_list_history`) juga tidak terdampak (definisi
  ini murni domain `attack_list`, bukan `attack_list_history`).

**Kesimpulan:** perubahan definisi ini **terisolasi** ke satu method
repository + turunannya (mode list biasa untuk expired). Tidak menyebar
ke fitur lain yang sudah stabil.

## Yang PERLU dipastikan sebelum implementasi

1. **Regresi test existing** — `test_attack_list_find_expired_mode_excludes_converted`
   (dan variannya) **mengasumsikan** perilaku LAMA (exclude converted).
   Kalau definisi diganti, test ini **wajib direvisi** (bukan dihapus
   diam-diam) — perlu persetujuan eksplisit Room 0 karena ini mengubah
   ekspektasi test yang sudah pernah di-sign-off sebelumnya.
2. **Tampilan mode list biasa** (`attack list tcare expired juli sa bdr`,
   TANPA kata konversi) — populasinya akan ikut berubah (bisa lebih
   banyak dari sebelumnya, karena unit converted ikut muncul). Formatter
   perlu menampilkan status per unit dengan jelas (kolom `status` sudah
   ada di dataframe, tinggal pastikan breakdown pending/converted
   ditampilkan di ringkasan — pola ini sudah ada di mode list non-expired,
   tinggal disamakan untuk mode expired).
3. **Nama/istilah** — dengan definisi baru, kata "expired" jadi murni
   soal WAKTU (jatuh tempo di bulan X), bukan lagi menyiratkan "sudah
   gugur/tidak berlaku". Perlu dipertimbangkan apakah istilah ini masih
   pas, atau perlu penyesuaian bahasa di pesan/summary supaya tidak
   membingungkan user lain yang sudah terbiasa dengan makna lama
   ("expired" = gugur). Ini soal komunikasi/UX, bukan soal teknis, tapi
   penting supaya user lain tidak salah paham arti "expired" berubah.
4. **Kombinasi "konversi ... expired ..."** — dengan definisi baru, Opsi
   A (tolak dengan pesan penjelasan) **tidak lagi berlaku** untuk
   kombinasi ini secara langsung. Perlu jalur baru: hitung
   pending/converted dari populasi yang SUDAH pakai definisi baru (tidak
   perlu attack_list_history sama sekali, cukup dari attack_list dengan
   filter batas_tcare tanpa exclude status) — mirip pola perhitungan yang
   sudah ada di mode list non-expired (`total_converted`/`total_pending`
   dihitung dari raw_df sebelum filter tampilan, `_execute_list()`
   baris 224-229).

## Rencana implementasi (menunggu persetujuan Room 0)

```
repositories/attack_list_repository.py::find():
  expired_mode=True -> filter HANYA strftime(batas_tcare)=bulan,
  HAPUS kondisi "status NOT IN (converted, resolved)"

service.py::_execute_list():
  total_converted/total_pending sudah dihitung dari raw_df
  (baris 224-229) -- TIDAK PERLU logic baru, otomatis benar begitu
  query di atas diubah (raw_df akan berisi campuran pending+converted).

Kombinasi "konversi ... expired ...":
  HAPUS/revisi cabang _execute_conversion_summary_rejected() --
  bukan ditolak lagi, tapi tampilkan ringkasan pending/converted dari
  populasi baru (via _execute_list() yang sudah otomatis benar).
  wants_conversion_summary tetap dipakai sebagai sinyal "user minta
  fokus ke angka konversi", tapi Service TIDAK LAGI menolak -- cukup
  format pesan yang menonjolkan angka konversi (bukan daftar unit).
```

## Pertanyaan untuk Room 0

1. Setuju definisi "expired" diubah jadi murni berbasis
   `batas_tcare` (tanpa exclude status)?
2. Kalau ya, boleh revisi
   `test_attack_list_find_expired_mode_excludes_converted` (ganti
   ekspektasi, bukan dihapus tanpa jejak)?
3. Perlu penyesuaian istilah/bahasa di pesan (poin §3) atau cukup
   pakai kata "expired" seperti sekarang dengan makna baru?

Menunggu keputusan sebelum mulai coding.
