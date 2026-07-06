#!/bin/sh
# API entrypoint for container platforms (Render, etc.):
# apply migrations, seed a dev tenant, then serve on the platform's $PORT.
#
# Kept as a script (not an inline dockerCommand) so the start command stays a
# simple, quote-free "sh scripts/start-api.sh" — some platforms don't run the
# command through a shell, so && / quotes / $PORT in the command itself break.
set -e

alembic upgrade head
python scripts/seed_dev_tenant.py || true

# $PORT is injected by the platform (defaults to 8000 for local use). exec so
# uvicorn becomes PID 1 and receives signals directly.
exec uvicorn prooflens.api.app:app --host 0.0.0.0 --port "${PORT:-8000}"
