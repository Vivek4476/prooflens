"""Pytest fixtures. Fully offline: stub backend, in-memory hash store."""

from __future__ import annotations

import pytest

from prooflens.engine import InMemoryHashStore
from prooflens.vision import get_backend


@pytest.fixture
def stub_backend():
    return get_backend("stub")


@pytest.fixture
def hash_store():
    return InMemoryHashStore()
