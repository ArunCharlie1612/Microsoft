"""Run lifecycle manager — tracks run state and launches the swarm."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from app.agents.orchestrator import orchestrator
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

    def create(self, req: CreateRunRequest) -> RunDetail:
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        detail = RunDetail(
            runId=run_id,
            name=req.name,
            status=RunStatus.QUEUED,
            agents=[AgentState(agentId=a) for a in _AGENT_IDS],
            stats=RunStats(),
        )
        self._runs[run_id] = detail
        scope = req.scope.model_dump(by_alias=False)
        self._tasks[run_id] = asyncio.create_task(self._execute(run_id, scope))
        return detail

    async def _execute(self, run_id: str, scope: dict) -> None:
        detail = self._runs[run_id]
        detail.status = RunStatus.RUNNING
        detail.started_at = datetime.now(UTC)
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
            )
        except Exception:  # noqa: BLE001
            detail.status = RunStatus.FAILED
        finally:
            detail.completed_at = datetime.now(UTC)

    def get(self, run_id: str) -> RunDetail | None:
        return self._runs.get(run_id)

    def list(self) -> list[RunDetail]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)

    async def cancel(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            self._runs[run_id].status = RunStatus.CANCELLED
            return True
        return False


run_manager = RunManager()
