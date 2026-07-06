"""Webhook signature verification."""

from __future__ import annotations

from prooflens.api.security import sign, verify


def test_sign_and_verify_roundtrip():
    secret, body = "s3cr3t", b'{"event_id":"e1"}'
    assert verify(secret, body, sign(secret, body)) is True


def test_wrong_secret_fails():
    body = b"payload"
    assert verify("right", body, sign("wrong", body)) is False


def test_tampered_body_fails():
    secret = "k"
    sig = sign(secret, b"original")
    assert verify(secret, b"tampered", sig) is False


def test_missing_signature_fails():
    assert verify("k", b"body", None) is False
    assert verify("k", b"body", "") is False
