"""Telemetry — structured JSON logging with a job id carried end-to-end.

Prometheus /metrics (queue depth, per-check latency, vision-call failures, band
distribution per tenant) is wired at the API layer in Phase 3.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """JSON logs to stdout. Never logs image bytes or credentials."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), 20)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(job_id: str | None = None, **bind):
    """A logger bound with a job id (and any extra context) for end-to-end tracing."""
    log = structlog.get_logger()
    if job_id is not None:
        bind["job_id"] = job_id
    return log.bind(**bind) if bind else log


__all__ = ["configure_logging", "get_logger"]
