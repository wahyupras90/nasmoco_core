"""
tests/test_room6_composite_history_tcare.py — ADR027 (+ revisi 2 bug)

CompositeHistoryTCAREHandler. Menggunakan DB Room 4 yang ASLI
(tests/fixtures_room4.make_temp_db) untuk sisi lokal -- supaya perilaku
"kasus normal identik dengan HistoryTCAREHandler asli" benar-benar teruji
terhadap fixture yang sama, bukan fixture baru yang bisa beda perilaku.

Web service (INT013, Room 6) di-mock -- TIDAK hit web TAM asli di test ini.

Untuk skenario Bug #2 (unit dikenal lokal, riwayat TCARE nol baris), fixture
Room 4 asli belum punya kasus persis ini -- ditambahkan lewat INSERT
tambahan langsung ke temp DB di `db_path_with_empty_tcare_unit` (fixture
BARU, TIDAK mengubah tests/fixtures_room4.py sama sekali).
"""

import os
import sqlite3

import pandas as pd
import pytest

from db.connection import close_connection
from handlers.history_tcare.handler import HistoryTCAREHandler
from handlers.history_tcare.service import HistoryTCAREService
from handlers.history_tcare_composite.handler import CompositeHistoryTCAREHandler
from repositories.history_tcare_repository import HistoryTCARERepository
from repositories.tcare_realtime_web_repository import VinFetchResult
from tests.fixtures_room4 import make_temp_db

# no_rangka baru khusus test Bug #2: ADA di rs+tcare_unit (unit_info
# ke-resolve), TAPI TIDAK PUNYA baris di tcare_schedule_full_history sama
# sekali -- ini kasus "unit dikenal, riwayat TCARE nol baris".
EMPTY_TCARE_NO_RANGKA = "MHKOSONGTCARE0001"
EMPTY_TCARE_CUSTOMER = "ANDI (KOSONG TCARE)"


@pytest.fixture()
def db_path():
    path = make_temp_db()
    yield path
    close_connection()
    os.remove(path)


# no_rangka khusus test Bug #3: ADA baris jadwal (7 milestone 1K-60K),
# TAPI SEMUANYA belum pernah direalisasi (bulan_realisasi=None, status
# pending, expired=1) -- reproduksi persis laporan Wahyu (MHKE8FB3JNK077471).
UNREALIZED_TCARE_NO_RANGKA = "MHBELUMREAL0001"
UNREALIZED_TCARE_CUSTOMER = "BUDI (BELUM REALISASI)"

# no_rangka pembanding: ADA jadwal, MINIMAL SATU baris SUDAH realisasi --
# untuk pastikan kasus ini TIDAK dianggap kosong (tidak fallback ke web).
PARTIAL_REALIZED_NO_RANGKA = "MHSEBAGIAN0001"
PARTIAL_REALIZED_CUSTOMER = "CICI (SEBAGIAN REALISASI)"


