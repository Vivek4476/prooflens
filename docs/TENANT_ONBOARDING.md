# Tenant Onboarding

How to bring a new tenant (a LeadSquared account) onto ProofLens. Everything is
tenant-scoped; a tenant sees only its own hashes, jobs and results.

## Prerequisites

- The stack is running and migrated (`docker compose ... up`, or `alembic
  upgrade head`).
- You have the `PROOFLENS_ADMIN_TOKEN`.
- From the tenant you need: a **webhook secret** (you choose it, they configure
  it in LSQ), their **LSQ API credentials**, and their three **custom-field ids**
  for band / score / reason.

## 1. Create the tenant

```bash
curl -sX POST localhost:8000/admin/tenants \
  -H "X-Admin-Token: $PROOFLENS_ADMIN_TOKEN" \
  -H "content-type: application/json" \
  -d '{
    "slug": "acme",
    "name": "Acme Insurance",
    "webhook_secret": "<shared-secret>",
    "vision_backend": "stub",
    "field_map": {
      "band":   "mx_Custom_ProofLensBand",
      "score":  "mx_Custom_ProofLensScore",
      "reason": "mx_Custom_ProofLensReason"
    },
    "lsq_credentials": "<access-key>:<secret-key>"
  }'
```

`lsq_credentials` is stored **Fernet-encrypted at rest**; responses never echo
it back (`has_lsq_credentials: true` is all you see).

## 2. Point LSQ at the webhook

Configure the tenant's LSQ automation to POST to:

```
POST https://<your-host>/v1/webhooks/lsq/acme
X-ProofLens-Signature: <HMAC-SHA256(body, webhook_secret) hex>
```

> **TODO(LSQ):** the real LSQ webhook payload shape and signature scheme are not
> yet confirmed (see the README "LSQ unknowns"). The signature header above is a
> placeholder that only `api/security.py` + `api/schemas.py` depend on; swap it
> for LSQ's scheme when known — no other code changes.

The body must carry the event id (idempotency key), the opportunity/lead id, the
rep id, and the image (inline base64 today; by-reference URL once the fetch
endpoint is specified).

## 3. Verify

Send a signed test webhook and confirm the round-trip:

```bash
# See scripts and tests/integration/test_webhook_e2e.py for a signed example.
curl -s localhost:8000/metrics | grep 'prooflens_band_total{tenant="<id>"'
```

A `202/200 accepted` from the webhook, a `done` job in the logs, and three
custom fields updated on the opportunity (**band, then score, then reason**)
means the tenant is live.

## 4. Tune per-tenant scoring (optional)

Every weight, threshold, cap and band cut-off has a sane default and can be
overridden per tenant via `scoring_overrides` (deep-merged over the defaults).
Example — make a tenant stricter about blur and raise the Clear bar:

```bash
curl -sX PATCH localhost:8000/admin/tenants/acme \
  -H "X-Admin-Token: $PROOFLENS_ADMIN_TOKEN" -H "content-type: application/json" \
  -d '{"scoring_overrides": {"thresholds": {"blur_floor": 60}, "bands": {"clear": 75}}}'
```

Start every tenant on `vision_backend: "stub"` to validate the integration with
zero cost, then switch to a real backend (`anthropic` / `local_vlm`) once the
field mapping and webhook are confirmed working.

## 5. Offboard

Soft-delete (preserves the audit trail; no image data exists to purge):

```bash
curl -sX POST localhost:8000/admin/tenants/acme/deactivate \
  -H "X-Admin-Token: $PROOFLENS_ADMIN_TOKEN"
```
