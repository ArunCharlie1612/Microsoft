"""Run + SSE endpoints — the heart of the API."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.core.events import event_bus
from app.core.security import Principal, enforce_scope, require_role
from app.models.schemas import CreateRunRequest, RunDetail, RunSummary
from app.services.run_manager import run_manager

router = APIRouter(prefix="/v1", tags=["runs"])


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    req: CreateRunRequest,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> dict:
    enforce_scope(req.scope.subscription_id, req.scope.sandbox_only)
    detail = run_manager.create(req)
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
    return run_manager.list()


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> RunDetail:
    detail = run_manager.get(run_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return detail


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> dict:
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
    if not run_manager.get(run_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")

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
