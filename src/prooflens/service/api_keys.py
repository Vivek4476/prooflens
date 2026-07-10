"""API-key helpers: mint a raw key, hash it, and take a display prefix.

Raw keys are shown once at mint and never stored — only sha256(raw) is kept and
compared. Hash-equality on the digest is inherently constant-time."""

from __future__ import annotations

import hashlib
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repo import Repo

KEY_PREFIX = "pl_"
PREFIX_DISPLAY_LEN = 12  # chars of the raw key kept for display — never enough to reconstruct


def generate_key() -> str:
    """A fresh raw API key: 'pl_' + url-safe random. Shown once, never stored."""
    return KEY_PREFIX + secrets.token_urlsafe(30)


def hash_key(raw: str) -> str:
    """sha256 hex of the raw key — what we store and compare."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def key_prefix(raw: str) -> str:
    """First PREFIX_DISPLAY_LEN chars, for display/debugging only."""
    return raw[:PREFIX_DISPLAY_LEN]


def mint_key(repo: Repo, slug: str, label: str = "") -> str:
    """Create a key for an existing tenant and return the RAW key (shown once).
    Raises ValueError for an unknown tenant. The caller commits the repo."""
    tenant = repo.get_tenant_by_slug(slug)
    if tenant is None:
        raise ValueError(f"unknown tenant {slug!r}")
    raw = generate_key()
    repo.record_api_key(tenant.id, hash_key(raw), key_prefix(raw), label)
    return raw
