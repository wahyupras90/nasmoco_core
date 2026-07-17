# INT006 — Ranking

Menampilkan peringkat SA berdasarkan metrik KPI (revenue/cpus/unit
entry/liter/jasa/tgp) untuk satu periode bulan, dibandingkan dengan
target kalau tersedia.

## Contoh query yang didukung

- "ranking revenue bulan ini"
- "peringkat cpus Januari 2026"
- "ranking SA 2026-03"

## Keputusan bisnis (dikonfirmasi eksplisit dengan user)

- `sa = 'Counter'` (transaksi tanpa WO) SELALU di-exclude dari ranking.
- Baris agregat outlet (`target_bulanan.sa='TOTAL'`) TIDAK ikut diberi
  nomor rank -- ditampilkan terpisah di akhir sebagai "jumlah", bukan
  entitas yang di-rank.
- Urutan rank berdasarkan ANGKA AKTUAL metrik yang dipilih, bukan
  persentase capaian terhadap target.
