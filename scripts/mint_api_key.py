"""Mint a per-tenant API key. Prints the raw key ONCE — store it now.

Usage:
    python scripts/mint_api_key.py --tenant dev --label "dev dashboard"
"""

from __future__ import annotations

import argparse

from prooflens.service.api_keys import mint_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Mint a per-tenant API key.")
    parser.add_argument("--tenant", required=True, help="tenant slug (e.g. dev)")
    parser.add_argument("--label", default="", help="human label for the key")
    args = parser.parse_args()

    from prooflens.db.base import session_scope
    from prooflens.db.repo import PostgresRepo

    session = session_scope()
    repo = PostgresRepo(session)
    try:
        raw = mint_key(repo, args.tenant, args.label)
        repo.commit()
    finally:
        session.close()
    print(raw)


if __name__ == "__main__":
    main()
