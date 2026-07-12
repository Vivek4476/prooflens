"""SSRF guard for operator-influenceable image URLs."""

from __future__ import annotations

import socket

import pytest

from prooflens.lsq.ssrf import UnsafeURLError, validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/i.jpg",        # not https
        "ftp://example.com/i.jpg",         # not https
        "https:///no-host",                # no host
        "https://127.0.0.1/i.jpg",         # loopback
        "https://10.0.0.5/i.jpg",          # private
        "https://192.168.1.10/i.jpg",      # private
        "https://169.254.169.254/latest",  # link-local (cloud metadata)
        "https://[::1]/i.jpg",             # loopback v6
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        validate_public_http_url(url)


def _resolves_to(ip: str):
    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

    return fake_getaddrinfo


def test_rejects_hostname_resolving_to_private(monkeypatch):
    # DNS-rebinding style: a public-looking hostname that resolves to a private IP.
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("10.1.2.3"))
    with pytest.raises(UnsafeURLError):
        validate_public_http_url("https://images.evil.example/i.jpg")


def test_allows_public_https(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _resolves_to("93.184.216.34"))
    # Should not raise.
    validate_public_http_url("https://images.example.com/proof.jpg")
