"""BreachSim FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import auth, demo, findings, health, runs, tenants
from app.config import settings
from app.core.cosmos import repository
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_telemetry
from app.services.run_manager import run_manager
from app.services.tenant_manager import tenant_manager

configure_logging()
configure_telemetry()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BreachSim orchestrator starting", extra={"trace_id": "boot"})
    await repository.connect()
    await tenant_manager.load()
    await run_manager.load()
    yield
    await repository.close()
    logger.info("BreachSim orchestrator stopped")


app = FastAPI(
    title="BreachSim — Agentic Red Team Swarm",
    description="Autonomous agent swarm that continuously red-teams your cloud posture.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(findings.router)
app.include_router(demo.router)
app.include_router(tenants.router)

from app.core.telemetry import instrument_app  # noqa: E402

instrument_app(app)


@app.get("/")
async def root() -> dict:
    return {"service": "BreachSim", "docs": "/docs", "health": "/health"}
