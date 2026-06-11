"""Tenant onboarding, API-key, and usage/billing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.core.security import Principal, require_role
from app.models.schemas import (
    SignupRequest,
    SignupResponse,
    TenantProfile,
    UsageSummary,
)
from app.services import billing
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
