# INT004 — KPI Summary

Menampilkan ringkasan KPI (unit entry, CPUS, revenue, jasa, TGP, ADT,
sublet, upselling, total liter) untuk satu SA atau level outlet, pada
satu periode bulan, dibandingkan dengan target (`target_bulanan`) kalau
tersedia.

## Contoh query yang didukung

- "kpi AGN bulan ini"
- "kpi IND Januari 2026"
- "kpi outlet 2026-03"
- "summary kpi bulan lalu"

## Catatan

- SA yang diketik diverifikasi ke `daily_kpi` (bukan daftar hardcode) —
  kalau tidak ketemu, hasilnya NOT_FOUND.
- Tidak menyebut SA / menyebut kata "outlet" → level outlet (semua SA
  termasuk transaksi Counter, sesuai keputusan bisnis yang dikonfirmasi).
- Target hanya tersedia untuk tahun 2026. Kalau user tanya periode 2024
  atau 2025, output tetap menampilkan angka KPI tapi bagian "vs Target"
  akan menyatakan target tidak tersedia untuk tahun tersebut.
