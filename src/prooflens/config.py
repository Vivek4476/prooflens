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

    # NVIDIA-hosted VLMs (free tier at build.nvidia.com; key looks like nvapi-...).
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field(
        default="meta/llama-3.2-90b-vision-instruct", alias="NVIDIA_MODEL"
    )
    nvidia_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_BASE_URL"
    )

    # Google Gemini via AI Studio (free tier; just a Google account, no card).
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai",
        alias="GEMINI_BASE_URL",
    )

    # OpenRouter (free ":free" vision models; email signup, no card).
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(
        default="nvidia/nemotron-nano-12b-v2-vl:free", alias="OPENROUTER_MODEL"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )

    # Queue / worker.
    queue_max_attempts: int = Field(default=5, alias="QUEUE_MAX_ATTEMPTS")
    queue_backoff_base_seconds: int = Field(default=5, alias="QUEUE_BACKOFF_BASE_SECONDS")
    queue_backoff_max_seconds: int = Field(default=900, alias="QUEUE_BACKOFF_MAX_SECONDS")
    worker_poll_interval_seconds: float = Field(default=2.0, alias="WORKER_POLL_INTERVAL_SECONDS")
    worker_batch_size: int = Field(default=5, alias="WORKER_BATCH_SIZE")
    # The worker exposes its own Prometheus endpoint (its counters live in its
    # own process, separate from the API's). 0 disables it.
    worker_metrics_port: int = Field(default=9100, alias="WORKER_METRICS_PORT")

    @property
    def secret_key_is_dev(self) -> bool:
        return self.secret_key in ("", _DEV_SECRET_KEY)

    def build_vision_backend(self, name: str | None = None) -> VisionBackend:
        """Construct the configured vision backend. Defaults to the stub."""
        name = (name or self.vision_backend or "stub").strip().lower()
        per_backend = {
            "stub": {},
            "anthropic": {"api_key": self.anthropic_api_key, "model": self.anthropic_model},
            "local_vlm": {
                "api_key": self.local_vlm_api_key,
                "model": self.local_vlm_model,
                "base_url": self.local_vlm_base_url,
            },
            "nvidia": {
                "api_key": self.nvidia_api_key,
                "model": self.nvidia_model,
                "base_url": self.nvidia_base_url,
            },
            "gemini": {
                "api_key": self.gemini_api_key,
                "model": self.gemini_model,
                "base_url": self.gemini_base_url,
            },
            "openrouter": {
                "api_key": self.openrouter_api_key,
                "model": self.openrouter_model,
                "base_url": self.openrouter_base_url,
            },
        }
        kwargs = per_backend.get(name, {})
        return get_backend(name, max_edge=self.vision_max_edge, **kwargs)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def default_scoring() -> ScoringConfig:
    """Sane per-tenant scoring defaults (tenants may override any field)."""
    return ScoringConfig()
