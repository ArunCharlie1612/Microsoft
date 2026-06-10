"""Risk Agent — assigns CVSS-style severity and business impact to validated findings."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent


class RiskAgent(BaseAgent):
    agent_id = "risk"
    role = "Scores severity + business impact"
    completion_event = "breachsim.risk.scored"
    system_prompt = (
        "You are the Risk Agent. Assign severity and business impact to each validated finding, "
        "factoring asset criticality and exploit-chain depth. Output strict JSON: "
        '{"cvss": float, "severity": one of info|low|medium|high|critical, '
        '"business_impact": string, "rationale": string}.'
    )

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        validations = ctx.blackboard.get("validations", [])
        prompt = f"Validated chain: {validations}. Score the overall finding."
        fallback = {
            "cvss": 9.1,
            "severity": "critical",
            "business_impact": "high",
            "rationale": "Anonymous blob access chained to Key Vault secret disclosure.",
        }
        risk = await self.reason(prompt, fallback=fallback)
        ctx.blackboard["risk"] = risk
        await self.emit(ctx, f"CVSS {risk['cvss']} ({risk['severity']})", {"risk": risk})
        return risk
