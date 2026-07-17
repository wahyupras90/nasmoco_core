"""
parsers/base_parser.py

Kontrak dasar untuk semua Parser (Room 6+, ADR025).

Parser bertugas mengubah raw text user menjadi parameter terstruktur
(biasanya dataclass yang extend BaseParams), SEBELUM masuk ke Service.

Aturan:
    - Parser TIDAK BOLEH mengakses database / menjalankan query SQL.
    - Parser TIDAK BOLEH berisi business rule (itu tugas Service).
    - Parser dipanggil dari Handler, hasilnya diteruskan ke Service.

Berlaku MULAI Room 6 (ADR025). Room 4/5 di-grandfather -- parser yang
sudah ada TIDAK wajib extend class ini, TIDAK perlu direfactor.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    """Base class untuk semua Parser (Room 6 dan seterusnya)."""

    @abstractmethod
    def parse(self, text: str) -> Any:
        """
        Ubah raw text menjadi parameter terstruktur (biasanya instance
        dataclass yang extend BaseParams). Harus dioverride oleh subclass.

        Return None (atau raise, sesuai konvensi Room masing-masing) kalau
        text tidak bisa diparse -- Handler yang menentukan bagaimana itu
        diterjemahkan ke HandlerResult (mis. {INT}_ERROR).
        """
        raise NotImplementedError("Parser wajib mengimplementasikan parse().")
