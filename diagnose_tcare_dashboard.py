"""
diagnose_tcare_dashboard.py — cari tahu endpoint/route yang benar untuk
cek VIN, kalau /tCare/vin?vin=... ternyata redirect balik ke dashboard.

Jalankan: python diagnose_tcare_dashboard.py
"""

import re

import requests
from bs4 import BeautifulSoup

from config import settings

BASE_URL = "https://aftersales.toyota.astra.co.id/data"
TIMEOUT = (settings.TAM_TIMEOUT_CONNECT, settings.TAM_TIMEOUT_READ)


def login(session: requests.Session) -> bool:
    r = session.get(f"{BASE_URL}/login", timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    token = soup.find("input", {"name": "_token"})["value"]
    payload = {"_token": token, "email": settings.TAM_EMAIL, "password": settings.TAM_PASSWORD}
    r = session.post(f"{BASE_URL}/login", data=payload, timeout=TIMEOUT)
    return "dashboard" in r.url.lower()


def main():
    session = requests.Session()
    if not login(session):
        print("Login gagal, stop.")
        return

    print("=== Ambil halaman dashboard, cari sidebar menu ===")
    r = session.get(f"{BASE_URL}/dashboard", timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")

    print("\n--- Semua <a href> yang mengandung 'care' atau 'vin' (case-insensitive) ---")
    found_any = False
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)
        if re.search(r"care|vin", href, re.IGNORECASE) or re.search(r"care|vin", text, re.IGNORECASE):
            print(f"  href={href!r}  text={text!r}")
            found_any = True

    if not found_any:
        print("  (tidak ada -- coba lihat SEMUA link sidebar di bawah)")
        print("\n--- Semua <a href> di halaman (untuk manual scan) ---")
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            if text:
                print(f"  href={a['href']!r}  text={text!r}")

    print("\n--- Meta CSRF token (kalau ada, dipakai request AJAX) ---")
    meta = soup.find("meta", {"name": "csrf-token"})
    print("  csrf-token meta:", meta["content"] if meta else "(tidak ada)")

    print("\n--- Cari referensi 'tcare'/'vin' di semua <script> (kemungkinan API endpoint AJAX) ---")
    for script in soup.find_all("script"):
        content = script.string or ""
        for match in re.finditer(r"[\"'](/[^\"']*(?:tcare|vin|care)[^\"']*)[\"']", content, re.IGNORECASE):
            print("  ditemukan di <script>:", match.group(1))


if __name__ == "__main__":
    main()
