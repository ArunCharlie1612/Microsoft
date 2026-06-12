"""Operator-feedback learning loop: PATCH endpoint + Validator severity adjustment."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.config import settings
from app.core import feedback

settings.breachsim_demo_pacing_ms = 0

from app.main import app  # noqa: E402

client = TestClient(app)


def _run_to_completion() -> str:
    payload = {
        "name": "feedback run",
        "scope": {
            "subscriptionId": "00000000-0000-0000-0000-000000000000",
            "resourceGroups": ["rg-breachsim-sandbox"],
            "sandboxOnly": True,
        },
        "authorizationAcknowledged": True,
        "authorizedBy": "test-suite",
    }
    run_id = client.post("/v1/runs", json=payload).json()["runId"]

    async def _wait():
        for _ in range(100):
            detail = client.get(f"/v1/runs/{run_id}").json()
            if detail["status"] in ("completed", "failed"):
                return detail
            await asyncio.sleep(0.1)
        return client.get(f"/v1/runs/{run_id}").json()

    assert asyncio.run(_wait())["status"] == "completed"
    return run_id


def test_feedback_endpoint_updates_finding():
    run_id = _run_to_completion()
    findings = client.get(f"/v1/runs/{run_id}/findings").json()
    finding_id = findings[0]["id"]

    r = client.patch(
        f"/v1/findings/{finding_id}/feedback",
        json={"verdict": "confirmed", "note": "valid exposure"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "confirmed"
    assert body["note"] == "valid exposure"
    assert body["feedback_at"]


def test_feedback_unknown_finding_404():
    r = client.patch("/v1/findings/does-not-exist/feedback", json={"verdict": "dismissed"})
    assert r.status_code == 404


def test_severity_adjustment_thresholds():
    assert feedback.severity_adjustment([]) == (0, "")

    confirmed = [{"verdict": "confirmed"} for _ in range(8)] + [{"verdict": "dismissed"}] * 2
    delta, reason = feedback.severity_adjustment(confirmed)
    assert delta == 1 and "boosted" in reason

    dismissed = [{"verdict": "dismissed"} for _ in range(8)] + [{"verdict": "confirmed"}] * 2
    delta, reason = feedback.severity_adjustment(dismissed)
    assert delta == -1 and "downgraded" in reason

    mixed = [{"verdict": "confirmed"}] * 5 + [{"verdict": "dismissed"}] * 5
    assert feedback.severity_adjustment(mixed) == (0, "")


def test_shift_severity_clamps():
    assert feedback.shift_severity("medium", 1) == "high"
    assert feedback.shift_severity("high", -1) == "medium"
    assert feedback.shift_severity("critical", 1) == "critical"
    assert feedback.shift_severity("info", -1) == "info"
    assert feedback.shift_severity("medium", 0) == "medium"
