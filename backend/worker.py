"""BreachSim durable run worker.

Consumes swarm-run messages from the Azure Service Bus queue and executes each run
via the existing orchestrator, so an API/Container App restart never drops an
in-flight simulation. Run as a separate process / Container App:

    python worker.py

Requires ``AZURE_SERVICE_BUS_CONNECTION_STRING`` to be set. Outcomes are logged to
Azure Application Insights when ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set.
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any

from app.config import settings
from app.core.cosmos import repository
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_telemetry
from app.services.run_manager import run_manager
from app.services.tenant_manager import tenant_manager

configure_logging()
configure_telemetry()
logger = get_logger(__name__)

# Renew the message lock for up to 5 minutes while a run executes.
MAX_LOCK_DURATION = timedelta(minutes=5)
# Pull one message at a time so a slow run does not starve others' lock renewal.
PREFETCH_COUNT = 1
# Dead-letter a message after this many delivery attempts.
MAX_DELIVERY_COUNT = 3


def _parse_message(raw: str) -> tuple[str, str, dict[str, Any]]:
    """Deserialize a queue message into ``(run_id, tenant_id, payload)``."""
    data = json.loads(raw)
    return data["runId"], data.get("tenantId", "local"), data["payload"]


async def _process_one(receiver, msg) -> None:  # noqa: ANN001
    """Execute a single run; complete on success, dead-letter after retries."""
    from azure.servicebus.aio import AutoLockRenewer

    run_id, tenant_id, payload = _parse_message(str(msg))
    renewer = AutoLockRenewer(max_lock_renewal_duration=MAX_LOCK_DURATION.total_seconds())
    try:
        renewer.register(receiver, msg)
        status = await run_manager.execute_from_message(run_id, tenant_id, payload)
        await receiver.complete_message(msg)
        logger.info(
            "Run executed successfully.",
            extra={"run_id": run_id, "trace_id": tenant_id, "event_type": status.value},
        )
    except Exception:  # noqa: BLE001
        delivery_count = msg.delivery_count or 1
        if delivery_count >= MAX_DELIVERY_COUNT:
            await receiver.dead_letter_message(
                msg, reason="MaxRetriesExceeded", error_description="Swarm run failed 3x"
            )
            logger.error(
                "Run dead-lettered after %d attempts.",
                delivery_count,
                extra={"run_id": run_id, "trace_id": tenant_id, "event_type": "dead_lettered"},
                exc_info=True,
            )
        else:
            await receiver.abandon_message(msg)
            logger.warning(
                "Run failed (attempt %d); message abandoned for retry.",
                delivery_count,
                extra={"run_id": run_id, "trace_id": tenant_id},
                exc_info=True,
            )
    finally:
        await renewer.close()


async def main() -> None:
    if not settings.service_bus_enabled:
        raise SystemExit(
            "AZURE_SERVICE_BUS_CONNECTION_STRING is not set — nothing to consume. "
            "The API runs swarms in-process in local/dev mode."
        )

    from azure.servicebus.aio import ServiceBusClient

    await repository.connect()
    await tenant_manager.load()
    await run_manager.load()
    logger.info(
        "Worker listening on Service Bus queue.",
        extra={"trace_id": settings.azure_service_bus_queue_name},
    )

    async with ServiceBusClient.from_connection_string(
        settings.azure_service_bus_connection_string
    ) as client:
        receiver = client.get_queue_receiver(
            settings.azure_service_bus_queue_name, prefetch_count=PREFETCH_COUNT
        )
        async with receiver:
            while True:
                messages = await receiver.receive_messages(
                    max_message_count=1, max_wait_time=30
                )
                for msg in messages:
                    await _process_one(receiver, msg)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped.")
