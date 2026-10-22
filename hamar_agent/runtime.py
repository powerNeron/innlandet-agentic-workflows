"""Composition only: connect JeppeGs's actual providers to the application."""
from dataclasses import replace
import json

from .application import WorkflowService
from .correction import OllamaCorrectionProvider
from .ollama_provider import OllamaClient, OllamaConfig, OllamaError, OllamaSummarizer, _local_post
from .summarize import MockSummarizer
from .workflow import run_workflow


CLAIM_RESPONSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"claims": {"type": "array", "minItems": 1, "maxItems": 8,
        "items": {"type": "object", "additionalProperties": False,
            "properties": {key: {"type": "string", "minLength": 1}
                           for key in ("id", "text", "paragraph_id", "evidence_quote")},
            "required": ["id", "text", "paragraph_id", "evidence_quote"]}}},
    "required": ["claims"],
}


def structured_transport(base_transport=_local_post):
    """Use the provider's Transport injection seam; no provider source rewrite.

    Delegate HTTP, bounds and errors to JeppeGs's existing local transport.
    Only request a stricter format for the already shared claim contract.
    """
    def post(url, headers, body, timeout, limit):
        payload = json.loads(body)
        payload["format"] = CLAIM_RESPONSE_SCHEMA
        return base_transport(url, headers, json.dumps(payload, ensure_ascii=False).encode("utf-8"), timeout, limit)
    return post


class OllamaApplicationService(WorkflowService):
    def __init__(self, client: OllamaClient, *, fallback_to_mock: bool = False):
        correction = OllamaCorrectionProvider(client)
        # Adapt the actual public revise API, not a guessed provider method.
        def correct(source, request):
            return correction.revise(source, request.prior_claims, request.findings)
        super().__init__(summarizer=OllamaSummarizer(client),
                         provider="ollama:" + client.config.model, corrector=correct)
        self.fallback_to_mock = fallback_to_mock

    def _execute(self, source):
        try:
            return run_workflow(source.id, self.summarizer, provider=self.provider,
                                loader=lambda _: source, corrector=self.corrector)
        except OllamaError:
            if not self.fallback_to_mock or not source.synthetic:
                raise
            result = run_workflow(source.id, MockSummarizer(),
                                  provider="mock:fallback-from-" + self.provider,
                                  loader=lambda _: source)
            return replace(result, warnings=result.warnings + (
                "Ollama failed. Explicit mock fallback used; this result is not real LLM output.",
            ))

    def run(self, source_id):
        return self._execute(self.load(source_id))

    def run_prepared(self, source):
        return self._execute(source)


def create_service(provider="mock", *, model=None, timeout=45.0,
                   fallback_to_mock=False, client=None):
    if provider == "mock":
        if fallback_to_mock:
            raise ValueError("Fallback is only meaningful with provider ollama")
        return WorkflowService()
    if provider == "openai":
        if fallback_to_mock:
            raise ValueError("Automatic provider fallback is not supported")
        from .openai_provider import OpenAIClaimSummarizer, OpenAICorrectionProvider, OpenAIClient, OpenAIConfig
        if client is None:
            config = OpenAIConfig.from_env()
            if model is not None and model != config.model:
                raise ValueError("OpenAI model must match the server-configured model")
            client = OpenAIClient(config)
        correction = OpenAICorrectionProvider(client)
        def correct(source, request):
            return correction.revise(source, request.prior_claims, request.findings)
        return WorkflowService(summarizer=OpenAIClaimSummarizer(client),
                               provider="openai:" + client.config.model, corrector=correct)
    if provider != "ollama":
        raise ValueError("Choose mock, ollama or openai")
    if client is None:
        selected = model if model is not None else OllamaConfig.from_env().model
        # Validate timeout/model configuration before any local availability probe.
        config = OllamaConfig(model=selected, timeout_seconds=timeout)
        from .provider_registry import require_installed_ollama_model
        require_installed_ollama_model(selected)
        client = OllamaClient(config, transport=structured_transport())
    return OllamaApplicationService(client, fallback_to_mock=fallback_to_mock)
