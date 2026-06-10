"""Compliance Agent — maps findings to NIST 800-53 / SOC 2 / ISO 27001 controls."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.cosmos import repository


class ComplianceAgent(BaseAgent):
    agent_id = "compliance"
    role = "Generates NIST/SOC2 evidence"
    completion_event = "breachsim.compliance.generated"
    system_prompt = (
        "You are the Compliance Agent. Map each finding and its remediation to relevant "
        "NIST 800-53, SOC 2, and ISO 27001 controls. Produce audit-ready evidence. Output strict "
        'JSON: {"records": [{"framework", "control_id", "rationale"}]}.'
    )

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        risk = ctx.blackboard.get("risk", {})
        plan = ctx.blackboard.get("plan", {})
        prompt = f"Finding risk: {risk}\nAttack chain: {plan}\nMap to controls."
        fallback = {
            "records": [
                {
                    "framework": "NIST-800-53",
                    "control_id": "AC-3",
                    "rationale": "Access enforcement failure on public blob.",
                },
                {
                    "framework": "NIST-800-53",
                    "control_id": "SC-7",
                    "rationale": "Boundary protection bypass via anonymous access.",
                },
                {
                    "framework": "SOC2",
                    "control_id": "CC6.1",
                    "rationale": "Logical access controls not enforced.",
                },
                {
                    "framework": "ISO-27001",
                    "control_id": "A.9.4.1",
                    "rationale": "Information access restriction violated.",
                },
            ]
        }
        out = await self.reason(prompt, fallback=fallback)
        for i, rec in enumerate(out["records"]):
            await repository.save(
                settings.cosmos_container_findings,
                {"id": f"{ctx.run_id}_comp_{i}", "run_id": ctx.run_id, "type": "compliance", **rec},
            )
        ctx.blackboard["compliance"] = out["records"]
        frameworks = sorted({r["framework"] for r in out["records"]})
        await self.emit(
            ctx, f"Evidence across {', '.join(frameworks)}", {"records": out["records"]}
        )
        return out
