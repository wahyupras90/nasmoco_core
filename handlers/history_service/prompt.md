# prompt.md — History Service (INT002)

Intent ini **tidak memakai LLM** untuk parsing — `parser.py` murni
pattern-matching berbasis regex (VIN, plat nomor, tanggal) + fallback
nama customer. File ini didokumentasikan sesuai opsi di brief Room 4
("opsional kalau pakai LLM untuk parsing"), tapi isinya di sini adalah
catatan pola yang didukung, bukan prompt LLM sungguhan.

## Pola teks yang dikenali `match()`

Harus mengandung salah satu kata history (`history`/`histori`/`riwayat`)
DAN salah satu kata service (`service`/`servis`/`kunjungan`/`wo`/
`bengkel`), dan TIDAK mengandung kata `tcare` (supaya tidak bentrok
dengan INT003). Contoh:

- "riwayat service Budi Santoso"
- "history servis mobil nopol B 1234 XYZ"
- "cek riwayat kunjungan customer atas nama Ahmad 3 bulan terakhir"
- "histori wo untuk MHFXXKF3JGK012345"

## Identifier customer (urutan prioritas ekstraksi)

1. VIN / no_rangka — 17 karakter (`[A-HJ-NPR-Z0-9]{17}`)
2. No polisi — pola `[A-Z]{1,2} ?\d{1,4} ?[A-Z]{1,3}`
3. Nama customer — fallback, token alfabet setelah stopword dibuang

## Rentang tanggal (opsional)

- Eksplisit: `YYYY-MM-DD sampai YYYY-MM-DD`
- Relatif: `N bulan terakhir` / `N bulan belakangan`
- Kalau tidak ada -> seluruh riwayat (tanpa filter tanggal)
