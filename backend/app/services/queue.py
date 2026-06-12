"""Durable run queue — publishes swarm runs to an Azure Service Bus queue.

When ``AZURE_SERVICE_BUS_CONNECTION_STRING`` is unset (local/dev), publishing is a
no-op and callers fall back to in-process execution, so the full swarm still runs
end-to-end without any cloud dependencies.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def send_run_to_queue(run_id: str, tenant_id: str, payload: dict[str, Any]) -> bool:
    """Publish a swarm run to the durable Service Bus queue.

    Args:
        run_id: The run identifier (used as the Service Bus ``message_id`` so that
            duplicate detection, if enabled on the queue, deduplicates retries).
        tenant_id: The owning tenant; carried in the message body for the worker.
        payload: Run inputs (e.g. ``{"name": ..., "scope": {...}}``) the worker
            passes to the orchestrator.

    Returns:
        ``True`` if the message was enqueued; ``False`` when Service Bus is not
        configured, in which case the caller should run the swarm in-process.
    """
    if not settings.service_bus_enabled:
        return False

    # Lazy import so local/dev mode does not require the azure-servicebus SDK.
    from azure.servicebus import ServiceBusMessage
    from azure.servicebus.aio import ServiceBusClient

    body = json.dumps({"runId": run_id, "tenantId": tenant_id, "payload": payload})
    try:
        async with ServiceBusClient.from_connection_string(
            settings.azure_service_bus_connection_string
        ) as client:
            sender = client.get_queue_sender(settings.azure_service_bus_queue_name)
            async with sender:
                await sender.send_messages(
                    ServiceBusMessage(
                        body,
                        message_id=run_id,
                        content_type="application/json",
                        application_properties={"tenantId": tenant_id},
                    )
                )
        logger.info(
            "Queued run for durable execution.",
            extra={"run_id": run_id, "trace_id": tenant_id},
        )
        return True
    except Exception:  # noqa: BLE001
        # Never let a transient queue error drop the run — fall back to in-process.
        logger.warning(
            "Failed to enqueue run; falling back to in-process execution.",
            extra={"run_id": run_id},
            exc_info=True,
        )
        return False
