"""Execution Agent — runs ONLY security-approved steps in a hard Azure Functions sandbox."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.cosmos import repository
from app.core.validation_probe import probe_public_endpoint, storage_account_url


class ExecutionAgent(BaseAgent):
    agent_id = "execution"
    role = "Sandbox payload test"
    completion_event = "breachsim.exec.completed"
    system_prompt = (
        "You are the Execution Agent operating in a hard sandbox. Execute ONLY the explicitly "
        "approved steps via the sandbox tool. Capture evidence for each. If a tool indicates an "
        "out-of-scope target, abort and emit a guardrail violation. Never improvise new steps."
    )

    def _reachability_target(self, ctx: AgentContext, step: dict[str, Any]) -> str | None:
        """Derive a public URL to *read-only* probe for an exposure-discovery step.

        Only reachability (technique T1595) is ever probed live, and only for resources
        recon already flagged as publicly exposed. Data-access / credential techniques
        are never executed live — they remain modeled.
        """
        if step.get("technique") != "T1595":
            return None
        target_asset = step.get("target_asset", "")
        for r in ctx.blackboard.get("resources", []):
            if not r.get("publicExposure"):
                continue
            if target_asset and target_asset not in (r.get("name", ""), r.get("type", "")):
                continue
            rtype = (r.get("type") or "").lower()
            if rtype == "microsoft.storage/storageaccounts":
                return storage_account_url(r["name"])
        return None

    async def run_sandbox_payload(
        self, ctx: AgentContext, step: dict[str, Any]
    ) -> dict[str, Any]:
        """Produce the outcome for one approved step.

        When ``breachsim_active_validation`` is enabled, exposure-discovery steps run a
        *real, read-only* reachability probe (no exploitation). Every other step — and
        all steps when active validation is off — is *modeled*: we record the expected
        outcome of the technique so analysts can reason about the kill chain without any
        real-world action. Results are explicitly labelled (``mode``) so the UI and
        reports never overstate what happened.
        """
        if settings.breachsim_active_validation:
            target = self._reachability_target(ctx, step)
            if target:
                probe = await probe_public_endpoint(target)
                return {
                    "order": step["order"],
                    "technique": step["technique"],
                    "mode": "active-validation",
                    "result": f"{probe['note']} ({target} → {probe['status']})",
                    "success": bool(probe["reachable"]),
                    "evidence": probe,
                    "artifactRef": f"probe://{step['order']}.json",
                }

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
        live_count = 0
        for step in plan["steps"]:
            if step["order"] not in approved:
                continue  # guardrail: never execute unapproved steps
            res = await self.run_sandbox_payload(ctx, step)
            if res.get("mode") == "active-validation":
                live_count += 1
            results.append(res)
            await repository.save(
                settings.cosmos_container_audit,
                {
                    "id": f"{ctx.run_id}_aud_{step['order']}",
                    "run_id": ctx.run_id,
                    "actor": self.agent_id,
                    "action": res.get("mode", "modeled_step"),
                    "before": None,
                    "after": res,
                },
            )
        ctx.blackboard["exec_results"] = results
        if live_count:
            summary = (
                f"{len(results)} steps processed "
                f"({live_count} confirmed via read-only validation, rest modeled)"
            )
        else:
            summary = f"{len(results)} steps modeled (no live execution)"
        await self.emit(ctx, summary, {"results": results})
        return {"results": results}
