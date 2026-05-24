"""Central, typed configuration for AEGIS.

Settings are read from environment variables (and a local ``.env`` file).
Everything has a sensible default so the project runs out of the box with
Ollama, requiring zero secrets.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Field names map to ``AEGIS_<UPPERCASE>`` env vars."""

    model_config = SettingsConfigDict(
        env_prefix="AEGIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM backend selection ---
    llm_backend: str = Field(default="ollama", description="'ollama' or 'claude'")

    # Ollama
    ollama_model: str = "llama3.1"
    ollama_host: str = "http://localhost:11434"

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Scraping
    user_agent: str = "AegisBot/0.1 (+https://github.com/yourname/aegis)"
    request_delay_seconds: float = 1.0
    max_concurrency: int = 4
    respect_robots: bool = True

    # Storage
    output_dir: Path = Path("data/output")

    def ensure_dirs(self) -> None:
        """Create directories the app expects to exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings
