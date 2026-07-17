"""
tests/test_base_handler.py

Unit test minimal untuk models.base_handler.BaseHandler (ADR021).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, make_code, SUFFIX_OK


class DummyHandler(BaseHandler):
    intent_id = "INT999"
    name = "Dummy Handler"

    def match(self, text: str) -> bool:
        return "dummy" in text.lower()

    def execute(self, text: str) -> HandlerResult:
        return HandlerResult(success=True, code=make_code(self.intent_id, SUFFIX_OK), message="ok")


def test_subclass_can_define_intent_id_and_name():
    handler = DummyHandler()
    assert handler.intent_id == "INT999"
    assert handler.name == "Dummy Handler"


def test_base_handler_defaults_are_empty_string():
    # BaseHandler sendiri (bukan subclass) punya default aman,
    # bukan None/AttributeError, supaya introspeksi Router tidak crash
    # kalau ada handler yang lupa override.
    assert BaseHandler.intent_id == ""
    assert BaseHandler.name == ""


def test_match_and_execute_still_not_implemented_on_base():
    base = BaseHandler()
    try:
        base.match("halo")
        assert False, "Harusnya raise NotImplementedError"
    except NotImplementedError:
        pass

    try:
        base.execute("halo")
        assert False, "Harusnya raise NotImplementedError"
    except NotImplementedError:
        pass


if __name__ == "__main__":
    test_subclass_can_define_intent_id_and_name()
    test_base_handler_defaults_are_empty_string()
    test_match_and_execute_still_not_implemented_on_base()
    print("Semua test BaseHandler PASSED.")
