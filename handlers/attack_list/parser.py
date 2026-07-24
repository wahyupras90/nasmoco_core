"""
handlers/attack_list/parser.py — INT008 Attack List

Extend BaseParser (ADR025). Tiga mode:
  - "list"            : query attack_list saat ini, dengan filter opsional
                         (source/status/sa_terakhir/segment_rfm/program_id).
  - "list" + expired   : sub-mode "expired" (lihat di bawah) -- BUKAN nilai
                         status, tapi mode filter berbeda berbasis
                         `batas_tcare` per periode.
  - "history"          : statistik konversi dari attack_list_history untuk
                         bulan tertentu -- reuse handlers._shared.period_parser
                         (BR027-style sharing, sama seperti Room 5).

Disambiguasi mode: kata "konversi"/"histori" DIKOMBINASIKAN dengan
penyebutan periode eksplisit (bulan ini/lalu/nama bulan/ISO) -> mode
history. Tanpa penyebutan periode eksplisit, "konversi" dianggap filter
status='converted' di mode list saja (bukan histori).

## Mode "expired" (ditambahkan setelah verifikasi terhadap
`tools/attack_list.py` versi legacy, dikirim Wahyu)

"expired" BUKAN nilai kolom `status` (nilai status yang ada hanya
pending/converted/resolved) -- ini MODE FILTER TERPISAH yang menggantikan
filter status biasa, persis logic legacy:

    kalau expired_mode:
        WHERE strftime('%Y-%m', batas_tcare) = <bulan>
          AND status NOT IN ('converted', 'resolved')

Kata "bulan ini"/"bulan agustus" dkk HANYA dipakai untuk memfilter
`batas_tcare` dalam mode expired ini (reuse `extract_period()`, default ke
bulan berjalan kalau tidak disebutkan eksplisit -- sama seperti
`_validate_bulan()` di legacy). Di luar mode expired, periode TIDAK
memfilter tabel `attack_list` (hanya dipakai untuk mode "history").

## Ekstraksi SA & segment_rfm (whitelist, BUKAN regex generik lagi)

Sebelumnya best-effort regex -- ditemukan bug: kata umum seperti "yg"
(singkatan "yang") salah tertangkap sebagai kandidat SA. Diperbaiki
dengan whitelist eksplisit (VALID_SA, dikonfirmasi Wahyu masih akurat;
VALID_SEGMENT, dari `tools/attack_list.py` legacy) -- jauh lebih aman
daripada pendekatan stopword/blacklist.

## CATATAN TERBUKA untuk Room 0 (belum diimplementasikan, sengaja ditunda)

`program_id` di skema `attack_list` bertipe INTEGER (dikonfirmasi PRAGMA),
tapi `tools/attack_list.py` legacy membandingkan `program_id = 'P1'` (kode
teks) lewat `PROGRAM_KEYWORD_MAP` ("panggil pulang"->P1, dst). Belum bisa
diverifikasi apakah representasi ini masih berlaku di tabel `attack_list`
unified sekarang (kemungkinan sudah berubah jadi id numerik asli dari
`marketing_program`). Ekstraksi `program_id` di sini TETAP hanya menerima
angka literal (`"program 11"`), TIDAK menambahkan alias teks seperti
"panggil pulang" sampai representasi program_id riil dikonfirmasi --
supaya tidak salah filter tanpa ketahuan.
"""

import re
from dataclasses import dataclass
from typing import Optional

from handlers._shared.period_parser import ParsedPeriod, extract_period
from parsers.base_params import BaseParams
from parsers.base_parser import BaseParser

ATTACK_LIST_KEYWORDS = (
    "attack list", "attack-list", "attacklist", "sasaran follow up",
    "unit follow up", "daftar attack",
)

_SOURCE_MAP = {
    "tcare": "TCARE",
    "crm": "CRM",
    "cr7": "CR7",
}

_STATUS_KEYWORDS = {
    "pending": "pending",
    "resolved": "resolved",
    "converted": "converted",
}

_HISTORY_TRIGGER_WORDS = ("konversi", "histori", "history")

