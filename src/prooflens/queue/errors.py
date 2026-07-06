"""Retry signalling for the worker.

The engine is fail-open: nothing here blocks an upload. These exceptions only
tell the queue HOW to reschedule a job.
"""

from __future__ import annotations


class JobError(Exception):
    """Base for job failures the queue understands."""


class RetryableError(JobError):
    """Transient failure — reschedule with backoff, counts against the budget.

    ``retry_after`` (seconds) honours an upstream 429 Retry-After header.
    """

    def __init__(self, message: str, *, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ProviderOverloaded(JobError):
    """Upstream is overloaded (e.g. HTTP 529). Back off, but DO NOT count this
    against the job's retry budget — it is not the job's fault."""

    def __init__(self, message: str, *, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class FatalError(JobError):
    """Permanent failure — dead-letter immediately, no retry."""
