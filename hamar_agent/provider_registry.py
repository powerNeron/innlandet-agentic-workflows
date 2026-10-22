"""Server-side allowlist and availability checks for selectable AI providers."""
from __future__ import annotations

import importlib.util
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .ollama_provider import OllamaConfig

_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
_TAGS_LIMIT = 64 * 1024


def configured_ollama_models() -> tuple[str, ...]:
    """Return the exact server-approved model names; never pull a model."""
    default = os.environ.get("HAMAR_OLLAMA_MODEL", "llama3.2:3b")
    raw = os.environ.get("HAMAR_OLLAMA_ALLOWED_MODELS", "")
    values = [default, *(part.strip() for part in raw.split(",") if part.strip())]
    if any(not isinstance(value, str) or not _MODEL_RE.fullmatch(value) for value in values):
        raise ValueError("Invalid server-side Ollama model allowlist")
    return tuple(dict.fromkeys(values))


def installed_ollama_models(*, base_url: str = "http://127.0.0.1:11434", timeout: float = 1.5) -> tuple[str, ...]:
    """List local Ollama tags with redirects and proxy use disabled."""
    config = OllamaConfig(base_url=base_url)

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(config.base_url.rstrip("/") + "/api/tags", headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(_TAGS_LIMIT + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        return ()
    if len(raw) > _TAGS_LIMIT:
        return ()
    try:
        payload = json.loads(raw.decode("utf-8"))
        models = payload["models"]
        if not isinstance(models, list):
            return ()
        names = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and _MODEL_RE.fullmatch(name):
                names.append(name)
        return tuple(dict.fromkeys(names))
    except (UnicodeError, ValueError, TypeError, KeyError):
        return ()


def require_installed_ollama_model(model: str) -> None:
    if model not in configured_ollama_models():
        raise ValueError("Ollama model is not in the server-side allowlist")
    if model not in installed_ollama_models():
        raise ValueError("Ollama model is not installed or the local server is unavailable")


class ProviderRegistry:
    """Reflect actual local availability, while keeping the allowlist server-side."""

    def __init__(self, *, ollama_models=None, openai_config_factory=None, sdk_available=None,
                 include_mock=False):
        self._ollama_models = ollama_models or installed_ollama_models
        if openai_config_factory is None:
            from .openai_provider import OpenAIConfig
            openai_config_factory = OpenAIConfig.from_env
        self._openai_config_factory = openai_config_factory
        self._sdk_available = sdk_available or (lambda: importlib.util.find_spec("openai") is not None)
        self.include_mock = include_mock

    def choices(self) -> list[dict[str, object]]:
        allowed = configured_ollama_models()
        installed = set(self._ollama_models())
        choices = [{"provider": "ollama", "model": model, "label": f"Ollama · {model}",
                    "processing": "local", "available": model in installed,
                    "reason": "" if model in installed else "Modellen er ikke installert lokalt."}
                   for model in allowed]
        if self.include_mock:
            choices.append({"provider": "mock", "model": "mock", "label": "Syntetisk demo · mock",
                            "processing": "local", "available": True,
                            "reason": "Mock-svar er syntetiske og ikke en ekte språkmodell."})
        config = self._openai_config_factory()
        authorized = config.enabled and config.privacy_authorized and bool(config.api_key) and bool(config.model)
        sdk_available = bool(self._sdk_available())
        ready = authorized and sdk_available
        reason = ""
        if not config.enabled:
            reason = "Ekstern behandling er deaktivert på serveren."
        elif not config.privacy_authorized:
            reason = "Eksplisitt personverngodkjenning mangler på serveren."
        elif not config.api_key:
            reason = "OPENAI_API_KEY mangler i servermiljøet."
        elif not config.model:
            reason = "HAMAR_OPENAI_MODEL mangler i servermiljøet."
        elif not sdk_available:
            reason = "OpenAI Python SDK er ikke installert."
        choices.append({"provider": "openai", "model": config.model, "label": f"OpenAI · {config.model or 'ikke konfigurert'}",
                        "processing": "external", "available": ready, "reason": reason})
        return choices

    def require_choice(self, provider: str, model: str) -> dict[str, object]:
        if not isinstance(provider, str) or not isinstance(model, str):
            raise ValueError("Choose an available provider and model")
        choice = next((item for item in self.choices()
                       if item["provider"] == provider and item["model"] == model), None)
        if choice is None or not choice["available"]:
            raise ValueError("Selected provider or model is unavailable")
        return choice
