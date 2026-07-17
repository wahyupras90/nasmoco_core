"""
parsers/base_params.py

Base dataclass kosong untuk parameter hasil parsing (Room 6+, ADR025).
Parser spesifik extend ini, contoh:

    @dataclass
    class AttackListParams(BaseParams):
        segment: Optional[str] = None
        ...
"""

from dataclasses import dataclass


@dataclass
class BaseParams:
    """Base class kosong -- parser spesifik menambah field sendiri."""
    pass
