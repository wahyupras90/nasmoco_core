"""
tests/test_app_v2.py — Room 3.

Test scope Room 3: create_router(), _safe_route(), konversi HandlerResult
ke JSON, dan endpoint API (/health, /query). Tidak menguji ulang perilaku
internal Router (itu sudah divalidasi Room 2 di test_router.py).
"""
import http.client
import json
import threading
import time

import pandas as pd
import pytest

from app_v2 import (
    create_router,
    _safe_route,
    handler_result_to_dict,
    build_api_server,
)
from ai.router import Router
from models.base_handler import BaseHandler
from models.handler_result import HandlerResult, make_code, SUFFIX_OK


class _EchoHandler(BaseHandler):
    intent_id = "INT001"
    name = "echo"

    def match(self, text: str) -> bool:
        return text.strip().lower() == "echo"

    def execute(self, text: str) -> HandlerResult:
        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message="echo ok",
            summary={"echoed": text},
        )


class _BoomHandler(BaseHandler):
    intent_id = "INT002"
    name = "boom"

    def match(self, text: str) -> bool:
        return text.strip().lower() == "boom"

    def execute(self, text: str) -> HandlerResult:
        raise RuntimeError("kaboom")


class _DataframeHandler(BaseHandler):
    intent_id = "INT003"
    name = "dataframe"

    def match(self, text: str) -> bool:
        return text.strip().lower() == "df"

    def execute(self, text: str) -> HandlerResult:
        return HandlerResult(
            success=True,
            code=make_code(self.intent_id, SUFFIX_OK),
            message="dataframe ok",
            dataframe=pd.DataFrame([{"a": 1, "b": 2}]),
        )


# ---------------------------------------------------------------------------
# create_router()
# ---------------------------------------------------------------------------

def test_create_router_returns_router_instance():
    router = create_router()
    assert isinstance(router, Router)


def test_create_router_accepts_register_and_route_without_error():
    router = create_router()
    router.register(_EchoHandler(), priority=10)
    result = router.route("echo")
    assert result.success is True
    assert result.code == "INT001_OK"


def test_unmatched_query_uses_null_fallback_gracefully():
    router = create_router()
    router.register(_EchoHandler(), priority=10)
    result = router.route("sesuatu yang tidak match apa pun")
    assert result.success is False
    assert result.code == "INT999_ERROR"


# ---------------------------------------------------------------------------
# _safe_route: exception tak terduga tidak boleh crash
# ---------------------------------------------------------------------------

def test_safe_route_catches_unexpected_handler_exception():
    router = create_router()
    router.register(_BoomHandler(), priority=10)
    result = _safe_route(router, "boom")
    assert result.success is False
    assert result.code.endswith("_ERROR")
    assert "kaboom" in result.message


def test_safe_route_passthrough_on_success():
    router = create_router()
    router.register(_EchoHandler(), priority=10)
    result = _safe_route(router, "echo")
    assert result.success is True


# ---------------------------------------------------------------------------
# handler_result_to_dict: konversi JSON-serializable
# ---------------------------------------------------------------------------

def test_handler_result_to_dict_converts_dataframe():
    router = create_router()
    router.register(_DataframeHandler(), priority=10)
    result = router.route("df")
    payload = handler_result_to_dict(result)

    json.dumps(payload)  # tidak boleh raise
    assert payload["dataframe"] == [{"a": 1, "b": 2}]


def test_handler_result_to_dict_none_dataframe():
    router = create_router()
    router.register(_EchoHandler(), priority=10)
    result = router.route("echo")
    payload = handler_result_to_dict(result)

    json.dumps(payload)  # tidak boleh raise
    assert payload["dataframe"] is None
    assert payload["summary"] == {"echoed": "echo"}


# ---------------------------------------------------------------------------
# API endpoint: /health dan /query
# ---------------------------------------------------------------------------

@pytest.fixture
def api_server():
    router = create_router()
    router.register(_EchoHandler(), priority=10)
    router.register(_BoomHandler(), priority=10)
    server = build_api_server(router, port=0)  # port 0 -> OS pilih port bebas
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield port
    server.shutdown()
    server.server_close()


def test_health_endpoint(api_server):
    conn = http.client.HTTPConnection("localhost", api_server)
    conn.request("GET", "/health")
    resp = conn.getresponse()
    body = json.loads(resp.read())
    assert resp.status == 200
    assert body == {"status": "ok"}
    conn.close()


def test_query_endpoint_success(api_server):
    conn = http.client.HTTPConnection("localhost", api_server)
    body = json.dumps({"text": "echo"})
    conn.request("POST", "/query", body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    payload = json.loads(resp.read())
    assert resp.status == 200
    assert payload["success"] is True
    assert payload["code"] == "INT001_OK"
    conn.close()


def test_query_endpoint_unexpected_exception_returns_error_json_not_crash(api_server):
    conn = http.client.HTTPConnection("localhost", api_server)
    body = json.dumps({"text": "boom"})
    conn.request("POST", "/query", body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    payload = json.loads(resp.read())
    assert resp.status == 200  # request tetap "berhasil" secara HTTP, errornya di body
    assert payload["success"] is False
    assert payload["code"].endswith("_ERROR")
    conn.close()


def test_query_endpoint_missing_text_field_returns_400(api_server):
    conn = http.client.HTTPConnection("localhost", api_server)
    body = json.dumps({})
    conn.request("POST", "/query", body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp.read()
    assert resp.status == 400
    conn.close()