@pytest.fixture()
def db_path_with_empty_tcare_unit():
    """Sama seperti `db_path`, ditambah:
    - 1 unit dikenal lokal (rs + tcare_unit ada) tapi tcare_schedule_full_history
      KOSONG TOTAL -- kasus Bug #2 (unit dikenal, 0 baris jadwal).
    - 1 unit dengan jadwal ADA (7 baris) tapi SEMUA bulan_realisasi=None --
      kasus Bug #3 (unit dikenal, riwayat efektif kosong meski ada baris jadwal).
    - 1 unit pembanding dengan SEBAGIAN sudah realisasi -- untuk pastikan
      kasus ini TIDAK trigger fallback (regresi Bug #3).
    """
    path = make_temp_db()
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO customer_profile (no_rangka, customer, model, segment, "
        "dealer_kategori, no_polisi, sa_terakhir, total_kunjungan_fisik, "
        "total_revenue_lifetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (EMPTY_TCARE_NO_RANGKA, EMPTY_TCARE_CUSTOMER, "Rush", "Retail", "A", "B 1111 KSG", "SA05", 2, 4_000_000.0),
    )
    conn.execute(
        "INSERT INTO rs (no_rangka, model, no_polisi, customer, "
        "dealer_kategori, batas_tcare, tgl_do) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (EMPTY_TCARE_NO_RANGKA, "Rush", "B 1111 KSG", EMPTY_TCARE_CUSTOMER, "A", "2026-01-10", "2023-01-10"),
    )
    conn.execute(
        "INSERT INTO tcare_unit (no_rangka, tcare_type, sisa_service, "
        "sisa_detail, sa_terakhir) VALUES (?, ?, ?, ?, ?)",
        (EMPTY_TCARE_NO_RANGKA, "Reguler", 7, "0 dari 7", "SA05"),
    )
    # SENGAJA TIDAK ADA insert ke tcare_schedule_full_history untuk
    # no_rangka ini -- itulah inti kasus Bug #2.

    # -- Bug #3: jadwal ADA, semua belum realisasi --
    conn.execute(
        "INSERT INTO customer_profile (no_rangka, customer, model, segment, "
        "dealer_kategori, no_polisi, sa_terakhir, total_kunjungan_fisik, "
        "total_revenue_lifetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (UNREALIZED_TCARE_NO_RANGKA, UNREALIZED_TCARE_CUSTOMER, "All New Rush", "Retail", "A", "AB-1930-GG", "NRK", 5, 6_000_000.0),
    )
    conn.execute(
        "INSERT INTO rs (no_rangka, model, no_polisi, customer, "
        "dealer_kategori, batas_tcare, tgl_do) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (UNREALIZED_TCARE_NO_RANGKA, "All New Rush", "AB-1930-GG", UNREALIZED_TCARE_CUSTOMER, "A", "2025-12-31", "2022-12-10"),
    )
    conn.execute(
        "INSERT INTO tcare_unit (no_rangka, tcare_type, sisa_service, "
        "sisa_detail, sa_terakhir) VALUES (?, ?, ?, ?, ?)",
        (UNREALIZED_TCARE_NO_RANGKA, "T-CARE", 7, "7 dari 7", "NRK"),
    )
    conn.executemany(
        "INSERT INTO tcare_schedule_full_history (no_rangka, dealer_kategori, "
        "tgl_do, kunjungan, pekerjaan, bulan_jadwal, bulan_realisasi, status, "
        "no_wo_real, sa_realisasi, expired, batas_tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (UNREALIZED_TCARE_NO_RANGKA, "A", "2022-12-10", i, m, bj, None, "pending", None, None, 1, "2025-12-31")
            for i, (m, bj) in enumerate(
                [("1K", "2023-01"), ("10K", "2023-06"), ("20K", "2023-12"), ("30K", "2024-06"),
                 ("40K", "2024-12"), ("50K", "2025-06"), ("60K", "2025-12")],
                start=1,
            )
        ],
    )

    # -- Pembanding: SEBAGIAN sudah realisasi (baris pertama saja) --
    conn.execute(
        "INSERT INTO customer_profile (no_rangka, customer, model, segment, "
        "dealer_kategori, no_polisi, sa_terakhir, total_kunjungan_fisik, "
        "total_revenue_lifetime) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (PARTIAL_REALIZED_NO_RANGKA, PARTIAL_REALIZED_CUSTOMER, "Calya", "Retail", "A", "B-2222-PR", "AGN", 3, 2_000_000.0),
    )
    conn.execute(
        "INSERT INTO rs (no_rangka, model, no_polisi, customer, "
        "dealer_kategori, batas_tcare, tgl_do) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (PARTIAL_REALIZED_NO_RANGKA, "Calya", "B-2222-PR", PARTIAL_REALIZED_CUSTOMER, "A", "2026-06-30", "2023-06-01"),
    )
    conn.execute(
        "INSERT INTO tcare_unit (no_rangka, tcare_type, sisa_service, "
        "sisa_detail, sa_terakhir) VALUES (?, ?, ?, ?, ?)",
        (PARTIAL_REALIZED_NO_RANGKA, "T-CARE", 2, "1 dari 2", "AGN"),
    )
    conn.executemany(
        "INSERT INTO tcare_schedule_full_history (no_rangka, dealer_kategori, "
        "tgl_do, kunjungan, pekerjaan, bulan_jadwal, bulan_realisasi, status, "
        "no_wo_real, sa_realisasi, expired, batas_tcare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (PARTIAL_REALIZED_NO_RANGKA, "A", "2023-06-01", 1, "1K", "2023-07", "2023-07-15", "done", "WO-999", "AGN", 0, "2026-06-30"),
            (PARTIAL_REALIZED_NO_RANGKA, "A", "2023-06-01", 2, "10K", "2024-01", None, "pending", None, None, 0, "2026-06-30"),
        ],
    )

    conn.commit()
    conn.close()
    yield path
    close_connection()
    os.remove(path)


