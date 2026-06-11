"""Stripe billing integration (optional).

Turns the existing per-tenant plan/quota model into a real paid subscription:

  * ``create_checkout_session`` starts a Stripe Checkout for the Pro plan and tags the
    session with the tenant id so the webhook can attribute it.
  * ``handle_webhook`` verifies the Stripe signature and upgrades/downgrades the tenant
    plan on ``checkout.session.completed`` and subscription lifecycle events.

Entirely optional: when Stripe is not configured (``settings.billing_enabled`` is
False) the upgrade flow is disabled and everything runs free on the FREE plan. The
``stripe`` package is imported lazily so local/offline runs need no extra dependency.
"""

from __future__ import annotations

from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import PlanTier
from app.services.tenant_manager import tenant_manager

logger = get_logger(__name__)


class BillingNotConfiguredError(RuntimeError):
    """Raised when a billing operation is attempted without Stripe configured."""


def _stripe():
    import stripe  # lazy: only needed when billing is enabled

    stripe.api_key = settings.stripe_api_key
    return stripe


async def create_checkout_session(tenant_id: str, email: str = "") -> str:
    """Create a Stripe Checkout session for the Pro plan. Returns the redirect URL."""
    if not settings.billing_enabled:
        raise BillingNotConfiguredError("Stripe billing is not configured.")
    stripe = _stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_pro, "quantity": 1}],
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
        client_reference_id=tenant_id,
        customer_email=email or None,
        metadata={"tenant_id": tenant_id},
    )
    return session.url


async def handle_webhook(payload: bytes, signature: str) -> dict:
    """Verify and process a Stripe webhook. Returns a small status dict."""
    if not settings.billing_enabled or not settings.stripe_webhook_secret:
        raise BillingNotConfiguredError("Stripe webhook is not configured.")
    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except Exception as exc:  # noqa: BLE001 — signature/parse failures
        logger.warning("Stripe webhook verification failed.", exc_info=True)
        raise ValueError("Invalid Stripe signature") from exc

    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        tenant_id = (obj.get("metadata") or {}).get("tenant_id") or obj.get(
            "client_reference_id"
        )
        if tenant_id:
            await tenant_manager.set_plan(
                tenant_id,
                PlanTier.PRO,
                stripe_customer_id=obj.get("customer", ""),
                stripe_subscription_id=obj.get("subscription", ""),
            )
        return {"handled": event_type, "tenant": tenant_id}

    if event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        tenant = tenant_manager.get_by_stripe_customer(obj.get("customer", ""))
        if tenant:
            await tenant_manager.set_plan(tenant.id, PlanTier.FREE)
        return {"handled": event_type, "tenant": tenant.id if tenant else None}

    return {"handled": "ignored", "type": event_type}
