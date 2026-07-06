"""Per-tenant webhook signature verification.

PLACEHOLDER SCHEME (see README TODOs): HMAC-SHA256 of the raw request body,
keyed by the tenant's webhook secret, hex-encoded, sent in the
``X-ProofLens-Signature`` header. Replace with LSQ's real signature scheme once
confirmed — this is intentionally isolated behind ``verify`` so only this
function changes.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-ProofLens-Signature"


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = sign(secret, body)
    # Constant-time comparison to avoid timing leaks.
    return hmac.compare_digest(expected, signature.strip())
