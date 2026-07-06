"""Worker process — drains the job queue and scores images.

``python -m prooflens.worker``. One pass claims a batch, runs the engine per job
and writes the verdict back to LSQ, then completes or reschedules the job. The
per-job logic lives in prooflens.service.processor and is storage-agnostic.

Fail-open: a job that errors is rescheduled with backoff (or dead-lettered after
its budget); an upload is never blocked and the worst case is a delayed score.
"""

from __future__ import annotations

import time

from .config import Settings, get_settings
from .lsq.base import LSQClient
from .lsq.fake import FakeLSQClient
from .service.processor import process_job
from .service.repo import Repo
from .telemetry import configure_logging, get_logger
from .telemetry.metrics import JOBS_PROCESSED, observe_verdict


def run_once(repo: Repo, lsq: LSQClient, settings: Settings) -> int:
    """Claim and process one batch. Returns the number of jobs processed OK."""
    jobs = repo.claim_batch(limit=settings.worker_batch_size)
    repo.commit()  # persist the claim so a crash doesn't silently lose the jobs

    processed = 0
    for job in jobs:
        jlog = get_logger(job_id=job.id, tenant_id=job.tenant_id, event_id=job.event_id)
        try:
            verdict = process_job(job, repo=repo, lsq=lsq, settings=settings)
            repo.complete(job.id)
            repo.commit()
            processed += 1
            observe_verdict(job.tenant_id, verdict)
            JOBS_PROCESSED.labels(outcome="done").inc()
            jlog.info("job.done", band=verdict.band, score=verdict.score,
                      reason_code=verdict.reason_code)
        except Exception as exc:  # noqa: BLE001 — fail-open, reschedule/DLQ
            repo.rollback()
            repo.fail(job.id, exc)
            repo.commit()
            JOBS_PROCESSED.labels(outcome="failed").inc()
            jlog.warning("job.failed", error=str(exc)[:300])
    return processed


def run_forever(repo_factory, lsq: LSQClient, settings: Settings) -> None:
    """Loop: drain, then idle-sleep when the queue is empty. `repo_factory()`
    yields a fresh Repo (and its own session/transaction) per pass."""
    log = get_logger()
    log.info("worker.start", batch_size=settings.worker_batch_size)
    while True:
        repo, close = repo_factory()
        try:
            n = run_once(repo, lsq, settings)
        finally:
            close()
        if n == 0:
            time.sleep(settings.worker_poll_interval_seconds)


def _postgres_repo_factory():
    from .db.base import session_scope
    from .db.repo import PostgresRepo

    session = session_scope()
    return PostgresRepo(session), session.close


def _default_lsq() -> LSQClient:
    # TODO(Phase 3): RealLSQClient. Until it exists, the worker uses the Fake
    # client so the pipeline runs end-to-end without a live LSQ.
    get_logger().warning("worker.lsq_fake", note="RealLSQClient is a Phase 3 TODO")
    return FakeLSQClient()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    run_forever(_postgres_repo_factory, _default_lsq(), settings)


if __name__ == "__main__":
    main()
