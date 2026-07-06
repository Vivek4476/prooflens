"""Fernet encryption for LSQ credentials at rest. Key from env (never in code)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from ..config import get_settings


def _fernet() -> Fernet:
    # Derive a stable 32-byte urlsafe key from the configured secret so operators
    # can supply any sufficiently-random string. Staging/prod validate strength.
    raw = get_settings().secret_key.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    return _fernet().decrypt(token).decode("utf-8")
