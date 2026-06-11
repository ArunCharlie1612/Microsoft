"""Optional Azure Monitor / Application Insights telemetry.

No-op unless ``applicationinsights_connection_string`` is configured, so local and
demo runs stay fully offline. When configured, wires OpenTelemetry traces, metrics
and logs to Application Insights via the azure-monitor-opentelemetry distro.
"""

from __future__ import annotations

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_configured = False


def configure_telemetry() -> None:
    global _configured
    if _configured or not settings.applicationinsights_connection_string:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        logger.warning("azure-monitor-opentelemetry not installed — telemetry disabled.")
        return
    try:
        configure_azure_monitor(
            connection_string=settings.applicationinsights_connection_string,
        )
        _configured = True
        logger.info("Application Insights telemetry enabled.")
    except Exception:  # noqa: BLE001
        logger.warning("Failed to configure Application Insights telemetry.", exc_info=True)


def instrument_app(app) -> None:  # noqa: ANN001
    """Attach FastAPI/HTTP instrumentation when telemetry is active."""
    if not _configured:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:  # noqa: BLE001
        logger.debug("FastAPI instrumentation unavailable.", exc_info=True)
