"""Shared FastAPI dependencies.

``get_repo`` yields a Postgres-backed Repo committed per request. Tests override
it with an InMemoryRepo, so the whole HTTP surface is exercised offline.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

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


def new_repo() -> tuple[Repo, Callable[[], None]]:
    """A fresh, caller-owned ``(repo, close)`` pair (its own session in
    production) — for background work (e.g. the bulk-scoring job) that
    outlives the request's ``get_repo`` dependency lifecycle and needs one
    Repo per unit of work, not one shared across concurrent tasks. Mirrors
    ``worker._postgres_repo_factory``. The caller commits/rolls back and MUST
    call ``close()`` when done with this repo (unlike ``get_repo``, which does
    this per request automatically).

    Tests override this the same way as ``get_repo`` — typically returning the
    SAME InMemoryRepo instance (with a no-op close) on every call, which is
    safe there because InMemoryRepo has no per-call session state.
    """
    from ..db.base import session_scope
    from ..db.repo import PostgresRepo

    session = session_scope()
    return PostgresRepo(session), session.close


def get_repo_factory() -> Callable[[], tuple[Repo, Callable[[], None]]]:
    """The FACTORY itself (not its result) — a FastAPI dependency so a route
    can hand it to a `BackgroundTasks` callback and have `app.dependency_overrides`
    apply (overriding a direct reference to ``new_repo`` would not, since
    background tasks call it well after the request's DI resolution).
    Defaults to ``new_repo``; tests override this to return a closure over
    their InMemoryRepo instance."""
    return new_repo
