"""require_tenant: bearer-key -> tenant, everything else -> 401."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from prooflens.api.auth import require_tenant
from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import generate_key, hash_key, key_prefix
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _repo_with_key() -> tuple[InMemoryRepo, str, str]:
    tenant = TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                        scoring=ScoringConfig(), vision_backend="stub")
    repo = InMemoryRepo([tenant])
    raw = generate_key()
    key_id = repo.record_api_key("t1", hash_key(raw), key_prefix(raw), "test")
    return repo, raw, key_id


def test_valid_bearer_resolves_tenant():
    repo, raw, _ = _repo_with_key()
    tenant = require_tenant(authorization=f"Bearer {raw}", repo=repo)
    assert tenant.id == "t1"


@pytest.mark.parametrize("header", [None, "", "Bearer ", "Token abc", "Bearer "])
def test_missing_or_malformed_header_401(header):
    repo, _, _ = _repo_with_key()
    with pytest.raises(HTTPException) as exc:
        require_tenant(authorization=header, repo=repo)
    assert exc.value.status_code == 401


def test_unknown_key_401():
    repo, _, _ = _repo_with_key()
    with pytest.raises(HTTPException) as exc:
        require_tenant(authorization=f"Bearer {generate_key()}", repo=repo)
    assert exc.value.status_code == 401


def test_revoked_key_401():
    repo, raw, key_id = _repo_with_key()
    repo.revoke_api_key(key_id)
    with pytest.raises(HTTPException) as exc:
        require_tenant(authorization=f"Bearer {raw}", repo=repo)
    assert exc.value.status_code == 401
