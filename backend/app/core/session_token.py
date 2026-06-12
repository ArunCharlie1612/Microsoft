"""BreachSim-issued session JWTs for enterprise SSO logins.

After an operator authenticates via Entra ID (MSAL), the ``/auth/callback`` endpoint
issues a short-lived HS256 JWT carrying the resolved tenant. The frontend stores this
token in memory and presents it on every request exactly like a self-service API key —
``get_principal`` accepts either credential. Keeping the token short-lived (and signed
with a server-side secret) means a leaked token expires quickly and can never be used to
mint new tenants.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_ALGORITHM = "HS256"
_ISSUER = "breachsim"


def issue_session_token(
    *, tenant_id: str, sub: str, email: str = "", roles: list[str] | None = None
) -> str:
    """Mint a short-lived session JWT for an SSO-authenticated operator."""
    now = datetime.now(UTC)
    claims = {
        "iss": _ISSUER,
        "token_use": "session",
        "sub": sub,
        "tid": tenant_id,
        "email": email,
        "roles": roles or ["breachsim.operator"],
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_jwt_ttl_minutes),
    }
    return jwt.encode(claims, settings.session_jwt_secret, algorithm=_ALGORITHM)


def decode_session_token(token: str) -> dict[str, Any] | None:
    """Validate a BreachSim session JWT. Returns its claims, or ``None`` if invalid."""
    try:
        claims = jwt.decode(
            token,
            settings.session_jwt_secret,
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
            options={"require": ["exp", "tid", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    if claims.get("token_use") != "session":
        return None
    return claims
