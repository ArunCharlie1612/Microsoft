"""Validator Agent — independently confirms exploitability and rejects unproven claims."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent


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
                    "validated": bool(r.get("success")),
                    "reproduction": r.get("result", ""),
                }
                for r in results
            ]
        }
        out = await self.reason(prompt, fallback=fallback)
        validated = [v for v in out["validations"] if v["validated"]]
        ctx.blackboard["validations"] = out["validations"]
        await self.emit(
            ctx,
            f"{len(validated)}/{len(out['validations'])} steps validated",
            {"validated": validated},
        )
        return out
