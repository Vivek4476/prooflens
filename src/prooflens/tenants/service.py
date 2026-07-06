"""Tenant resolution — scoring config, credentials, field mappings.

Every tenant may override any scoring field; overrides are deep-merged over the
ScoringConfig defaults so there are no per-tenant magic numbers scattered in the
service. Credentials are decrypted on demand and never logged.
"""

from __future__ import annotations

from ..db.crypto import decrypt
from ..db.models import Tenant
from ..engine.scoring_config import ScoringConfig


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def resolve_scoring(tenant: Tenant) -> ScoringConfig:
    """ScoringConfig with the tenant's overrides deep-merged over the defaults."""
    merged = _deep_merge(ScoringConfig().model_dump(), tenant.scoring_overrides or {})
    return ScoringConfig(**merged)


def get_by_slug(session, slug: str) -> Tenant | None:
    return session.query(Tenant).filter(Tenant.slug == slug, Tenant.active.is_(True)).one_or_none()


def lsq_credentials(tenant: Tenant) -> str | None:
    """Decrypt the tenant's LSQ credentials, or None if unset."""
    if not tenant.lsq_credentials_encrypted:
        return None
    return decrypt(tenant.lsq_credentials_encrypted)
