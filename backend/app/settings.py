"""Application settings for Agentic Wealth Copilot.

This module centralises configuration for the backend.  It relies on
``pydantic-settings`` to read environment variables from a ``.env`` file
when present.  Providing a single source of configuration makes it
straightforward to override values during development, testing or
deployment.  See ``.env.example`` at the project root for sample
settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration values loaded from environment variables.

    Attributes:
        app_env: The runtime environment (e.g. ``dev`` or ``prod``).
        backend_host: Hostname on which the FastAPI backend should bind.
        backend_port: Port on which the FastAPI backend should listen.
        openai_api_key: Optional API key for the LLM provider.
        openai_model: Optional LLM model identifier.  Defaults to
            ``gpt-4o-mini``.

    ``extra`` is set to ``ignore`` so that unknown environment
    variables won't raise validation errors.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"


# Create a module‑level settings instance so other modules can import
# configured values without instantiating ``Settings`` themselves.
settings = Settings()
