"""Enterprise SSO (Entra/MSAL) endpoints + session-token credential path."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import get_principal
from app.core.session_token import decode_session_token, issue_session_token

settings.breachsim_demo_pacing_ms = 0

from app.main import app  # noqa: E402

client = TestClient(app)


def test_login_503_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "azure_tenant_id", "")
    monkeypatch.setattr(settings, "azure_client_id", "")
    monkeypatch.setattr(settings, "azure_client_secret", "")
    monkeypatch.setattr(settings, "azure_redirect_uri", "")

    r = client.get("/auth/login", follow_redirects=False)
    assert r.status_code == 503
    assert r.json()["error"] == "enterprise_auth_not_configured"


def test_login_redirects_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "azure_tenant_id", "common")
    monkeypatch.setattr(settings, "azure_client_id", "client-123")
    monkeypatch.setattr(settings, "azure_client_secret", "secret-xyz")
    monkeypatch.setattr(settings, "azure_redirect_uri", "http://localhost:8000/auth/callback")

    r = client.get("/auth/login", follow_redirects=False)
    assert r.status_code == 302
    assert "login.microsoftonline.com" in r.headers["location"]


def test_session_token_roundtrip():
    token = issue_session_token(
        tenant_id="tnt_abc", sub="entra:alice@contoso.com", email="alice@contoso.com"
    )
    claims = decode_session_token(token)
    assert claims is not None
    assert claims["tid"] == "tnt_abc"
    assert claims["email"] == "alice@contoso.com"
    assert claims["roles"] == ["breachsim.operator"]


def test_decode_rejects_garbage():
    assert decode_session_token("not-a-jwt") is None


def test_get_principal_accepts_session_token():
    token = issue_session_token(tenant_id="tnt_xyz", sub="entra:bob@contoso.com")
    principal = asyncio.run(get_principal(authorization=None, x_api_key=token, api_key_qs=None))
    assert principal.tenant_id == "tnt_xyz"
    assert principal.has_role("breachsim.operator")
