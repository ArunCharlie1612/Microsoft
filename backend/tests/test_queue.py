"""Tests for durable run queueing + the run-status endpoint.

Verifies the offline fallback: with no Service Bus configured, runs execute
in-process and ``/v1/runs/{id}/status`` reflects the stored status.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.config import settings
from app.services.queue import send_run_to_queue

# Disable demo pacing so the in-process swarm completes promptly under TestClient.
settings.breachsim_demo_pacing_ms = 0

from app.main import app  # noqa: E402

client = TestClient(app)


def test_send_run_to_queue_falls_back_when_unconfigured():
    settings.azure_service_bus_connection_string = ""
    queued = asyncio.run(send_run_to_queue("run_test", "local", {"scope": {}}))
    assert queued is False


def test_run_status_endpoint_reports_completion():
    payload = {
        "name": "status run",
        "scope": {
            "subscriptionId": "00000000-0000-0000-0000-000000000000",
            "resourceGroups": ["rg-breachsim-sandbox"],
            "sandboxOnly": True,
        },
        "authorizationAcknowledged": True,
        "authorizedBy": "test-suite",
    }
    r = client.post("/v1/runs", json=payload)
    assert r.status_code == 202
    body = r.json()
    # Response exposes both snake_case and camelCase ids; status starts queued.
    assert body["run_id"] == body["runId"]
    assert body["status"] == "queued"
    run_id = body["runId"]

    async def _wait():
        for _ in range(100):
            s = client.get(f"/v1/runs/{run_id}/status").json()
            if s["status"] in ("completed", "failed"):
                return s
            await asyncio.sleep(0.1)
        return client.get(f"/v1/runs/{run_id}/status").json()

    status = asyncio.run(_wait())
    assert status["runId"] == run_id
    assert status["status"] == "completed"
