"""Admin API — tenant CRUD. Guarded by a static admin token (X-Admin-Token).

Responses NEVER include the webhook secret or LSQ credentials. Credentials are
accepted as plaintext on write and stored Fernet-encrypted at rest.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..config import get_settings

router = APIRouter(prefix="/admin/tenants", tags=["admin"])


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    import hmac

    expected = get_settings().admin_token
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="invalid admin token")


def get_session() -> Iterator:
    from ..db.base import session_scope

    session = session_scope()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- schemas ---
class TenantCreate(BaseModel):
    slug: str
    name: str
    webhook_secret: str
    field_map: dict[str, str] = Field(default_factory=dict)
    scoring_overrides: dict = Field(default_factory=dict)
    vision_backend: str = "stub"
    lsq_credentials: str | None = None  # plaintext in, encrypted at rest


class TenantUpdate(BaseModel):
    name: str | None = None
    webhook_secret: str | None = None
    field_map: dict[str, str] | None = None
    scoring_overrides: dict | None = None
    vision_backend: str | None = None
    lsq_credentials: str | None = None
    active: bool | None = None


class TenantOut(BaseModel):
    id: str
    slug: str
    name: str
    active: bool
    vision_backend: str
    field_map: dict[str, str]
    has_lsq_credentials: bool


def _out(t) -> TenantOut:
    return TenantOut(
        id=str(t.id), slug=t.slug, name=t.name, active=t.active,
        vision_backend=t.vision_backend, field_map=dict(t.field_map or {}),
        has_lsq_credentials=t.lsq_credentials_encrypted is not None,
    )


@router.post("", response_model=TenantOut, dependencies=[Depends(require_admin)])
def create_tenant(body: TenantCreate, session=Depends(get_session)) -> TenantOut:
    from ..db.crypto import encrypt
    from ..db.models import Tenant

    if session.query(Tenant).filter(Tenant.slug == body.slug).one_or_none():
        raise HTTPException(status_code=409, detail="slug already exists")
    tenant = Tenant(
        slug=body.slug, name=body.name, webhook_secret=body.webhook_secret,
        field_map=body.field_map, scoring_overrides=body.scoring_overrides,
        vision_backend=body.vision_backend,
        lsq_credentials_encrypted=encrypt(body.lsq_credentials) if body.lsq_credentials else None,
    )
    session.add(tenant)
    session.flush()
    return _out(tenant)


@router.get("", response_model=list[TenantOut], dependencies=[Depends(require_admin)])
def list_tenants(session=Depends(get_session)) -> list[TenantOut]:
    from ..db.models import Tenant

    return [_out(t) for t in session.query(Tenant).order_by(Tenant.created_at).all()]


def _get_or_404(session, slug: str):
    from ..db.models import Tenant

    t = session.query(Tenant).filter(Tenant.slug == slug).one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="unknown tenant")
    return t


@router.get("/{slug}", response_model=TenantOut, dependencies=[Depends(require_admin)])
def get_tenant(slug: str, session=Depends(get_session)) -> TenantOut:
    return _out(_get_or_404(session, slug))


@router.patch("/{slug}", response_model=TenantOut, dependencies=[Depends(require_admin)])
def update_tenant(slug: str, body: TenantUpdate, session=Depends(get_session)) -> TenantOut:
    from ..db.crypto import encrypt

    t = _get_or_404(session, slug)
    data = body.model_dump(exclude_unset=True)
    if "lsq_credentials" in data:
        creds = data.pop("lsq_credentials")
        t.lsq_credentials_encrypted = encrypt(creds) if creds else None
    for key, value in data.items():
        setattr(t, key, value)
    session.flush()
    return _out(t)


@router.post("/{slug}/deactivate", response_model=TenantOut, dependencies=[Depends(require_admin)])
def deactivate_tenant(slug: str, session=Depends(get_session)) -> TenantOut:
    t = _get_or_404(session, slug)
    t.active = False
    session.flush()
    return _out(t)


@router.delete("/{slug}", response_model=TenantOut, deprecated=True,
               dependencies=[Depends(require_admin)])
def delete_tenant_alias(slug: str, session=Depends(get_session)) -> TenantOut:
    # Soft delete only — never hard-delete a tenant (audit trail).
    return deactivate_tenant(slug, session)
