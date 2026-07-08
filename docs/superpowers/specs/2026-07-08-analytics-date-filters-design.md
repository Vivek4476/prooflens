# Analytics date-range filters

- **Date:** 2026-07-08
- **Branch:** `backend/analytics-date-filters`
- **Status:** Design approved; pending spec review before implementation plan.

## Problem

`GET /v1/analytics/summary` (`src/prooflens/api/scoring.py:181`) aggregates **all**
results (up to 5,000 newest rows via `repo.list_results(...)`). The frontend charts
cannot be scoped to a time window. We need optional `start_date` / `end_date` query
params so the UI can filter analytics by date range.

## Goals

- Add optional `start_date` and `end_date` query params to the analytics endpoint.
- Accept **both** ISO-8601 forms:
  - **Date-only** `YYYY-MM-DD` → whole-day semantics.
  - **Full timestamp** `YYYY-MM-DDTHH:MM:SS[±HH:MM]` → exact-instant semantics.
- Backward compatible: omitting both params reproduces today's behaviour exactly.

## Non-goals

- Tenant-scoping the analytics reads (a pre-existing behaviour — the endpoint returns
  all tenants' results; unchanged here).
- Removing the 5,000-row Python-aggregation ceiling (pre-existing; unchanged).
- Exposing the params on `/v1/results` (only the analytics endpoint, per the request).

## Design

### 1. API surface

`analytics_summary` gains two optional query params:

```python
start_date: str | None = Query(default=None)
end_date: str | None = Query(default=None)
```

Response shape is **unchanged** — same keys, aggregates simply reflect the filtered set.

### 2. Parsing & boundary semantics

A single shared helper parses a bound string into a timezone-aware UTC `datetime`:

```
_parse_bound(value: str | None, *, is_end: bool) -> datetime | None
```

- `None` → `None` (no bound).
- **Date-only** (`len == 10`, matches `YYYY-MM-DD`): parse the date at `00:00:00` UTC.
  For `is_end`, add **one day** (so the end day is fully included).
- **Full timestamp**: `datetime.fromisoformat(value)`; if the result is naive (no
  offset), attach UTC. Used as the exact instant (no day rounding).
- On `ValueError` → raise so the API layer can return **HTTP 400**.

Filtering is **half-open**: `created_at >= start AND created_at < end`.
- Date-only end + one day ⇒ that end day is inclusive.
- Full-timestamp end ⇒ exclusive of that instant.
This gives one consistent rule while making both input forms behave intuitively
(`start_date=end_date=2026-07-08` returns exactly that day).

### 3. Where the filter lives

Parse at the **API boundary** (so malformed input fails fast with a 400), then pass
`datetime` objects down. Extend `Repo.list_results` and both implementations with two
optional params:

```
list_results(..., start: datetime | None = None, end: datetime | None = None)
```

- **PostgresRepo** (`db/repo.py`): add SQL `WHERE created_at >= :start` and
  `created_at < :end` before the count/fetch — filters server-side.
- **InMemoryRepo** (`service/repo.py`): parse each stored ISO `created_at` string to a
  tz-aware `datetime` and compare against the bounds.

The analytics endpoint calls `list_results(limit=5000, start=…, end=…)`.

### 4. Validation

- Unparseable `start_date` / `end_date` → **HTTP 400** with a clear message naming the
  offending param.
- `start > end` → a valid but **empty** range: zeros / empty `series`, **not** an error.

## Behaviour changes (summary)

| Request | Result |
|---|---|
| no params | all results (unchanged) |
| `?start_date=2026-07-01&end_date=2026-07-08` | results in `[Jul 1 00:00Z, Jul 9 00:00Z)` |
| `?start_date=2026-07-08T14:00:00Z` | results at/after that instant |
| `?start_date=bogus` | HTTP 400 |
| `start > end` | empty aggregates, HTTP 200 |

## Testing

- Existing analytics test (`tests/integration/test_scoring_api.py`) stays green
  (no params → unchanged).
- **New:** seed results across multiple days (via `repo.record_result` with explicit
  tz-aware timestamps); assert a date-only range filters to the expected subset.
- **New:** full-timestamp bound filters at the instant.
- **New:** malformed date → 400.
- **New:** `start > end` → empty aggregates, 200.
- Unit-test `_parse_bound` directly for both forms + the end-day `+1` rule.

## Rollout & frontend

- Adding query params **changes `/openapi.json`**. On merge, the frontend agent must run
  `npm run gen:api` to regenerate `src/lib/api/schema.ts` and then wire the date picker
  to pass `start_date` / `end_date`. This will be called out explicitly at handoff.
- No DB migration. No change to stored data.

## Risks

- Timezone confusion: date-only inputs are interpreted as **UTC**. Documented in the
  endpoint's docstring and here; the frontend should send UTC dates (or full offsets).
- InMemory vs Postgres parity: both must apply the identical half-open rule — covered by
  running the same filter tests against both repos where the suite already does.
