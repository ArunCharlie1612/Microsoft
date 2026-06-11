"""Run + SSE endpoints — the heart of the API."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.core.cosmos import repository
from app.core.events import event_bus
from app.core.logging import get_logger
from app.core.ratelimit import run_rate_limiter
from app.core.security import (
    Principal,
    enforce_consent,
    enforce_scope,
    require_role,
)
from app.models.schemas import CreateRunRequest, RunDetail, RunSummary
from app.services import billing
from app.services.run_manager import run_manager
from app.services.tenant_manager import tenant_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["runs"])


def _require_run_access(run_id: str, principal: Principal) -> RunDetail:
    """Fetch a run, enforcing tenant isolation (admins may access any tenant)."""
    detail = run_manager.get(run_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    if not principal.has_role("breachsim.admin") and detail.tenant_id != principal.tenant_id:
        # Do not reveal cross-tenant existence.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return detail


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    req: CreateRunRequest,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> dict:
    run_rate_limiter.check(principal.sub or "anonymous")
    enforce_consent(req.authorization_acknowledged, req.authorized_by)
    enforce_scope(req.scope.subscription_id, req.scope.sandbox_only)
    # Enforce the tenant's plan quota (skip for the synthetic local/admin principal).
    tenant = tenant_manager.get(principal.tenant_id)
    if tenant and not billing.within_quota(tenant.id, tenant.plan):
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Daily run quota reached for the '{tenant.plan}' plan. Upgrade or try tomorrow.",
        )
    detail = run_manager.create(req, tenant_id=principal.tenant_id)
    # Record the authorization-to-test attestation for audit.
    await repository.save(
        settings.cosmos_container_audit,
        {
            "id": f"{detail.run_id}_consent",
            "run_id": detail.run_id,
            "actor": principal.sub,
            "action": "authorization_to_test",
            "after": {
                "authorizedBy": req.authorized_by,
                "subscriptionId": req.scope.subscription_id,
                "sandboxOnly": req.scope.sandbox_only,
                "tenantId": principal.tenant_id,
            },
        },
    )
    return {
        "runId": detail.run_id,
        "status": detail.status.value,
        "createdAt": detail.created_at.isoformat(),
        "links": {
            "self": f"/v1/runs/{detail.run_id}",
            "events": f"/v1/runs/{detail.run_id}/events",
            "graph": f"/v1/runs/{detail.run_id}/graph",
        },
    }


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> list[RunDetail]:
    # Admins see all tenants; everyone else sees only their own.
    tenant = None if principal.has_role("breachsim.admin") else principal.tenant_id
    return run_manager.list(tenant_id=tenant)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> RunDetail:
    return _require_run_access(run_id, principal)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> dict:
    _require_run_access(run_id, principal)
    ok = await run_manager.cancel(run_id)
    if not ok:
        raise HTTPException(status.HTTP_409_CONFLICT, "Run not cancellable")
    return {"runId": run_id, "status": "cancelled"}


@router.get("/runs/{run_id}/events")
async def stream_events(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> EventSourceResponse:
    """Server-Sent Events stream of live agent activity."""
    _require_run_access(run_id, principal)

    async def event_generator():
        async for evt in event_bus.subscribe(run_id):
            done = evt["type"] == "breachsim.run.completed"
            yield {
                "event": "done" if done else "agent",
                "data": json.dumps(
                    {
                        "agentId": evt["data"].get("agentId"),
                        "eventType": evt["type"],
                        "summary": evt["data"].get("summary", ""),
                        "phase": evt["data"].get("phase"),
                        "progress": evt["data"].get("progress"),
                    }
                ),
            }

    return EventSourceResponse(event_generator())
