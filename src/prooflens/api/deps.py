"""Shared FastAPI dependencies.

``get_repo`` yields a Postgres-backed Repo committed per request. Tests override
it with an InMemoryRepo, so the whole HTTP surface is exercised offline.
"""

from __future__ import annotations

from collections.abc import Iterator

from ..service.repo import Repo


def get_repo() -> Iterator[Repo]:
    # Imported lazily so the API module is import-safe without psycopg, and so
    # tests (which override this dependency) never touch the database.
    from ..db.base import session_scope
    from ..db.repo import PostgresRepo

    session = session_scope()
    repo = PostgresRepo(session)
    try:
        yield repo
        repo.commit()
    except Exception:
        repo.rollback()
        raise
    finally:
        session.close()
