"""Deterministic, auditable risk scoring and compliance mapping.

Risk severity and compliance evidence must be reproducible for an audit — they cannot
be a number the LLM invents. These pure functions derive a CVSS-style score and the
mapped control set from the *validated* attack chain and any grounded CVE evidence, so
the same inputs always yield the same outputs.
"""

from __future__ import annotations

from typing import Any

# MITRE ATT&CK technique → (base CVSS contribution, short impact descriptor).
# Conservative, documented baselines; the chain aggregates them below.
_TECHNIQUE_WEIGHTS: dict[str, tuple[float, str]] = {
    "T1595": (4.0, "active scanning / exposure discovery"),
    "T1530": (7.5, "data from cloud storage object"),
    "T1078": (8.8, "valid account abuse / privilege use"),
    "T1486": (9.0, "data encrypted for impact"),
    "T1485": (8.5, "data destruction"),
    "T1098": (8.1, "account manipulation / persistence"),
    "T1110": (7.0, "brute force"),
    "T1190": (8.6, "exploit public-facing application"),
}

# Technique → relevant controls across frameworks (auditable crosswalk).
_TECHNIQUE_CONTROLS: dict[str, list[dict[str, str]]] = {
    "T1595": [
        {
            "framework": "NIST-800-53",
            "control_id": "RA-5",
            "rationale": "Vulnerability scanning / exposure management.",
        },
        {
            "framework": "NIST-800-53",
            "control_id": "SC-7",
            "rationale": "Boundary protection of public-facing assets.",
        },
    ],
    "T1530": [
        {
            "framework": "NIST-800-53",
            "control_id": "AC-3",
            "rationale": "Access enforcement on stored data.",
        },
        {
            "framework": "SOC2",
            "control_id": "CC6.1",
            "rationale": "Logical access controls over data at rest.",
        },
        {
            "framework": "ISO-27001",
            "control_id": "A.8.3",
            "rationale": "Information access restriction.",
        },
    ],
    "T1078": [
        {
            "framework": "NIST-800-53",
            "control_id": "IA-2",
            "rationale": "Identification & authentication of users.",
        },
        {
            "framework": "NIST-800-53",
            "control_id": "AC-6",
            "rationale": "Least privilege for accounts/identities.",
        },
        {
            "framework": "SOC2",
            "control_id": "CC6.3",
            "rationale": "Credential and privilege management.",
        },
        {"framework": "ISO-27001", "control_id": "A.9.2", "rationale": "User access management."},
    ],
}


def _severity_band(cvss: float) -> str:
    if cvss >= 9.0:
        return "critical"
    if cvss >= 7.0:
        return "high"
    if cvss >= 4.0:
        return "medium"
    if cvss > 0.0:
        return "low"
    return "info"


def compute_risk(
    validations: list[dict[str, Any]], evidence: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Deterministically score the validated attack chain.

    The score is the highest single-technique base score plus a small chaining bonus
    for each additional validated step (capped at 10.0). If grounded CVE evidence
    carries a higher CVSS, that raises the floor.
    """
    validated_techniques = [
        v.get("technique") for v in validations if v.get("validated") and v.get("technique")
    ]
    base = 0.0
    impacts: list[str] = []
    for technique in validated_techniques:
        weight, impact = _TECHNIQUE_WEIGHTS.get(technique, (3.0, "unspecified technique"))
        base = max(base, weight)
        impacts.append(impact)

    chain_bonus = 0.3 * max(0, len(validated_techniques) - 1)
    evidence_floor = max(
        (float(e.get("cvss", 0.0)) for e in (evidence or []) if e.get("cvss")), default=0.0
    )
    cvss = round(min(10.0, max(base + chain_bonus, evidence_floor)), 1)
    severity = _severity_band(cvss)

    if not validated_techniques:
        rationale = "No steps were validated; no exploitable chain demonstrated."
        business_impact = "low"
    else:
        rationale = (
            f"Validated {len(validated_techniques)}-step chain "
            f"({' → '.join(validated_techniques)}): {'; '.join(impacts)}."
        )
        business_impact = "high" if cvss >= 7.0 else "medium"

    return {
        "cvss": cvss,
        "severity": severity,
        "business_impact": business_impact,
        "rationale": rationale,
        "method": "deterministic",
    }


def map_compliance(techniques: list[str]) -> list[dict[str, str]]:
    """Return the auditable control crosswalk for the given techniques (deduplicated)."""
    seen: set[tuple[str, str]] = set()
    records: list[dict[str, str]] = []
    for technique in techniques:
        for rec in _TECHNIQUE_CONTROLS.get(technique, []):
            key = (rec["framework"], rec["control_id"])
            if key not in seen:
                seen.add(key)
                records.append(dict(rec))
    if not records:
        records.append(
            {
                "framework": "NIST-800-53",
                "control_id": "CA-8",
                "rationale": "Penetration testing / control assessment performed.",
            }
        )
    return records
