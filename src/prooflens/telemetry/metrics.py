"""Prometheus metrics — the cheap drift detector.

Exposes: queue depth, per-check latency, vision-call failures, and band
distribution per tenant (a sudden shift in the band mix is the first sign of a
model/rubric regression or an upstream capture change).
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

QUEUE_DEPTH = Gauge("prooflens_queue_depth", "Jobs waiting to be processed")

CHECK_LATENCY = Histogram(
    "prooflens_check_latency_ms",
    "Per-check wall-clock latency (ms)",
    labelnames=["check"],
    buckets=(1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)

VISION_FAILURES = Counter(
    "prooflens_vision_call_failures_total",
    "Vision backend calls that failed and were scored without content analysis",
    labelnames=["backend"],
)

BAND_TOTAL = Counter(
    "prooflens_band_total",
    "Verdict band distribution per tenant",
    labelnames=["tenant", "band"],
)

JOBS_PROCESSED = Counter(
    "prooflens_jobs_processed_total",
    "Jobs processed by the worker",
    labelnames=["outcome"],  # done | failed
)


def observe_verdict(tenant: str, verdict) -> None:
    """Record metrics for one scored image."""
    BAND_TOTAL.labels(tenant=tenant, band=verdict.band).inc()
    for check in verdict.checks:
        if check.latency_ms is not None:
            CHECK_LATENCY.labels(check=check.name).observe(check.latency_ms)
        if check.name == "content" and not check.available and check.data.get("error"):
            VISION_FAILURES.labels(backend=str(check.data.get("backend", "unknown"))).inc()


def render() -> tuple[bytes, str]:
    """(body, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
