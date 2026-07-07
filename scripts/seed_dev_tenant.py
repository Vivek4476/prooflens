"""Seed one dev tenant. Idempotent — safe to re-run.

Requires a live database and `alembic upgrade head` first. Run:
    python scripts/seed_dev_tenant.py
"""

from __future__ import annotations

from prooflens.db import Tenant, session_scope
from prooflens.db.crypto import encrypt

DEV_SLUG = "dev"


def main() -> None:
    session = session_scope()
    try:
        existing = session.query(Tenant).filter(Tenant.slug == DEV_SLUG).one_or_none()
        if existing is not None:
            print(f"tenant {DEV_SLUG!r} already exists: {existing.id}")
            return

        tenant = Tenant(
            slug=DEV_SLUG,
            name="Aditya Birla Sun Life Insurance",
            webhook_secret="dev-webhook-secret-change-me",
            # Placeholder LSQ creds (encrypted at rest). Replace for real use.
            lsq_credentials_encrypted=encrypt("dev-lsq-access-key:dev-lsq-secret-key"),
            # LSQ custom-field ids for write-back — stub values (see README TODOs).
            field_map={
                "band": "mx_Custom_ProofLensBand",
                "score": "mx_Custom_ProofLensScore",
                "reason": "mx_Custom_ProofLensReason",
            },
            scoring_overrides={},
            vision_backend="stub",
        )
        session.add(tenant)
        session.commit()
        print(f"seeded tenant {DEV_SLUG!r}: {tenant.id}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
