"""Azure Event Grid publisher — the agent message bus.

Publishes CloudEvents for inter-agent communication. In local/demo mode events are
fanned out to an in-process asyncio bus so the SSE feed still works offline.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EventBus:
    """Hybrid Event Grid + in-process pub/sub bus keyed by runId.

    Keeps a bounded per-run history so that late subscribers (e.g. the frontend SSE
    connection that attaches just after a run starts) replay every event from the
    beginning. Without this, fast runs would complete before the UI subscribes and
    the agent feed/graph would appear empty.
    """

    _MAX_HISTORY = 500

    def __init__(self) -> None:
        self._enabled = bool(settings.eventgrid_topic_endpoint)
        self._client = None
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._completed: set[str] = set()

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        from azure.core.credentials import AzureKeyCredential
        from azure.eventgrid import EventGridPublisherClient

        self._client = EventGridPublisherClient(
            settings.eventgrid_topic_endpoint,
            AzureKeyCredential(settings.eventgrid_topic_key),
        )
        return self._client

    async def publish(self, run_id: str, event_type: str, data: dict[str, Any]) -> None:
        envelope = {
            "type": event_type,
            "source": f"breachsim/agents/{data.get('agentId', 'orchestrator')}",
            "subject": f"runs/{run_id}",
            "data": {"runId": run_id, **data},
        }
        if self._enabled:
            from azure.eventgrid import EventGridEvent

            client = self._ensure_client()
            client.send(
                EventGridEvent(
                    subject=envelope["subject"],
                    event_type=event_type,
                    data=envelope["data"],
                    data_version="1.0",
                )
            )
        # Always fan out locally for SSE
        for q in self._subscribers.get(run_id, []):
            await q.put(envelope)

        # Retain history for late subscribers (replay) and mark terminal state.
        hist = self._history.setdefault(run_id, [])
        hist.append(envelope)
        if len(hist) > self._MAX_HISTORY:
            del hist[: len(hist) - self._MAX_HISTORY]
        if event_type == "breachsim.run.completed":
            self._completed.add(run_id)
        logger.info("event published", extra={"run_id": run_id, "event_type": event_type})

    async def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(q)
        try:
            # Replay any events that fired before this subscriber attached.
            replayed_completed = False
            for past in list(self._history.get(run_id, [])):
                yield past
                if past["type"] == "breachsim.run.completed":
                    replayed_completed = True
            if replayed_completed:
                return

            while True:
                event = await q.get()
                yield event
                if event["type"] == "breachsim.run.completed":
                    break
        finally:
            subs = self._subscribers.get(run_id, [])
            if q in subs:
                subs.remove(q)

    def reset(self, run_id: str) -> None:
        """Drop retained history for a run (call when re-running a demo id)."""
        self._history.pop(run_id, None)
        self._completed.discard(run_id)


event_bus = EventBus()
