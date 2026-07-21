"""
tests/test_room6_tcare_realtime.py

INT013 (TCARE Realtime). DoD Room 6: unit test WAJIB mock HTTP, TIDAK
BOLEH hit website TAM asli. HTML di bawah diambil dari inspeksi manual
langsung terhadap situs (bukan ditulis dari asumsi) -- lihat histori
diagnosis Room 6 (VIN MHKA6GK6JSJ084260, dikonfirmasi Wahyu).
"""

import pandas as pd
import pytest

from handlers.tcare_realtime import formatter
from handlers.tcare_realtime.handler import TCARERealtimeHandler
from handlers.tcare_realtime.parser import TCARERealtimeParser
from handlers.tcare_realtime.service import TCARERealtimeParams, TCARERealtimeService
from repositories.tcare_realtime_web_repository import (
    TCARERealtimeError,
    TCARERealtimeWebRepository,
)

LOGIN_HTML = '<html><body><input name="_token" value="tok123"></body></html>'

# HTML asli (diambil langsung dari inspeksi situs, VIN dikonfirmasi Wahyu
# masih terdaftar -- lihat histori diagnosis Room 6).
VIN_FOUND_HTML = """
<html><body>
<table>
 <tr><td style="width: 150px;">VIN</td><td style="width: 10px;">:</td><td style="width: 200px;">MHKA6GK6JSJ084260</td></tr>
 <tr><td>Model</td><td>:</td><td>CALYA</td></tr>
 <tr><td>Type</td><td>:</td><td>1.2 G A/T</td></tr>
 <tr><td>Color</td><td>:</td><td>SILVER METALLIC</td></tr>
 <tr><td>PLOD</td><td>:</td><td>2025-08-05</td></tr>
 <tr><td>Delivery Date</td><td>:</td><td>2025-08-14</td></tr>
 <tr><td>Program Name</td><td>:</td><td>T-CARE LITE + TAM</td></tr>
 <tr><td>Post Service</td><td>:</td><td></td></tr>
 <tr><td>Delivery Date Submit</td><td>:</td><td>-</td></tr>
</table>
<table>
 <tr><td colspan="3"><span class="text-danger">Owners have not registered, please register to download the certificate.</span></td></tr>
</table>
<table class="table-danger">
 <tr class="table-danger"><td>Service No</td><td>Service Date</td><td>Dealer</td><td>Tepat Waktu</td><td>Status</td><td>Ontime Service</td></tr>
 <tr><td>1/1 bln</td><td>04-Nov-25</td><td>-</td><td>No</td><td>-</td><td>30 Sep 2025</td></tr>
 <tr><td>2/6 bln</td><td>12-Feb-26</td><td>NASMOCO - TEGAL</td><td>Yes</td><td>Approve Claim</td><td>28 Feb 2026</td></tr>
</table>
</body></html>
"""

# Dikonfirmasi Wahyu: VIN tidak ditemukan -> redirect ke /dashboard, 0 tabel.
DASHBOARD_HTML = "<html><body><h1>Dashboard</h1></body></html>"


