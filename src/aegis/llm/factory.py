"""Factory: pick an LLM backend based on configuration."""

from __future__ import annotations

from aegis.llm.base import LLMProvider
from aegis.utils.config import Settings, get_settings
from aegis.utils.logging import get_logger

log = get_logger(__name__)


def build_llm(settings: Settings | None = None) -> LLMProvider:
    """Construct the configured LLM provider.

    Reads ``settings.llm_backend`` and returns either an Ollama or Claude
    provider. Importing the Claude module is deferred so users who never
    touch Claude don't need the ``anthropic`` package installed.
    """
    settings = settings or get_settings()
    backend = settings.llm_backend.lower().strip()

    if backend == "ollama":
        from aegis.llm.ollama_provider import OllamaProvider

        provider: LLMProvider = OllamaProvider(
            model=settings.ollama_model, host=settings.ollama_host
        )
    elif backend == "claude":
        from aegis.llm.claude_provider import ClaudeProvider

        provider = ClaudeProvider(
            api_key=settings.anthropic_api_key, model=settings.claude_model
        )
    else:
        raise ValueError(
            f"Unknown AEGIS_LLM_BACKEND={backend!r}. Use 'ollama' or 'claude'."
        )

    log.info("LLM backend: %s", provider.name)
    return provider
