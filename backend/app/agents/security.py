"""Security Agent — the swarm's safety brake. Approves or vetoes planned steps."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings


class SecurityAgent(BaseAgent):
    agent_id = "security"
    role = "Prevents scope creep; can veto any step"
    completion_event = "breachsim.security.reviewed"
    system_prompt = (
        "You are the Security Agent — the swarm's safety brake. Review each proposed step against "
        "the consented scope and blast-radius limits. Veto anything touching out-of-scope "
        "subscriptions, production data, or destructive operations. Output strict JSON: "
        '{"decisions": [{"order", "decision" (approve|veto), "reason"}]}. Your veto is final.'
    )

    def _destructive(self, technique: str) -> bool:
        return technique in {"T1485", "T1486", "T1490", "T1561"}  # data destruction families

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        plan = ctx.blackboard.get("plan", {"steps": []})
        sandbox_only = ctx.scope.get("sandbox_only", True)

        # Deterministic guardrails first (defense in depth), then model judgment.
        decisions = []
        for step in plan["steps"]:
            if settings.breachsim_sandbox_only and not sandbox_only:
                decisions.append(
                    {"order": step["order"], "decision": "veto", "reason": "non-sandbox target"}
                )
            elif self._destructive(step["technique"]):
                decisions.append(
                    {"order": step["order"], "decision": "veto", "reason": "destructive technique"}
                )
            else:
                decisions.append(
                    {
                        "order": step["order"],
                        "decision": "approve",
                        "reason": "in scope, non-destructive",
                    }
                )

        approved = [d["order"] for d in decisions if d["decision"] == "approve"]
        ctx.blackboard["approved_steps"] = approved
        ctx.blackboard["security_decisions"] = decisions
        vetoes = len(decisions) - len(approved)
        await self.emit(
            ctx,
            f"{len(approved)} approved, {vetoes} vetoed",
            {"approved": approved, "decisions": decisions},
        )
        return {"decisions": decisions, "approved": approved}
