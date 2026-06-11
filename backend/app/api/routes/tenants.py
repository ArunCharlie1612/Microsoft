"""Tenant onboarding, API-key, and usage/billing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.core.security import Principal, require_role
from app.models.schemas import (
    SignupRequest,
    SignupResponse,
    TenantProfile,
    UsageSummary,
)
from app.services import billing, stripe_billing
from app.services.tenant_manager import tenant_manager

router = APIRouter(prefix="/v1/tenants", tags=["tenants"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(req: SignupRequest) -> SignupResponse:
    """Self-service onboarding: create a tenant and return its first API key (once)."""
    if not settings.breachsim_public_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Public signup is disabled.")
    if not req.name.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "name is required")
    tenant, raw_key = await tenant_manager.create_tenant(req.name.strip(), req.email, req.plan)
    return SignupResponse(tenantId=tenant.id, name=tenant.name, plan=tenant.plan, apiKey=raw_key)


@router.get("/me", response_model=TenantProfile)
async def me(principal: Principal = Depends(require_role("breachsim.operator"))) -> TenantProfile:
    tenant = tenant_manager.get(principal.tenant_id)
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return TenantProfile(
        tenantId=tenant.id,
        name=tenant.name,
        email=tenant.email,
        plan=tenant.plan,
        status=tenant.status,
        apiKeys=tenant.api_keys,
    )


@router.post("/me/api-keys", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> SignupResponse:
    tenant = tenant_manager.get(principal.tenant_id)
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    raw_key = await tenant_manager.issue_api_key(tenant.id)
    if raw_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return SignupResponse(tenantId=tenant.id, name=tenant.name, plan=tenant.plan, apiKey=raw_key)


@router.get("/me/usage", response_model=UsageSummary)
async def usage(
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> UsageSummary:
    return billing.usage_summary(principal.tenant_id)


@router.post("/me/checkout")
async def checkout(
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> dict:
    """Start a Stripe Checkout session to upgrade this tenant to the Pro plan."""
    if not settings.billing_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Billing is not configured.")
    tenant = tenant_manager.get(principal.tenant_id)
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    try:
        url = await stripe_billing.create_checkout_session(tenant.id, tenant.email)
    except stripe_billing.BillingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return {"checkoutUrl": url}


@router.post("/billing/webhook", include_in_schema=False)
async def stripe_webhook(request: Request) -> dict:
    """Stripe webhook receiver — verifies the signature and updates the tenant plan."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        return await stripe_billing.handle_webhook(payload, signature)
    except stripe_billing.BillingNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
