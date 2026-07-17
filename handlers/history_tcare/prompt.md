# prompt.md — History TCARE (INT003)

Sama seperti INT002, intent ini tidak memakai LLM untuk parsing — murni
regex di `parser.py`. File ini mendokumentasikan pola yang didukung.

## Pola teks yang dikenali `match()`

Harus mengandung kata history (`history`/`histori`/`riwayat`) **DAN**
kata `tcare` secara eksplisit (kebalikan dari INT002 yang menolak kata
`tcare`). Contoh:

- "history tcare MHFXXKF3JGK012345"
- "riwayat tcare mobil nopol B 1234 XYZ"
- "cek tcare punya Budi Santoso"

## Identifier customer/kendaraan

1. VIN / no_rangka — 17 karakter (sama seperti INT002 & legacy)
2. No polisi — pola sama seperti INT002
3. Nama customer — fallback

## Perbedaan penting dari kode legacy (`tools/history_tcare.py`)

- Legacy **hanya** menerima VIN sebagai identifier. Room 4 menambahkan
  dukungan plat nomor & nama (resolusi lewat `customer_profile`,
  BR027 — repository yang sama dipakai INT002).
- Legacy query riwayat ke `tcare_schedule` — **SALAH** (ADR024, final).
  Room 4 WAJIB query ke `tcare_schedule_full_history`.
- Legacy menyebut tabel info unit `unit_tcare` — nama aktual di skema
  adalah `tcare_unit`.
- Legacy menganggap "tidak ditemukan" hanya berdasarkan tabel info unit
  kosong. Room 4 menambahkan fallback: kalau info unit kosong tapi
  riwayat TCARE (`tcare_schedule_full_history`) ada, tetap dianggap OK
  (lihat `service.py` untuk detail & DoD test kasus lama-expired).
