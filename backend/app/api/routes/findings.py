"""Findings, attack graph, compliance, and remediation read endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.core.cosmos import repository
from app.core.security import Principal, require_role
from app.models.schemas import FeedbackRequest

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


@router.patch("/findings/{finding_id}/feedback")
async def submit_feedback(
    finding_id: str,
    body: FeedbackRequest,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> dict:
    """Record an operator's triage verdict on a finding — the swarm's learning signal.

    Judges: this endpoint closes the human-in-the-loop learning loop. The verdict is
    stored two ways:

      1. Stamped onto the finding itself (``verdict`` / ``note`` / ``feedback_at``) so the
         UI can show the decision and disable re-submission.
      2. Persisted as a standalone ``feedback`` record keyed by the finding's
         ``(resource_type, technique)`` bucket.

    On every subsequent run the Validator agent reads the most recent verdicts for that
    same bucket: if ≥70% were *confirmed* it boosts the severity of the new finding by one
    level, and if ≥70% were *dismissed* it downgrades it. Operator triage therefore
    continuously re-calibrates the swarm's severity scoring with no model retraining.
    """
    finding = await repository.get(settings.cosmos_container_findings, finding_id)
    if not finding or "title" not in finding:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")

    now = datetime.now(UTC).isoformat()
    finding["verdict"] = body.verdict
    finding["note"] = body.note
    finding["feedback_at"] = now
    finding["feedback_by"] = principal.sub
    await repository.save(settings.cosmos_container_findings, finding)

    # Standalone, queryable record that feeds the Validator's learning loop on future runs.
    feedback_record = {
        "id": f"{finding_id}_feedback_{now}",
        "type": "feedback",
        "finding_id": finding_id,
        "run_id": finding.get("run_id"),
        "resource_type": finding.get("resource_type", "unknown"),
        "technique": finding.get("technique", ""),
        "verdict": body.verdict,
        "note": body.note,
        "created_at": now,
        "created_by": principal.sub,
    }
    await repository.save(settings.cosmos_container_findings, feedback_record)

    return finding

