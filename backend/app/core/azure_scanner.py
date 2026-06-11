"""Read-only Azure Resource Graph scanner.

Replaces simulated recon with a real, READ-ONLY enumeration of the target
subscription using Azure Resource Graph (ARG). All queries are projections — the
scanner never mutates anything. It requires the runtime identity to hold at least
``Reader`` on the in-scope subscription; if the SDK or permissions are unavailable
the caller falls back to model/stub recon so a run never hard-fails.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# KQL: surface common public-exposure / over-privilege signals across resource types.
_ARG_QUERY = """
Resources
| project name, type, location, properties, identity
| limit 200
"""


def _public_exposure(resource_type: str, props: dict[str, Any]) -> bool:
    """Heuristic, deterministic public-exposure flag from real resource properties."""
    t = (resource_type or "").lower()
    if t == "microsoft.storage/storageaccounts":
        return bool(props.get("allowBlobPublicAccess")) or (
            props.get("networkAcls", {}).get("defaultAction") == "Allow"
        )
    if t == "microsoft.network/publicipaddresses":
        return True
    if t in ("microsoft.sql/servers", "microsoft.dbforpostgresql/servers"):
        return props.get("publicNetworkAccess", "Enabled") == "Enabled"
    if t == "microsoft.keyvault/vaults":
        return props.get("networkAcls", {}).get("defaultAction", "Allow") == "Allow"
    if t == "microsoft.web/sites":
        return props.get("publicNetworkAccess", "Enabled") != "Disabled"
    return False


def _summarize(resources: list[dict[str, Any]]) -> str:
    total = len(resources)
    public = sum(1 for r in resources if r.get("publicExposure"))
    identities = sum(1 for r in resources if r.get("config", {}).get("hasIdentity"))
    return (
        f"{total} resources enumerated via Azure Resource Graph; "
        f"{public} with public exposure, {identities} with attached identities"
    )


async def scan_subscription(subscription_id: str) -> dict[str, Any] | None:
    """Enumerate resources in a subscription read-only via Resource Graph.

    Returns a recon result ``{"resources": [...], "summary": str}`` matching the
    ReconAgent contract, or ``None`` if scanning is unavailable (missing SDK,
    credentials, or permissions) so the caller can fall back gracefully.
    """
    if not subscription_id:
        return None
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.mgmt.resourcegraph.aio import ResourceGraphClient
        from azure.mgmt.resourcegraph.models import QueryRequest
    except ImportError:
        logger.info("azure-mgmt-resourcegraph not installed — skipping live recon.")
        return None

    try:
        credential = DefaultAzureCredential()
        try:
            client = ResourceGraphClient(credential)
            try:
                request = QueryRequest(subscriptions=[subscription_id], query=_ARG_QUERY)
                response = await client.resources(request)
            finally:
                await client.close()
        finally:
            await credential.close()
    except Exception:  # noqa: BLE001 — any auth/permission/network error → fall back
        logger.warning("Live recon failed; falling back to modeled recon.", exc_info=True)
        return None

    rows = getattr(response, "data", None) or []
    resources: list[dict[str, Any]] = []
    for row in rows:
        props = row.get("properties") or {}
        identity = row.get("identity") or {}
        resources.append(
            {
                "name": row.get("name", "unknown"),
                "type": row.get("type", "unknown"),
                "publicExposure": _public_exposure(row.get("type", ""), props),
                "config": {
                    "location": row.get("location"),
                    "hasIdentity": bool(identity),
                    "identityType": identity.get("type"),
                },
            }
        )

    if not resources:
        return None
    return {"resources": resources, "summary": _summarize(resources)}
