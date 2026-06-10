"""Planner Agent — reasons over recon + CVE evidence to compose an attack chain."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.cosmos import repository


class PlannerAgent(BaseAgent):
    agent_id = "planner"
    role = "Chains exploit paths via GPT-4o reasoning"
    completion_event = "breachsim.plan.ready"
    system_prompt = (
        "You are the Planner Agent of an authorized red-team swarm operating ONLY in a consented "
        "sandbox. Given reconnaissance of the target and grounded CVE context, compose the most "
        "plausible multi-step attack chain an elite adversary would attempt. Output strict JSON: "
        '{"steps": [{"order", "technique" (MITRE ATT&CK ID), "target_asset", '
        '"precondition", "expected_effect", "confidence"}], "narrative"}. Prefer chains '
        "that escalate privilege or reach sensitive data. Never propose actions outside scope."
    )

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        resources = ctx.blackboard.get("resources", [])
        evidence = ctx.blackboard.get("cve_evidence", [])
        prompt = (
            f"Resources: {resources}\nCVE evidence: {evidence}\n"
            "Compose the highest-confidence attack chain."
        )
        fallback = {
            "steps": [
                {
                    "order": 1,
                    "technique": "T1595",
                    "target_asset": "stbreachdemo",
                    "precondition": "public endpoint reachable",
                    "expected_effect": "discover anonymous-readable container",
                    "confidence": 0.95,
                },
                {
                    "order": 2,
                    "technique": "T1530",
                    "target_asset": "container:configs",
                    "precondition": "anonymous read enabled",
                    "expected_effect": "download appsettings.json with connection string",
                    "confidence": 0.9,
                },
                {
                    "order": 3,
                    "technique": "T1078",
                    "target_asset": "kv-breach-demo",
                    "precondition": "leaked credential valid",
                    "expected_effect": "authenticate to Key Vault, read secrets",
                    "confidence": 0.78,
                },
            ],
            "narrative": (
                "Internet → public blob (anonymous read) → leaked connection string → "
                "Key Vault access via over-privileged identity."
            ),
        }
        plan = await self.reason(prompt, fallback=fallback, temperature=0.3)

        # Build a coherent kill-chain in the threat graph: an adversary origin node linked
        # through each step's target asset. Reuse recon's resource nodes where the asset
        # matches; create a node on the fly for assets recon didn't enumerate. Every edge
        # endpoint is guaranteed to exist as a node (prevents orphan-edge render crashes).
        resource_node_ids: dict[str, str] = dict(ctx.blackboard.get("resource_node_ids", {}))

        actor_node_id = f"{ctx.run_id}_actor"
        await repository.save(
            settings.cosmos_container_threatgraph,
            {
                "id": actor_node_id,
                "run_id": ctx.run_id,
                "kind": "node",
                "nodeKind": "actor",
                "label": "Adversary",
                "props": {"origin": "internet"},
            },
        )

        prev_node_id = actor_node_id
        for step in plan["steps"]:
            asset = step["target_asset"]
            asset_node_id = resource_node_ids.get(asset)
            if asset_node_id is None:
                # Asset not surfaced by recon (e.g. a sub-resource) — materialize a node.
                asset_node_id = f"{ctx.run_id}_asset_{step['order']}"
                resource_node_ids[asset] = asset_node_id
                await repository.save(
                    settings.cosmos_container_threatgraph,
                    {
                        "id": asset_node_id,
                        "run_id": ctx.run_id,
                        "kind": "node",
                        "nodeKind": "resource",
                        "label": asset,
                        "props": {"derived": True},
                    },
                )
            await repository.save(
                settings.cosmos_container_threatgraph,
                {
                    "id": f"{ctx.run_id}_edge_{step['order']}",
                    "run_id": ctx.run_id,
                    "kind": "edge",
                    "fromNode": prev_node_id,
                    "toNode": asset_node_id,
                    "relation": step["technique"],
                    "confidence": step.get("confidence", 0.5),
                },
            )
            prev_node_id = asset_node_id
        ctx.blackboard["plan"] = plan
        await self.emit(ctx, plan["narrative"], {"stepCount": len(plan["steps"])})
        return plan
