# INT007 — WIP (Work In Progress)

Menampilkan unit yang BELUM diinvoice (`tgl_invoice`/`no_invoice` kosong,
definisi dikonfirmasi eksplisit dengan user), diagregasi ke level
unit/WO (bukan level item pekerjaan), dengan breakdown opsional per
`kelompok` (SBE/GRP/WRT/SBI/LUB/PDS).

## Contoh query yang didukung

- "wip"
- "wip SBE"
- "wip AGN"
- "unit belum invoice kelompok GRP"

## Catatan

- 1 baris `unitmasuk` = 1 item pekerjaan, BUKAN 1 unit -- dihitung ulang
  ke level `no_wo` di Service.
- Breakdown per kelompok TIDAK saling eksklusif: satu unit/WO bisa
  mengandung item pekerjaan dari lebih dari satu kelompok sekaligus.
- Tidak ada NOT_FOUND untuk intent ini -- 0 unit WIP untuk filter
  tertentu adalah jawaban valid.
