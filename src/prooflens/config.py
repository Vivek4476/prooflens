"""Environment-driven settings (pydantic-settings).

Global/service configuration only. Per-tenant scoring policy (weights,
thresholds, caps, bands) lives in prooflens.engine.scoring_config and is
resolved per tenant by the service — not here.
"""

from __future__ import annotations

import functools

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .engine.scoring_config import ScoringConfig
from .vision import VisionBackend, get_backend

# A fixed, obviously-non-secret key so the app boots in dev without setup.
# Staging/prod MUST set PROOFLENS_SECRET_KEY (validated at startup elsewhere).
_DEV_SECRET_KEY = "dev-insecure-key-do-not-use-in-production-0000000000000000="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = Field(default="dev", alias="PROOFLENS_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Admin API bearer token (X-Admin-Token). Staging/prod MUST override.
    admin_token: str = Field(default="dev-admin-token", alias="PROOFLENS_ADMIN_TOKEN")

    database_url: str = Field(
        default="postgresql+psycopg://prooflens:prooflens@localhost:5432/prooflens",
        alias="DATABASE_URL",
    )
    secret_key: str = Field(default=_DEV_SECRET_KEY, alias="PROOFLENS_SECRET_KEY")

    # Vision backend (default stub = zero network / zero keys).
    vision_backend: str = Field(default="stub", alias="VISION_BACKEND")
    vision_max_edge: int = Field(default=768, alias="VISION_MAX_EDGE")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-haiku-4-5", alias="ANTHROPIC_MODEL")

    local_vlm_base_url: str = Field(
        default="http://localhost:11434/v1", alias="LOCAL_VLM_BASE_URL"
    )
    local_vlm_model: str = Field(default="qwen2-vl:7b", alias="LOCAL_VLM_MODEL")
    local_vlm_api_key: str = Field(default="not-needed", alias="LOCAL_VLM_API_KEY")

    # Queue / worker.
    queue_max_attempts: int = Field(default=5, alias="QUEUE_MAX_ATTEMPTS")
    queue_backoff_base_seconds: int = Field(default=5, alias="QUEUE_BACKOFF_BASE_SECONDS")
    queue_backoff_max_seconds: int = Field(default=900, alias="QUEUE_BACKOFF_MAX_SECONDS")
    worker_poll_interval_seconds: float = Field(default=2.0, alias="WORKER_POLL_INTERVAL_SECONDS")
    worker_batch_size: int = Field(default=5, alias="WORKER_BATCH_SIZE")

    @property
    def secret_key_is_dev(self) -> bool:
        return self.secret_key in ("", _DEV_SECRET_KEY)

    def build_vision_backend(self, name: str | None = None) -> VisionBackend:
        """Construct the configured vision backend. Defaults to the stub."""
        name = (name or self.vision_backend or "stub").strip().lower()
        return get_backend(
            name,
            api_key=(
                self.anthropic_api_key if name == "anthropic" else self.local_vlm_api_key
            ),
            model=(self.anthropic_model if name == "anthropic" else self.local_vlm_model),
            base_url=self.local_vlm_base_url,
            max_edge=self.vision_max_edge,
        )


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def default_scoring() -> ScoringConfig:
    """Sane per-tenant scoring defaults (tenants may override any field)."""
    return ScoringConfig()