# INT010 (extend PX): kata pemicu KHUSUS untuk fallback nama PX -- SENGAJA
# hanya "konversi", TIDAK termasuk "histori"/"history". Ditemukan lewat
# testing nyata (bukan asumsi): "history <nama PX>" ambigu dengan
# HistoryServiceHandler/History TCARE (yang MEMANG berhak atas kata
# "history"/"histori", priority sama di router -- tie-break menang
# duluan karena registrasi lebih awal). "konversi" tidak overlap sama
# sekali dengan domain manapun (dicek: tidak ada handler lain yang pakai
# kata ini), jadi aman jadi satu-satunya pemicu untuk PX.
_PX_HISTORY_TRIGGER_WORDS = ("konversi",)

# INT010: kata "datang" saja terlalu generik (bisa soal WIP/servis lain di
# luar domain attack list) -- HANYA dianggap trigger history kalau muncul
# BERSAMA salah satu penanda domain attack list (source/program/kata
# konversi/frasa attack list itu sendiri). Lihat _wants_history_natural().
_NATURAL_CONVERSION_WORDS = ("datang",)

EXPIRED_KEYWORD = "expired"

# Whitelist nama program CRM (P1-P4) -- dari attack_list_history.program,
# dikonfirmasi Wahyu via query langsung ke DB (2026-07). Sama seperti
# VALID_SA/VALID_SEGMENT: whitelist eksplisit, BUKAN regex generik, supaya
# tidak salah tangkap kalimat lain (ADR028). Kalau daftar program berubah
# di marketing_program, whitelist ini perlu diupdate manual (satu titik).
VALID_PROGRAM = (
    "panggil pulang - at risk",
    "panggil pulang - lost",
    "percepat interval - loyal customer",
    "aktivasi new & potential",
)

# Whitelist kode SA -- dikonfirmasi Wahyu (2026-07) masih akurat. Kalau
# roster SA berubah di masa depan, cukup update daftar ini (satu titik).
VALID_SA = ("AGN", "ARIS", "BDR", "IND", "NRK", "SAID", "ZKY", "KHA")

# Whitelist segment_rfm -- dari tools/attack_list.py legacy (VALID_SEGMENT).
# Nilai asli lowercase di database ("at risk", "champion", dst).
VALID_SEGMENT = ("at risk", "lost", "champion", "loyal", "potential", "new")

_PROGRAM_ID_REGEX = re.compile(r"\bprogram\s*(?:id\s*)?[:#]?\s*(\d+)\b", re.IGNORECASE)

SUMMARY_ONLY_KEYWORDS = ("total", "berapa", "jumlah")
# CATATAN: "list" SENGAJA TIDAK dimasukkan di sini -- trigger phrase intent
# ini sendiri ("attack list") selalu mengandung kata "list", jadi kalau
# dipakai sebagai LIST_KEYWORDS, wants_summary_only akan SELALU False untuk
# semua query attack list (bug ditemukan lewat unit test). "daftar" cukup
# mewakili niat "tampilkan daftar" dalam Bahasa Indonesia di domain ini.
LIST_KEYWORDS = ("daftar", "detail", "rincian")

_MONTHS = [
    "januari", "februari", "maret", "april", "mei", "juni",
    "juli", "agustus", "september", "oktober", "november", "desember",
    "jan", "feb", "mar", "apr", "jun", "jul", "agu", "sep", "okt", "nov", "des"
]
_MONTHS_REGEX = r"\b(" + "|".join(_MONTHS) + r")\b"

_DYNAMIC_SOURCE_IGNORE_WORDS = set(
    list(SUMMARY_ONLY_KEYWORDS) +
    list(LIST_KEYWORDS) +
    list(_HISTORY_TRIGGER_WORDS) +
    list(_STATUS_KEYWORDS.keys()) +
    [sa.lower() for sa in VALID_SA] +
    _MONTHS +
    [
        "expired", "semua", "all", "keseluruhan", "seluruh",
        "bulan", "ini", "lalu", "depan", "tahun",
        "tolong", "tampilkan", "kasih", "lihat", "dong", "min",
        "carikan", "cari", "buat", "bikinkan", "cek", "cekkan", "ya",
        "dari", "untuk", "data", "yg", "yang", "di", "ke", "ada",
        "sa", "service", "advisor",  # PENAMBAHAN BUGFIX: Abaikan kata SA sebagai source
        "berapa", "datang", "sudah", "belum",  # INT010: trigger natural, bukan source
        # BUGFIX (INT010 PX, ditemukan lewat test manual chatbot production):
        # kata "program" sendiri (tanpa angka setelahnya, lolos dari
        # _PROGRAM_ID_REGEX yang cuma hapus "program 11") tidak pernah
        # ter-strip -- membuat "program Panggil Pulang At Risk" (nama CRM
        # tanpa tanda hubung, gagal match whitelist VALID_PROGRAM) salah
        # tertangkap sebagai source PX "program Panggil Pulang" (kata
        # "program" ikut kebawa masuk).
        "program",
    ]
)


