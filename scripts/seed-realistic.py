#!/usr/bin/env python3
"""Seed a realistic, multi-thousand-row demo dataset (Analytics v4, Pain 3, Task 10).

Thin CLI wrapper around the pure logic in ``scripts/lib/seed_data.py`` (Task 9):
this script owns everything that logic deliberately does NOT — reading
``DATABASE_URL``, resolving the tenant, uploading the sample hierarchy, and
persisting each generated record via ``PostgresRepo.record_result(...,
source="seed")``.

It never calls the vision backend and needs no ``GROQ_API_KEY`` — every
verdict is drawn from the same score/band/reason vocabulary the real engine
uses (see ``scripts/lib/seed_data.py::sample_verdict``), not scored live.

NOT IDEMPOTENT. Unlike ``scripts/seed_dev_tenant.py``, re-running this adds
more rows on top of whatever is already there. The safe re-run path is
``--wipe-existing-seed``, which deletes only rows with ``source = 'seed'``
before seeding — it never touches ``direct`` or ``webhook`` rows. (A blunter
alternative for a throwaway dev DB: ``TRUNCATE results, hierarchy;`` yourself,
then re-run without the flag.)

Usage:
    export DATABASE_URL=postgresql+psycopg://prooflens:prooflens@localhost:5432/prooflens
    python scripts/seed-realistic.py --days 75

    # Preview without touching the database at all:
    python scripts/seed-realistic.py --dry-run --days 75

Requires the ``dev`` tenant to already exist (run ``scripts/seed_dev_tenant.py``
first) — this script resolves tenants, it does not create them.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))  # belt-and-suspenders vs. an editable install

from scripts.lib.seed_data import SeedRecord, generate_agent_pool, generate_seed_plan  # noqa: E402

if TYPE_CHECKING:
    from prooflens.service.repo import Repo

DEFAULT_TENANT_SLUG = "dev"  # matches scripts/seed_dev_tenant.py's DEV_SLUG
DEFAULT_HIERARCHY_CSV = Path(__file__).resolve().parent / "sample-hierarchy.csv"
RECORDS_PER_DAY_RANGE = (30, 90)
COMMIT_BATCH_SIZE = 500


def _brand_error(message: str) -> None:
    """Print a specific, forward-looking error (BRAND.md voice: no "oops",
    no drama) and exit non-zero."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Seed a realistic historical dataset (results + org hierarchy) so "
            "Analytics/History/By-Team have credible data immediately."
        )
    )
    parser.add_argument(
        "--days", type=int, default=75,
        help="Size of the seeded window in days, ending today (default: 75; spec range 60-90).",
    )
    parser.add_argument(
        "--tenant-slug", default=DEFAULT_TENANT_SLUG,
        help=f"Tenant to seed into (default: {DEFAULT_TENANT_SLUG!r}, must already exist).",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="RNG seed for a reproducible run (default: nondeterministic).",
    )
    parser.add_argument(
        "--hierarchy-csv", default=str(DEFAULT_HIERARCHY_CSV),
        help=f"Path to the sample hierarchy CSV (default: {DEFAULT_HIERARCHY_CSV}).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the planned record count + band/reason distribution. No writes, no DB.",
    )
    parser.add_argument(
        "--wipe-existing-seed", action="store_true",
        help="Before seeding, delete existing rows WHERE source='seed' only "
        "(never direct/webhook rows). The safe way to re-run this script.",
    )
    return parser


