"""Unit tests for deterministic scoring and compliance mapping."""
from __future__ import annotations

from app.core.scoring import compute_risk, map_compliance


def test_compute_risk_is_deterministic():
    validations = [
        {"order": 1, "validated": True, "technique": "T1595"},
        {"order": 2, "validated": True, "technique": "T1530"},
        {"order": 3, "validated": True, "technique": "T1078"},
    ]
    a = compute_risk(validations)
    b = compute_risk(validations)
    assert a == b
    assert a["method"] == "deterministic"
    # Highest single weight is T1078 (8.8) + chain bonus for 2 extra steps (0.6).
    assert a["cvss"] == 9.4
    assert a["severity"] == "critical"
    assert a["business_impact"] == "high"


def test_compute_risk_no_validations():
    result = compute_risk([{"order": 1, "validated": False, "technique": "T1078"}])
    assert result["cvss"] == 0.0
    assert result["severity"] == "info"
    assert result["business_impact"] == "low"


def test_compute_risk_evidence_floor():
    validations = [{"order": 1, "validated": True, "technique": "T1595"}]
    # T1595 alone is 4.0, but a grounded CVE with CVSS 9.1 must raise the floor.
    result = compute_risk(validations, evidence=[{"cvss": 9.1}])
    assert result["cvss"] == 9.1
    assert result["severity"] == "critical"


def test_compute_risk_caps_at_ten():
    validations = [
        {"order": i, "validated": True, "technique": "T1486"} for i in range(20)
    ]
    result = compute_risk(validations)
    assert result["cvss"] <= 10.0


def test_map_compliance_dedupes_and_maps():
    records = map_compliance(["T1078", "T1078", "T1530"])
    keys = {(r["framework"], r["control_id"]) for r in records}
    # No duplicates.
    assert len(keys) == len(records)
    assert ("NIST-800-53", "IA-2") in keys
    assert ("SOC2", "CC6.1") in keys


def test_map_compliance_defaults_when_unknown():
    records = map_compliance(["T9999"])
    assert records == [
        {
            "framework": "NIST-800-53",
            "control_id": "CA-8",
            "rationale": "Penetration testing / control assessment performed.",
        }
    ]
