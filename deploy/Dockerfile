# ProofLens — one image, two processes (api / worker) selected by the command.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# opencv-python-headless needs libglib2.0-0 at runtime; libgomp1 for its threads.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (better layer caching), then the source.
COPY pyproject.toml README.md ./
COPY src ./src
COPY rubrics ./rubrics
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts

# Service extra only — NEVER the vision extra (no anthropic/openai in the image).
RUN pip install --no-cache-dir -e ".[service]"

# Drop root.
RUN useradd -m prooflens
USER prooflens

EXPOSE 8000

# Default to the API; the worker service overrides the command.
CMD ["uvicorn", "prooflens.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
