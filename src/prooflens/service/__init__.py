"""Application layer — composes the pure engine with the queue, tenants and LSQ.

The API and worker depend on the :class:`Repo` seam (in-memory for tests,
Postgres in production), so the whole webhook -> queue -> worker -> write-back
flow is exercised offline while production uses the real Postgres queue.
"""

from .processor import process_job
from .repo import InMemoryRepo, Repo
from .views import JobView, TenantView

__all__ = ["Repo", "InMemoryRepo", "process_job", "TenantView", "JobView"]
