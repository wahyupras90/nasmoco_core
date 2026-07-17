# INT005 — KPI Detail

Menampilkan rincian KPI HARIAN (bukan agregat) untuk satu SA atau level
outlet, pada satu periode bulan. Sumber data sama dengan INT004
(`daily_kpi`), tapi ditampilkan per-baris/per-tanggal, bukan dijumlahkan.

## Contoh query yang didukung

- "kpi detail AGN bulan ini"
- "rincian kpi harian IND Januari 2026"
- "kpi per hari outlet 2026-03"

## Catatan

- Wajib menyebut kata domain "detail"/"harian"/"per hari"/"rincian" agar
  tidak bentrok dengan INT004 (KPI Summary).
- SA diverifikasi ke `daily_kpi` (bukan whitelist hardcode).
