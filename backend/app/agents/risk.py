"""Risk Agent — assigns CVSS-style severity and business impact to validated findings."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.core.feedback import shift_severity
from app.core.scoring import compute_risk


class RiskAgent(BaseAgent):
    agent_id = "risk"
    role = "Scores severity + business impact"
    completion_event = "breachsim.risk.scored"
    system_prompt = (
        "You are the Risk Agent. Severity is computed deterministically from the validated "
        "attack chain and grounded CVE evidence for auditability."
    )

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        validations = ctx.blackboard.get("validations", [])
        evidence = ctx.blackboard.get("cve_evidence", [])
        # Deterministic, reproducible scoring (no LLM guess) so the result is auditable.
        risk = compute_risk(validations, evidence)
        # Apply the operator-feedback learning signal computed by the Validator: a track
        # record of confirmations/dismissals for this (resource_type, technique) shifts the
        # severity one level. The reason is recorded for auditability.
        adjustment = ctx.blackboard.get("feedback_adjustment")
        if adjustment and adjustment.get("delta"):
            risk["severity"] = shift_severity(risk["severity"], adjustment["delta"])
            risk["feedback_adjustment"] = adjustment["reason"]
        ctx.blackboard["risk"] = risk
        await self.emit(ctx, f"CVSS {risk['cvss']} ({risk['severity']})", {"risk": risk})
        return risk
