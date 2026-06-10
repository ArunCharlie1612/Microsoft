"""Orchestrator — drives the swarm state machine and fans out events.

State machine:
  RECON → RESEARCH → PLAN → SECURITY_REVIEW → EXECUTE → VALIDATE → RISK
        → (COMPLIANCE ∥ REMEDIATION) → REPORT
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.base import AgentContext
from app.agents.compliance import ComplianceAgent
from app.agents.execution import ExecutionAgent
from app.agents.memory import MemoryAgent
from app.agents.planner import PlannerAgent
from app.agents.recon import ReconAgent
from app.agents.remediation import RemediationAgent
from app.agents.research import ResearchAgent
from app.agents.risk import RiskAgent
from app.agents.security import SecurityAgent
from app.agents.validator import ValidatorAgent
from app.config import settings
from app.core.events import event_bus
from app.core.logging import get_logger
from app.models.schemas import RunPhase

logger = get_logger(__name__)


class SwarmOrchestrator:
    """Coordinates the agent swarm for a single run."""

    def __init__(self) -> None:
        self.recon = ReconAgent()
        self.research = ResearchAgent()
        self.planner = PlannerAgent()
        self.security = SecurityAgent()
        self.execution = ExecutionAgent()
        self.validator = ValidatorAgent()
        self.risk = RiskAgent()
        self.compliance = ComplianceAgent()
        self.remediation = RemediationAgent()
        self.memory = MemoryAgent()

    async def _phase(self, run_id: str, phase: RunPhase, progress: float) -> None:
        # Demo pacing: brief pause between phases so the live agent feed/graph is
        # watchable even when agents return instantly (stub mode). 0 in production.
        if settings.breachsim_demo_pacing_ms > 0:
            await asyncio.sleep(settings.breachsim_demo_pacing_ms / 1000)
        await event_bus.publish(
            run_id,
            "breachsim.phase.changed",
            {
                "agentId": "orchestrator",
                "phase": phase.value,
                "progress": progress,
                "summary": f"Phase: {phase.value}",
            },
        )

    async def run(self, run_id: str, scope: dict[str, Any]) -> dict[str, Any]:
        ctx = AgentContext(run_id, scope)
        await event_bus.publish(
            run_id,
            "breachsim.run.started",
            {"agentId": "orchestrator", "summary": "Swarm deployed into target tenant"},
        )
        try:
            await self._phase(run_id, RunPhase.RECON, 0.1)
            await self.recon.run(ctx)

            await self._phase(run_id, RunPhase.PLAN, 0.25)
            await self.research.run(ctx)
            await self.planner.run(ctx)

            await self._phase(run_id, RunPhase.SECURITY_REVIEW, 0.4)
            await self.security.run(ctx)

            await self._phase(run_id, RunPhase.EXECUTE, 0.55)
            await self.execution.run(ctx)

            await self._phase(run_id, RunPhase.VALIDATE, 0.7)
            await self.validator.run(ctx)

            await self._phase(run_id, RunPhase.RISK, 0.8)
            await self.risk.run(ctx)

            # Parallel fan-out: compliance + remediation run concurrently.
            await self._phase(run_id, RunPhase.COMPLIANCE, 0.9)
            await asyncio.gather(self.compliance.run(ctx), self.remediation.run(ctx))

            await self._phase(run_id, RunPhase.REPORT, 0.97)
            result = await self.memory.run(ctx)

            await event_bus.publish(
                run_id,
                "breachsim.run.completed",
                {
                    "agentId": "orchestrator",
                    "summary": "Run complete — remediation PR opened",
                    "progress": 1.0,
                },
            )
            result["stats"] = {
                "resources": len(ctx.blackboard.get("resources", [])),
                "findings": 1 if ctx.blackboard.get("risk") else 0,
                "tokens_used": ctx.tokens_used,
            }
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("run failed", extra={"run_id": run_id})
            await event_bus.publish(
                run_id,
                "breachsim.run.completed",
                {"agentId": "orchestrator", "status": "failed", "summary": f"Run failed: {exc}"},
            )
            raise


orchestrator = SwarmOrchestrator()