@dataclass
class AttackListParams(BaseParams):
    mode: str = "list"  # "list" | "history"
    source: Optional[str] = None
    status: Optional[str] = None
    sa_terakhir: Optional[str] = None
    segment_rfm: Optional[str] = None
    program_id: Optional[int] = None
    program: Optional[str] = None  # INT010: nama program CRM (VALID_PROGRAM), breakdown history
    period: Optional[ParsedPeriod] = None  # mode=="history" ATAU expired_mode=True
    expired_mode: bool = False
    wants_summary_only: bool = False
    # KEPUTUSAN FINAL ROOM 0 (2026-07-24, Opsi A): kalau kata trigger
    # konversi/history disebut BERSAMA "expired", TIDAK beralih ke
    # mode="history" (attack_list_history tidak punya konsep "expired PADA
    # bulan lampau", dan JOIN runtime ke attack_list untuk itu semantiknya
    # tidak akurat -- lihat brief investigasi Room 7a). Tetap mode="list" +
    # expired_mode=True (populasi SAMA PERSIS dengan "attack list ...
    # expired ..."), TIDAK berubah. Flag ini menandakan Service harus
    # MENOLAK dengan pesan penjelasan -- BUKAN menghitung angka konversi
    # apa pun -- karena "expired" adalah status akhir final (unit
    # gugur/hangus dari follow-up), sehingga "konversi dari unit yang
    # sudah expired" secara konsep tidak valid ditanya (mirip peran
    # wants_summary_only sebagai preseden pola flag).
    wants_conversion_summary: bool = False



def _extract_sa(text_upper: str) -> Optional[str]:
    """Whitelist-based -- cari token VALID_SA yang berdiri sendiri (word
    boundary), BUKAN regex generik + stopword (rawan false-positive, mis.
    'yg' tertangkap jadi SA -- bug yang sudah ditemukan & diperbaiki)."""
    for sa in VALID_SA:
        if re.search(rf"\b{sa}\b", text_upper):
            return sa
    return None


def _extract_segment(text_lower: str) -> Optional[str]:
    """Whitelist-based, dari VALID_SEGMENT (tools/attack_list.py legacy)."""
    for seg in VALID_SEGMENT:
        if seg in text_lower:
            return seg
    return None


def _extract_program(text_lower: str) -> Optional[str]:
    """Whitelist-based (VALID_PROGRAM) -- sama pola dengan _extract_sa/
    _extract_segment. Dicek SEBELUM _extract_dynamic_source supaya nama
    program (yang mengandung spasi & tanda hubung) tidak keburu terpotong
    jadi source PX asal-asalan."""
    for prog in VALID_PROGRAM:
        if prog in text_lower:
            return prog
    return None


def _extract_history_source_or_program(text: str, t_lower: str):
    """INT010 (extend): tentukan (source, program) untuk trigger history
    natural, dengan URUTAN WAJIB (dikonfirmasi Room 0, bukan detail bebas):

        1. Whitelist VALID_PROGRAM (CRM P1-P4) dicek LEBIH DULU.
        2. HANYA kalau (1) tidak match, fallback ke source statis
           (tcare/crm/cr7) ATAU ekstraksi PX dinamis
           (`_extract_dynamic_source`, reuse fungsi yang sama dipakai
           mode "list" -- TIDAK menduplikasi logic ekstraksi PX).

    Urutan ini penting supaya nama program CRM (mengandung spasi/tanda
    hubung) tidak pernah "bocor" ke ekstraksi PX (bug lama, sudah
    diperbaiki), DAN sebaliknya nama PX custom tidak pernah salah
    diproses seolah program CRM (whitelist CRM sudah pasti/terbatas 4
    nilai, jadi kalau tidak match salah satu dari situ, otomatis aman
    dilanjutkan ke jalur PX).

    Return: (source, program) -- program None kalau hasilnya PX/source
    statis (PX/TCARE/CR7 tidak granular per program, sesuai desain awal).
    """
    program = _extract_program(t_lower)
    if program is not None:
        return "CRM", program

    for key, value in _SOURCE_MAP.items():
        if re.search(rf"\b{key}\b", t_lower):
            return value, None

    px_source = _extract_dynamic_source(text)
    if px_source:
        return px_source, None

    return None, None


