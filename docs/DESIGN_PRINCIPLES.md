# ProofLens Design Principles

The enterprise design charter for ProofLens. **No dashboard UI is built in
Phase 1** — this document governs the future Phase 2 batch dashboard, and it
already governs the shape of the CLI and API output today.

## First principle: decision-first

Every screen (and every CLI/API response) leads with the **decision**, then the
**evidence**, then the **internals**. A reviewer should be able to act on the
band without reading anything else. ProofLens output is ordered:

1. **Verdict** — band, score, reason.
2. **Evidence** — the per-check breakdown (what was found).
3. **Internals** — rubric version, raw metrics.

The CLI and API follow this exact hierarchy; the dashboard must too.

## Layout & information hierarchy

- **One primary metric or action per screen.** Do not make the reviewer choose
  between five equally-weighted things.
- **Tables for operational data** (queues, results, audit trails). **Cards only
  for KPIs** — a card is a headline number, not a row of data.
- **Empty states teach**: say *what* this screen is, *why* it is empty, *what*
  to do next, and give exactly one call-to-action.

## Colour

- **Accent ≤ 10% of the interface.** The interface is mostly neutral.
- **Brand crimson `#C8102E` is masthead-only** — never interface chrome, never
  buttons, never table rows.
- **Green / amber / red are reserved for verdict semantics** (Clear / Doubtful /
  Suspect) and are **always paired with the word**. Colour never carries meaning
  on its own — colour-blind and greyscale readers get the same information.

## Accessibility

- **AA contrast** minimum for all text.
- **44px minimum touch targets.**
- **Respect `prefers-reduced-motion`.**

## Motion

- Motion **communicates state only** (loading, appearing, transitioning) — never
  decoration.
- **≤ 250ms.** Anything slower gets in the reviewer's way.

## AI transparency

Whenever ProofLens shows a verdict it must also show:

1. **What was found** — the per-check evidence.
2. **Why** — the reason, in plain language (see
   [VERDICT_COPY.md](VERDICT_COPY.md)).
3. **Confidence** — the score and which signals are soft vs. hard gates.
4. **Next action** — retake, review, or accept.

The stub backend is always labelled as a stub; a verdict never implies a real
model judged the image when it did not.

## Non-negotiables (never build)

Facial recognition or identity matching · gesture/pose analysis · blocking
behaviour · image persistence · GPS hard gates · per-rep behavioural profiling ·
secrets in code. ProofLens is a **capture-integrity / triage tool**, not a truth
detector or a surveillance system.