@pytest.fixture()
def local_handler(db_path):
    return HistoryTCAREHandler(HistoryTCAREService(HistoryTCARERepository(db_path)))


@pytest.fixture()
def local_handler_empty_tcare(db_path_with_empty_tcare_unit):
    return HistoryTCAREHandler(HistoryTCAREService(HistoryTCARERepository(db_path_with_empty_tcare_unit)))


class FakeWebService:
    """Stub TCARERealtimeService -- kontrol penuh atas
    credentials_configured()/get_single() tanpa jaringan sama sekali."""

    def __init__(self, configured=True, result=None, raise_exc=None):
        self._configured = configured
        self._result = result
        self._raise_exc = raise_exc
        self.get_single_calls = []

    def credentials_configured(self) -> bool:
        return self._configured

    def get_single(self, no_rangka: str) -> VinFetchResult:
        self.get_single_calls.append(no_rangka)
        if self._raise_exc:
            raise self._raise_exc
        return self._result


def _found_result(no_rangka="MHNOTFOUND000001"):
    services = pd.DataFrame(
        [{"kunjungan": "1/1 bln", "tanggal": "01-Jan-26", "dealer": "NASMOCO", "tepat": "Yes", "status": "Approve Claim", "ontime_service": "01 Feb 2026"}]
    )
    vehicle = pd.DataFrame([{"key": "VIN", "value": no_rangka}])
    customer = pd.DataFrame(columns=["key", "value"])
    return VinFetchResult(vin=no_rangka, vehicle=vehicle, customer=customer, services=services)


def _not_found_result(no_rangka="MHNOTFOUND000001"):
    return VinFetchResult(vin=no_rangka, error="Data tidak ditemukan (VIN tidak terdaftar atau struktur halaman berubah)")


def _technical_error_result(no_rangka="MHNOTFOUND000001"):
    return VinFetchResult(vin=no_rangka, error="Login TAM gagal (kredensial ditolak atau redirect tidak sesuai)")


# -- DoD 1: kasus normal (ditemukan di lokal) IDENTIK dengan HistoryTCAREHandler asli --

def test_local_found_identical_to_original_handler(local_handler):
    web_service = FakeWebService()  # tidak boleh sampai dipanggil sama sekali
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    query = "history tcare 01S208014054"  # kasus ADR024 (lama-expired, tetap OK)
    expected = local_handler.execute(query)
    actual = composite.execute(query)

    assert actual.success == expected.success
    assert actual.code == expected.code == "INT003_OK"
    assert actual.message == expected.message
    assert len(actual.dataframe) == len(expected.dataframe)
    assert actual.summary == expected.summary
    assert web_service.get_single_calls == []  # fallback TIDAK dipanggil


def test_local_ambiguous_not_affected_by_composite(local_handler):
    web_service = FakeWebService()
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare budi")

    assert result.code == "INT003_AMBIGUOUS"
    assert web_service.get_single_calls == []


# -- DoD 2: NOT_FOUND lokal + web BERHASIL --

def test_local_not_found_web_found_returns_ok_with_source_prefix(local_handler):
    web_service = FakeWebService(result=_found_result("MHNOTFOUND000001"))
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare MHNOTFOUND000001")

    assert result.success is True
    assert result.code == "INT003_OK"
    assert result.message.startswith("[Realtime dari web TAM]")
    assert result.metadata["source"] == "web_tam_realtime"
    assert result.summary["source"] == "web_tam_realtime"
    assert len(result.dataframe) == 1
    assert web_service.get_single_calls == ["MHNOTFOUND000001"]


# -- DoD 3: NOT_FOUND lokal + web JUGA NOT_FOUND --

def test_local_not_found_web_also_not_found(local_handler):
    web_service = FakeWebService(result=_not_found_result("MHNOTFOUND000001"))
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare MHNOTFOUND000001")

    assert result.success is False
    assert result.code == "INT003_NOT_FOUND"
    assert "maupun di web tam" in result.message.lower()


