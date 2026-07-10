"""Per-tenant API-key auth for the /v1/* data surface.

Every data route depends on ``require_tenant``: it reads ``Authorization: Bearer
<key>``, hashes it, and resolves the owning ACTIVE tenant via a non-revoked
api_keys row. Missing/unknown/revoked/inactive -> 401 (never 403; we do not
confirm a key's existence). The webhook (HMAC) and admin routes (X-Admin-Token)
have their own schemes and do NOT use this."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from ..service.api_keys import hash_key
from ..service.repo import Repo
from ..service.views import TenantView
from .deps import get_repo

_BEARER = "bearer "


def require_tenant(
    authorization: str | None = Header(default=None),
    repo: Repo = Depends(get_repo),
) -> TenantView:
    if not authorization or not authorization.lower().startswith(_BEARER):
        raise HTTPException(status_code=401, detail="missing bearer token")
    raw = authorization[len(_BEARER):].strip()
    if not raw:
        raise HTTPException(status_code=401, detail="missing bearer token")
    tenant = repo.tenant_for_api_key(hash_key(raw))
    if tenant is None:
        raise HTTPException(status_code=401, detail="invalid api key")
    return tenant
