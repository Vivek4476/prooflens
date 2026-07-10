"""mint_key: creates a resolvable key for an existing tenant."""

from __future__ import annotations

import pytest

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import hash_key, mint_key
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _repo() -> InMemoryRepo:
    return InMemoryRepo([TenantView(id="t1", slug="dev", webhook_secret="s",
                                    field_map={}, scoring=ScoringConfig(), vision_backend="stub")])


def test_mint_key_returns_resolvable_key():
    repo = _repo()
    raw = mint_key(repo, "dev", "test-label")
    assert raw.startswith("pl_")
    assert repo.tenant_for_api_key(hash_key(raw)) is not None


def test_mint_key_unknown_tenant_raises():
    repo = _repo()
    with pytest.raises(ValueError, match="unknown tenant"):
        mint_key(repo, "ghost", "x")