# -- DoD 4: NOT_FOUND lokal + web GAGAL TEKNIS --

def test_local_not_found_web_technical_failure_returns_error_not_not_found(local_handler):
    web_service = FakeWebService(result=_technical_error_result("MHNOTFOUND000001"))
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare MHNOTFOUND000001")

    assert result.success is False
    assert result.code == "INT003_ERROR"  # BUKAN NOT_FOUND
    assert "login" in result.message.lower() or "gagal" in result.message.lower()


def test_local_not_found_web_raises_exception_returns_error(local_handler):
    web_service = FakeWebService(raise_exc=RuntimeError("boom"))
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare MHNOTFOUND000001")

    assert result.success is False
    assert result.code == "INT003_ERROR"
    assert "boom" in result.message


# -- DoD 5: kredensial TAM kosong -> skip diam-diam, tapi log warning --

def test_credentials_not_configured_skips_fallback_silently(local_handler, caplog):
    web_service = FakeWebService(configured=False)
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    with caplog.at_level("WARNING"):
        result = composite.execute("history tcare MHNOTFOUND000001")

    assert result.code == "INT003_NOT_FOUND"  # hasil lokal apa adanya, tanpa prefix web
    assert "[Realtime dari web TAM]" not in result.message
    assert web_service.get_single_calls == []  # get_single TIDAK dipanggil
    assert any("kredensial" in rec.message.lower() for rec in caplog.records)


# -- DoD 6: identifier bukan no_rangka (plate/name) -> skip fallback tanpa mencoba web --

def test_identifier_type_name_skips_fallback(local_handler):
    """'history tcare budi' -> AMBIGUOUS (bukan NOT_FOUND), tapi kasus NOT_FOUND
    dengan identifier_type='name' (nama tidak ketemu sama sekali, bukan
    ambiguous) juga harus skip fallback -- pakai nama unik yang pasti
    NOT_FOUND, bukan AMBIGUOUS."""
    web_service = FakeWebService()
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare pelanggan zzznamasangattidakada")

    assert result.code == "INT003_NOT_FOUND"
    assert web_service.get_single_calls == []  # fallback TIDAK dicoba sama sekali


def test_identifier_type_name_not_found_gets_vin_hint(local_handler):
    """Room 0 approved (non-blocking UX): pesan NOT_FOUND untuk plat/nama
    diberi petunjuk kenapa tidak coba ke web, bukan diam saja."""
    web_service = FakeWebService()
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare pelanggan zzznamasangattidakada")

    assert result.code == "INT003_NOT_FOUND"
    assert "nomor rangka (VIN)" in result.message
    assert web_service.get_single_calls == []


def test_identifier_type_plate_not_found_gets_vin_hint(local_handler):
    web_service = FakeWebService()
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare B 9999 ZZ")

    assert result.code == "INT003_NOT_FOUND"
    assert "nomor rangka (VIN)" in result.message
    assert web_service.get_single_calls == []


def test_identifier_type_plate_skips_fallback(local_handler):
    web_service = FakeWebService()
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare B 9999 ZZ")

    assert result.code == "INT003_NOT_FOUND"
    assert web_service.get_single_calls == []


# -- match() didelegasikan apa adanya ke handler lokal --

def test_match_delegates_to_local_handler(local_handler):
    web_service = FakeWebService()
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    assert composite.match("history tcare MHFXX1JGK000BUDI1") is True
    assert composite.match("riwayat service MHFXX1JGK000BUDI1") is False


def test_intent_id_and_name(local_handler):
    composite = CompositeHistoryTCAREHandler(local_handler, FakeWebService())
    assert composite.intent_id == "INT003"


# =====================================================================
# ADR027 REVISI — Bug #1: permintaan eksplisit "web" harus ke INT013,
# bukan tercegat Composite, walau lokal punya data.
# =====================================================================

