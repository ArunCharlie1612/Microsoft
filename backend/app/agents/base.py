"""Base agent abstraction.

Every BreachSim agent is an Azure AI Foundry-backed worker with a narrow role,
an allow-listed tool set, and a single responsibility. Agents never call each other
directly — they emit events through the EventBus and write to Cosmos.
"""

from __future__ import annotations

import abc
from typing import Any

from app.core.events import event_bus
from app.core.logging import get_logger
from app.core.openai_client import openai_client

logger = get_logger(__name__)


def _coerce_summary(summary: Any) -> str:
    """Ensure an event summary is always a human-readable string.

    The LLM occasionally returns a structured object (e.g. a dict of metrics) for a
    field the prompt described as a free-text summary. Rendering such an object would
    crash the React client, so we flatten it to a compact, readable string here.
    """
    if isinstance(summary, str):
        return summary
    if isinstance(summary, dict):
        return ", ".join(f"{k}: {v}" for k, v in summary.items())
    if isinstance(summary, (list, tuple)):  # noqa: UP038
        return ", ".join(str(item) for item in summary)
    return str(summary)


class AgentContext:
    """Shared, run-scoped context passed between agents via the orchestrator."""

    def __init__(self, run_id: str, scope: dict[str, Any]) -> None:
        self.run_id = run_id
        self.scope = scope
        self.blackboard: dict[str, Any] = {}  # shared working memory for the run
        self.tokens_used = 0


class BaseAgent(abc.ABC):
    #: Stable agent identifier used in events, audit log, and the tool matrix.
    agent_id: str = "base"
    #: Human-readable role description.
    role: str = ""
    #: System prompt sent to GPT-4o.
    system_prompt: str = ""
    #: Event type emitted on successful completion.
    completion_event: str = "breachsim.agent.completed"

    async def emit(self, ctx: AgentContext, summary: Any, payload: dict[str, Any]) -> None:
        await event_bus.publish(
            ctx.run_id,
            self.completion_event,
            {"agentId": self.agent_id, "summary": _coerce_summary(summary), **payload},
        )

    async def reason(
        self, user_prompt: str, *, fallback: Any = None, temperature: float = 0.2
    ) -> Any:
        return await openai_client.reason_json(
            self.system_prompt, user_prompt, temperature=temperature, fallback=fallback
        )

    @abc.abstractmethod
    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        """Execute the agent's task and return a result dict for the blackboard."""
        raise NotImplementedError
