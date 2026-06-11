"""Azure Cosmos DB async client + repository.

Falls back to an in-memory store when Cosmos is not configured (local/demo mode),
so the full swarm runs end-to-end without any cloud dependencies.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class _InMemoryContainer:
    """Minimal async Cosmos-like container for local/demo runs."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            self._items[body["id"]] = body
            return body

    async def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        return self._items[item]

    async def query(self, predicate) -> list[dict[str, Any]]:
        return [i for i in self._items.values() if predicate(i)]


class CosmosRepository:
    """Repository wrapping Cosmos containers (or in-memory fallback)."""

    def __init__(self) -> None:
        self._enabled = bool(settings.cosmos_endpoint)
        self._client = None
        self._containers: dict[str, Any] = defaultdict(_InMemoryContainer)

    async def connect(self) -> None:
        if not self._enabled:
            logger.info("Cosmos not configured — using in-memory store (demo mode).")
            return
        # Lazy import so local mode needs no azure-cosmos at runtime.
        from azure.cosmos.aio import CosmosClient
        from azure.identity.aio import DefaultAzureCredential

        if settings.cosmos_key:
            self._client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        else:
            self._client = CosmosClient(
                settings.cosmos_endpoint, credential=DefaultAzureCredential()
            )
        db = self._client.get_database_client(settings.cosmos_database)
        for name in (
            settings.cosmos_container_findings,
            settings.cosmos_container_agents,
            settings.cosmos_container_threatgraph,
            settings.cosmos_container_audit,
            settings.cosmos_container_runs,
        ):
            self._containers[name] = db.get_container_client(name)
        logger.info("Connected to Cosmos DB.")

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    def container(self, name: str):
        return self._containers[name]

    # ── High-level helpers ────────────────────────────────────────────────
    async def save(self, container: str, doc: dict[str, Any]) -> dict[str, Any]:
        return await self.container(container).upsert_item(doc)

    async def list_by_run(self, container: str, run_id: str) -> list[dict[str, Any]]:
        c = self.container(container)
        if isinstance(c, _InMemoryContainer):
            return await c.query(lambda i: i.get("run_id") == run_id)
        # Real Cosmos query
        query = "SELECT * FROM c WHERE c.run_id = @run_id"
        params = [{"name": "@run_id", "value": run_id}]
        items: list[dict[str, Any]] = []
        async for item in c.query_items(query=query, parameters=params):
            items.append(item)
        return items

    async def list_all(self, container: str) -> list[dict[str, Any]]:
        """Return every document in a container (cross-partition)."""
        c = self.container(container)
        if isinstance(c, _InMemoryContainer):
            return list(c._items.values())
        items: list[dict[str, Any]] = []
        async for item in c.query_items(query="SELECT * FROM c"):
            items.append(item)
        return items


repository = CosmosRepository()
