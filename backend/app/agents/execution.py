"""Execution Agent — runs ONLY security-approved steps in a hard Azure Functions sandbox."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.cosmos import repository


class ExecutionAgent(BaseAgent):
    agent_id = "execution"
    role = "Sandbox payload test"
    completion_event = "breachsim.exec.completed"
    system_prompt = (
        "You are the Execution Agent operating in a hard sandbox. Execute ONLY the explicitly "
        "approved steps via the sandbox tool. Capture evidence for each. If a tool indicates an "
        "out-of-scope target, abort and emit a guardrail violation. Never improvise new steps."
    )

    async def run_sandbox_payload(self, step: dict[str, Any]) -> dict[str, Any]:
        """Produce the outcome for one approved step.

        BreachSim does NOT execute live exploits. Each step is *modeled*: we record the
        expected outcome of the technique against the target so analysts can reason about
        the kill chain without any real-world action. A future, opt-in sandbox (isolated
        Azure Functions on a private VNet) could replace this with real, contained
        execution — until then every result is explicitly labelled ``mode="modeled"`` so
        the UI and reports never overstate what happened.
        """
        modeled = {
            "T1595": "Public endpoint reachable: https://stbreachdemo.blob.core.windows.net/configs",
            "T1530": "Anonymous container read would expose appsettings.json (connection string)",
            "T1078": "Leaked credential would authenticate to kv-breach-demo (4 secrets readable)",
        }
        return {
            "order": step["order"],
            "technique": step["technique"],
            "mode": "modeled",
            "result": modeled.get(step["technique"], "outcome modeled (no live execution)"),
            "success": True,
            "artifactRef": f"blob://artifacts/{step['order']}.json",
        }

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        plan = ctx.blackboard.get("plan", {"steps": []})
        approved = set(ctx.blackboard.get("approved_steps", []))
        results = []
        for step in plan["steps"]:
            if step["order"] not in approved:
                continue  # guardrail: never execute unapproved steps
            res = await self.run_sandbox_payload(step)
            results.append(res)
            await repository.save(
                settings.cosmos_container_audit,
                {
                    "id": f"{ctx.run_id}_aud_{step['order']}",
                    "run_id": ctx.run_id,
                    "actor": self.agent_id,
                    "action": "modeled_step",
                    "before": None,
                    "after": res,
                },
            )
        ctx.blackboard["exec_results"] = results
        await self.emit(
            ctx, f"{len(results)} steps modeled (no live execution)", {"results": results}
        )
        return {"results": results}
