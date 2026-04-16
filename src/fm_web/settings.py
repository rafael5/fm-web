"""fm-web configuration — pydantic-settings, 12-factor env-driven."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Every field can be overridden by env var ``FM_WEB_<NAME>`` or by a
    ``.env`` file in the working directory.
    """

    model_config = SettingsConfigDict(
        env_prefix="FM_WEB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Session
    session_secret: str = Field(
        default="dev-only-change-me-in-production-9x3k7q",
        description="HMAC secret for signed session cookies",
    )
    session_max_age_seconds: int = Field(default=900)  # 15 min idle
    session_cookie_name: str = "fm_web_session"
    session_cookie_secure: bool = False  # set True behind TLS

    # Broker connection defaults — overridable per-site via sites.yaml.
    broker_host: str = "localhost"
    broker_port: int = 9430
    broker_uci: str = "VAH"
    broker_app_context: str = "OR CPRS GUI CHART"
    broker_timeout_seconds: float = 10.0

    # CORS — Vite dev server
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # Phase-2 frontmatter.db for doc-link service
    frontmatter_db: str | None = None


def get_settings() -> Settings:
    """FastAPI dependency. Caching deferred until profiling says otherwise."""
    return Settings()
