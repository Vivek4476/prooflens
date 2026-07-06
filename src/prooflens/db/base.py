"""SQLAlchemy engine/session wiring. Postgres does triple duty for ProofLens.

Import-safe without a database: the engine is created lazily on first use, so
the pure engine, CLI and offline tests never touch this module.
"""

from __future__ import annotations

import functools

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@functools.lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_engine(settings.sqlalchemy_url, pool_pre_ping=True, future=True)


@functools.lru_cache(maxsize=1)
def get_sessionmaker():
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def session_scope():
    """Return a new Session. Caller manages commit/rollback/close (or use `with`)."""
    return get_sessionmaker()()
