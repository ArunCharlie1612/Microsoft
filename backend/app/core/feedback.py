"""Operator-feedback learning loop.

Human triage verdicts (✓ confirmed / ✗ dismissed) on past findings are persisted and
fed back into how the Validator agent ranks *future* findings of the same
``(resource_type, technique)`` combination:

  * a track record of confirmations boosts the severity by one level, and
  * a track record of dismissals downgrades it by one level.

This turns each operator decision into a lightweight, auditable online-learning signal
that sharpens the swarm over time — without any model retraining. The adjustment is
applied deterministically (a documented threshold over a bounded window) so the result
stays reproducible for an audit.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.core.cosmos import repository
from app.core.logging import get_logger
from app.core.scoring import _TECHNIQUE_WEIGHTS

logger = get_logger(__name__)

# Severity ladder (ascending). Boost/downgrade moves one step along this ladder.
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]

# Learning-loop tuning (documented for auditability).
FEEDBACK_WINDOW = 10  # only the most recent N verdicts inform an adjustment
CONFIRM_THRESHOLD = 0.70  # ≥70% confirmed → boost
DISMISS_THRESHOLD = 0.70  # ≥70% dismissed → downgrade

# Coarse Azure resource-type buckets so feedback generalises across specific instances.
_COARSE_TYPES: dict[str, str] = {
    "storage": "storage",
    "keyvault": "keyvault",
    "vault": "keyvault",
    "virtualmachine": "compute",
    "compute": "compute",
    "sql": "database",
    "cosmos": "database",
    "network": "network",
    "kubernetes": "kubernetes",
    "managedcluster": "kubernetes",
    "web": "appservice",
    "sites": "appservice",
    "identity": "identity",
}


def coarse_resource_type(azure_type: str) -> str:
    """Map a fine-grained Azure type (``Microsoft.Storage/storageAccounts``) to a bucket."""
    lowered = (azure_type or "").lower()
    for needle, bucket in _COARSE_TYPES.items():
        if needle in lowered:
            return bucket
    # Fall back to the trailing path segment so the key is still stable.
    tail = lowered.rsplit("/", 1)[-1] if "/" in lowered else lowered
    return tail or "unknown"


def primary_finding_key(blackboard: dict[str, Any]) -> tuple[str, str]:
    """Representative ``(resource_type, technique)`` for the run's headline finding.

    Both the Validator's feedback lookup and the Memory agent's persisted finding derive
    their key from this single function so the two always agree (a confirmed finding
    later matches the same bucket on the next run).
    """
    resources = blackboard.get("resources", [])
    resource_type = (
        coarse_resource_type(str(resources[0].get("type", ""))) if resources else "unknown"
    )

    validations = blackboard.get("validations", [])
    techniques = [
        v.get("technique") for v in validations if v.get("validated") and v.get("technique")
    ]
    # Headline technique = the highest-impact validated technique (deterministic tie-break
    # on the documented scoring weights), defaulting to the canonical data-access technique.
    technique = max(
        techniques,
        key=lambda t: _TECHNIQUE_WEIGHTS.get(t, (0.0, ""))[0],
        default="",
    ) or "T1530"
    return resource_type, technique


def shift_severity(severity: str, delta: int) -> str:
    """Move ``severity`` ``delta`` levels along the ladder (clamped to the ends)."""
    if delta == 0 or severity not in SEVERITY_ORDER:
        return severity
    idx = SEVERITY_ORDER.index(severity)
    return SEVERITY_ORDER[max(0, min(len(SEVERITY_ORDER) - 1, idx + delta))]


async def recent_feedback(
    resource_type: str, technique: str, limit: int = FEEDBACK_WINDOW
) -> list[dict[str, Any]]:
    """Return up to ``limit`` most-recent feedback records for this combination."""
    docs = await repository.list_all(settings.cosmos_container_findings)
    matches = [
        d
        for d in docs
        if d.get("type") == "feedback"
        and d.get("resource_type") == resource_type
        and d.get("technique") == technique
    ]
    matches.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return matches[:limit]


def severity_adjustment(feedback: list[dict[str, Any]]) -> tuple[int, str]:
    """Derive a severity delta (+1 / 0 / −1) and a human-readable reason from verdicts."""
    if not feedback:
        return 0, ""
    total = len(feedback)
    confirmed = sum(1 for f in feedback if f.get("verdict") == "confirmed")
    dismissed = sum(1 for f in feedback if f.get("verdict") == "dismissed")
    if confirmed / total >= CONFIRM_THRESHOLD:
        return 1, (
            f"Severity boosted one level: {confirmed}/{total} recent operator verdicts "
            f"confirmed findings of this resource/technique."
        )
    if dismissed / total >= DISMISS_THRESHOLD:
        return -1, (
            f"Severity downgraded one level: {dismissed}/{total} recent operator verdicts "
            f"dismissed findings of this resource/technique."
        )
    return 0, ""
