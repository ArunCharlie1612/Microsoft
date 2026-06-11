"""Plan limits + usage/billing aggregation.

Usage is derived from the tenant's runs (token + cost metering already lives on each
run's stats). This module turns that into a per-tenant usage summary and enforces the
plan's daily run quota. Billing here is metering + quota only; charging a card would be
an external integration (e.g. Stripe) layered on top of these numbers.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config import settings
from app.models.schemas import PlanTier, UsageSummary
from app.services.run_manager import run_manager
from app.services.tenant_manager import tenant_manager


def daily_run_limit(plan: PlanTier) -> int:
    if plan == PlanTier.PRO:
        return settings.plan_pro_daily_runs
    return settings.plan_free_daily_runs


def _runs_for_tenant(tenant_id: str) -> list:
    return run_manager.list(tenant_id=tenant_id)


def runs_today(tenant_id: str) -> int:
    today = datetime.now(UTC).date()
    return sum(1 for r in _runs_for_tenant(tenant_id) if r.created_at.date() == today)


def usage_summary(tenant_id: str) -> UsageSummary:
    tenant = tenant_manager.get(tenant_id)
    plan = tenant.plan if tenant else PlanTier.FREE
    runs = _runs_for_tenant(tenant_id)
    tokens = sum(r.stats.tokens_used for r in runs)
    cost = round(sum(r.stats.estimated_cost_usd for r in runs), 4)
    return UsageSummary(
        tenantId=tenant_id,
        plan=plan,
        runsTotal=len(runs),
        runsToday=runs_today(tenant_id),
        dailyRunLimit=daily_run_limit(plan),
        tokensUsed=tokens,
        estimatedCostUsd=cost,
    )


def within_quota(tenant_id: str, plan: PlanTier) -> bool:
    """True if the tenant may start another run today under its plan."""
    return runs_today(tenant_id) < daily_run_limit(plan)
