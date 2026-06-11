"""Run lifecycle manager — tracks run state and launches the swarm."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from app.agents.orchestrator import orchestrator
from app.config import settings
from app.core.cosmos import repository
from app.core.logging import get_logger
from app.models.schemas import (
    AgentState,
    AgentStatus,
    CreateRunRequest,
    RunDetail,
    RunStats,
    RunStatus,
)

logger = get_logger(__name__)

_AGENT_IDS = [
    "recon",
    "research",
    "planner",
    "security",
    "execution",
    "validator",
    "risk",
    "compliance",
    "remediation",
    "memory",
]


class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, RunDetail] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._bg: set[asyncio.Task] = set()

    async def load(self) -> None:
        """Hydrate the in-memory cache from Cosmos so runs survive restarts."""
        try:
            docs = await repository.list_all(settings.cosmos_container_runs)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load persisted runs (continuing empty).", exc_info=True)
            return
        for doc in docs:
            try:
                detail = RunDetail.model_validate(doc)
            except Exception:  # noqa: BLE001
                continue
            # A run still marked RUNNING means the process died mid-run; mark it failed.
            if detail.status in (RunStatus.RUNNING, RunStatus.QUEUED):
                detail.status = RunStatus.FAILED
            self._runs[detail.run_id] = detail
        if self._runs:
            logger.info("Loaded %d persisted run(s) from Cosmos.", len(self._runs))

    async def _persist(self, detail: RunDetail) -> None:
        """Write-through persist a run's current state to Cosmos (best-effort)."""
        try:
            doc = detail.model_dump(mode="json", by_alias=True)
            doc["id"] = detail.run_id
            await repository.save(settings.cosmos_container_runs, doc)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to persist run %s.", detail.run_id, exc_info=True)

    def create(self, req: CreateRunRequest, tenant_id: str = "local") -> RunDetail:
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        detail = RunDetail(
            runId=run_id,
            name=req.name,
            status=RunStatus.QUEUED,
            tenantId=tenant_id,
            agents=[AgentState(agentId=a) for a in _AGENT_IDS],
            stats=RunStats(),
        )
        self._runs[run_id] = detail
        scope = req.scope.model_dump(by_alias=False)
        persist_task = asyncio.create_task(self._persist(detail))
        self._bg.add(persist_task)
        persist_task.add_done_callback(self._bg.discard)
        self._tasks[run_id] = asyncio.create_task(self._execute(run_id, scope))
        return detail

    async def _execute(self, run_id: str, scope: dict) -> None:
        detail = self._runs[run_id]
        detail.status = RunStatus.RUNNING
        detail.started_at = datetime.now(UTC)
        await self._persist(detail)
        try:
            result = await orchestrator.run(run_id, scope)
            detail.status = RunStatus.COMPLETED
            detail.progress = 1.0
            for a in detail.agents:
                a.status = AgentStatus.COMPLETED
            stats = (result or {}).get("stats", {})
            detail.stats = RunStats(
                resources=stats.get("resources", 0),
                findings=stats.get("findings", 0),
                tokensUsed=stats.get("tokens_used", 0),
                estimatedCostUsd=stats.get("estimated_cost_usd", 0.0),
            )
        except Exception:  # noqa: BLE001
            detail.status = RunStatus.FAILED
        finally:
            detail.completed_at = datetime.now(UTC)
            await self._persist(detail)

    def get(self, run_id: str) -> RunDetail | None:
        return self._runs.get(run_id)

    def list(self, tenant_id: str | None = None) -> list[RunDetail]:
        runs = self._runs.values()
        if tenant_id is not None:
            runs = [r for r in runs if r.tenant_id == tenant_id]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    async def cancel(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            self._runs[run_id].status = RunStatus.CANCELLED
            await self._persist(self._runs[run_id])
            return True
        return False


run_manager = RunManager()