def test_bug1_explicit_web_request_routes_to_int013_even_with_local_data(local_handler):
    """Reproduksi persis Bug #1: 'history tcare web <VIN yang ADA
    datanya di lokal>' -- sebelum fix, Composite (priority 20) selalu
    menang tie-break atas TCARERealtimeHandler (priority 10 lama),
    walau user eksplisit minta 'web'. Priority yang benar (Composite=20,
    TCARERealtimeHandler=30, sesuai app_v2.py yang sudah diperbaiki)
    HARUS membuat TCARERealtimeHandler menang."""
    from ai.router import NullFallbackProvider, Router
    from handlers.tcare_realtime.handler import TCARERealtimeHandler

    composite = CompositeHistoryTCAREHandler(local_handler, FakeWebService())
    realtime = TCARERealtimeHandler()  # kredensial kosong di test env -- tidak masalah,
    # kita cuma membuktikan Handler MANA yang dipilih Router, bukan hasil fetch-nya.

    router = Router(fallback=NullFallbackProvider())
    router.register(composite, priority=20)
    router.register(realtime, priority=30)  # fix Bug #1: lebih tinggi dari Composite

    query = "history tcare web MHFXX1JGK000BUDI1"  # BUDI1 punya data lokal lengkap
    assert composite.match(query) is True   # keduanya MEMANG match (akar masalah)
    assert realtime.match(query) is True

    result = router.route(query)

    assert result.code.startswith("INT013")  # BUKAN INT003 -- ini yang gagal sebelum fix


def test_bug1_priority_misconfigured_reproduces_the_bug(local_handler):
    """Test negatif -- sengaja pasang priority versi LAMA (sama-sama/lebih
    rendah) untuk membuktikan bug memang nyata kalau priority salah, bukan
    cuma klaim di brief. Kalau test ini SUATU SAAT gagal (Composite tidak
    lagi menang), berarti asumsi akar masalah sudah berubah -- perlu
    ditinjau ulang, bukan langsung dianggap 'makin baik'."""
    from ai.router import NullFallbackProvider, Router
    from handlers.tcare_realtime.handler import TCARERealtimeHandler

    composite = CompositeHistoryTCAREHandler(local_handler, FakeWebService())
    realtime = TCARERealtimeHandler()

    router = Router(fallback=NullFallbackProvider())
    router.register(composite, priority=20)
    router.register(realtime, priority=10)  # priority LAMA (bug)

    result = router.route("history tcare web MHFXX1JGK000BUDI1")

    assert result.code.startswith("INT003")  # bug lama: Composite menang


def test_bug1_query_without_web_keyword_still_goes_to_composite(local_handler):
    """Pastikan fix priority TIDAK mengubah perilaku untuk query biasa
    (tanpa kata 'web'/'realtime') -- harus tetap ke Composite seperti biasa."""
    from ai.router import NullFallbackProvider, Router
    from handlers.tcare_realtime.handler import TCARERealtimeHandler

    composite = CompositeHistoryTCAREHandler(local_handler, FakeWebService())
    realtime = TCARERealtimeHandler()

    router = Router(fallback=NullFallbackProvider())
    router.register(composite, priority=20)
    router.register(realtime, priority=30)

    query = "history tcare MHFXX1JGK000BUDI1"  # tanpa kata "web"/"realtime"
    assert realtime.match(query) is False  # TCARERealtimeHandler TIDAK match sama sekali
    result = router.route(query)
    assert result.code == "INT003_OK"


# =====================================================================
# ADR027 REVISI — Bug #2: "OK tapi riwayat kosong" harus trigger fallback.
# =====================================================================

def test_bug2_local_ok_but_empty_triggers_fallback_check(local_handler_empty_tcare):
    """Sanity check dulu: pastikan fixture baru benar-benar menghasilkan
    local_result.success=True + total_riwayat_tcare == 0 (bukan NOT_FOUND) --
    ini prasyarat skenario Bug #2."""
    local_result = local_handler_empty_tcare.execute(f"history tcare {EMPTY_TCARE_NO_RANGKA}")
    assert local_result.success is True
    assert local_result.code == "INT003_OK"
    assert local_result.summary["total_riwayat_tcare"] == 0
    assert local_result.summary["no_rangka"] == EMPTY_TCARE_NO_RANGKA


def test_bug2_web_also_empty_returns_bukan_tcare_message(local_handler_empty_tcare):
    web_service = FakeWebService(result=_not_found_result(EMPTY_TCARE_NO_RANGKA))
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    result = composite.execute(f"history tcare {EMPTY_TCARE_NO_RANGKA}")

    assert result.success is True
    assert result.code == "INT003_OK"  # BUKAN NOT_FOUND/ERROR
    assert "tidak memiliki riwayat tcare" in result.message.lower()
    assert result.metadata["source"] == "local"
    assert result.metadata["tcare_history_checked_web"] is True
    assert web_service.get_single_calls == [EMPTY_TCARE_NO_RANGKA]
    # no_rangka dipakai LANGSUNG dari local_result.summary, TIDAK re-parse teks


