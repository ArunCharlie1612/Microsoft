"""Unit tests for tenant onboarding, API-key auth, billing quota, and probes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings

settings.breachsim_demo_pacing_ms = 0

from app.core.validation_probe import _is_safe_target, probe_public_endpoint  # noqa: E402
from app.main import app  # noqa: E402
from app.services.tenant_manager import TenantManager  # noqa: E402

client = TestClient(app)


# ── SSRF guard ────────────────────────────────────────────────────────────────
def test_ssrf_guard_blocks_loopback():
    assert _is_safe_target("http://127.0.0.1/") is False
    assert _is_safe_target("http://localhost/") is False


def test_ssrf_guard_blocks_non_http():
    assert _is_safe_target("file:///etc/passwd") is False
    assert _is_safe_target("ftp://example.com/") is False


@pytest.mark.asyncio
async def test_probe_rejects_unsafe_target_without_network():
    result = await probe_public_endpoint("http://169.254.169.254/")  # cloud metadata
    assert result["reachable"] is False
    assert "SSRF" in result["note"]


# ── Tenant manager + API keys ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_tenant_issues_resolvable_key():
    tm = TenantManager()
    tenant, raw = await tm.create_tenant("Acme", "a@acme.test")
    assert raw.startswith("bsk_")
    assert tm.resolve_api_key(raw) is tenant
    # The raw key is never stored — only its hash.
    assert raw not in tenant.api_key_hashes


@pytest.mark.asyncio
async def test_resolve_rejects_unknown_key():
    tm = TenantManager()
    await tm.create_tenant("Acme")
    assert tm.resolve_api_key("bsk_not_a_real_key") is None
    assert tm.resolve_api_key("") is None


# ── Signup + API-key auth end-to-end ────────────────────────────────────────────
def test_signup_and_authenticated_run():
    resp = client.post("/v1/tenants/signup", json={"name": "Tenant E2E"})
    assert resp.status_code == 201
    body = resp.json()
    api_key = body["apiKey"]
    assert api_key.startswith("bsk_")

    headers = {"X-API-Key": api_key}
    # /me reflects the authenticated tenant.
    me = client.get("/v1/tenants/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["tenantId"] == body["tenantId"]

    # A run created with this key is attributed to the tenant.
    run = client.post(
        "/v1/runs",
        headers=headers,
        json={
            "name": "tenant run",
            "scope": {
                "subscriptionId": "00000000-0000-0000-0000-000000000000",
                "sandboxOnly": True,
            },
            "authorizationAcknowledged": True,
            "authorizedBy": "owner",
        },
    )
    assert run.status_code == 202


def test_invalid_api_key_rejected():
    r = client.get("/v1/tenants/me", headers={"X-API-Key": "bsk_bogus"})
    assert r.status_code == 401


# ── Billing quota ────────────────────────────────────────────────────────────────
def test_quota_blocks_after_free_limit(monkeypatch):
    monkeypatch.setattr(settings, "plan_free_daily_runs", 2)
    resp = client.post("/v1/tenants/signup", json={"name": "Quota Co"})
    api_key = resp.json()["apiKey"]
    headers = {"X-API-Key": api_key}
    payload = {
        "name": "r",
        "scope": {"subscriptionId": "00000000-0000-0000-0000-000000000000", "sandboxOnly": True},
        "authorizationAcknowledged": True,
        "authorizedBy": "owner",
    }
    assert client.post("/v1/runs", headers=headers, json=payload).status_code == 202
    assert client.post("/v1/runs", headers=headers, json=payload).status_code == 202
    # Third run today exceeds the free plan limit.
    assert client.post("/v1/runs", headers=headers, json=payload).status_code == 402


def test_usage_summary_reports_plan_limit():
    resp = client.post("/v1/tenants/signup", json={"name": "Usage Co"})
    api_key = resp.json()["apiKey"]
    usage = client.get("/v1/tenants/me/usage", headers={"X-API-Key": api_key}).json()
    assert usage["plan"] == "free"
    assert usage["dailyRunLimit"] == settings.plan_free_daily_runs


# ── Stripe billing ───────────────────────────────────────────────────────────────
def test_checkout_503_when_billing_disabled():
    resp = client.post("/v1/tenants/signup", json={"name": "No Billing Co"})
    api_key = resp.json()["apiKey"]
    r = client.post("/v1/tenants/me/checkout", headers={"X-API-Key": api_key})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_set_plan_upgrades_and_resolves_by_customer():
    from app.models.schemas import PlanTier

    tm = TenantManager()
    tenant, _ = await tm.create_tenant("Upgrade Co")
    updated = await tm.set_plan(tenant.id, plan=PlanTier.PRO, stripe_customer_id="cus_123")
    assert updated is not None
    assert updated.plan == "pro"
    assert tm.get_by_stripe_customer("cus_123") is tenant


@pytest.mark.asyncio
async def test_webhook_upgrades_tenant_on_checkout_completed(monkeypatch):
    from app.models.schemas import PlanTier
    from app.services import stripe_billing
    from app.services.tenant_manager import tenant_manager as global_tm

    # Create a real tenant in the global manager so the webhook can find it.
    tenant, _ = await global_tm.create_tenant("Webhook Co")
    monkeypatch.setattr(settings, "stripe_api_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_price_pro", "price_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_x")

    # Stub Stripe signature verification to return a canned event.
    class _FakeStripe:
        class Webhook:
            @staticmethod
            def construct_event(payload, signature, secret):
                return {
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "metadata": {"tenant_id": tenant.id},
                            "customer": "cus_abc",
                            "subscription": "sub_abc",
                        }
                    },
                }

    monkeypatch.setattr(stripe_billing, "_stripe", lambda: _FakeStripe)
    result = await stripe_billing.handle_webhook(b"{}", "sig")
    assert result["handled"] == "checkout.session.completed"
    assert global_tm.get(tenant.id).plan == PlanTier.PRO
