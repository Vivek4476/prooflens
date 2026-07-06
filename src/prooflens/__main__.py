"""ProofLens CLI — ``python -m prooflens score <image>``.

Scores an image offline with the stub backend and an in-memory hash store, and
prints the full Verdict as JSON: verdict first, evidence second, internals last.
No network, no database, no keys required.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import default_scoring, get_settings
from .engine import EngineContext, InMemoryHashStore, score


def _score_command(args: argparse.Namespace) -> int:
    paths = [Path(p) for p in args.images]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        print(f"error: file(s) not found: {', '.join(missing)}", file=sys.stderr)
        return 2

    settings = get_settings()
    backend = settings.build_vision_backend(args.backend)
    store = InMemoryHashStore()  # process-local; near-duplicates within a run are caught

    results = []
    for path in paths:
        image_bytes = path.read_bytes()
        ctx = EngineContext(
            tenant_id=args.tenant,
            vision=backend,
            hash_store=store,
            scoring=default_scoring(),
            rep_id=args.rep,
            opportunity_id=args.opportunity,
        )
        verdict = score(image_bytes, ctx)
        payload = {"image": str(path), **verdict.to_dict()}
        results.append(payload)

    out = results[0] if len(results) == 1 else results
    print(json.dumps(out, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prooflens", description="ProofLens scoring CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sc = sub.add_parser("score", help="Score one or more images (offline, stub backend)")
    sc.add_argument("images", nargs="+", help="path(s) to image file(s)")
    sc.add_argument("--tenant", default="dev", help="tenant id (default: dev)")
    sc.add_argument("--rep", default=None, help="rep id for the uniqueness trail")
    sc.add_argument("--opportunity", default=None, help="opportunity/lead id for the trail")
    sc.add_argument(
        "--backend",
        default="stub",
        help=(
            "vision backend: stub (default, offline) | gemini | openrouter | "
            "nvidia | anthropic | local_vlm"
        ),
    )
    sc.set_defaults(func=_score_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