def _wants_history_natural(t: str) -> bool:
    """INT010: kata "datang" (mis. 'berapa yang datang') dianggap trigger
    history HANYA kalau muncul bersama penanda domain attack list --
    source (tcare/crm/cr7), nama program (VALID_PROGRAM), kata konversi
    itu sendiri, atau frasa attack list. "Berapa yang datang" tanpa
    konteks itu SENGAJA TIDAK ditangkap (terlalu generik, bisa soal
    WIP/servis lain -- checklist ADR028).

    BUGFIX: source dicek dengan word-boundary (\\bkey\\b), BUKAN substring
    biasa -- substring biasa membuat VIN yang mengandung "tcare" sebagai
    substring (mis. "MHTCARE0000001") salah tertangkap sebagai penanda
    source, sehingga kalimat riwayat servis biasa ("MHTCARE0000001 kapan
    terakhir datang service") salah match ke attack_list, padahal harusnya
    ke history_service/history_tcare. Ditemukan lewat test ADR028
    checklist eksplisit, bukan asumsi."""
    if not any(w in t for w in _NATURAL_CONVERSION_WORDS):
        return False
    has_domain_context = (
        any(k in t for k in ATTACK_LIST_KEYWORDS)
        or any(re.search(rf"\b{key}\b", t) for key in _SOURCE_MAP)
        or any(prog in t for prog in VALID_PROGRAM)
        or any(w in t for w in _HISTORY_TRIGGER_WORDS)
    )
    return has_domain_context


def _extract_dynamic_source(text: str) -> Optional[str]:
    """Ekstraksi nama source dinamis (PX) dengan pola subtraktif (menghapus
    semua parameter/keyword yang sudah dikenali sistem). Sisanya dianggap
    sebagai nama spesifik source. Mendukung nama dengan spasi (mis: 'test program')."""
    t_lower = text.lower()

    # -1. BUGFIX: Hapus format ISO date (YYYY-MM atau YYYY-MM-DD) agar tidak ditangkap sebagai source PX
    t_lower = re.sub(r"\b\d{4}-\d{2}(?:-\d{2})?\b", " ", t_lower)

    # 0. Hapus pola kombinasi waktu spesifik yang mengandung angka teks-bulan (Bugfix: "juli 26", "26 juli")
    t_lower = re.sub(_MONTHS_REGEX + r"\s+\d{2,4}\b", " ", t_lower)
    t_lower = re.sub(r"\b\d{2,4}\s+" + _MONTHS_REGEX, " ", t_lower)

    # 1. Hapus nilai Program ID (mis: "program 11") dari pencarian
    t_lower = _PROGRAM_ID_REGEX.sub(" ", t_lower)

    # 2. Hapus frase trigger intent
    for kw in ATTACK_LIST_KEYWORDS:
        t_lower = t_lower.replace(kw, " ")

    # 3. Hapus frase whitelist segment
    for seg in VALID_SEGMENT:
        t_lower = t_lower.replace(seg, " ")

    # 3b. Hapus frase whitelist nama program CRM (INT010) -- supaya nama
    # program (mengandung spasi/tanda hubung) tidak salah tertangkap
    # sebagai nama source PX.
    for prog in VALID_PROGRAM:
        t_lower = t_lower.replace(prog, " ")

    # 4. Tokenisasi dan abaikan kata parameter standar / stop-words
    words = t_lower.split()
    clean_words = []
    for w in words:
        if w in _DYNAMIC_SOURCE_IGNORE_WORDS:
            continue
        # Abaikan angka 4 digit yang berdiri sendiri (mencegah tahun ditarik jadi source, 
        # namun membiarkan string utuh yang menyatu seperti "Recall_Rem_2026").
        if re.match(r"^20\d{2}$", w):
            continue
        clean_words.append(w)

    if not clean_words:
        return None

    # BUGFIX (2026-07-23, ditemukan Wahyu): sisa teks HARUS punya minimal
    # 1 karakter alfanumerik -- sebelumnya tanda baca murni (mis. ">",
    # sisa dari artefak copy-paste prompt CLI) lolos dianggap nama source
    # PX yang valid, menyebabkan "source=>" yang jelas tidak masuk akal.
    joined_check = "".join(clean_words)
    if not re.search(r"[a-zA-Z0-9]", joined_check):
        return None

    # 5. Pasangkan kembali dengan original teks agar casing/huruf besar-kecil tetap natural (jika ada)
    pattern = r"\s+".join([re.escape(w) for w in clean_words])
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(0).strip()
        
    return " ".join(clean_words)


