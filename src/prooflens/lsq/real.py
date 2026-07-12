"""RealLSQClient — write verdicts back to LeadSquared over HTTP.

Built LAST, and deliberately INCOMPLETE: the exact LSQ contract is not yet
confirmed, so the unknowns are stubbed behind clearly-marked TODOs (mirrored in
the README). Everything else in ProofLens runs against FakeLSQClient, so nothing
depends on this being finished; when the LSQ details land, only this file
changes.

Constructed per tenant with that tenant's decrypted credentials (LSQ is
multi-tenant): the worker resolves the client per job. This client is NEVER used
in tests.

Open items (see README "LSQ unknowns"):
  1. API auth — access-key/secret vs bearer token, and how they're passed.
  2. The custom-field update endpoint + request body shape.
  3. Image fetch-by-reference (if the webhook sends a URL, not bytes).
"""

from __future__ import annotations

from .base import FieldUpdate
from .ssrf import validate_public_http_url

# TODO(LSQ): confirm base URL / region host (e.g. https://api-in21.leadsquared.com).
_DEFAULT_BASE_URL = "https://api.leadsquared.com"

# TODO(LSQ): confirm the opportunity/lead custom-field update path + verb.
_UPDATE_PATH = "/v2/LeadManagement.svc/Lead.Update"


class RealLSQClient:
    is_real = True

    def __init__(
        self,
        *,
        access_key: str,
        secret_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._access_key = access_key
        self._secret_key = secret_key
        self._timeout = timeout
        import httpx  # imported lazily; only the service extra ships httpx

        # TODO(LSQ): confirm auth mechanism. LSQ commonly uses accessKey +
        # secretKey as query params; if it's a bearer token instead, set headers
        # here and drop the params below.
        self._client = httpx.Client(
            base_url=self.base_url,
            params={"accessKey": access_key, "secretKey": secret_key},
            timeout=timeout,
        )

    def update_custom_fields(self, opportunity_id: str, updates: list[FieldUpdate]) -> None:
        # TODO(LSQ): confirm the exact request body. This is a plausible shape
        # (LSQ Lead.Update takes LeadId + a list of {Attribute, Value}); the real
        # field ids come from the tenant's field_map. Order is preserved
        # (band, score, reason) as the caller builds it.
        body = {
            "LeadId": opportunity_id,  # TODO(LSQ): is the write target Lead or Opportunity?
            "Fields": [{"Attribute": u.field_id, "Value": u.value} for u in updates],
        }
        resp = self._client.post(_UPDATE_PATH, json=body)
        resp.raise_for_status()

    def fetch_image(self, image_url: str) -> bytes:
        # SSRF gate FIRST: image_url traces back to an operator-uploaded CSV, so
        # it must be validated before any network call. Wired in now so the
        # Phase-3 implementer physically cannot add the fetch without the guard.
        validate_public_http_url(image_url)
        # TODO(LSQ): fetch-by-reference — auth for the image endpoint is unknown.
        # Only needed if the webhook delivers a URL rather than inline bytes.
        # When implemented: pin the connection to the address validated above
        # (do not re-resolve the hostname) to be DNS-rebinding safe.
        raise NotImplementedError("LSQ image fetch-by-reference is not yet specified")

    def close(self) -> None:
        self._client.close()
