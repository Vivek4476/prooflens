"""ProofLens demo — FastAPI app.

Serves the single-page UI at `/` and exposes `POST /score`, which accepts an
uploaded image and returns the fused score, band, per-check breakdown, and the
raw vision verdict.

Run:
    uvicorn app:app --reload
    # then open http://localhost:8000
"""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

# Load .env if python-dotenv is available (optional convenience).
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from config import VISION_BACKEND
from checks import sharpness, uniqueness, person, metadata
from checks import relevance
from vision import get_backend
import fusion
import store

app = FastAPI(title="ProofLens demo", version="1.0.0")

HERE = os.path.dirname(__file__)
INDEX_HTML = os.path.join(HERE, "static", "index.html")

MAX_BYTES = 12 * 1024 * 1024  # 12 MB upload cap


@app.on_event("startup")
def _startup() -> None:
    store.init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_HTML)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "vision_backend": VISION_BACKEND,
        "hashes_stored": store.count(),
    }


@app.post("/score")
async def score(image: UploadFile = File(...)) -> JSONResponse:
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 12 MB).")

    # Deterministic checks (real, server-side).
    sharp_res = sharpness.run(data)
    uniq_res = uniqueness.run(data)
    person_res = person.run(data)
    meta_res = metadata.run(data)

    # The star: real (or stubbed) vision judgement.
    backend = get_backend()
    content_res, verdict = relevance.assess(data, backend=backend)

    checks = [content_res, sharp_res, person_res, uniq_res, meta_res]
    fused = fusion.fuse(checks, verdict)

    payload = {
        "score": fused.score,
        "band": fused.band,
        "gates_fired": fused.gates_fired,
        "vision_backend": backend.name,
        "vision_is_real": backend.is_real,
        "checks": [c.to_dict() for c in checks],
        "vision": verdict,
    }
    return JSONResponse(payload)
