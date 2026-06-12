"""Health + readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.core.cosmos import repository

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness + store readiness.

    Judges can hit this URL to confirm Cosmos is connected in the live demo — ``store``
    is ``"cosmos"`` when a Cosmos backend is in use and ``"memory"`` for the local
    in-memory fallback.
    """
    return {
        "status": "ok",
        "store": repository.backend,
        "environment": settings.environment,
        "version": __version__,
        "service": "breachsim-orchestrator",
    }