def test_bug2_web_found_but_zero_visits_also_returns_bukan_tcare(local_handler_empty_tcare):
    """VIN terdaftar di web (ok=True) TAPI 0 baris histori kunjungan --
    ini JUGA harus dianggap 'bukan TCARE', bukan dianggap 'fallback
    berhasil' (karena tidak ada data baru yang didapat dari web)."""
    empty_services = pd.DataFrame(columns=["kunjungan", "tanggal", "dealer", "tepat", "status", "ontime_service"])
    vehicle = pd.DataFrame([{"key": "VIN", "value": EMPTY_TCARE_NO_RANGKA}])
    web_result = VinFetchResult(vin=EMPTY_TCARE_NO_RANGKA, vehicle=vehicle, customer=pd.DataFrame(columns=["key", "value"]), services=empty_services)
    web_service = FakeWebService(result=web_result)
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    result = composite.execute(f"history tcare {EMPTY_TCARE_NO_RANGKA}")

    assert result.success is True
    assert result.code == "INT003_OK"
    assert "tidak memiliki riwayat tcare" in result.message.lower()
    assert result.metadata["source"] == "local"


def test_bug2_web_has_history_returns_success_from_web(local_handler_empty_tcare):
    """Kebalikan dari kasus di atas: web TERNYATA punya riwayat yang lokal
    tidak punya -> fallback berhasil, data dari web dipakai."""
    web_service = FakeWebService(result=_found_result(EMPTY_TCARE_NO_RANGKA))
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    result = composite.execute(f"history tcare {EMPTY_TCARE_NO_RANGKA}")

    assert result.success is True
    assert result.code == "INT003_OK"
    assert result.message.startswith("[Realtime dari web TAM]")
    assert result.metadata["source"] == "web_tam_realtime"
    assert len(result.dataframe) == 1


def test_bug2_web_technical_failure_falls_back_to_local_result_unchanged(local_handler_empty_tcare, caplog):
    """Keputusan desain tambahan (ditandai di docstring handler.py, bukan
    eksplisit di brief): kegagalan teknis pada kasus OK-tapi-kosong TIDAK
    men-downgrade jadi ERROR -- identitas lokal yang valid tetap
    dikembalikan apa adanya, cukup di-log sebagai warning."""
    web_service = FakeWebService(result=_technical_error_result(EMPTY_TCARE_NO_RANGKA))
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    with caplog.at_level("WARNING"):
        result = composite.execute(f"history tcare {EMPTY_TCARE_NO_RANGKA}")

    assert result.success is True
    assert result.code == "INT003_OK"
    assert "tidak memiliki riwayat tcare" not in result.message.lower()  # bukan kesimpulan "bukan TCARE"
    assert result.summary["no_rangka"] == EMPTY_TCARE_NO_RANGKA  # summary lokal apa adanya
    assert any("gagal teknis" in rec.message.lower() for rec in caplog.records)


def test_bug2_credentials_not_configured_skips_silently_for_empty_case(local_handler_empty_tcare, caplog):
    web_service = FakeWebService(configured=False)
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    with caplog.at_level("WARNING"):
        result = composite.execute(f"history tcare {EMPTY_TCARE_NO_RANGKA}")

    assert result.code == "INT003_OK"
    assert "tidak memiliki riwayat tcare" not in result.message.lower()
    assert web_service.get_single_calls == []
    assert any("kredensial" in rec.message.lower() for rec in caplog.records)


# =====================================================================
# Regresi eksplisit: kasus normal (riwayat ADA, seperti Bug #1/#2 test)
# harus tetap IDENTIK -- pastikan fix tidak mengubah jalur bahagia.
# =====================================================================

def test_regression_normal_case_with_history_still_unaffected(local_handler):
    """BUDI1 (riwayat TCARE ADA, non-empty) -- fix Bug #2 TIDAK BOLEH
    membuat Composite mencoba fallback untuk kasus ini."""
    web_service = FakeWebService()  # tidak boleh dipanggil sama sekali
    composite = CompositeHistoryTCAREHandler(local_handler, web_service)

    result = composite.execute("history tcare MHFXX1JGK000BUDI1")

    assert result.code == "INT003_OK"
    assert web_service.get_single_calls == []


