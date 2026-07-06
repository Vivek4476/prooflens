"""Postgres job queue — drained with SELECT ... FOR UPDATE SKIP LOCKED.

State machine: queued -> in_progress -> done | failed(->queued) | dead_letter.
Idempotency is enforced by a unique (tenant_id, event_id) constraint: enqueuing
a duplicate event is a no-op that returns the existing job.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from ..config import get_settings
from ..db.models import Job, JobStatus
from .backoff import backoff_seconds
from .errors import FatalError, ProviderOverloaded, RetryableError


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(session, *, tenant_id: uuid.UUID, event_id: str, payload: dict) -> Job:
    """Insert a job, or return the existing one for a duplicate event (idempotent)."""
    existing = (
        session.query(Job)
        .filter(Job.tenant_id == tenant_id, Job.event_id == event_id)
        .one_or_none()
    )
    if existing is not None:
        return existing

    settings = get_settings()
    job = Job(
        tenant_id=tenant_id,
        event_id=event_id,
        payload=payload,
        status=JobStatus.QUEUED,
        max_attempts=settings.queue_max_attempts,
        scheduled_at=_now(),
    )
    session.add(job)
    session.flush()
    return job


def claim_batch(session, *, limit: int) -> list[Job]:
    """Atomically claim up to `limit` due jobs. Concurrent workers skip locked rows."""
    rows = session.execute(
        text(
            """
            SELECT id FROM jobs
            WHERE status IN ('queued', 'failed')
              AND scheduled_at <= now()
            ORDER BY scheduled_at
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).all()
    ids = [r[0] for r in rows]
    if not ids:
        return []

    jobs = session.query(Job).filter(Job.id.in_(ids)).all()
    for job in jobs:
        job.status = JobStatus.IN_PROGRESS
        job.locked_at = _now()
        job.attempts += 1
    session.flush()
    return jobs


def complete(session, job: Job) -> None:
    job.status = JobStatus.DONE
    job.locked_at = None
    job.last_error = None
    session.flush()


def fail(session, job: Job, error: Exception) -> None:
    """Reschedule (with backoff) or dead-letter, per the error type and budget."""
    settings = get_settings()
    job.last_error = str(error)[:2000]

    if isinstance(error, FatalError):
        job.status = JobStatus.DEAD_LETTER
        job.locked_at = None
        session.flush()
        return

    if isinstance(error, ProviderOverloaded):
        # Not the job's fault: refund the attempt so 529s don't burn the budget.
        job.attempts = max(0, job.attempts - 1)
        retry_after = error.retry_after
    elif isinstance(error, RetryableError):
        retry_after = error.retry_after
    else:
        retry_after = None

    if job.attempts >= job.max_attempts:
        job.status = JobStatus.DEAD_LETTER
        job.locked_at = None
        session.flush()
        return

    delay = backoff_seconds(
        job.attempts,
        base=settings.queue_backoff_base_seconds,
        maximum=settings.queue_backoff_max_seconds,
        retry_after=retry_after,
    )
    job.status = JobStatus.QUEUED
    job.locked_at = None
    job.scheduled_at = _now() + timedelta(seconds=delay)
    session.flush()


def depth(session) -> int:
    """Number of jobs waiting to run (for the queue-depth metric)."""
    return (
        session.query(Job)
        .filter(Job.status.in_([JobStatus.QUEUED, JobStatus.FAILED]))
        .count()
    )
