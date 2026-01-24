"""Application settings for Agentic Wealth Copilot.

This module centralises configuration for the backend.  It relies on
``pydantic-settings`` to read environment variables from a ``.env`` file
when present.  Providing a single source of configuration makes it
straightforward to override values during development, testing or
deployment.  See ``.env.example`` at the project root for sample
settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration values loaded from environment variables.

    All settings can be overridden via environment variables or a .env file.
    Variable names are case-insensitive and match the attribute names below.

    ``extra`` is set to ``ignore`` so that unknown environment
    variables won't raise validation errors.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ==========================================================================
    # Application Environment
    # ==========================================================================
    app_env: str = Field(default="dev", description="Runtime environment: dev, staging, prod")
    debug: bool = Field(default=False, description="Enable debug mode with verbose logging")
    log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")

    # ==========================================================================
    # Backend Server Configuration
    # ==========================================================================
    backend_host: str = Field(default="127.0.0.1", description="Host to bind the FastAPI server")
    backend_port: int = Field(default=8000, description="Port for the FastAPI server")
    api_prefix: str = Field(default="/api", description="API route prefix")

    # ==========================================================================
    # Frontend Configuration
    # ==========================================================================
    frontend_port: int = Field(default=8501, description="Port for the Streamlit frontend")

    # ==========================================================================
    # Data Storage Paths
    # ==========================================================================
    data_dir: str = Field(default="data", description="Base directory for all data storage")
    raw_data_dir: str = Field(default="data/raw", description="Directory for raw uploaded files")
    parsed_data_dir: str = Field(default="data/parsed", description="Directory for parsed JSON data")
    logs_dir: str = Field(default="data/logs", description="Directory for application logs")

    # ==========================================================================
    # Azure OpenAI Configuration
    # ==========================================================================
    azure_openai_endpoint: Optional[str] = Field(default=None, description="Azure OpenAI endpoint URL (e.g., https://xxx.openai.azure.com)")
    azure_openai_api_key: Optional[str] = Field(default=None, description="Azure OpenAI API key")
    azure_openai_api_version: str = Field(default="2024-08-01-preview", description="Azure OpenAI API version")
    azure_openai_deployment: str = Field(default="gpt-4o-mini", description="Azure OpenAI deployment name for chat/vision")
    azure_openai_embedding_deployment: str = Field(default="text-embedding-3-small", description="Azure OpenAI deployment name for embeddings")
    azure_openai_max_tokens: int = Field(default=2000, description="Max tokens for LLM responses")
    azure_openai_temperature: float = Field(default=0.1, description="Temperature for LLM responses (0-1)")

    # ==========================================================================
    # Azure Document Intelligence (for document parsing)
    # ==========================================================================
    azure_doc_intelligence_endpoint: Optional[str] = Field(
        default=None, description="Azure Document Intelligence endpoint URL"
    )
    azure_doc_intelligence_key: Optional[str] = Field(
        default=None, description="Azure Document Intelligence API key"
    )

    # ==========================================================================
    # SMTP Email (for stock price alerts)
    # ==========================================================================
    smtp_host: Optional[str] = Field(default=None, description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP login username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP login password")
    smtp_from: Optional[str] = Field(default=None, description="Sender address (defaults to smtp_user)")
    smtp_use_tls: bool = Field(default=True, description="Use STARTTLS for SMTP connection")

    # ==========================================================================
    # Rate Limiting / Performance
    # ==========================================================================
    max_upload_size_mb: int = Field(default=10, description="Maximum file upload size in MB")
    api_rate_limit: int = Field(default=100, description="API requests per minute limit")

    @property
    def cors_origins_list(self) -> list[str]:
        """Generate CORS origins from frontend_port."""
        return [
            f"http://localhost:{self.frontend_port}",
            f"http://127.0.0.1:{self.frontend_port}",
        ]

    @property
    def data_path(self) -> Path:
        """Return data directory as Path object."""
        return Path(self.data_dir)

    @property
    def raw_data_path(self) -> Path:
        """Return raw data directory as Path object."""
        return Path(self.raw_data_dir)

    @property
    def parsed_data_path(self) -> Path:
        """Return parsed data directory as Path object."""
        return Path(self.parsed_data_dir)


# Create a module‑level settings instance so other modules can import
# configured values without instantiating ``Settings`` themselves.
settings = Settings()