# =====================================================================
# ADR027 REVISI KE-2 — Bug #3: baris jadwal ADA tapi SEMUA belum
# terealisasi (bulan_realisasi=None) -- reproduksi laporan Wahyu
# (MHKE8FB3JNK077471, 7 baris milestone 1K-60K, semua pending & expired).
# =====================================================================

def test_bug3_all_pending_no_realization_treated_as_empty(local_handler_empty_tcare):
    """Sanity check: fixture benar-benar menghasilkan total_riwayat_tcare=7
    (BUKAN 0) tapi semua bulan_realisasi None -- prasyarat kasus Bug #3."""
    local_result = local_handler_empty_tcare.execute(f"history tcare {UNREALIZED_TCARE_NO_RANGKA}")
    assert local_result.success is True
    assert local_result.code == "INT003_OK"
    assert local_result.summary["total_riwayat_tcare"] == 7  # BUKAN 0 -- inti Bug #3
    assert local_result.dataframe["bulan_realisasi"].isna().all()


def test_bug3_web_also_empty_returns_bukan_tcare(local_handler_empty_tcare):
    """7 baris jadwal, semua belum realisasi + web JUGA tidak ada riwayat
    -> tetap 'bukan TCARE' (bukan NOT_FOUND/ERROR), sama seperti Bug #2."""
    web_service = FakeWebService(result=_not_found_result(UNREALIZED_TCARE_NO_RANGKA))
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    result = composite.execute(f"history tcare {UNREALIZED_TCARE_NO_RANGKA}")

    assert result.success is True
    assert result.code == "INT003_OK"
    assert "tidak memiliki riwayat tcare" in result.message.lower()
    assert result.metadata["source"] == "local"
    assert web_service.get_single_calls == [UNREALIZED_TCARE_NO_RANGKA]


def test_bug3_web_has_history_returns_success_from_web(local_handler_empty_tcare):
    """7 baris jadwal lokal (semua belum realisasi) TAPI web ternyata
    punya riwayat nyata -> fallback berhasil, data web dipakai (mis. data
    lokal belum ter-sync tapi sebenarnya sudah ada kunjungan di TAM)."""
    web_service = FakeWebService(result=_found_result(UNREALIZED_TCARE_NO_RANGKA))
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    result = composite.execute(f"history tcare {UNREALIZED_TCARE_NO_RANGKA}")

    assert result.success is True
    assert result.code == "INT003_OK"
    assert result.message.startswith("[Realtime dari web TAM]")
    assert result.metadata["source"] == "web_tam_realtime"


def test_bug3_partial_realization_not_treated_as_empty(local_handler_empty_tcare):
    """REGRESI PENTING: unit dengan MINIMAL SATU baris sudah realisasi
    TIDAK boleh dianggap kosong -- fallback TIDAK dicoba sama sekali,
    meski baris lain masih pending."""
    web_service = FakeWebService()  # tidak boleh dipanggil
    composite = CompositeHistoryTCAREHandler(local_handler_empty_tcare, web_service)

    result = composite.execute(f"history tcare {PARTIAL_REALIZED_NO_RANGKA}")

    assert result.code == "INT003_OK"
    assert web_service.get_single_calls == []  # fallback TIDAK dicoba


def test_is_effectively_empty_helper_directly():
    """Unit test langsung ke helper -- edge case dataframe None/kosong/
    kolom tidak ada."""
    handler = CompositeHistoryTCAREHandler.__new__(CompositeHistoryTCAREHandler)

    assert handler._is_effectively_empty(None) is True
    assert handler._is_effectively_empty(pd.DataFrame()) is True

    all_none = pd.DataFrame({"bulan_realisasi": [None, None, None]})
    assert handler._is_effectively_empty(all_none) is True

    some_filled = pd.DataFrame({"bulan_realisasi": [None, "2024-01", None]})
    assert handler._is_effectively_empty(some_filled) is False

    no_column = pd.DataFrame({"status": ["pending", "pending"]})
    assert handler._is_effectively_empty(no_column) is False  # fail-safe: default False