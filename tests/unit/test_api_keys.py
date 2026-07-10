"""API-key hashing helpers + InMemoryRepo key storage/lookup."""

from __future__ import annotations

from prooflens.engine.scoring_config import ScoringConfig
from prooflens.service.api_keys import generate_key, hash_key, key_prefix
from prooflens.service.repo import InMemoryRepo
from prooflens.service.views import TenantView


def _tenant() -> TenantView:
    return TenantView(id="t1", slug="dev", webhook_secret="s", field_map={},
                      scoring=ScoringConfig(), vision_backend="stub")


def test_generate_key_is_prefixed_and_unique():
    a, b = generate_key(), generate_key()
    assert a.startswith("pl_") and b.startswith("pl_")
    assert a != b
    assert len(a) > 20


def test_hash_is_stable_hex_64_and_prefix_is_short():
    raw = "pl_example"
    assert hash_key(raw) == hash_key(raw)
    assert len(hash_key(raw)) == 64
    assert all(c in "0123456789abcdef" for c in hash_key(raw))
    assert key_prefix(raw) == "pl_example"[:12]


def test_record_and_resolve_api_key():
    repo = InMemoryRepo([_tenant()])
    raw = generate_key()
    repo.record_api_key("t1", hash_key(raw), key_prefix(raw), "test")
    resolved = repo.tenant_for_api_key(hash_key(raw))
    assert resolved is not None and resolved.id == "t1"
    # An unknown key resolves to nothing.
    assert repo.tenant_for_api_key(hash_key("pl_nope")) is None


def test_revoked_key_resolves_to_none():
    repo = InMemoryRepo([_tenant()])
    raw = generate_key()
    key_id = repo.record_api_key("t1", hash_key(raw), key_prefix(raw), "test")
    assert repo.tenant_for_api_key(hash_key(raw)) is not None
    repo.revoke_api_key(key_id)
    assert repo.tenant_for_api_key(hash_key(raw)) is None
