"""Server-side allowlist and availability checks for selectable AI providers."""
from __future__ import annotations

import importlib.util
import json
import os
from types import SimpleNamespace
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .ollama_provider import OllamaConfig

_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
_TAGS_LIMIT = 64 * 1024


class ProviderSelectionError(ValueError):
    """A request selected an option outside the server's selectable choices."""

    code = "provider_selection_invalid"


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


def _openai_option_config():
    """Inspect public settings and credential presence, never its value or an SDK client."""
    from .openai_provider import OpenAIConfig, _flag
    config = OpenAIConfig(model=os.environ.get('HAMAR_OPENAI_MODEL', '').strip(),
        enabled=_flag('HAMAR_OPENAI_ENABLED'), privacy_authorized=_flag('HAMAR_OPENAI_PRIVACY_AUTHORIZED'),
        timeout_seconds=float(os.environ.get('HAMAR_OPENAI_TIMEOUT', '20')),
        max_output_tokens=int(os.environ.get('HAMAR_OPENAI_MAX_OUTPUT_TOKENS', '512')))
    if config.model and (not _MODEL_RE.fullmatch(config.model) or config.model.startswith('sk-')):
        raise ValueError('Invalid public model setting')
    return SimpleNamespace(model=config.model, enabled=config.enabled,
        privacy_authorized=config.privacy_authorized, key_present='OPENAI_API_KEY' in os.environ)


class ProviderRegistry:
    """Keep selection server-side; readiness never asserts successful inference.

    available retains its selectable-option meaning for existing clients.
    availability_status states what was actually checked, without cloud probes.
    """

    def __init__(self, *, ollama_models=None, openai_config_factory=None, sdk_available=None,
                 include_mock=False):
        self._ollama_models = ollama_models or installed_ollama_models
        if openai_config_factory is None:
            openai_config_factory = _openai_option_config
        self._openai_config_factory = openai_config_factory
        self._sdk_available = sdk_available or (lambda: importlib.util.find_spec("openai") is not None)
        self.include_mock = include_mock

    def choices(self, *, provider: str | None = None) -> list[dict[str, object]]:
        if provider not in (None, "ollama", "openai", "mock"):
            raise ProviderSelectionError("Unknown provider")
        choices = []
        if provider in (None, "ollama"):
            try:
                allowed = configured_ollama_models()
            except (ValueError, TypeError):
                choices.append({"provider": "ollama", "model": "", "label": "Ollama · oppsett må kontrolleres",
                    "processing": "local", "available": False, "availability_status": "configuration_error",
                    "connection_status": "not_verified", "generation_verified": False,
                    "reason": "Ollama-oppsettet på serveren må kontrolleres. Andre konfigurerte modeller kan fortsatt velges."})
            else:
                try:
                    installed = set(self._ollama_models())
                except (OSError, RuntimeError, ValueError, TypeError):
                    installed = set()
                choices.extend({"provider": "ollama", "model": model, "label": f"Ollama · {model}",
                    "processing": "local", "available": model in installed,
                    "availability_status": "installed" if model in installed else "unavailable",
                    "connection_status": "local_catalog_verified" if model in installed else "not_verified",
                    "generation_verified": False,
                    "reason": "Modellen finnes i den lokale modellkatalogen. Generering er ikke testet." if model in installed else "Ollama er utilgjengelig, eller modellen er ikke installert lokalt."}
                    for model in allowed)
        if self.include_mock and provider in (None, "mock"):
            choices.append({"provider": "mock", "model": "mock", "label": "Syntetisk demo · mock",
                            "processing": "local", "available": True,
                            "availability_status": "synthetic", "connection_status": "not_applicable",
                            "generation_verified": False,
                            "reason": "Mock-svar er syntetiske og ikke en ekte språkmodell."})
        if provider not in (None, "openai"):
            return choices
        try:
            config = self._openai_config_factory()
            sdk_available = bool(self._sdk_available())
        except (ValueError, TypeError, RuntimeError, ImportError):
            choices.append({"provider": "openai", "model": "", "label": "OpenAI · oppsett må kontrolleres",
                            "processing": "external", "available": False,
                            "availability_status": "configuration_error", "connection_status": "not_checked",
                            "generation_verified": False, "reason": "OpenAI-oppsettet på serveren må kontrolleres. Lokalt søk kan fortsatt brukes."})
            return choices
        key_present = config.key_present if hasattr(config, 'key_present') else bool(config.api_key)  # Injected test configurations.
        authorized = config.enabled and config.privacy_authorized and key_present and bool(config.model)
        ready = authorized and sdk_available
        reason = ""
        if not config.enabled:
            reason = "OpenAI er deaktivert av eier. Betalt bruk krever eierens godkjenning. Lokal AI kan fortsatt brukes."
        elif not config.privacy_authorized:
            reason = "Eksplisitt personverngodkjenning mangler på serveren."
        elif not key_present:
            reason = "OpenAI-tilgang er ikke konfigurert på serveren."
        elif not config.model:
            reason = "Ingen OpenAI-modell er valgt på serveren."
        elif not sdk_available:
            reason = "Serverens OpenAI-støtte er ikke installert."
        else:
            reason = "OpenAI er konfigurert. Tilkobling og tilgang er ikke testet; de kontrolleres når du sender et spørsmål."
        choices.append({"provider": "openai", "model": config.model, "label": f"OpenAI · {config.model or 'ikke konfigurert'}",
                        "processing": "external", "available": ready,
                        "availability_status": "configured" if ready else "paused" if not config.enabled else "setup_required",
                        "connection_status": "not_checked", "generation_verified": False, "reason": reason})
        return choices

    def require_choice(self, provider: str, model: str) -> dict[str, object]:
        if not isinstance(provider, str) or not isinstance(model, str):
            raise ProviderSelectionError("Choose an available provider and model")
        choice = next((item for item in self.choices(provider=provider)
                       if item["provider"] == provider and item["model"] == model), None)
        if choice is None or not choice["available"]:
            raise ProviderSelectionError("Selected provider or model is unavailable")
        return choice
