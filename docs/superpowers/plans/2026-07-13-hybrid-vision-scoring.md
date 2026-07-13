# Hybrid Two-Model Vision Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-stage vision backend — Scout (perception) on Cloudflare + gpt-oss-120b (reasoning) on Cloudflare — that returns the same `ContentAssessment`, and make it the default vision path.

**Architecture:** A new `HybridBackend` composes the existing `OpenAICompatBackend` (Stage 1, image) with a new text-only `Reasoner` (Stage 2). Both hit Cloudflare's OpenAI-compatible endpoint through a shared HTTP helper. It implements the existing `VisionBackend` Protocol, so fusion/scoring/DB/webhook are untouched. Fail-open: Stage-2 failure keeps Scout's own judgment; Stage-1 failure raises `VisionUnavailable` (existing Unassessed path).

**Tech Stack:** Python 3.14, pydantic, urllib (stdlib only — no SDK), pytest, YAML rubric files.

## Global Constraints

- Stdlib-only HTTP (no `openai`/`requests` SDK) — match existing `openai_compat.py`.
- Both stages run at `temperature = 0.0` (reproducibility: same photo → same verdict).
- Vision model default: `@cf/meta/llama-4-scout-17b-16e-instruct`. Reasoner default: `@cf/openai/gpt-oss-120b`.
- Cloudflare base URL: `https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1`.
- The hybrid returns an unchanged `ContentAssessment`; no change to fusion, scoring config, verdict bands, analytics, DB schema, or webhook.
- `HybridBackend.is_real = True`; `name = "hybrid"`; provenance `model = "{vision_model}+{reasoner_model}"`.
- Unit tests never hit the network (monkeypatch `urllib.request.urlopen`). One live smoke test is env-guarded and skipped by default.
- Reasoner never receives the image — only Scout's perceptual fields as JSON.

---

### Task 1: Extract a shared HTTP helper and refactor `OpenAICompatBackend` onto it

**Files:**
- Create: `src/prooflens/vision/_http.py`
- Modify: `src/prooflens/vision/openai_compat.py`
- Test: `tests/unit/test_vision_http.py` (new), `tests/unit/test_vision_backend.py` (must stay green)

**Interfaces:**
- Produces: `VisionUnavailable(message: str, *, status: int | None = None)` (moved here; re-exported from `openai_compat`), and `post_chat(*, invoke_url: str, api_key: str, payload: dict, timeout: float, name: str, model: str) -> tuple[dict, str | None]` returning `(parsed_json, request_id)`, raising `VisionUnavailable` on HTTP/transport error.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_vision_http.py
"""Shared chat-completions POST helper: happy path + error mapping."""
from __future__ import annotations

import json
import urllib.error

import pytest

from prooflens.vision import _http
from prooflens.vision._http import VisionUnavailable, post_chat


class _FakeResp:
    headers = {"cf-ray": "ray-123"}

    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def test_post_chat_returns_data_and_request_id(monkeypatch):
    def fake_urlopen(req, timeout):
        assert json.loads(req.data)["model"] == "m"
        return _FakeResp({"id": "gen-1", "choices": []})

    monkeypatch.setattr(_http.urllib.request, "urlopen", fake_urlopen)
    data, request_id = post_chat(
        invoke_url="https://x/chat/completions", api_key="k",
        payload={"model": "m"}, timeout=5.0, name="scout", model="m",
    )
    assert data["id"] == "gen-1"
    assert request_id == "ray-123"


