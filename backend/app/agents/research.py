"""Research Agent — RAG over the CVE/ATT&CK vector index (Azure AI Search)."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.logging import get_logger
from app.core.nvd import search_cves

logger = get_logger(__name__)


class ResearchAgent(BaseAgent):
    agent_id = "research"
    role = "Grounds planning in real CVE/ATT&CK evidence"
    completion_event = "breachsim.research.completed"
    system_prompt = (
        "You are the Research Agent. Retrieve and synthesize authoritative CVE/CWE/ATT&CK context "
        "for the requested techniques. Cite source IDs. Never speculate beyond retrieved evidence."
    )

    async def search_cve_index(self, query: str, top: int = 3) -> list[dict[str, Any]]:
        """Retrieve grounding CVE evidence.

        Priority: (1) Azure AI Search CVE index if configured, (2) live NVD lookup,
        (3) a clearly-labelled illustrative fallback so a run never blocks on evidence.
        """
        if settings.azure_search_endpoint:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents.aio import SearchClient

            client = SearchClient(
                settings.azure_search_endpoint,
                settings.azure_search_index,
                AzureKeyCredential(settings.azure_search_api_key),
            )
            results = []
            async with client:
                async for doc in await client.search(
                    search_text=query, top=top, query_type="semantic"
                ):
                    results.append(dict(doc))
            if results:
                return results

        # No search index — try the real NVD database before any placeholder.
        # Skip the live lookup in local/offline mode so dev and tests stay network-free.
        if not settings.is_local:
            nvd = await search_cves(query, top=top)
            if nvd:
                return nvd

        return [
            {
                "id": "ILLUSTRATIVE-0001",
                "title": "Illustrative: anonymous blob access enables data exfiltration",
                "technique": "T1530",
                "source": "fallback",
                "note": "No CVE source configured; example evidence only.",
            }
        ]

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        resources = ctx.blackboard.get("resources", [])
        query = " ".join(r["type"] for r in resources) or "cloud misconfiguration"
        evidence = await self.search_cve_index(query)
        ctx.blackboard["cve_evidence"] = evidence
        await self.emit(ctx, f"{len(evidence)} CVE references retrieved", {"evidence": evidence})
        return {"evidence": evidence}
