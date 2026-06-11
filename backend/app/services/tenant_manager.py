"""Tenant lifecycle + API-key management (self-service onboarding).

Tenants are the unit of multi-customer isolation. Each tenant owns its runs, findings,
and usage. Authentication for a tenant is via an API key:

  * a raw key looks like ``bsk_<random>`` and is shown to the customer exactly once;
  * only the SHA-256 hash is ever stored, so a database leak cannot reveal live keys;
  * lookups hash the presented key and match against stored hashes (constant-time).

Works fully offline: persists to Cosmos when configured, otherwise an in-memory store.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid

from app.config import settings
from app.core.cosmos import repository
from app.core.logging import get_logger
from app.models.schemas import ApiKeyInfo, PlanTier, Tenant

logger = get_logger(__name__)

_KEY_PREFIX = "bsk_"


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_raw_key() -> str:
    return f"{_KEY_PREFIX}{secrets.token_urlsafe(32)}"


class TenantManager:
    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._hash_index: dict[str, str] = {}  # api_key_hash -> tenant_id
        self._loaded = False

    async def load(self) -> None:
        """Hydrate tenants from Cosmos (best-effort)."""
        if self._loaded:
            return
        try:
            docs = await repository.list_all(settings.cosmos_container_tenants)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load tenants (continuing empty).", exc_info=True)
            self._loaded = True
            return
        for doc in docs:
            try:
                tenant = Tenant.model_validate(doc)
            except Exception:  # noqa: BLE001
                continue
            self._index(tenant)
        self._loaded = True
        if self._tenants:
            logger.info("Loaded %d tenant(s).", len(self._tenants))

    def _index(self, tenant: Tenant) -> None:
        self._tenants[tenant.id] = tenant
        for h in tenant.api_key_hashes:
            self._hash_index[h] = tenant.id

    async def _persist(self, tenant: Tenant) -> None:
        try:
            doc = tenant.model_dump(mode="json", by_alias=True)
            await repository.save(settings.cosmos_container_tenants, doc)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to persist tenant %s.", tenant.id, exc_info=True)

    async def create_tenant(
        self, name: str, email: str = "", plan: PlanTier = PlanTier.FREE
    ) -> tuple[Tenant, str]:
        """Create a tenant and issue its first API key. Returns (tenant, raw_key)."""
        tenant_id = f"tnt_{uuid.uuid4().hex[:12]}"
        raw = _new_raw_key()
        key_hash = _hash_key(raw)
        tenant = Tenant(
            id=tenant_id,
            name=name,
            email=email,
            plan=plan,
            api_key_hashes=[key_hash],
            api_keys=[ApiKeyInfo(prefix=raw[: len(_KEY_PREFIX) + 6])],
        )
        self._index(tenant)
        await self._persist(tenant)
        logger.info("Tenant created: %s (plan=%s).", tenant_id, plan)
        return tenant, raw

    async def issue_api_key(self, tenant_id: str) -> str | None:
        """Issue an additional API key for an existing tenant. Returns the raw key."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
        raw = _new_raw_key()
        key_hash = _hash_key(raw)
        tenant.api_key_hashes.append(key_hash)
        tenant.api_keys.append(ApiKeyInfo(prefix=raw[: len(_KEY_PREFIX) + 6]))
        self._hash_index[key_hash] = tenant_id
        await self._persist(tenant)
        return raw

    def get(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)

    def get_by_stripe_customer(self, customer_id: str) -> Tenant | None:
        if not customer_id:
            return None
        for tenant in self._tenants.values():
            if tenant.stripe_customer_id == customer_id:
                return tenant
        return None

    async def set_plan(
        self,
        tenant_id: str,
        plan: PlanTier,
        *,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
    ) -> Tenant | None:
        """Update a tenant's plan (and optional Stripe references). Persists the change."""
        tenant = self._tenants.get(tenant_id)
        if not tenant:
            return None
        tenant.plan = plan
        if stripe_customer_id is not None:
            tenant.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            tenant.stripe_subscription_id = stripe_subscription_id
        await self._persist(tenant)
        logger.info("Tenant %s plan set to %s.", tenant_id, plan)
        return tenant

    def resolve_api_key(self, raw: str) -> Tenant | None:
        """Return the tenant owning ``raw`` (or None). Constant-time hash compare."""
        if not raw or not raw.startswith(_KEY_PREFIX):
            return None
        presented = _hash_key(raw)
        for stored_hash, tenant_id in self._hash_index.items():
            if hmac.compare_digest(stored_hash, presented):
                return self._tenants.get(tenant_id)
        return None


tenant_manager = TenantManager()
