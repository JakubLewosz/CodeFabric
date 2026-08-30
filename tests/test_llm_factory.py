import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO

import pytest

from tools import llm_factory


class _Response:
    def __init__(self, payload: dict):
        self._body = BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._body.read()


def test_get_ollama_status_returns_sorted_unique_models(monkeypatch) -> None:
    payload = {
        "models": [
            {"name": "qwen:latest"},
            {"model": "bielik:latest"},
            {"name": "qwen:latest"},
        ]
    }
    monkeypatch.setattr(
        llm_factory,
        "_urlopen_no_redirect",
        lambda *_args, **_kwargs: _Response(payload),
    )

    status = llm_factory.get_ollama_status()

    assert status.available is True
    assert status.models == ("bielik:latest", "qwen:latest")
    assert status.error is None


def test_get_ollama_status_handles_connection_errors(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(llm_factory, "_urlopen_no_redirect", fail)
    status = llm_factory.get_ollama_status()

    assert status.available is False
    assert status.models == ()
    assert "offline" in (status.error or "")


def test_get_ollama_status_handles_invalid_models_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        llm_factory,
        "_urlopen_no_redirect",
        lambda *_args, **_kwargs: _Response({"models": None}),
    )

    status = llm_factory.get_ollama_status()

    assert status.available is False
    assert status.models == ()
    assert "format" in (status.error or "")


def test_token_estimate_rounds_up_and_validates_limits() -> None:
    assert llm_factory.estimate_tokens("") == 0
    assert llm_factory.estimate_tokens("12345") == 2
    with pytest.raises(ValueError):
        llm_factory.check_context_usage("tekst", 0)


@pytest.mark.parametrize("value", [None, "invalid", "nan", "inf", 0, -1])
def test_positive_float_falls_back_for_invalid_values(value) -> None:
    assert llm_factory._positive_float(value, 15.0) == 15.0


def test_positive_float_accepts_finite_positive_values() -> None:
    assert llm_factory._positive_float("2.5", 15.0) == 2.5


def test_invalid_base_url_is_reported_without_network_call(monkeypatch) -> None:
    monkeypatch.setattr(llm_factory, "OLLAMA_URL", "not-a-url")

    status = llm_factory.get_ollama_status()

    assert status.available is False
    assert "OLLAMA_BASE_URL" in (status.error or "")


@pytest.mark.parametrize(
    "invalid_url",
    [
        "http://localhost:abc",
        "http://localhost:70000",
        "http://localhost:11434\nX-Injected: yes",
        "http://localhost:11434/path with space",
    ],
)
def test_malformed_ollama_urls_never_escape_status_check(monkeypatch, invalid_url) -> None:
    monkeypatch.setattr(llm_factory, "OLLAMA_URL", invalid_url)
    monkeypatch.setattr(
        llm_factory,
        "_urlopen_no_redirect",
        lambda *_args, **_kwargs: pytest.fail("network call must not be attempted"),
    )

    status = llm_factory.get_ollama_status()

    assert status.available is False
    assert "OLLAMA_BASE_URL" in (status.error or "")
    with pytest.raises(ValueError, match="OLLAMA_BASE_URL"):
        llm_factory.get_llm("test-model")


def test_invalid_token_header_is_reported_without_crashing(monkeypatch) -> None:
    monkeypatch.setattr(llm_factory, "OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(llm_factory, "OLLAMA_TOKEN", "token\r\ninjected")
    monkeypatch.setattr(
        llm_factory,
        "_urlopen_no_redirect",
        lambda *_args, **_kwargs: pytest.fail("network call must not be attempted"),
    )

    status = llm_factory.get_ollama_status()

    assert status.available is False
    assert "OLLAMA_TOKEN" in (status.error or "")
    with pytest.raises(ValueError, match="OLLAMA_TOKEN"):
        llm_factory.get_llm("test-model")


def test_health_check_never_forwards_token_through_redirect(monkeypatch) -> None:
    sink_headers = []
    source_headers = []

    class SinkHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            sink_headers.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"models": []}')

        def log_message(self, _format, *_args):
            return

    sink = HTTPServer(("127.0.0.1", 0), SinkHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            source_headers.append(self.headers.get("Authorization"))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{sink.server_port}/capture")
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    source = HTTPServer(("127.0.0.1", 0), RedirectHandler)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in (sink, source)
    ]
    for thread in threads:
        thread.start()

    try:
        monkeypatch.setattr(llm_factory, "OLLAMA_URL", f"http://127.0.0.1:{source.server_port}")
        monkeypatch.setattr(llm_factory, "OLLAMA_TOKEN", "TOPSECRET")

        status = llm_factory.get_ollama_status()
    finally:
        for server in (source, sink):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)

    assert status.available is False
    assert source_headers == ["Bearer TOPSECRET"]
    assert sink_headers == []


def test_llm_timeout_reaches_sync_and_async_http_clients(monkeypatch) -> None:
    monkeypatch.setattr(llm_factory, "OLLAMA_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(llm_factory, "OLLAMA_TIMEOUT", 12.5)

    llm = llm_factory.get_llm("test-model")

    for client in (llm._client._client, llm._async_client._client):
        timeout = client.timeout
        assert timeout.connect == 12.5
        assert timeout.read == 12.5
        assert timeout.write == 12.5
        assert timeout.pool == 12.5
