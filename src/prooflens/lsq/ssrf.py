"""SSRF guard for operator-influenceable image URLs.

Bulk scoring and (Phase 3) RealLSQClient fetch images by URL that ultimately
trace back to an operator-uploaded CSV — i.e. attacker-influenceable. Fetching
such a URL server-side is a classic SSRF sink: an attacker points it at
``http://169.254.169.254/…`` (cloud metadata) or an internal host. This module
is the single gate every server-side image fetch MUST pass through.

Policy: https only; the host must resolve exclusively to public (global)
addresses — any loopback/link-local/private/reserved/multicast result is
rejected. Callers doing the actual fetch should additionally pin the connection
to the validated IP to be robust against DNS-rebinding (validate, then connect
to the resolved address, not re-resolve the hostname).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Raised when a URL is not safe to fetch server-side (SSRF risk)."""


def validate_public_http_url(url: str) -> None:
    """Raise :class:`UnsafeURLError` unless ``url`` is https and resolves only to
    public IP addresses. Returns None on success."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UnsafeURLError(f"only https URLs may be fetched, got scheme {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    # A bare IP literal is validated directly; a hostname is resolved and EVERY
    # resolved address must be public (a single private answer is a reject).
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"could not resolve host {host!r}: {exc}") from exc

    if not infos:
        raise UnsafeURLError(f"host {host!r} did not resolve to any address")

    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURLError(
                f"host {host!r} resolves to non-public address {ip} "
                "(loopback/link-local/private/reserved/multicast blocked)"
            )
