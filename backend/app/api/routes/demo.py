"""Demo endpoint — provisions a deliberately misconfigured sandbox for the live demo."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import Principal, require_role

router = APIRouter(prefix="/v1/demo", tags=["demo"])


@router.post("/seed")
async def seed_demo(
    principal: Principal = Depends(require_role("breachsim.admin")),
) -> dict:
    """Provision (or simulate) a misconfigured blob storage target for the demo.

    In a deployed environment this triggers a Bicep deployment of a sandbox resource
    group with an intentionally public storage account. In local mode it returns the
    canned target descriptor the swarm will 'discover'.
    """
    return {
        "sandbox": {
            "resourceGroup": "rg-breachsim-sandbox",
            "storageAccount": "stbreachdemo",
            "misconfig": "allowBlobPublicAccess=true on container 'configs'",
            "subscriptionId": "00000000-0000-0000-0000-000000000000",
        },
        "ready": True,
        "message": "Misconfigured sandbox ready. Start a run scoped to this subscription.",
    }