def test_post_chat_maps_http_error_to_vision_unavailable(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(_http.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(VisionUnavailable) as ei:
        post_chat(invoke_url="https://x/chat/completions", api_key="k",
                  payload={}, timeout=5.0, name="scout", model="m")
    assert ei.value.status == 429
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_vision_http.py -v`
Expected: FAIL with `ImportError: cannot import name 'post_chat'`.

- [ ] **Step 3: Create the helper**

```python
# src/prooflens/vision/_http.py
"""Shared OpenAI-compatible /chat/completions POST (stdlib only).

Used by every hosted backend (Scout, reasoner, Groq, ...) so HTTP + error
semantics are identical: bot-safe User-Agent, HTTP status carried on
VisionUnavailable, transport errors mapped to the same exception.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger("prooflens.vision")


class VisionUnavailable(RuntimeError):
    """The vision provider could not be reached or returned an error.

    Carries the exact reason (HTTP status or transport failure) so the API can
    surface it instead of a generic message.
    """

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def post_chat(
    *, invoke_url: str, api_key: str, payload: dict, timeout: float, name: str, model: str
) -> tuple[dict, str | None]:
    """POST a chat-completions payload; return (parsed_json, request_id).

    Raises VisionUnavailable on any HTTP or transport failure.
    """
    req = urllib.request.Request(
        invoke_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Some providers sit behind Cloudflare and 403 the default urllib UA.
            "User-Agent": "ProofLens/0.1 (+https://prooflens.app)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            request_id = resp.headers.get("x-request-id") or resp.headers.get("cf-ray")
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        req_id = exc.headers.get("x-request-id") if exc.headers else None
        logger.warning(
            "vision inference FAILED backend=%s model=%s http=%s request_id=%s detail=%s",
            name, model, exc.code, req_id, detail,
        )
        raise VisionUnavailable(f"{name} API error {exc.code}: {detail}", status=exc.code) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        logger.warning(
            "vision inference FAILED backend=%s model=%s transport=%r", name, model, reason
        )
        raise VisionUnavailable(
            f"{name} could not be reached (timeout/connection): {reason}"
        ) from exc
    return data, request_id
```

- [ ] **Step 4: Refactor `openai_compat.py` onto the helper**

Replace the `VisionUnavailable` class definition and the `try/except` request block. The new file top imports:

```python
# src/prooflens/vision/openai_compat.py  (imports section)
from .base import VisionBackend, resize_for_model
from ._http import VisionUnavailable, post_chat  # VisionUnavailable re-exported for back-compat
from .rubric import SYSTEM_PROMPT, USER_PROMPT
from .schema import ContentAssessment, parse_model_json
```

Delete the local `class VisionUnavailable(...)` block. Replace the body of `assess` from the `req = urllib.request.Request(...)` line through the `data = json.loads(resp.read())` except-block with:

```python
        data, request_id = post_chat(
            invoke_url=self.invoke_url, api_key=self.api_key,
            payload=payload, timeout=self.timeout, name=self.name, model=self.model,
        )
        generation_id = data.get("id")
        logger.info(
            "vision inference OK backend=%s model=%s request_id=%s generation_id=%s",
            self.name, self.model, request_id, generation_id,
        )
```

Leave the rest of `assess` (the `text = data["choices"][0]...` parsing and `return ContentAssessment(...)`) unchanged. Remove the now-unused `import urllib.error` / `import urllib.request` only if no longer referenced (keep `json`, `base64`).

- [ ] **Step 5: Run both test files to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_vision_http.py tests/unit/test_vision_backend.py -v`
Expected: PASS (existing `test_vision_backend.py` monkeypatches `openai_compat.urllib.request.urlopen`, which is the same module object `_http` calls — so it stays green).

- [ ] **Step 6: Run full suite + lint**

Run: `PYTHONPATH=src python -m pytest -q && ruff check src tests && mypy src`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/vision/_http.py src/prooflens/vision/openai_compat.py tests/unit/test_vision_http.py
git commit -m "refactor(vision): extract shared post_chat HTTP helper"
```

---

### Task 2: Add the `Judgment` model, reasoner prompt, and loader

**Files:**
- Modify: `src/prooflens/vision/schema.py`
- Create: `rubrics/reasoner_v1.yaml`
- Modify: `src/prooflens/vision/rubric.py`
- Test: `tests/unit/test_judgment_schema.py` (new)

**Interfaces:**
- Produces: `Judgment` pydantic model with `plausibility: int (0-100)`, `visit_context: int | None`, `context_confidence: str`, `reason: str`. And in `rubric.py`: `REASONER_VERSION: str`, `REASONER_SYSTEM_PROMPT: str`, `REASONER_USER_TEMPLATE: str` (contains the literal token `{perception}`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_judgment_schema.py
"""Judgment validates + coerces the reasoner's 4 output fields."""
from __future__ import annotations

from prooflens.vision.schema import Judgment


def test_judgment_coerces_and_clamps():
    j = Judgment(plausibility="85", visit_context="150",
                 context_confidence="MEDIUM", reason=None)
    assert j.plausibility == 85
    assert j.visit_context == 100          # clamped to 0-100
    assert j.context_confidence == "moderate"  # "medium" -> "moderate"
    assert j.reason == ""


def test_judgment_missing_visit_context_is_none():
    j = Judgment(plausibility=40, context_confidence="low")
    assert j.visit_context is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_judgment_schema.py -v`
Expected: FAIL with `ImportError: cannot import name 'Judgment'`.

- [ ] **Step 3: Add `Judgment` to `schema.py`**

Append to `src/prooflens/vision/schema.py` (after `ContentAssessment`, before `parse_model_json`):

```python
class Judgment(BaseModel):
    """The reasoner's refined judgment over a perception. Same 4 fields the
    reasoner is allowed to set on the final ContentAssessment."""

    plausibility: int = Field(ge=0, le=100)
    visit_context: int | None = None
    context_confidence: str = "moderate"
    reason: str = ""

    @field_validator("reason", mode="before")
    @classmethod
    def _coerce_reason(cls, v: Any) -> str:
        return "" if v is None else str(v)[:300]

    @field_validator("context_confidence", mode="before")
    @classmethod
    def _coerce_conf(cls, v: Any) -> str:
        s = str(v or "").strip().lower()
        if s in {"high", "moderate", "low"}:
            return s
        if s in {"medium", "mid"}:
            return "moderate"
        return "moderate"

    @field_validator("visit_context", mode="before")
    @classmethod
    def _coerce_vc(cls, v: Any) -> int | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        try:
            return max(0, min(100, int(round(float(v)))))
        except (TypeError, ValueError):
            return None

    @field_validator("plausibility", mode="before")
    @classmethod
    def _coerce_plaus(cls, v: Any) -> int:
        try:
            return max(0, min(100, int(round(float(v)))))
        except (TypeError, ValueError):
            return 0
```

- [ ] **Step 4: Create the reasoner prompt file**

```yaml
# rubrics/reasoner_v1.yaml
# ProofLens REASONER prompt — VERSIONED POLICY (judgment-only, no image).
# Given a structured perception (already extracted by the vision model), judge
# how credibly the scene evidences a genuine field-visit meeting. Same policy as
# the vision rubric, applied to the perception alone.
version: "reasoner_v1"

system_prompt: |
  You are ProofLens's compliance reasoner. You are given a STRUCTURED PERCEPTION
  of a field-force "proof of visit" photo, already extracted by a vision model —
  you do NOT see the image itself. A Direct Sales Executive submitted the photo
  as proof that a face-to-face customer meeting took place. From the perception
  ALONE, judge how credibly it evidences a genuine meeting.

  Rules:
  - A meeting needs AT LEAST TWO people apparently interacting. A lone person, a
    selfie, or people merely co-present but not interacting is weak or no evidence.
  - looks_like_photo_of_a_screen / is_designed_graphic / is_meme_or_screenshot
    each mean LOW capture authenticity.
  - VENUE-BLIND: never judge the quality, size or status of the location, nor any
    person's identity or character. A roadside stall and a corporate office are
    equally valid.
  - When the perception is ambiguous, report LOWER context_confidence rather than
    guessing. Ambiguity lowers confidence; it never manufactures suspicion.

user_prompt: |
  Here is the perception as JSON:
  {perception}

  Respond with ONLY a JSON object (no prose, no markdown fences) with EXACTLY
  these keys:
    plausibility: integer 0-100 — how plausibly this is a REAL captured scene
      (authenticity only; NOT how "ideal" the venue looks)
    visit_context: integer 0-100 — how strongly the scene evidences a genuine
      two-person customer meeting (two or more people present AND interacting)
    context_confidence: one of "high", "moderate", "low"
    reason: one short sentence explaining the judgment
```

- [ ] **Step 5: Add the loader to `rubric.py`**

Append to `src/prooflens/vision/rubric.py`:

```python
# Reasoner prompt (Stage 2 of the hybrid backend). Versioned like the rubric.
REASONER_VERSION = "reasoner_v1"
_REASONER = load_rubric(REASONER_VERSION)
REASONER_SYSTEM_PROMPT: str = _REASONER["system_prompt"]
REASONER_USER_TEMPLATE: str = _REASONER["user_prompt"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_judgment_schema.py -v && PYTHONPATH=src python -c "from prooflens.vision.rubric import REASONER_USER_TEMPLATE; assert '{perception}' in REASONER_USER_TEMPLATE"`
Expected: PASS, and the assert exits 0.

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/vision/schema.py rubrics/reasoner_v1.yaml src/prooflens/vision/rubric.py tests/unit/test_judgment_schema.py
git commit -m "feat(vision): add Judgment model + reasoner_v1 prompt"
```

---

### Task 3: The `Reasoner` (Stage 2, text-only)

**Files:**
- Create: `src/prooflens/vision/reasoner.py`
- Test: `tests/unit/test_reasoner.py`

**Interfaces:**
- Consumes: `post_chat` (Task 1), `Judgment`/`parse_model_json` (Task 2/existing), `ContentAssessment` (existing), reasoner prompt constants (Task 2).
- Produces: `Reasoner(*, api_key: str, model: str, base_url: str, timeout: float = 30.0, temperature: float = 0.0)` with `.model: str` and `refine(perception: ContentAssessment) -> Judgment`. Raises `VisionUnavailable` (transport) or `ValueError`/`ValidationError` (bad JSON) — the hybrid catches these.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_reasoner.py
"""Reasoner sends perception-as-text (no image) and parses a Judgment."""
from __future__ import annotations

import json

import pytest

from prooflens.vision import _http
from prooflens.vision.reasoner import Reasoner
from prooflens.vision.schema import ContentAssessment, Judgment

_PERCEPTION = ContentAssessment(
    people_count=2, people_interacting=True, setting="office",
    scene_description="two people at a desk with paperwork", plausibility=50,
)


class _FakeResp:
    headers: dict = {}

    def __init__(self, content: str):
        self._c = content

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self) -> bytes:
        return json.dumps({"id": "r-1", "choices": [{"message": {"content": self._c}}]}).encode()


def test_refine_sends_no_image_and_returns_judgment(monkeypatch):
    captured: dict = {}

    def fake_urlopen(req, timeout):
        captured["body"] = json.loads(req.data)
        return _FakeResp(json.dumps(
            {"plausibility": 90, "visit_context": 80, "context_confidence": "high",
             "reason": "two people interacting over paperwork"}
        ))

    monkeypatch.setattr(_http.urllib.request, "urlopen", fake_urlopen)
    r = Reasoner(api_key="k", model="@cf/openai/gpt-oss-120b",
                 base_url="https://api.example.com")
    out = r.refine(_PERCEPTION)

    body = json.dumps(captured["body"])
    assert "image_url" not in body                       # text-only
    assert "two people at a desk" in body                # perception embedded
    assert captured["body"]["temperature"] == 0.0
    assert isinstance(out, Judgment)
    assert out.plausibility == 90 and out.visit_context == 80
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_reasoner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prooflens.vision.reasoner'`.

- [ ] **Step 3: Implement `reasoner.py`**

```python
# src/prooflens/vision/reasoner.py
"""Stage 2 of the hybrid backend: reason over a perception (no image).

Takes a ContentAssessment's perceptual fields, asks a strong text model to
judge authenticity + visit-context, and returns a validated Judgment.
"""
from __future__ import annotations

import json
import logging

from ._http import VisionUnavailable, post_chat
from .rubric import REASONER_SYSTEM_PROMPT, REASONER_USER_TEMPLATE, REASONER_VERSION
from .schema import ContentAssessment, Judgment, parse_model_json

logger = logging.getLogger("prooflens.vision")

# The perceptual fields handed to the reasoner (NOT the judgment fields, which it
# produces, nor provenance).
PERCEPTION_FIELDS = (
    "people_count", "people_interacting", "setting", "environment",
    "primary_subject", "scene_description", "emotional_tone",
    "looks_like_photo_of_a_screen", "is_designed_graphic", "is_meme_or_screenshot",
)


class Reasoner:
    def __init__(
        self, *, api_key: str, model: str, base_url: str,
        timeout: float = 30.0, temperature: float = 0.0,
    ):
        if not api_key:
            raise ValueError("an API key is required for the reasoner")
        self.api_key = api_key
        self.model = model
        self.invoke_url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.temperature = temperature
        self.version = REASONER_VERSION

    def refine(self, perception: ContentAssessment) -> Judgment:
        p = {k: getattr(perception, k) for k in PERCEPTION_FIELDS}
        user = REASONER_USER_TEMPLATE.replace(
            "{perception}", json.dumps(p, ensure_ascii=False)
        )
        payload = {
            "model": self.model,
            "max_tokens": 300,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": REASONER_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        }
        data, request_id = post_chat(
            invoke_url=self.invoke_url, api_key=self.api_key,
            payload=payload, timeout=self.timeout, name="reasoner", model=self.model,
        )
        logger.info("reasoner OK model=%s request_id=%s", self.model, request_id)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise VisionUnavailable(
                f"reasoner returned an unexpected shape: {str(data)[:200]}"
            ) from exc
        raw = parse_model_json(text)     # may raise ValueError (bad JSON)
        return Judgment(**raw)           # may raise ValidationError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_reasoner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/vision/reasoner.py tests/unit/test_reasoner.py
git commit -m "feat(vision): add text-only Reasoner (hybrid stage 2)"
```

---

### Task 4: The `HybridBackend` (orchestration + fail-open)

**Files:**
- Create: `src/prooflens/vision/hybrid.py`
- Test: `tests/unit/test_hybrid_backend.py`

**Interfaces:**
- Consumes: `OpenAICompatBackend` (existing), `Reasoner` (Task 3), `VisionUnavailable` (Task 1), `ContentAssessment` (existing).
- Produces: `HybridBackend(*, name: str = "hybrid", api_key: str, base_url: str, vision_model: str, reasoner_model: str, max_edge: int = 768, timeout: float = 30.0)` implementing `VisionBackend`: attrs `name`, `is_real = True`, `model = f"{vision_model}+{reasoner_model}"`, and `assess(image_bytes: bytes) -> ContentAssessment`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_hybrid_backend.py
"""HybridBackend: merge, stage-2 fallback, stage-1 propagation."""
from __future__ import annotations

import pytest

from prooflens.vision._http import VisionUnavailable
from prooflens.vision.hybrid import HybridBackend
from prooflens.vision.schema import ContentAssessment, Judgment

_SCOUT = ContentAssessment(
    people_count=2, setting="office", scene_description="two at a desk",
    plausibility=50, visit_context=40, context_confidence="low", reason="scout view",
)


def _make(monkeypatch, *, scout_result=None, scout_exc=None,
          reason_result=None, reason_exc=None):
    hb = HybridBackend(api_key="k", base_url="https://cf/ai/v1",
                       vision_model="scout-m", reasoner_model="reason-m")

    def scout_assess(_img):
        if scout_exc:
            raise scout_exc
        return scout_result

    def reason_refine(_perc):
        if reason_exc:
            raise reason_exc
        return reason_result

    monkeypatch.setattr(hb.scout, "assess", scout_assess)
    monkeypatch.setattr(hb.reasoner, "refine", reason_refine)
    return hb


def test_happy_path_merges_reasoner_judgment(monkeypatch):
    j = Judgment(plausibility=90, visit_context=85, context_confidence="high",
                 reason="clear two-way interaction")
    hb = _make(monkeypatch, scout_result=_SCOUT, reason_result=j)
    out = hb.assess(b"img")
    assert out.plausibility == 90 and out.visit_context == 85
    assert out.context_confidence == "high" and out.reason == "clear two-way interaction"
    assert out.scene_description == "two at a desk"     # perception preserved
    assert out.backend == "hybrid" and out.model == "scout-m+reason-m"


def test_stage2_failure_keeps_scout_judgment(monkeypatch):
    hb = _make(monkeypatch, scout_result=_SCOUT,
               reason_exc=VisionUnavailable("429", status=429))
    out = hb.assess(b"img")
    assert out.plausibility == 50 and out.reason == "scout view"   # Scout's own
    assert out.backend == "hybrid"
    assert "reasoner-unavailable" in out.model


def test_stage2_bad_json_keeps_scout_judgment(monkeypatch):
    hb = _make(monkeypatch, scout_result=_SCOUT, reason_exc=ValueError("bad json"))
    out = hb.assess(b"img")
    assert out.plausibility == 50 and out.backend == "hybrid"


def test_stage1_failure_propagates(monkeypatch):
    hb = _make(monkeypatch, scout_exc=VisionUnavailable("down", status=503))
    with pytest.raises(VisionUnavailable):
        hb.assess(b"img")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_hybrid_backend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prooflens.vision.hybrid'`.

- [ ] **Step 3: Implement `hybrid.py`**

```python
# src/prooflens/vision/hybrid.py
"""Two-stage vision backend: Scout (perception) + Reasoner (judgment).

Implements VisionBackend. Stage 1 produces a full ContentAssessment; Stage 2
refines the judgment fields. Fail-open: a Stage-2 failure keeps Scout's own
judgment (never worse than single-Scout); a Stage-1 failure propagates as
VisionUnavailable (the existing Unassessed path).
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from ._http import VisionUnavailable
from .base import VisionBackend
from .openai_compat import OpenAICompatBackend
from .reasoner import Reasoner
from .schema import ContentAssessment

logger = logging.getLogger("prooflens.vision")


class HybridBackend(VisionBackend):
    is_real = True

    def __init__(
        self, *, name: str = "hybrid", api_key: str, base_url: str,
        vision_model: str, reasoner_model: str,
        max_edge: int = 768, timeout: float = 30.0,
    ):
        self.name = name
        self.scout = OpenAICompatBackend(
            name="scout", api_key=api_key, model=vision_model,
            base_url=base_url, max_edge=max_edge, timeout=timeout,
        )
        self.reasoner = Reasoner(
            api_key=api_key, model=reasoner_model, base_url=base_url, timeout=timeout,
        )
        self.model = f"{vision_model}+{reasoner_model}"

    def assess(self, image_bytes: bytes) -> ContentAssessment:
        # Stage 1 — perception (+ Scout's own judgment). Raises → Stage-1 fail-open.
        perception = self.scout.assess(image_bytes)
        try:
            judgment = self.reasoner.refine(perception)
        except (VisionUnavailable, ValidationError, ValueError) as exc:
            logger.warning("hybrid degraded=scout-only reason=%r", exc)
            return perception.model_copy(update={
                "backend": self.name,
                "model": f"{self.scout.model} (reasoner-unavailable)",
            })
        logger.info("hybrid OK degraded=false model=%s", self.model)
        return perception.model_copy(update={
            "plausibility": judgment.plausibility,
            "visit_context": judgment.visit_context,
            "context_confidence": judgment.context_confidence,
            "reason": judgment.reason,
            "backend": self.name,
            "model": self.model,
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_hybrid_backend.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/prooflens/vision/hybrid.py tests/unit/test_hybrid_backend.py
git commit -m "feat(vision): add HybridBackend (Scout + reasoner) with fail-open"
```

---

### Task 5: Register `cloudflare` + `hybrid`, wire config, flip default

**Files:**
- Modify: `src/prooflens/vision/__init__.py`
- Modify: `src/prooflens/config.py`
- Test: `tests/unit/test_config_default.py` (update), `tests/unit/test_hybrid_wiring.py` (new)

**Interfaces:**
- Consumes: `HybridBackend` (Task 4), `OpenAICompatBackend` (existing).
- Produces: `get_backend("hybrid", api_key=..., base_url=..., vision_model=..., reasoner_model=..., max_edge=...)` → `HybridBackend`; `get_backend("cloudflare", api_key=..., model=..., base_url=...)` → `OpenAICompatBackend`; `Settings.cf_base_url` property; `Settings.build_vision_backend("hybrid")` constructs the hybrid from CF settings; default `Settings().vision_backend == "hybrid"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_hybrid_wiring.py
"""get_backend + Settings wire the hybrid from CF settings."""
from __future__ import annotations

from prooflens import config
from prooflens.vision import get_backend
from prooflens.vision.hybrid import HybridBackend


def test_get_backend_builds_hybrid():
    b = get_backend("hybrid", api_key="k", base_url="https://cf/ai/v1",
                    vision_model="scout-m", reasoner_model="reason-m")
    assert isinstance(b, HybridBackend)
    assert b.model == "scout-m+reason-m"


def test_settings_build_hybrid(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct-1")
    monkeypatch.setenv("CF_API_TOKEN", "cf-token")
    s = config.Settings()
    assert s.cf_base_url == "https://api.cloudflare.com/client/v4/accounts/acct-1/ai/v1"
    b = s.build_vision_backend("hybrid")
    assert isinstance(b, HybridBackend)
```

And update `tests/unit/test_config_default.py`:

```python
# tests/unit/test_config_default.py
"""The default vision backend is the hybrid; stub is only reachable by name."""
from __future__ import annotations

from prooflens import config


def test_default_backend_is_hybrid(monkeypatch):
    for var in ("VISION_BACKEND",):
        monkeypatch.delenv(var, raising=False)
    assert config.Settings().vision_backend == "hybrid"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_hybrid_wiring.py tests/unit/test_config_default.py -v`
Expected: FAIL — `get_backend("hybrid")` raises `ValueError: unknown vision backend: 'hybrid'`, and the default assertion fails (still `"groq"`).

- [ ] **Step 3: Register in `get_backend`**

In `src/prooflens/vision/__init__.py`, add `"cloudflare"` to the OpenAI-compatible tuple and a `hybrid` branch:

```python
    # OpenAI-compatible hosted/local endpoints (Gemini, OpenRouter, Groq, Cloudflare, ...).
    if name in ("local_vlm", "gemini", "openrouter", "aimlapi", "groq", "cloudflare"):
        from .openai_compat import OpenAICompatBackend

        return OpenAICompatBackend(
            name=name,
            api_key=kwargs.get("api_key", "not-needed"),
            model=kwargs["model"],
            base_url=kwargs["base_url"],
            max_edge=kwargs.get("max_edge", 768),
        )
    if name == "hybrid":
        from .hybrid import HybridBackend

        return HybridBackend(
            api_key=kwargs["api_key"],
            base_url=kwargs["base_url"],
            vision_model=kwargs["vision_model"],
            reasoner_model=kwargs["reasoner_model"],
            max_edge=kwargs.get("max_edge", 768),
        )
```

Also add `"get_backend"` already in `__all__` (present). No change to imports at top (lazy import inside the branch).

- [ ] **Step 4: Add CF settings + wiring in `config.py`**

Add fields near the other backends (after the Groq block):

```python
    # Cloudflare Workers AI (OpenAI-compatible). Powers the default hybrid backend.
    cf_account_id: str = Field(default="", alias="CF_ACCOUNT_ID")
    cf_api_token: str = Field(default="", alias="CF_API_TOKEN")
    cf_vision_model: str = Field(
        default="@cf/meta/llama-4-scout-17b-16e-instruct", alias="CF_VISION_MODEL"
    )
    cf_reasoner_model: str = Field(
        default="@cf/openai/gpt-oss-120b", alias="CF_REASONER_MODEL"
    )
```

Flip the default:

```python
    # Vision backend: default is the two-stage Cloudflare hybrid. Set
    # VISION_BACKEND=groq (or stub) to revert instantly.
    vision_backend: str = Field(default="hybrid", alias="VISION_BACKEND")
```

Add the derived base-URL property (near `cors_origins_list`):

```python
    @property
    def cf_base_url(self) -> str:
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.cf_account_id}/ai/v1"
        )
```

Add the two dict entries inside `build_vision_backend`'s `per_backend` map:

```python
            "cloudflare": {
                "api_key": self.cf_api_token,
                "model": self.cf_vision_model,
                "base_url": self.cf_base_url,
            },
            "hybrid": {
                "api_key": self.cf_api_token,
                "base_url": self.cf_base_url,
                "vision_model": self.cf_vision_model,
                "reasoner_model": self.cf_reasoner_model,
            },
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH=src python -m pytest tests/unit/test_hybrid_wiring.py tests/unit/test_config_default.py -v`
Expected: PASS.

- [ ] **Step 6: Full suite + lint + types**

Run: `PYTHONPATH=src python -m pytest -q && ruff check src tests && mypy src`
Expected: all green. (`test_db_models.py` still passes — the Tenant ORM column default remains `"groq"`; only the env default changed.)

- [ ] **Step 7: Commit**

```bash
git add src/prooflens/vision/__init__.py src/prooflens/config.py tests/unit/test_hybrid_wiring.py tests/unit/test_config_default.py
git commit -m "feat(vision): register cloudflare + hybrid backends, default to hybrid"
```

---

### Task 6: Opt-in live smoke test (env-guarded)

**Files:**
- Test: `tests/live/test_hybrid_live.py` (new)

**Interfaces:**
- Consumes: `Settings.build_vision_backend("hybrid")`, a real image fixture.

- [ ] **Step 1: Write the guarded live test**

```python
# tests/live/test_hybrid_live.py
"""Opt-in end-to-end hybrid call against Cloudflare. Skipped unless
CF_ACCOUNT_ID + CF_API_TOKEN are set AND RUN_LIVE_VISION=1.
Run: RUN_LIVE_VISION=1 PYTHONPATH=src python -m pytest tests/live/test_hybrid_live.py -v
"""
from __future__ import annotations

import io
import os

import pytest

from prooflens import config

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_VISION") != "1"
    or not os.getenv("CF_ACCOUNT_ID")
    or not os.getenv("CF_API_TOKEN"),
    reason="live vision test is opt-in (set RUN_LIVE_VISION=1 + CF creds)",
)


def _tiny_scene_jpeg() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (320, 240), (135, 206, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 170, 320, 240], fill=(60, 160, 60))
    d.rectangle([90, 110, 190, 175], fill=(200, 60, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_hybrid_scores_a_real_image():
    backend = config.Settings().build_vision_backend("hybrid")
    out = backend.assess(_tiny_scene_jpeg())
    assert out.backend == "hybrid"
    assert 0 <= out.plausibility <= 100
    assert out.scene_description  # perception populated
```

- [ ] **Step 2: Verify it SKIPS by default**

Run: `PYTHONPATH=src python -m pytest tests/live/test_hybrid_live.py -v`
Expected: 1 skipped (no CF creds / RUN_LIVE_VISION unset).

- [ ] **Step 3: Commit**

```bash
git add tests/live/test_hybrid_live.py
git commit -m "test(vision): opt-in live hybrid smoke test"
```

---

## Rollout (post-merge, operational — not code)

1. Set `CF_ACCOUNT_ID` and `CF_API_TOKEN` (Workers AI · Read scope) as **server env** on Render. Until set, constructing the hybrid raises a clear "API key required" error; pin `VISION_BACKEND=groq` to revert.
2. **Make production use it:** the async processor scores with `tenant.vision_backend`, not the env default. Update the ABSLI tenant row to `vision_backend = "hybrid"` via the existing admin/tenant-update path (a data update — the ORM column default stays `"groq"`, so no migration). New tenants defaulting to `groq` is an accepted minor follow-up (effectively one tenant today).
3. Run the live smoke test against Cloudflare once, then watch the `degraded=scout-only` log rate and per-call latency.

## Self-Review Notes

- **Spec coverage:** architecture (Tasks 1,3,4), data flow + merge (Task 4), fail-open both directions (Task 4 tests), config + default flip (Task 5), reasoner prompt versioned (Task 2), telemetry via `model`/`degraded` logs (Tasks 3,4), testing offline + opt-in live (all tasks + Task 6), rollout (section above). The tenant-vs-env default nuance is covered in Rollout.
- **No new DB schema** — tenant column default unchanged; production switch is a data update.
- **Type consistency:** `post_chat` signature identical in Tasks 1/3; `HybridBackend` ctor kwargs match `get_backend`/config in Task 5; `Judgment` fields match the merge `update={...}` keys in Task 4.
