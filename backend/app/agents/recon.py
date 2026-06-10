"""Recon Agent — maps the attack surface (resources, identities, exposure)."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.cosmos import repository


class ReconAgent(BaseAgent):
    agent_id = "recon"
    role = "Maps attack surface"
    completion_event = "breachsim.recon.completed"
    system_prompt = (
        "You are the Recon Agent of an authorized red-team swarm operating ONLY in a consented "
        "sandbox. Enumerate the target's cloud resources, identities, and public exposure. "
        'Return strict JSON: {"resources": [{"name", "type", "publicExposure", '
        '"config"}], "summary"}.'
    )

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        prompt = (
            f"Reconnaissance scope: {ctx.scope}. Enumerate likely resources and flag public "
            "exposure and over-privileged identities."
        )
        fallback = {
            "resources": [
                {
                    "name": "stbreachdemo",
                    "type": "Microsoft.Storage/storageAccounts",
                    "publicExposure": True,
                    "config": {"allowBlobPublicAccess": True, "container": "configs"},
                },
                {
                    "name": "id-app-runtime",
                    "type": "Microsoft.ManagedIdentity",
                    "publicExposure": False,
                    "config": {"roles": ["Storage Blob Data Contributor", "Key Vault Reader"]},
                },
                {
                    "name": "kv-breach-demo",
                    "type": "Microsoft.KeyVault/vaults",
                    "publicExposure": False,
                    "config": {"networkAcls": "Allow"},
                },
            ],
            "summary": (
                "12 resources, 1 public blob with anonymous read, 1 over-privileged identity"
            ),
        }
        result = await self.reason(prompt, fallback=fallback)

        # Persist resources + threat-graph nodes. Track a name -> node-id map so the
        # Planner can wire the attack chain to these exact nodes (avoids orphan edges).
        resource_node_ids: dict[str, str] = {}
        for i, r in enumerate(result["resources"]):
            node_id = f"{ctx.run_id}_node_{i}"
            resource_node_ids[r["name"]] = node_id
            await repository.save(
                settings.cosmos_container_threatgraph,
                {
                    "id": node_id,
                    "run_id": ctx.run_id,
                    "kind": "node",
                    "nodeKind": "resource",
                    "label": r["name"],
                    "props": {
                        "publicExposure": r.get("publicExposure", False),
                        **r.get("config", {}),
                    },
                },
            )
        ctx.blackboard["resources"] = result["resources"]
        ctx.blackboard["resource_node_ids"] = resource_node_ids
        await self.emit(ctx, result["summary"], {"resourceCount": len(result["resources"])})
        return result
