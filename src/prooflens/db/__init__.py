"""Database layer — models, session wiring, Postgres hash store, crypto.

Import-safe without a live database (the engine is created lazily).
"""

from .base import Base, get_engine, get_sessionmaker, session_scope
from .hashstore import PostgresHashStore
from .models import AuditLog, ImageHash, Job, JobStatus, Result, Tenant

__all__ = [
    "Base",
    "get_engine",
    "get_sessionmaker",
    "session_scope",
    "Tenant",
    "Job",
    "JobStatus",
    "ImageHash",
    "Result",
    "AuditLog",
    "PostgresHashStore",
]
