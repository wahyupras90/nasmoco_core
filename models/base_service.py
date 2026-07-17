"""
models/base_service.py

Interface wajib untuk semua Service di nasmoco_core.

Business rule BOLEH ada di layer ini. Service adalah satu-satunya
layer yang menjembatani Handler (presentation logic) dengan
Repository (data access).

Nama method WAJIB `execute()` di semua Service (Interface Standard,
lihat root docs) — dilarang `run()`, `handle()`, `process()`, `query()`.
Ini menjaga Handler bisa memanggil Service manapun tanpa perlu tahu
nama method spesifiknya.

Per ADR020: parameter untuk execute() SEBAIKNYA berupa satu dataclass
milik service tersebut, BUKAN **kwargs bebas. Ini memberi type-safety
dan dokumentasi implisit soal parameter apa yang dibutuhkan, tanpa
melanggar konsistensi nama method di seluruh layer.

Contoh pola yang benar:

    @dataclass
    class KPIParams:
        branch: str
        period: str

    class KPIService(BaseService):
        def execute(self, params: KPIParams) -> pd.DataFrame:
            ...
"""

from typing import Any


class BaseService:
    """Base class untuk semua service."""

    def execute(self, params: Any) -> Any:
        """
        Jalankan business logic dan kembalikan hasil.

        Harus dioverride oleh subclass. `params` idealnya berupa
        dataclass spesifik milik service tersebut (ADR020), bukan
        dict/kwargs bebas. Return type bebas (`Any`) karena tiap
        service punya kebutuhan output berbeda — biasanya dikonsumsi
        langsung oleh Handler untuk dibungkus jadi HandlerResult.
        """
        raise NotImplementedError("Service wajib mengimplementasikan execute().")
