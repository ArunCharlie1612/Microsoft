"""Environment-gated store selection + /health store reporting."""
from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.core.cosmos import CosmosRepository


def test_local_without_cosmos_uses_memory(monkeypatch):
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "cosmos_endpoint", "")
    monkeypatch.setattr(settings, "cosmos_connection_string", "")

    repo = CosmosRepository()
    asyncio.run(repo.connect())  # must NOT raise
    assert repo.backend == "memory"


def test_production_without_cosmos_raises(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "cosmos_endpoint", "")
    monkeypatch.setattr(settings, "cosmos_connection_string", "")

    repo = CosmosRepository()
    with pytest.raises(RuntimeError, match="COSMOS_CONNECTION_STRING is required"):
        asyncio.run(repo.connect())


def test_development_without_cosmos_raises(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "cosmos_endpoint", "")
    monkeypatch.setattr(settings, "cosmos_connection_string", "")

    repo = CosmosRepository()
    with pytest.raises(RuntimeError):
        asyncio.run(repo.connect())


def test_cosmos_configured_property(monkeypatch):
    monkeypatch.setattr(settings, "cosmos_endpoint", "")
    monkeypatch.setattr(settings, "cosmos_connection_string", "")
    assert settings.cosmos_configured is False

    monkeypatch.setattr(settings, "cosmos_connection_string", "AccountEndpoint=https://x/;")
    assert settings.cosmos_configured is True


def test_health_endpoint_reports_store_and_environment():
    settings.breachsim_demo_pacing_ms = 0
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["store"] in ("cosmos", "memory")
    assert body["environment"] == settings.environment
