"""Findings, attack graph, compliance, and remediation read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.core.cosmos import repository
from app.core.security import Principal, require_role

router = APIRouter(prefix="/v1", tags=["findings"])


@router.get("/runs/{run_id}/graph")
async def get_graph(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> dict:
    docs = await repository.list_by_run(settings.cosmos_container_threatgraph, run_id)
    nodes = [
        {
            "id": d["id"],
            "kind": d.get("nodeKind", "node"),
            "label": d.get("label", d["id"]),
            "props": d.get("props", {}),
        }
        for d in docs
        if d.get("kind") == "node"
    ]
    node_ids = {n["id"] for n in nodes}
    edges = [
        {
            "from": d.get("fromNode"),
            "to": d.get("toNode"),
            "relation": d.get("relation", ""),
            "confidence": d.get("confidence", 0.5),
        }
        for d in docs
        if d.get("kind") == "edge"
        # Drop edges whose endpoints aren't present so the client force graph never
        # references a missing node ("node not found").
        and d.get("fromNode") in node_ids
        and d.get("toNode") in node_ids
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/runs/{run_id}/findings")
async def list_findings(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> list[dict]:
    docs = await repository.list_by_run(settings.cosmos_container_findings, run_id)
    return [d for d in docs if d.get("type") != "compliance" and "title" in d]


@router.get("/runs/{run_id}/compliance")
async def get_compliance(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.auditor")),
) -> list[dict]:
    docs = await repository.list_by_run(settings.cosmos_container_findings, run_id)
    return [d for d in docs if d.get("type") == "compliance"]


@router.get("/runs/{run_id}/remediations")
async def get_remediations(
    run_id: str,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> list[dict]:
    docs = await repository.list_by_run(settings.cosmos_container_findings, run_id)
    return [d.get("remediation") for d in docs if d.get("remediation")]
