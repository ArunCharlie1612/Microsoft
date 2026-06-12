"""Validator Agent — independently confirms exploitability and rejects unproven claims."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.core.feedback import (
    primary_finding_key,
    recent_feedback,
    severity_adjustment,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class ValidatorAgent(BaseAgent):
    agent_id = "validator"
    role = "Confirms risk severity"
    completion_event = "breachsim.validation.completed"
    system_prompt = (
        "You are the Validator Agent. Independently confirm whether each executed step truly "
        "demonstrates the claimed vulnerability. Reject unproven claims. Output strict JSON: "
        '{"validations": [{"order", "validated" (bool), "reproduction"}]}.'
    )

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        results = ctx.blackboard.get("exec_results", [])
        prompt = f"Execution results to validate: {results}"
        fallback = {
            "validations": [
                {
                    "order": r["order"],
                    "technique": r.get("technique"),
                    "validated": bool(r.get("success")),
                    "reproduction": r.get("result", ""),
                }
                for r in results
            ]
        }
        out = await self.reason(prompt, fallback=fallback)
        # Ensure each validation carries its technique (the model may omit it) so the
        # deterministic risk scorer can weight the chain correctly.
        by_order = {r["order"]: r.get("technique") for r in results}
        for v in out.get("validations", []):
            v.setdefault("technique", by_order.get(v.get("order")))
        validated = [v for v in out["validations"] if v["validated"]]
        ctx.blackboard["validations"] = out["validations"]
        await self._apply_feedback_learning(ctx)
        await self.emit(
            ctx,
            f"{len(validated)}/{len(out['validations'])} steps validated",
            {"validated": validated},
        )
        return out

    async def _apply_feedback_learning(self, ctx: AgentContext) -> None:
        """Fold operator triage history into the upcoming severity decision.

        Before the Risk agent assigns final severity, query the last 10 operator verdicts
        for this finding's ``(resource_type, technique)`` bucket: ≥70% confirmed boosts the
        severity by one level, ≥70% dismissed downgrades it. The decision (delta + reason)
        is stashed on the blackboard for the Risk agent to apply and the Memory agent to
        log into the finding's evidence — keeping severity scoring deterministic.
        """
        resource_type, technique = primary_finding_key(ctx.blackboard)
        ctx.blackboard["finding_key"] = {
            "resource_type": resource_type,
            "technique": technique,
        }
        feedback = await recent_feedback(resource_type, technique)
        delta, reason = severity_adjustment(feedback)
        if delta != 0:
            ctx.blackboard["feedback_adjustment"] = {"delta": delta, "reason": reason}
            logger.info(
                "feedback severity adjustment",
                extra={"resource_type": resource_type, "technique": technique, "delta": delta},
            )
