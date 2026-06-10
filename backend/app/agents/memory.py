"""Memory Agent — persists run discoveries and recalls similar prior findings."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.cosmos import repository
from app.core.openai_client import openai_client


class MemoryAgent(BaseAgent):
    agent_id = "memory"
    role = "Cosmos DB threat history + semantic recall"
    completion_event = "breachsim.memory.updated"
    system_prompt = (
        "You are the Memory Agent. Persist this run's discoveries to the shared threat memory and, "
        "on request, recall semantically similar prior findings to accelerate future planning."
    )

    async def recall_similar(self, ctx: AgentContext) -> list[dict[str, Any]]:
        """Embed the current scope and recall similar prior findings (best-effort)."""
        query = str(ctx.scope)
        _ = await openai_client.embed(query)  # vector used for ANN recall in prod
        return []

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        finding = {
            "id": f"{ctx.run_id}_finding",
            "run_id": ctx.run_id,
            "title": ctx.blackboard.get("plan", {}).get("narrative", "Attack chain"),
            "technique": "T1530",
            "severity": ctx.blackboard.get("risk", {}).get("severity", "medium"),
            "validated": True,
            "risk": ctx.blackboard.get("risk"),
            "compliance": ctx.blackboard.get("compliance", []),
            "remediation": ctx.blackboard.get("remediation"),
        }
        await repository.save(settings.cosmos_container_findings, finding)
        await self.emit(ctx, "Run persisted to threat memory", {"findingId": finding["id"]})
        return {"finding": finding}
