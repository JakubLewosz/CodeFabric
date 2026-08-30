from __future__ import annotations

import importlib

import pytest
import requests

import debug_raw


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nie pozwól, by prywatny plik .env wpływał na testy."""
    monkeypatch.setattr(debug_raw, "load_dotenv", lambda: False)
    for name in (
        "OLLAMA_BASE_URL",
        "OLLAMA_TOKEN",
        "VERIFY_SSL",
        "MODEL_CODER",
        "OLLAMA_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_import_does_not_send_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_request(*args: object, **kwargs: object) -> None:
        raise AssertionError("import nie może wysyłać żądania")

    monkeypatch.setattr(requests, "post", unexpected_request)
    importlib.reload(debug_raw)


def test_diagnostic_uses_secure_defaults(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    request: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, dict[str, str]]:
            return {"message": {"content": "Ollama działa."}}

    def fake_post(url: str, **kwargs: object) -> Response:
        request["url"] = url
        request.update(kwargs)
        return Response()

    monkeypatch.setattr(debug_raw.requests, "post", fake_post)

    assert debug_raw.main() == 0
    assert request["url"] == "http://localhost:11434/api/chat"
    assert request["verify"] is True
    assert "Ollama działa." in capsys.readouterr().out


def test_diagnostic_reports_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def failed_request(*args: object, **kwargs: object) -> None:
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(debug_raw.requests, "post", failed_request)

    assert debug_raw.main() == 1


@pytest.mark.parametrize("value", ["0", "-1", "nan", "forever"])
def test_diagnostic_rejects_invalid_timeout(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_TIMEOUT", value)
    monkeypatch.setattr(
        debug_raw.requests,
        "post",
        lambda *args, **kwargs: pytest.fail("nie wolno wysłać żądania"),
    )

    assert debug_raw.main() == 2


@pytest.mark.parametrize("value", ["maybe", "2", "enabled"])
def test_env_flag_rejects_ambiguous_values(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_SSL", value)

    with pytest.raises(ValueError, match="VERIFY_SSL"):
        debug_raw.env_flag("VERIFY_SSL", default=True)
