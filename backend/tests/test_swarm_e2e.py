"""End-to-end smoke test: the full swarm runs offline in local/demo mode."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_complete_run():
    payload = {
        "name": "smoke run",
        "scope": {
            "subscriptionId": "00000000-0000-0000-0000-000000000000",
            "resourceGroups": ["rg-breachsim-sandbox"],
            "sandboxOnly": True,
        },
    }
    r = client.post("/v1/runs", json=payload)
    assert r.status_code == 202
    run_id = r.json()["runId"]

    # Poll until the background swarm completes.
    async def _wait():
        for _ in range(50):
            detail = client.get(f"/v1/runs/{run_id}").json()
            if detail["status"] in ("completed", "failed"):
                return detail
            await asyncio.sleep(0.1)
        return client.get(f"/v1/runs/{run_id}").json()

    detail = asyncio.run(_wait())
    assert detail["status"] == "completed"

    findings = client.get(f"/v1/runs/{run_id}/findings").json()
    assert len(findings) >= 1

    graph = client.get(f"/v1/runs/{run_id}/graph").json()
    assert len(graph["nodes"]) >= 1
