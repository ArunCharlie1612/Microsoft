"""Resolve a GitHub API token for remediation PRs.

Precedence (most→least preferred for a real product):
  1. GitHub App installation token (``github_app_id`` + private key + installation id)
     — short-lived, least-privilege, rotates automatically.
  2. A PAT pulled from Key Vault (``azure_key_vault_uri`` + secret ``github-token``).
  3. A PAT from the ``github_token`` setting (Container App secret / env).

Returns ``None`` when nothing is configured so the caller degrades gracefully.
"""

from __future__ import annotations

import time

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_GITHUB_API = "https://api.github.com"
_cached_installation_token: tuple[str, float] | None = None


def _read_private_key() -> str | None:
    path = settings.github_private_key_path
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        logger.warning("GitHub App private key not readable at %s.", path)
        return None


async def _installation_token() -> str | None:
    """Mint a GitHub App installation access token (cached until ~5 min before expiry)."""
    global _cached_installation_token
    if not (settings.github_app_id and settings.github_installation_id):
        return None
    if _cached_installation_token and _cached_installation_token[1] - 300 > time.time():
        return _cached_installation_token[0]

    private_key = _read_private_key()
    if not private_key:
        return None
    try:
        import jwt  # PyJWT[crypto]
    except ImportError:
        logger.warning("PyJWT not installed — cannot use GitHub App auth.")
        return None

    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": settings.github_app_id},
        private_key,
        algorithm="RS256",
    )
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"/app/installations/{settings.github_installation_id}/access_tokens"
    try:
        async with httpx.AsyncClient(base_url=_GITHUB_API, headers=headers, timeout=15.0) as client:
            resp = await client.post(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        logger.warning("Failed to mint GitHub App installation token.", exc_info=True)
        return None

    token = data.get("token")
    # Installation tokens last 1h; cache with the returned expiry where possible.
    _cached_installation_token = (token, time.time() + 3300)
    return token


async def _key_vault_token() -> str | None:
    if not settings.azure_key_vault_uri:
        return None
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.keyvault.secrets.aio import SecretClient
    except ImportError:
        return None
    try:
        credential = DefaultAzureCredential()
        try:
            client = SecretClient(settings.azure_key_vault_uri, credential)
            try:
                secret = await client.get_secret("github-token")
                return secret.value
            finally:
                await client.close()
        finally:
            await credential.close()
    except Exception:  # noqa: BLE001
        logger.warning("Could not read github-token from Key Vault.", exc_info=True)
        return None


async def resolve_github_token() -> str | None:
    """Return the best available GitHub token, or None if unconfigured."""
    token = await _installation_token()
    if token:
        return token
    token = await _key_vault_token()
    if token:
        return token
    return settings.github_token or None