class AttackListParser(BaseParser):

    def match(self, text: str) -> bool:
        t = text.lower()
        if any(k in t for k in ATTACK_LIST_KEYWORDS):
            return True
        # INT010: trigger natural tanpa kata "attack list" -- "konversi
        # program X", "berapa yang datang dari program Y", dst. Tetap
        # butuh konteks domain (source/program/kata konversi) supaya
        # tidak menangkap kalimat umum di luar attack list (ADR028).
        # Whitelist VALID_PROGRAM (CRM) DICEK LEBIH DULU -- urutan wajib,
        # dikonfirmasi Room 0 (lihat _extract_history_source_or_program).
        if any(prog in t for prog in VALID_PROGRAM):
            return True
        # BUGFIX: word-boundary, bukan substring -- "MHTCARE0000001"
        # (VIN) tidak boleh salah tertangkap sebagai penanda source "tcare".
        if any(w in t for w in _HISTORY_TRIGGER_WORDS) and any(
            re.search(rf"\b{key}\b", t) for key in _SOURCE_MAP
        ):
            return True
        # INT010 (extend): kata pemicu KHUSUS "konversi" (bukan
        # histori/history, lihat _PX_HISTORY_TRIGGER_WORDS) + nama
        # program PX custom (fallback SETELAH whitelist CRM & source
        # statis di atas tidak match) -- kata pemicu tetap WAJIB ada
        # (ADR028: nama PX sendirian, tanpa kata pemicu, TIDAK boleh
        # match, karena nama PX bebas/tidak whitelist seperti CRM).
        if any(w in t for w in _PX_HISTORY_TRIGGER_WORDS):
            px_source = _extract_dynamic_source(text)
            if px_source:
                return True
        return _wants_history_natural(t)

    def parse(self, text: str) -> AttackListParams:
        t = text.lower()
        text_upper = text.upper()

        # INT010: cek nama program (whitelist) LEBIH DULU. Kalau ketemu,
        # source CRM tersirat -- jangan panggil _extract_dynamic_source
        # sama sekali, supaya sisa kata "program" (tanpa angka, lolos dari
        # _PROGRAM_ID_REGEX) tidak salah tertangkap jadi source PX.
        program = _extract_program(t)

        source = None
        if program is not None:
            source = "CRM"
        else:
            # Evaluasi MAP statis dulu (Prioritas TCARE/CRM/CR7)
            for key, value in _SOURCE_MAP.items():
                if re.search(rf"\b{key}\b", t):
                    source = value
                    break

            # Jika bukan source statis, ekstraksi sisa teks untuk dinamis (PX)
            if not source:
                source = _extract_dynamic_source(text)

        status = None
        for key, value in _STATUS_KEYWORDS.items():
            if key in t:
                status = value
                break

        period = extract_period(text)
        wants_history = period.is_explicit and any(w in t for w in _HISTORY_TRIGGER_WORDS)
        expired_mode = EXPIRED_KEYWORD in t

        sa_terakhir = _extract_sa(text_upper)
        segment_rfm = _extract_segment(t)

        program_id = None
        m = _PROGRAM_ID_REGEX.search(text)
        if m:
            program_id = int(m.group(1))

        # wants_history sekarang punya BEBERAPA jalur:
        #   1. eksplisit: kata konversi/histori/history + periode eksplisit
        #      (perilaku lama Room 6, TIDAK berubah)
        #   2. natural (INT010): sebut nama program (VALID_PROGRAM) secara
        #      langsung, ATAU kata "datang" + konteks domain -- keduanya
        #      dianggap niat history meski periode tidak eksplisit
        #      (default ke bulan berjalan, sama seperti expired_mode)
        #   3. natural PX (extend): kata pemicu KHUSUS "konversi" (BUKAN
        #      histori/history -- itu domain History Service/History
        #      TCARE, ditemukan bentrok lewat testing nyata) + source
        #      ketemu via fallback PX dinamis (source SUDAH dihitung di
        #      atas, whitelist CRM->statis->PX, urutan wajib dikonfirmasi
        #      Room 0) -- kata pemicu tetap disyaratkan (ADR028), nama PX
        #      sendirian tanpa itu TIDAK masuk sini.
        wants_history_px = (
            any(w in t for w in _PX_HISTORY_TRIGGER_WORDS)
            and source is not None
            and source not in _SOURCE_MAP.values()
            and program is None
        )
        wants_history = (
            wants_history or program is not None or _wants_history_natural(t) or wants_history_px
        )

        # KEPUTUSAN FINAL ROOM 0 (2026-07-24, Opsi A): begitu kata "expired"
        # disebut BERSAMA kata trigger konversi/history, jangan pernah
        # beralih ke mode="history" -- attack_list_history tidak mengenal
        # konsep "expired" sama sekali (kolom batas_tcare cuma ada di
        # attack_list, dan JOIN runtime secara semantik tidak akurat untuk
        # histori bulan lampau, lihat brief investigasi Room 7a). Tetap
        # mode="list" + expired_mode=True (TIDAK berubah), tandai
        # wants_conversion_summary=True sebagai sinyal Service untuk
        # MENOLAK dengan pesan penjelasan -- "expired" adalah status akhir
        # final (unit gugur/hangus dari follow-up), "konversi dari unit
        # yang sudah expired" secara konsep tidak valid ditanya, BUKAN
        # angka 0 ataupun angka lain.
        wants_conversion_summary = False
        if wants_history and expired_mode:
            wants_history = False
            wants_conversion_summary = True

        wants_summary_only = any(k in t for k in SUMMARY_ONLY_KEYWORDS) and not any(
            k in t for k in LIST_KEYWORDS
        )

        if wants_history:
            # BUGFIX (INT010, ditemukan lewat test manual production):
            # sa_terakhir sebelumnya TIDAK disertakan di sini sama sekali
            # -- kata "sa bdr" di query "konversi ... sa bdr" berhasil
            # diekstrak (baris di atas) tapi DIBUANG diam-diam, filter SA
            # tidak pernah diterapkan (silent failure). Sekarang
            # disertakan -- KEPUTUSAN ROOM 0: untuk mode history, field
            # ini dipetakan ke filter `sa_konversi` (SA yang closing
            # transaksi riil), BUKAN `attack_list.sa_terakhir` (SA
            # assignment attack list, konsep BEDA, dipakai mode list
            # saja) -- pemetaan ke kolom yang benar terjadi di
            # handler.py/service.py, bukan di sini.
            return AttackListParams(
                mode="history", source=source, program=program,
                sa_terakhir=sa_terakhir, period=period,
            )

        return AttackListParams(
            mode="list",
            source=source,
            status=status,
            sa_terakhir=sa_terakhir,
            segment_rfm=segment_rfm,
            program_id=program_id,
            # PENTING: period SELALU diisi (bukan cuma saat expired_mode
            # seperti sebelumnya) -- ditemukan bug 2026-07-23: mode "all"
            # ("Attack List Semua") butuh tahu periode yang diminta user
            # (mis. "juli") untuk scoping TCARE pending/converted, tapi
            # sebelumnya period selalu None kalau bukan expired_mode,
            # jadi _execute_all_summary() diam-diam selalu pakai
            # datetime.now() (hari ini), mengabaikan periode yang diketik
            # user sama sekali.
            period=period,
            expired_mode=expired_mode,
            wants_summary_only=wants_summary_only,
            wants_conversion_summary=wants_conversion_summary,
        )