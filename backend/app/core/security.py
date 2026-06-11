"""Entra ID auth + scope guardrails (the Security Agent's enforcement primitives)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Principal:
    """Authenticated caller derived from an Entra ID JWT."""

    def __init__(self, sub: str, tenant_id: str, roles: list[str]) -> None:
        self.sub = sub
        self.tenant_id = tenant_id
        self.roles = roles

    def has_role(self, role: str) -> bool:
        return role in self.roles or "breachsim.admin" in self.roles


async def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    """Validate the Entra bearer token and return the principal.

    When auth is disabled (local dev, or a demo without ``breachsim_require_auth``)
    a synthetic admin principal is returned so the swarm runs without an identity
    provider. When enabled, a valid Entra ID JWT is required.
    """
    if not settings.auth_enabled:
        return Principal(sub="local-dev", tenant_id="local", roles=["breachsim.admin"])

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    token = authorization.split(" ", 1)[1]
    claims = await _validate_entra_jwt(token)
    return Principal(
        sub=claims.get("sub", ""),
        tenant_id=claims.get("tid", ""),
        roles=claims.get("roles", []),
    )


async def _validate_entra_jwt(token: str) -> dict:
    """Validate a JWT against Entra ID JWKS and the configured audience."""
    import jwt  # PyJWT (optional dependency in prod images)
    from jwt import PyJWKClient

    jwks_uri = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/discovery/v2.0/keys"
    signing_key = PyJWKClient(jwks_uri).get_signing_key_from_jwt(token).key
    return jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        audience=settings.entra_api_audience,
    )


def require_role(role: str):
    """FastAPI dependency factory enforcing an RBAC role."""

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.has_role(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {role}")
        return principal

    return _dep


def enforce_scope(subscription_id: str, sandbox_only: bool) -> None:
    """Hard guardrail: reject out-of-scope or non-sandbox targets.

    This is the programmatic backstop behind the Security Agent's veto power.
    """
    if settings.breachsim_sandbox_only and not sandbox_only:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "BREACHSIM_SANDBOX_ONLY is enforced; sandbox_only must be true.",
        )
    allow = settings.allowed_subscriptions
    if allow and subscription_id not in allow:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Subscription is not in the consented allow-list.",
        )


def enforce_consent(acknowledged: bool, authorized_by: str) -> None:
    """Require an explicit authorization-to-test attestation on each run.

    Simulating attacks against an environment requires documented permission. When
    ``breachsim_require_consent`` is set, the caller must attest authorization and name
    the authorizing party — both are recorded in the audit log by the caller.
    """
    if not settings.breachsim_require_consent:
        return
    if not acknowledged or not authorized_by.strip():
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Authorization-to-test required: set authorizationAcknowledged=true and "
            "authorizedBy to the name of the approving owner.",
        )
