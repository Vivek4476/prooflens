# Analytics date-range filters — Revision (default range, validation, gap-filled series)

- **Date:** 2026-07-08
- **Branch:** `backend/analytics-date-filters` (revises PR #8 — do NOT merge #8 as-is)
- **Status:** Design approved; writing plan.

## Context

PR #8 already added `start_date`/`end_date` to `GET /v1/analytics/summary` via a `parse_bound`
helper and half-open `[start, end)` filtering in `Repo.list_results` (both InMemory + Postgres).
The endpoint aggregates in **Python over the filtered `list_results` items**, not per-metric SQL.
This revision extends PR #8 to meet new requirements from the frontend's premium Analytics
redesign (band donut, area trend, horizontal bar). It is a revision of the existing branch, not a
new feature.

## Goals

1. **Validate** dates strictly, rejecting bad input with **HTTP 400** (the frontend owns user-facing
   UX validation; the backend fails hard):
   - any provided date **in the future** (> today, UTC) → 400
   - `start_date > end_date` → 400
   - unparseable date → 400 (already present)
   - **range span > 400 days** → 400 (new safeguard against pathological gap-fill arrays)
2. **All listed metrics filter strictly to the range** — `total`, `avg_score`, `suspect_pct`,
   `duplicates_caught`, `top_reasons`, `band_distribution`. **Already satisfied** by PR #8's
   `list_results` filtering (they aggregate over the filtered item set); **no change required**.
3. **Gap-fill the `series`**: emit a bucket for **every calendar day** in the resolved range;
   days with no data get `{date, count:0, clear:0, doubtful:0, suspect:0, avg_score:0}`,
   oldest→newest — so the redesigned area chart renders smoothly.
4. **Default to the last 30 days** when parameters are omitted.

## Non-goals

- Rewriting the aggregation as raw SQL (would break the InMemory/Postgres repo parity the suite
  relies on).
- Changing the route (stays `/v1/analytics/summary`; the frontend calls exactly that — "`/api/analytics`"
  was shorthand).
- Front-end date-picker validation (frontend handles UX).

## Design

### Bounds & conventions

Reuse `parse_bound` (PR #8): date-only → whole-day; full timestamp → exact instant; tz-aware UTC;
half-open filtering `created_at >= start AND created_at < end`. "Today" = `datetime.now(UTC).date()`.

### `resolve_range(start_date: str | None, end_date: str | None) -> tuple[datetime, datetime]`

New helper in `src/prooflens/api/date_range.py`. Produces an **always-bounded** half-open
`[start, end)` so gap-fill has a finite span. Raises `ValueError` on any validation failure (the
endpoint maps `ValueError` → 400).

Resolution:
- Parse each provided bound with `parse_bound` (`start`: `is_end=False`; `end`: `is_end=True`).
- Apply defaults on the **date**:
  - neither provided → `end_date_d = today`, `start_date_d = today − 29 days` (30 calendar days incl. today)
  - only `start` provided → `end_date_d = today`
  - only `end` provided → `start_date_d = end_date_d − 29 days`
  - both provided → as given
- Materialize to datetimes: `start = start_date_d 00:00Z`; `end = (end_date_d + 1 day) 00:00Z` (exclusive).

Validation (raise `ValueError` with a message naming the field):
- **Future:** any *provided* date whose day `> today` → `ValueError("end_date is in the future")`
  (and likewise `start_date`). Defaulted bounds are never future by construction.
- **Order:** `start > end` (equivalently the resolved `start >= end`) → `ValueError("start_date must be <= end_date")`.
  Same-day (`start_date == end_date`) is valid (span = 1 day).
- **Span cap:** `(end − start) > 400 days` → `ValueError("date range too large (max 400 days)")`.

Returns `(start, end)` — both non-None.

### `fill_series(by_day: dict[str, list], start: datetime, end: datetime) -> list[dict]`

New helper (in `api/scoring.py` near the endpoint, or `api/date_range.py`). Enumerates every
calendar day from `start.date()` through `(end − 1 day).date()` inclusive. For each day present in
`by_day`, compute the existing per-day bucket (count, clear/doubtful/suspect, avg_score); for a
missing day emit the zero bucket. Output oldest→newest.

### Endpoint (`analytics_summary`)

- Replace the two bare `parse_bound` calls with a single `resolve_range(start_date, end_date)` inside
  the existing `try/except ValueError -> HTTPException(400, ...)`.
- Pass the resolved `start`/`end` to `repo.list_results(limit=5000, offset=0, start=start, end=end)`.
- Build `by_day` as today, then `series = fill_series(by_day, start, end)`.
- All other aggregates are unchanged (they already run over the filtered `items`).
- Response shape unchanged except `series` is now dense (gap-filled).

## Data flow

request → `resolve_range` (default + parse + validate; 400 on failure) → `list_results(start,end)` →
Python aggregation over filtered items → `fill_series` densifies the series → JSON (same keys).

## Error handling

All validation failures surface as **HTTP 400** with a message naming the offending field. No 500s
for bad input. `start > end`, future dates, over-span, and unparseable all funnel through the same
`ValueError → 400` path.

## Testing

- `resolve_range` unit tests: neither/only-start/only-end/both defaults; future `start_date` → ValueError;
  future `end_date` → ValueError; `start > end` → ValueError; same-day allowed; span > 400d → ValueError.
- `fill_series` unit tests: a range with an interior empty day → a 0-count bucket appears in order;
  first/last day boundaries included; a fully-empty range → all-zero buckets spanning every day.
- Endpoint integration: no-params → range covers ~30 days and `series` length == number of days in range
  (dense); a future `end_date` → 400; `start_date > end_date` → 400; over-span → 400; existing
  no-regression (`test_results_and_analytics_populate` adjusted for the new default if needed).

## Rollout & frontend

- Same branch/PR (#8). Params already in OpenAPI (no new surface); dense `series` is additive and is
  exactly what the redesigned area chart needs.
- **Behavior change:** the un-redesigned dashboard (no params) now shows the last 30 days instead of
  all-time — intended per req #4. Flag in the PR description.
- No DB migration.

## Risks

- The `test_results_and_analytics_populate` test may need adjustment: it uploads "today" images and
  asserts `total == 3` with no params. Under the 30-day default that still holds (today is within the
  last 30 days), but the `series`/`images_today` assertions should be reviewed against the dense series.
- Timezone: "today"/"future"/"last 30 days" are all UTC — consistent with existing `created_at` storage
  and `parse_bound`.