class FakeResponse:
    def __init__(self, text="", url="", status_code=200):
        self.text = text
        self.url = url
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Pengganti requests.Session -- tidak ada koneksi jaringan sama sekali."""

    def __init__(self, login_html=LOGIN_HTML, login_ok=True, vin_pages=None):
        self._login_html = login_html
        self._login_ok = login_ok
        self._vin_pages = vin_pages or {}
        self.get_calls = []
        self.post_calls = []

    def get(self, url, params=None, timeout=None):
        self.get_calls.append((url, params))
        if url.endswith("/login"):
            return FakeResponse(text=self._login_html, url=url)
        if "/tCare/vin" in url:
            vin = params.get("vin") if params else None
            html = self._vin_pages.get(vin)
            if html is None:
                return FakeResponse(text=DASHBOARD_HTML, url="https://aftersales.toyota.astra.co.id/data/dashboard")
            return FakeResponse(text=html, url=url)
        raise AssertionError(f"GET tidak terduga: {url}")

    def post(self, url, data=None, timeout=None):
        self.post_calls.append((url, data))
        redirect = "/dashboard" if self._login_ok else "/login"
        return FakeResponse(text="", url=f"https://aftersales.toyota.astra.co.id/data{redirect}")


def _make_repo(monkeypatch, fake_session: FakeSession) -> TCARERealtimeWebRepository:
    monkeypatch.setattr(
        "repositories.tcare_realtime_web_repository.requests.Session",
        lambda: fake_session,
    )
    return TCARERealtimeWebRepository(email="test@example.com", password="secret")


# -- Repository level --

def test_repo_get_vin_data_found(monkeypatch):
    session = FakeSession(vin_pages={"MHKA6GK6JSJ084260": VIN_FOUND_HTML})
    repo = _make_repo(monkeypatch, session)

    result = repo.get_vin_data("MHKA6GK6JSJ084260")

    assert result.ok is True
    assert result.vehicle is not None
    assert dict(zip(result.vehicle["key"], result.vehicle["value"]))["Model"] == "CALYA"
    assert len(result.services) == 2
    assert result.customer.iloc[0]["key"] == "catatan"
    assert "not registered" in result.customer.iloc[0]["value"].lower()


def test_repo_get_vin_data_not_found(monkeypatch):
    session = FakeSession(vin_pages={})  # tidak ada VIN terdaftar
    repo = _make_repo(monkeypatch, session)

    result = repo.get_vin_data("MHTIDAKADA000001")

    assert result.ok is False
    assert "tidak ditemukan" in result.error.lower()


def test_repo_login_failure_returns_error_not_raise_uncaught(monkeypatch):
    """WAJIB (brief Room 6): kegagalan login TIDAK BOLEH exit()/crash --
    harus jadi VinFetchResult.error yang bisa ditangani per-VIN."""
    session = FakeSession(login_ok=False)
    repo = _make_repo(monkeypatch, session)

    result = repo.get_vin_data("MHKA6GK6JSJ084260")

    assert result.ok is False
    assert "login" in result.error.lower()


def test_repo_get_multiple_one_failure_does_not_fail_others(monkeypatch):
    session = FakeSession(vin_pages={"MHKA6GK6JSJ084260": VIN_FOUND_HTML})
    repo = _make_repo(monkeypatch, session)

    results = repo.get_multiple(["MHKA6GK6JSJ084260", "MHTIDAKADA000001"])

    assert len(results) == 2
    assert results[0].ok is True
    assert results[1].ok is False


def test_repo_rejects_empty_credentials():
    with pytest.raises(ValueError):
        TCARERealtimeWebRepository(email="", password="")


# -- Service level (session-per-request via repo_factory) --

def test_service_execute_returns_results(monkeypatch):
    session = FakeSession(vin_pages={"MHKA6GK6JSJ084260": VIN_FOUND_HTML})

    def factory():
        return _make_repo(monkeypatch, session)

    service = TCARERealtimeService(repo_factory=factory)
    results = service.execute(TCARERealtimeParams(vins=["MHKA6GK6JSJ084260"]))

    assert len(results) == 1
    assert results[0].ok is True


def test_service_execute_empty_vins_returns_empty_list():
    service = TCARERealtimeService(repo_factory=lambda: (_ for _ in ()).throw(AssertionError("should not be called")))
    results = service.execute(TCARERealtimeParams(vins=[]))
    assert results == []


# -- Handler level (error handling wajib, ADR021 + brief Room 6) --

def test_handler_ok_end_to_end(monkeypatch):
    session = FakeSession(vin_pages={"MHKA6GK6JSJ084260": VIN_FOUND_HTML})

    def factory():
        return _make_repo(monkeypatch, session)

    handler = TCARERealtimeHandler(service=TCARERealtimeService(repo_factory=factory))
    result = handler.execute("cek tcare realtime MHKA6GK6JSJ084260")

    assert result.success is True
    assert result.code == "INT013_OK"
    assert result.summary["berhasil"] == 1
    assert isinstance(result.dataframe, pd.DataFrame)
    assert len(result.dataframe) == 2  # 2 baris histori service


def test_handler_no_vin_detected_returns_not_found():
    handler = TCARERealtimeHandler()
    result = handler.execute("cek tcare realtime")
    assert result.success is False
    assert result.code == "INT013_NOT_FOUND"


def test_match_word_order_reversed_web_tcare():
    """Bug ditemukan Wahyu: 'history web tcare <plat>' tidak match karena
    keyword lama cuma substring berurutan tetap ('tcare web'). Diperbaiki:
    cek kata 'tcare' + 'web'/'realtime' terpisah, urutan bebas."""
    parser = TCARERealtimeParser()
    assert parser.match("history web tcare ab1930gg") is True
    assert parser.match("history tcare web ab1930gg") is True
    assert parser.match("cek realtime tcare MHKA123") is True


def test_match_web_without_tcare_still_rejected():
    """'web'/'realtime' saja TANPA kata 'tcare' TIDAK boleh match --
    supaya tidak menangkap kalimat tak terkait sembarangan."""
    parser = TCARERealtimeParser()
    assert parser.match("buka website resmi") is False
    assert parser.match("real time monitoring outlet") is False


def test_handler_missing_credentials_returns_error_not_crash():
    """WAJIB: kredensial kosong -> HandlerResult error, bukan exception
    yang menjalar ke app_v2.py."""

    def factory():
        return TCARERealtimeWebRepository(email="", password="")

    handler = TCARERealtimeHandler(service=TCARERealtimeService(repo_factory=factory))
    result = handler.execute("cek tcare realtime MHKA6GK6JSJ084260")

    assert result.success is False
    assert result.code == "INT013_ERROR"


def test_handler_multiple_vins_one_failure_does_not_fail_request(monkeypatch):
    session = FakeSession(vin_pages={"MHKA6GK6JSJ084260": VIN_FOUND_HTML})

    def factory():
        return _make_repo(monkeypatch, session)

    handler = TCARERealtimeHandler(service=TCARERealtimeService(repo_factory=factory))
    result = handler.execute("cek tcare realtime MHKA6GK6JSJ084260 dan MHTIDAKADA000001")

    assert result.success is True
    assert result.code == "INT013_OK"
    assert result.summary["berhasil"] == 1
    assert result.summary["gagal"] == 1
    assert result.summary["vin_gagal"][0]["vin"] == "MHTIDAKADA000001"


# -- Formatter --

def test_formatter_message_includes_all_sections():
    session = FakeSession(vin_pages={"MHKA6GK6JSJ084260": VIN_FOUND_HTML})
    repo = TCARERealtimeWebRepository.__new__(TCARERealtimeWebRepository)
    repo._session = session
    result = repo._parse_vin_page("MHKA6GK6JSJ084260", VIN_FOUND_HTML)

    message = formatter.format_message([result])

    assert "MHKA6GK6JSJ084260" in message
    assert "CALYA" in message
    assert "not registered" in message.lower()
    assert "NASMOCO - TEGAL" in message


# =====================================================================
# Pencarian by-nama (brief Wahyu via Room 0, reuse Repository Room 4:
# CustomerProfileRepository + HistoryServiceRepository -- TIDAK ADA file
# Room 4 yang diubah untuk fitur ini).
# =====================================================================

import os

from db.connection import close_connection
from handlers.tcare_realtime.name_resolver import CustomerNameResolver
from repositories.customer_profile_repository import CustomerProfileRepository
from repositories.history_service_repository import HistoryServiceRepository
from tests.fixtures_room4 import make_temp_db as make_temp_db_room4


@pytest.fixture()
def db_path_room4():
    path = make_temp_db_room4()
    yield path
    close_connection()
    os.remove(path)


@pytest.fixture()
def name_resolver(db_path_room4):
    return CustomerNameResolver(
        CustomerProfileRepository(db_path_room4),
        HistoryServiceRepository(db_path_room4),
    )


def test_parser_vin_direct_unaffected_by_name_feature():
    """REGRESI WAJIB: input VIN langsung TIDAK berubah sama sekali oleh
    fitur pencarian by-nama."""
    parser = TCARERealtimeParser()
    parsed = parser.parse("cek tcare realtime MHKA6GK6JSJ084260")
    assert parsed.vins == ["MHKA6GK6JSJ084260"]
    assert parsed.customer_name is None


def test_parser_detects_customer_name_when_no_vin():
    parser = TCARERealtimeParser()
    parsed = parser.parse("history tcare web long well")
    assert parsed.vins == []
    assert parsed.customer_name == "long well"


def test_name_search_single_match_proceeds_to_web(monkeypatch, name_resolver):
    """Nama dengan TEPAT 1 kandidat -> lanjut ke alur VIN biasa seperti
    kalau user ketik VIN langsung, sukses fetch web (di-mock)."""
    session = FakeSession(vin_pages={"MHFXX1JGK000BUDI1": VIN_FOUND_HTML})

    def factory():
        return _make_repo(monkeypatch, session)

    handler = TCARERealtimeHandler(
        service=TCARERealtimeService(repo_factory=factory),
        name_resolver=name_resolver,
    )
    result = handler.execute("history tcare web santoso")

    assert result.success is True
    assert result.code == "INT013_OK"
    assert result.summary["berhasil"] == 1


def test_name_search_ambiguous_returns_candidate_list_not_web(name_resolver):
    """Nama dengan >1 kandidat -> AMBIGUOUS, TIDAK lanjut ke web sama
    sekali (keputusan eksplisit Wahyu -- jangan otomatis pilih satu)."""
    def factory():
        raise AssertionError("Web TIDAK BOLEH dipanggil untuk kasus AMBIGUOUS")

    handler = TCARERealtimeHandler(
        service=TCARERealtimeService(repo_factory=factory),
        name_resolver=name_resolver,
    )

    result = handler.execute("history tcare web budi")

    assert result.success is False
    assert result.code == "INT013_AMBIGUOUS"
    assert len(result.suggestions) == 2
    assert "MHFXX1JGK000BUDI1" in result.message
    assert "MHFXX1JGK000BUDI2" in result.message
    assert result.suggestions[0]["customer"] == "BUDI SANTOSO"
    assert result.suggestions[1]["customer"] == "BUDI HARTONO"


def test_name_search_not_found_returns_specific_message(name_resolver):
    handler = TCARERealtimeHandler(name_resolver=name_resolver)

    result = handler.execute("history tcare web namasangattidakada")

    assert result.success is False
    assert result.code == "INT013_NOT_FOUND"
    assert "namasangattidakada" in result.message.lower()


def test_name_search_uses_unitmasuk_fallback_when_customer_profile_empty(monkeypatch, name_resolver):
    """Reuse PERSIS pola Room 4 (INT002): customer_profile 0 hasil ->
    fallback ke unitmasuk. Data uji 'PT UNTESTED WELL SEJAHTERA' sudah
    ada di fixtures_room4.py (dibuat khusus Room 4 untuk kasus analog
    ini -- 'PT. LONG WELL INTERNATIONAL')."""
    session = FakeSession(vin_pages={"MHUNTESTED0000001": VIN_FOUND_HTML})

    def factory():
        return _make_repo(monkeypatch, session)

    handler = TCARERealtimeHandler(
        service=TCARERealtimeService(repo_factory=factory),
        name_resolver=name_resolver,
    )
    result = handler.execute("history tcare web untested well")

    assert result.success is True
    assert result.code == "INT013_OK"


def test_name_resolver_prioritizes_customer_profile_over_unitmasuk(name_resolver):
    """customer_profile PRIORITAS MUTLAK -- kalau sudah ada hasil (BUDI,
    2 kandidat), unitmasuk TIDAK PERNAH dicek sama sekali."""
    resolution = name_resolver.resolve("budi")
    assert resolution.used_fallback is False
    assert resolution.count == 2


def test_vin_regex_requires_mixed_letters_and_digits():
    """Root cause fix (ditemukan lewat testing fitur pencarian by-nama):
    kata alfabet murni 5-17 huruf (mis. nama orang seperti 'SANTOSO')
    TIDAK BOLEH tertangkap sebagai kandidat VIN -- WAJIB campuran
    huruf+angka, sama seperti pola Room 4 (NO_RANGKA_REGEX). Sebelum fix
    ini, 'history tcare web santoso' salah mendeteksi 'SANTOSO' sebagai
    VIN, membuat fitur pencarian by-nama tidak pernah sempat jalan."""
    parser = TCARERealtimeParser()

    # Nama orang biasa (alfabet murni) -- TIDAK boleh jadi VIN.
    for name_word in ("SANTOSO", "HARTONO", "WIDODO", "PRATAMA", "SEJAHTERA"):
        parsed = parser.parse(f"history tcare web {name_word.lower()}")
        assert parsed.vins == [], f"{name_word!r} salah tertangkap jadi VIN"

    # VIN asli (campuran huruf+angka) TETAP harus terdeteksi.
    parsed = parser.parse("cek tcare realtime MHKA6GK6JSJ084260")
    assert parsed.vins == ["MHKA6GK6JSJ084260"]