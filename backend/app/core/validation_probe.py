"""Safe, read-only active validation probes.

BreachSim never exploits, exfiltrates, or uses credentials. To move beyond purely
*modeled* findings, this module performs **benign reachability checks**: an anonymous
HTTP request that confirms whether a resource is publicly reachable *without
authentication*. It is strictly:

  * read-only (HEAD, or a tiny capped GET) — never writes, deletes, or mutates;
  * non-destructive — no fuzzing, no load, a single request with a short timeout;
  * non-exfiltrating — it records only the status code / content-type, never body data;
  * SSRF-guarded — refuses private, loopback, link-local, and non-HTTP(S) targets.

This is the same class of check a CSPM / attack-path-validation tool uses to *confirm*
an exposure is real, as opposed to claiming an exploit was performed.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_BODY_BYTES = 256  # we only need enough to confirm a response, never the content
_TIMEOUT_SECONDS = 5.0


def _is_safe_target(url: str) -> bool:
    """Reject SSRF-prone targets: non-HTTP(S), or hosts that resolve to private space."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def storage_account_url(name: str) -> str:
    """Public blob endpoint for an Azure Storage account (used for reachability checks)."""
    return f"https://{name}.blob.core.windows.net/"


async def probe_public_endpoint(url: str) -> dict:
    """Confirm whether ``url`` is anonymously reachable. Read-only and non-destructive.

    Returns a structured result; ``reachable`` is True only when the endpoint answered
    an unauthenticated request. Never raises — failures map to ``reachable=False``.
    """
    result: dict = {
        "url": url,
        "reachable": False,
        "status": None,
        "contentType": None,
        "anonymous": False,
        "note": "",
    }
    if not _is_safe_target(url):
        result["note"] = "Target refused by SSRF guard (private/loopback/non-HTTP)."
        return result
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            # HEAD first (no body); some endpoints disallow HEAD, so fall back to a
            # tiny capped GET that we never read beyond a few bytes.
            resp = await client.head(url)
            if resp.status_code >= 400 and resp.status_code != 405:
                resp = await client.get(url, headers={"Range": "bytes=0-255"})
            result["status"] = resp.status_code
            result["contentType"] = resp.headers.get("content-type")
            # 2xx/3xx to an unauthenticated request means it answered anonymously.
            result["reachable"] = resp.status_code < 400
            result["anonymous"] = resp.status_code < 400
            result["note"] = (
                "Endpoint answered an unauthenticated request."
                if result["anonymous"]
                else f"Endpoint responded {resp.status_code} (auth required / not public)."
            )
    except httpx.HTTPError as exc:
        result["note"] = f"No anonymous response ({type(exc).__name__})."
    return result
