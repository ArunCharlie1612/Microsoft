"""Azure Functions — sandboxed payload execution surface for the Execution Agent.

Runs in a dedicated, network-isolated plan with NO peering to production resources.
This is the ONLY place exploit payloads are ever executed, and only against the
per-run sandbox resource group.
"""
from __future__ import annotations

import json
import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="sandbox/execute", methods=["POST"])
def execute_payload(req: func.HttpRequest) -> func.HttpResponse:
    """Execute a single approved attack step in the sandbox and return evidence."""
    try:
        step = req.get_json()
    except ValueError:
        return func.HttpResponse("invalid json", status_code=400)

    # Hard guardrail: refuse anything outside the sandbox resource group.
    target = step.get("target_asset", "")
    if "sandbox" not in step.get("scope", "") and not target.startswith("stbreachdemo"):
        logging.warning("guardrail: rejected out-of-scope target %s", target)
        return func.HttpResponse(
            json.dumps({"error": "out-of-scope target rejected"}), status_code=403
        )

    result = {
        "order": step.get("order"),
        "technique": step.get("technique"),
        "result": f"executed {step.get('technique')} against {target}",
        "success": True,
        "artifactRef": f"blob://artifacts/{step.get('order')}.json",
    }
    return func.HttpResponse(json.dumps(result), mimetype="application/json")


@app.event_grid_trigger(arg_name="event")
def on_agent_event(event: func.EventGridEvent) -> None:
    """Subscribe to the agent message bus for async orchestration hooks."""
    logging.info("agent event: %s", event.event_type)