def _print_distribution(plan: list[SeedRecord]) -> None:
    bands = Counter(r.verdict.band for r in plan)
    reasons = Counter(r.verdict.reason_code for r in plan)
    total = len(plan)

    print(f"planned records: {total}")
    print("band distribution:")
    for band, count in sorted(bands.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * count / total if total else 0.0
        print(f"  {band:<10} {count:>6}  ({pct:5.1f}%)")
    print("reason distribution:")
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * count / total if total else 0.0
        print(f"  {reason:<28} {count:>6}  ({pct:5.1f}%)")


def _generate_plan(args: argparse.Namespace, today: date) -> list[SeedRecord]:
    agent_pool = generate_agent_pool(args.hierarchy_csv)
    rng = Random(args.seed) if args.seed is not None else Random()
    # Window MUST end today, or the dashboard's most-recent buckets render
    # empty and the demo looks stale — never rely on generate_seed_plan's
    # internal default anchor.
    start_day = today - timedelta(days=args.days - 1)
    return generate_seed_plan(
        args.days,
        RECORDS_PER_DAY_RANGE,
        agent_pool,
        rng,
        start_day=start_day,
    )


def _parse_hierarchy_csv(path: str) -> list[dict]:
    """Parse ``sample-hierarchy.csv`` into the exact row-dict shape
    ``hierarchy_admin.py``'s upload endpoint produces, so this script's
    hierarchy upload never drifts from the real upload contract."""
    from prooflens.api.hierarchy_admin import _parse_csv

    data = Path(path).read_bytes()
    return _parse_csv(data)


def _seed(args: argparse.Namespace, plan: list[SeedRecord]) -> None:
    from prooflens.db.base import session_scope
    from prooflens.db.models import Result
    from prooflens.db.repo import PostgresRepo

    session = session_scope()
    try:
        repo: Repo = PostgresRepo(session)
        tenant = repo.get_tenant_by_slug(args.tenant_slug)
        if tenant is None:
            _brand_error(
                f"tenant {args.tenant_slug!r} does not exist yet. Run "
                "`python scripts/seed_dev_tenant.py` first, then re-run this script."
            )
            return  # unreachable — _brand_error raises SystemExit

        if args.wipe_existing_seed:
            deleted = (
                session.query(Result)
                .filter(Result.tenant_id == tenant.id, Result.source == "seed")
                .delete(synchronize_session=False)
            )
            session.commit()
            print(f"wiped {deleted} existing source='seed' rows")

        rows = _parse_hierarchy_csv(args.hierarchy_csv)
        upload_id = uuid.uuid4().hex
        repo.replace_hierarchy(tenant.id, rows, upload_id)
        repo.commit()
        print(f"uploaded hierarchy: {len(rows)} rows (upload_id={upload_id})")

        total = len(plan)
        for i, record in enumerate(plan, start=1):
            repo.record_result(
                tenant.id,
                job_id=None,
                verdict=record.verdict,
                opportunity_id=record.opportunity_id,
                rep_id=record.rep_id,
                source="seed",
            )
            # record_result flushes but leaves created_at at its server
            # default (now()) — backdate it to the sampled historical
            # timestamp so the seeded window actually spans `--days` days
            # instead of every row landing on "today".
            session.query(Result).filter(
                Result.tenant_id == tenant.id,
                Result.opportunity_id == record.opportunity_id,
            ).update({Result.created_at: record.created_at}, synchronize_session=False)

            if i % COMMIT_BATCH_SIZE == 0:
                repo.commit()
                print(f"  ...{i}/{total} records committed")

        repo.commit()
        print(f"done: {total} records committed for tenant {args.tenant_slug!r}")
    finally:
        session.close()


def main(argv: list[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if not (60 <= args.days <= 90):
        print(
            f"warning: --days {args.days} is outside the recommended 60-90 range; "
            "continuing anyway.",
            file=sys.stderr,
        )

    today = datetime.now(UTC).date()

    if args.dry_run:
        plan = _generate_plan(args, today)
        _print_distribution(plan)
        return

    if not os.environ.get("DATABASE_URL"):
        _brand_error(
            "DATABASE_URL is not set. Export it before running this script, e.g.\n"
            "  export DATABASE_URL=postgresql+psycopg://prooflens:prooflens@localhost:5432/prooflens\n"
            "(--dry-run works without a database if you just want to preview the plan)."
        )
        return  # unreachable — _brand_error raises SystemExit

    plan = _generate_plan(args, today)
    print(f"generated {len(plan)} records for tenant {args.tenant_slug!r} over {args.days} days")
    _seed(args, plan)


if __name__ == "__main__":
    main()
