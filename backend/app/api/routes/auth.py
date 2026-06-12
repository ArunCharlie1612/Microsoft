"""Enterprise SSO (Azure Entra ID / MSAL) login endpoints.

These sit alongside the self-service API-key flow: judges can authenticate as enterprise
users via Microsoft, and the callback issues a BreachSim session JWT that the frontend
uses identically to an API key. When the four Entra env vars are unset (local dev), the
endpoints degrade gracefully with a 503 so nothing else breaks.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.core.logging import get_logger
from app.core.session_token import issue_session_token
from app.services.tenant_manager import tenant_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Minimal scope: we only need the signed id_token (OpenID Connect claims) to identify
# the user — no Graph access is requested.
_SCOPES = ["User.Read"]


def _not_configured() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "enterprise_auth_not_configured",
            "message": (
                "Enterprise SSO is not configured. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
                "AZURE_CLIENT_SECRET and AZURE_REDIRECT_URI to enable Microsoft sign-in, "
                "or use the self-service API key flow."
            ),
        },
    )


def _msal_app():
    import msal

    return msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
    )


def _frontend_base() -> str:
    origins = settings.cors_origin_list
    return origins[0] if origins else "http://localhost:3000"


@router.get("/login", response_model=None)
async def login() -> RedirectResponse | JSONResponse:
    """Redirect to the Azure AD OAuth2 authorize URL (or 503 if SSO is unconfigured)."""
    if not settings.enterprise_auth_configured:
        return _not_configured()
    auth_url = _msal_app().get_authorization_request_url(
        scopes=_SCOPES,
        redirect_uri=settings.azure_redirect_uri,
    )
    return RedirectResponse(auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback", response_model=None)
async def callback(
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse | JSONResponse:
    """Exchange the auth code for tokens, resolve the tenant, and issue a session JWT.

    On success the browser is redirected back to the frontend with the JWT in the URL
    fragment so the SPA can store it in memory (never persisted server-side).
    """
    if not settings.enterprise_auth_configured:
        return _not_configured()
    if error or not code:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            error_description or error or "Missing authorization code",
        )

    result = _msal_app().acquire_token_by_authorization_code(
        code,
        scopes=_SCOPES,
        redirect_uri=settings.azure_redirect_uri,
    )
    if "id_token_claims" not in result:
        logger.warning("Token exchange failed: %s", result.get("error"))
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            result.get("error_description", "Token exchange failed"),
        )

    claims = result["id_token_claims"]
    email = claims.get("preferred_username") or claims.get("email") or claims.get("upn") or ""
    name = claims.get("name", "") or email
    if not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "id_token did not contain an email")

    tenant = await tenant_manager.get_or_create_by_email(email, name)
    token = issue_session_token(
        tenant_id=tenant.id,
        sub=claims.get("sub", f"entra:{email}"),
        email=email,
    )

    # Hand the JWT back to the SPA via the URL fragment (not a query string), so it never
    # lands in server logs or the Referer header.
    redirect = f"{_frontend_base()}/#{urlencode({'token': token, 'tenant': tenant.name})}"
    return RedirectResponse(redirect, status_code=status.HTTP_302_FOUND)
