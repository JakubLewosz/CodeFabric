"""Minimalny test połączenia HTTP z Ollamą.

Skrypt jest celowo niezależny od aplikacji Streamlit. Sam import modułu nie
wykonuje żadnego żądania sieciowego.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Any
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def env_flag(name: str, *, default: bool) -> bool:
    """Odczytaj flagę logiczną ze zmiennej środowiskowej."""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} musi mieć wartość true albo false (otrzymano: {value!r})")


def env_positive_float(name: str, *, default: float) -> float:
    """Odczytaj dodatni, skończony limit czasu."""
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} musi być liczbą (otrzymano: {raw_value!r})") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} musi być dodatnią, skończoną liczbą")
    return value


def chat_endpoint(base_url: str) -> str:
    """Zbuduj endpoint czatu po sprawdzeniu adresu serwera."""
    normalized = base_url.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("OLLAMA_BASE_URL musi być pełnym adresem http:// lub https://")
    return f"{normalized}/api/chat"


def _extract_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    message = payload.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def main() -> int:
    """Wyślij jedno kontrolne zapytanie i zwróć kod procesu."""
    load_dotenv()

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
    model = os.getenv("MODEL_CODER", "qwen2.5-coder:7b").strip()
    token = os.getenv("OLLAMA_TOKEN", "").strip()

    try:
        endpoint = chat_endpoint(base_url)
        if not model:
            raise ValueError("MODEL_CODER nie może być pusty")
        verify_ssl = env_flag("VERIFY_SSL", default=True)
        timeout = env_positive_float("OLLAMA_TIMEOUT", default=120)
    except ValueError as exc:
        print(f"Błąd konfiguracji: {exc}", file=sys.stderr)
        return 2

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print("--- TEST POŁĄCZENIA Z OLLAMA ---")
    print(f"Cel: {base_url}")
    print(f"Model: {model}")
    print(f"Weryfikacja TLS: {'włączona' if verify_ssl else 'wyłączona'}")

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Napisz jedno krótkie zdanie."}],
                "stream": False,
            },
            timeout=timeout,
            verify=verify_ssl,
        )
        response.raise_for_status()
        content = _extract_content(response.json())
    except requests.JSONDecodeError as exc:
        print(f"Serwer zwrócił niepoprawny JSON: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Błąd połączenia: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Serwer zwrócił niepoprawny JSON: {exc}", file=sys.stderr)
        return 1

    if not content:
        print("Odpowiedź nie zawiera pola message.content.", file=sys.stderr)
        return 1

    print(f"\nOdpowiedź:\n{content}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
