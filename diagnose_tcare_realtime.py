"""
diagnose_tcare_realtime.py — jalankan manual untuk debug INT013.

Cetak informasi mentah (bukan lewat parser) supaya kita tahu persis apa
yang dikembalikan web TAM: status login, URL redirect, jumlah tabel HTML,
dan potongan HTML mentah kalau tabelnya tidak 3.

Jalankan: python diagnose_tcare_realtime.py <VIN>
"""

import sys

import requests
from bs4 import BeautifulSoup

from config import settings

BASE_URL = "https://aftersales.toyota.astra.co.id/data"
TIMEOUT = (settings.TAM_TIMEOUT_CONNECT, settings.TAM_TIMEOUT_READ)


def main(vin: str):
    session = requests.Session()

    print("=== STEP 1: GET halaman login ===")
    r = session.get(f"{BASE_URL}/login", timeout=TIMEOUT)
    print("status_code:", r.status_code)
    print("final url  :", r.url)

    soup = BeautifulSoup(r.text, "html.parser")
    token_input = soup.find("input", {"name": "_token"})
    print("token ditemukan:", token_input is not None)

    if token_input is None:
        print("\n--- HTML halaman login (500 char pertama) ---")
        print(r.text[:500])
        return

    token = token_input["value"]

    print("\n=== STEP 2: POST login ===")
    payload = {"_token": token, "email": settings.TAM_EMAIL, "password": settings.TAM_PASSWORD}
    r = session.post(f"{BASE_URL}/login", data=payload, timeout=TIMEOUT)
    print("status_code:", r.status_code)
    print("final url  :", r.url)
    print("login sukses (ada 'dashboard' di url)?:", "dashboard" in r.url.lower())

    if "dashboard" not in r.url.lower():
        print("\n--- HTML hasil POST login (1000 char pertama) ---")
        print(r.text[:1000])
        return

    print(f"\n=== STEP 3: GET halaman VIN ({vin}) ===")
    r = session.get(f"{BASE_URL}/tCare/vin", params={"vin": vin}, timeout=TIMEOUT)
    print("status_code:", r.status_code)
    print("final url  :", r.url)

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    print("jumlah <table> ditemukan:", len(tables))

    for i, t in enumerate(tables):
        rows = t.find_all("tr")
        print(f"  table[{i}]: {len(rows)} baris")

    if len(tables) < 3:
        print("\n--- HTML halaman VIN (2000 char pertama) ---")
        print(r.text[:2000])
    else:
        print("\n--- Isi table[0] (Data Kendaraan, mentah) ---")
        print(tables[0].prettify()[:1500])
        print("\n--- Isi table[1] (Customer, mentah) ---")
        print(tables[1].prettify()[:1500])
        print("\n--- Isi table[2] (Histori Service, mentah, maks 3 baris pertama) ---")
        rows = tables[2].find_all("tr")[:3]
        for row in rows:
            print(row.prettify())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diagnose_tcare_realtime.py <VIN>")
        sys.exit(1)
    main(sys.argv[1])
