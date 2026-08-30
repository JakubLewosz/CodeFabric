from __future__ import annotations

import json
import math
import os
import ssl
from dataclasses import dataclass
from http.client import HTTPException, InvalidURL
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()

# Globalne ustawienia z .env
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "").strip()
# Only explicit false-like values disable verification. Typos therefore fail
# secure instead of silently turning TLS checks off.
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


def _positive_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) and parsed > 0 else default


OLLAMA_TIMEOUT = _positive_float(os.getenv("OLLAMA_TIMEOUT", "300"), 300.0)


def _validated_base_url() -> str:
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in OLLAMA_URL
    ):
        raise ValueError("OLLAMA_BASE_URL zawiera niedozwolone białe lub sterujące znaki.")
    try:
        parsed = urlsplit(OLLAMA_URL)
        hostname = parsed.hostname
        _port = parsed.port  # Wymusza walidację zakresu i formatu portu.
    except ValueError as exc:
        raise ValueError("OLLAMA_BASE_URL zawiera niepoprawny host lub port.") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not hostname:
        raise ValueError("OLLAMA_BASE_URL musi być pełnym adresem http:// lub https://.")
    return OLLAMA_URL


def _authorization_headers() -> dict[str, str]:
    if not OLLAMA_TOKEN:
        return {}
    if any(ord(character) < 32 or ord(character) == 127 for character in OLLAMA_TOKEN):
        raise ValueError("OLLAMA_TOKEN zawiera niedozwolone znaki sterujące.")
    return {"Authorization": f"Bearer {OLLAMA_TOKEN}"}


@dataclass(frozen=True)
class OllamaStatus:
    """Result of a lightweight Ollama availability check."""

    available: bool
    models: tuple[str, ...] = ()
    error: str | None = None


class _NoRedirectHandler(HTTPRedirectHandler):
    """Treat redirects as errors so Authorization never reaches another URL."""

    def redirect_request(self, _req, _fp, _code, _msg, _headers, _newurl):
        return None


def _urlopen_no_redirect(
    request: Request,
    *,
    timeout: float,
    context: ssl.SSLContext | None = None,
):
    handlers = [_NoRedirectHandler()]
    if context is not None:
        handlers.append(HTTPSHandler(context=context))
    return build_opener(*handlers).open(request, timeout=timeout)


def _ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not VERIFY_SSL:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def get_ollama_status(timeout: float = 2.0) -> OllamaStatus:
    """Return connection status and locally installed model names.

    Ollama exposes this information through ``GET /api/tags``.  The function
    deliberately uses the standard library so checking the sidebar does not
    add another runtime dependency.
    """

    timeout = _positive_float(timeout, 2.0)
    try:
        endpoint = f"{_validated_base_url()}/api/tags"
        headers = {"Accept": "application/json", **_authorization_headers()}
        request = Request(endpoint, headers=headers, method="GET")
        kwargs = {"timeout": timeout}
        if endpoint.lower().startswith("https://"):
            kwargs["context"] = _ssl_context()
        with _urlopen_no_redirect(request, **kwargs) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        ValueError,
        HTTPException,
        InvalidURL,
        json.JSONDecodeError,
    ) as exc:
        return OllamaStatus(available=False, error=str(exc))

    raw_models = payload.get("models", []) if isinstance(payload, dict) else []
    if not isinstance(raw_models, (list, tuple)):
        return OllamaStatus(
            available=False,
            error="Ollama zwróciła nieprawidłowy format listy modeli.",
        )
    models = sorted(
        {
            str(model.get("name") or model.get("model")).strip()
            for model in raw_models
            if isinstance(model, dict) and (model.get("name") or model.get("model"))
        }
    )
    return OllamaStatus(available=True, models=tuple(models))


def get_llm(model_name: str, temperature: float = 0.1, num_ctx: int = 8192):
    """
    Tworzy instancję modelu z odpowiednimi parametrami.

    Args:
        model_name: Nazwa modelu (np. "qwen2.5-coder:7b")
        temperature: 0.0 = deterministyczny, 1.0 = kreatywny
        num_ctx: Rozmiar okna kontekstowego (tokeny)

    Returns:
        ChatOllama instance
    """

    if not model_name or not model_name.strip():
        raise ValueError("Nazwa modelu Ollama nie może być pusta.")
    if num_ctx <= 0:
        raise ValueError("Rozmiar kontekstu musi być dodatni.")
    base_url = _validated_base_url()
    auth_headers = _authorization_headers()

    if num_ctx > 16384:
        print(f"⚠️ UWAGA: Duże okno kontekstowe ({num_ctx} tokenów). To może spowolnić generację.")

    if num_ctx >= 32000:
        recommended_models = ["qwen3-coder", "qwen2.5-coder", "llama3.3", "qwq"]
        if not any(rec in model_name for rec in recommended_models):
            print(f"💡 Dla {num_ctx} tokenów zalecane: {', '.join(recommended_models)}")

    return ChatOllama(
        model=model_name.strip(),
        base_url=base_url,
        temperature=temperature,
        num_ctx=num_ctx,
        client_kwargs={
            "verify": VERIFY_SSL,
            "timeout": OLLAMA_TIMEOUT,
            "headers": auth_headers,
        },
    )


def estimate_tokens(text: str) -> int:
    """
    Przybliżona estymacja liczby tokenów (1 token ≈ 4 znaki dla języków zachodnich).
    """
    return max(1, (len(text) + 3) // 4) if text else 0


def check_context_usage(text: str, num_ctx: int, warn_threshold: float = 0.8):
    """
    Sprawdza czy tekst nie przekracza limitu kontekstu.

    Args:
        text: Tekst do sprawdzenia
        num_ctx: Maksymalny rozmiar kontekstu
        warn_threshold: Próg ostrzeżenia (0.0-1.0)

    Returns:
        tuple: (estimated_tokens, is_safe, warning_message)
    """
    if num_ctx <= 0:
        raise ValueError("Rozmiar kontekstu musi być dodatni.")
    if not 0 < warn_threshold <= 1:
        raise ValueError("Próg ostrzeżenia musi należeć do przedziału (0, 1].")

    estimated = estimate_tokens(text)
    usage_ratio = estimated / num_ctx

    is_safe = usage_ratio < 1.0
    warning = None

    if usage_ratio >= 1.0:
        warning = f"🚨 PRZEKROCZONO LIMIT! {estimated} tokenów > {num_ctx} (kontekst)"
    elif usage_ratio >= warn_threshold:
        warning = (
            f"⚠️ Kontekst prawie pełny: {estimated}/{num_ctx} tokenów ({usage_ratio * 100:.1f}%)"
        )

    return estimated, is_safe, warning
