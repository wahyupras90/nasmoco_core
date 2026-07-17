"""
tests/test_handler_result.py

Unit test minimal untuk models.handler_result.HandlerResult.
"""

import sys
from pathlib import Path

import pandas as pd

# Pastikan root project ada di sys.path saat test dijalankan langsung.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.handler_result import HandlerResult, make_code, SUFFIX_OK, SUFFIX_NOT_FOUND


def test_minimal_construction_success():
    result = HandlerResult(success=True, code="INT002_OK", message="OK")
    assert result.success is True
    assert result.code == "INT002_OK"
    assert result.message == "OK"
    # Default mutable fields harus ter-inisialisasi, bukan None.
    assert result.suggestions == []
    assert result.export == {}
    assert result.metadata == {}
    assert result.dataframe is None
    assert result.summary == {}
    assert result.execution_ms == 0.0


def test_full_construction_with_dataframe():
    df = pd.DataFrame({"a": [1, 2]})
    result = HandlerResult(
        success=True,
        code="INT002_OK",
        message="Data ditemukan",
        dataframe=df,
        summary={"total_rows": 2, "customer": "Budi"},
        suggestions=["opsi 1", "opsi 2"],
        export={"excel": df},
        metadata={"source": "unit-test"},
        execution_ms=12.5,
    )
    assert result.dataframe.equals(df)
    assert result.summary == {"total_rows": 2, "customer": "Budi"}
    assert result.suggestions == ["opsi 1", "opsi 2"]
    assert result.export["excel"].equals(df)
    assert result.metadata["source"] == "unit-test"
    assert result.execution_ms == 12.5


def test_not_found_case():
    result = HandlerResult(
        success=False,
        code="INT002_NOT_FOUND",
        message="Data tidak ditemukan",
    )
    assert result.success is False
    assert result.code == "INT002_NOT_FOUND"


def test_make_code_helper():
    assert make_code("INT002", SUFFIX_OK) == "INT002_OK"
    assert make_code("INT002", SUFFIX_NOT_FOUND) == "INT002_NOT_FOUND"


if __name__ == "__main__":
    test_minimal_construction_success()
    test_full_construction_with_dataframe()
    test_not_found_case()
    test_make_code_helper()
    print("Semua test HandlerResult PASSED.")
