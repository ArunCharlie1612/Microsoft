"""Compliance Agent — maps findings to NIST 800-53 / SOC 2 / ISO 27001 controls."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.cosmos import repository
from app.core.scoring import map_compliance


class ComplianceAgent(BaseAgent):
    agent_id = "compliance"
    role = "Generates NIST/SOC2 evidence"
    completion_event = "breachsim.compliance.generated"
    system_prompt = (
        "You are the Compliance Agent. Control mappings are derived deterministically from the "
        "validated techniques via an auditable crosswalk (no model guessing)."
    )

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        validations = ctx.blackboard.get("validations", [])
        techniques = [
            v.get("technique") for v in validations if v.get("validated") and v.get("technique")
        ]
        # Deterministic, auditable technique → control crosswalk.
        records = map_compliance(techniques)
        out = {"records": records}
        for i, rec in enumerate(records):
            await repository.save(
                settings.cosmos_container_findings,
                {"id": f"{ctx.run_id}_comp_{i}", "run_id": ctx.run_id, "type": "compliance", **rec},
            )
        ctx.blackboard["compliance"] = records
        frameworks = sorted({r["framework"] for r in records})
        await self.emit(ctx, f"Evidence across {', '.join(frameworks)}", {"records": records})
        return out
