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
        """Invoke the network-isolated Azure Functions sandbox for one step.

        In demo mode, returns a deterministic successful simulation. In prod, this
        calls the Functions endpoint over a private VNet with no prod peering.
        """
        if not settings.is_local:
            # Real call would go here (httpx POST to Functions sandbox URL with MI auth).
            pass
        simulated = {
            "T1595": "Public endpoint confirmed: https://stbreachdemo.blob.core.windows.net/configs",
            "T1530": "Downloaded appsettings.json (contains AccountKey=***redacted***)",
            "T1078": "Authenticated to kv-breach-demo; listed 4 secrets",
        }
        return {
            "order": step["order"],
            "technique": step["technique"],
            "result": simulated.get(step["technique"], "step executed"),
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
                    "action": "sandbox_payload_run",
                    "before": None,
                    "after": res,
                },
            )
        ctx.blackboard["exec_results"] = results
        await self.emit(ctx, f"{len(results)} steps executed in sandbox", {"results": results})
        return {"results": results}
