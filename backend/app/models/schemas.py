"""Pydantic schemas: API contracts + internal swarm data models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


# ─────────────────────────── Enums ───────────────────────────
class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunPhase(StrEnum):
    RECON = "RECON"
    PLAN = "PLAN"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    RISK = "RISK"
    COMPLIANCE = "COMPLIANCE"
    REMEDIATION = "REMEDIATION"
    REPORT = "REPORT"


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    VETOED = "vetoed"
    FAILED = "failed"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─────────────────────────── API request/response ───────────────────────────
class RunScope(BaseModel):
    subscription_id: str = Field(..., alias="subscriptionId")
    resource_groups: list[str] = Field(default_factory=list, alias="resourceGroups")
    sandbox_only: bool = Field(True, alias="sandboxOnly")

    model_config = {"populate_by_name": True}


class RunOptions(BaseModel):
    max_token_budget: int = Field(200_000, alias="maxTokenBudget")
    frameworks: list[str] = Field(default_factory=lambda: ["NIST-800-53", "SOC2"])

    model_config = {"populate_by_name": True}


class CreateRunRequest(BaseModel):
    name: str
    scope: RunScope
    options: RunOptions = Field(default_factory=RunOptions)
    # Authorization-to-test: the caller must explicitly attest they are permitted to
    # assess the target scope. Enforced when ``breachsim_require_consent`` is set.
    authorization_acknowledged: bool = Field(False, alias="authorizationAcknowledged")
    authorized_by: str = Field("", alias="authorizedBy")

    model_config = {"populate_by_name": True}


class AgentState(BaseModel):
    agent_id: str = Field(..., alias="agentId")
    status: AgentStatus = AgentStatus.PENDING

    model_config = {"populate_by_name": True}


class RunStats(BaseModel):
    resources: int = 0
    findings: int = 0
    tokens_used: int = Field(0, alias="tokensUsed")
    estimated_cost_usd: float = Field(0.0, alias="estimatedCostUsd")

    model_config = {"populate_by_name": True}


class RunSummary(BaseModel):
    run_id: str = Field(..., alias="runId")
    name: str
    status: RunStatus
    phase: RunPhase | None = None
    progress: float = 0.0
    tenant_id: str = Field("local", alias="tenantId")
    created_at: datetime = Field(default_factory=_now, alias="createdAt")

    model_config = {"populate_by_name": True}


class RunDetail(RunSummary):
    agents: list[AgentState] = Field(default_factory=list)
    stats: RunStats = Field(default_factory=RunStats)
    started_at: datetime | None = Field(None, alias="startedAt")
    completed_at: datetime | None = Field(None, alias="completedAt")


# ─────────────────────────── Swarm domain models ───────────────────────────
class Resource(BaseModel):
    id: str
    run_id: str
    type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    public_exposure: bool = False


class AttackStep(BaseModel):
    order: int
    technique: str  # MITRE ATT&CK ID
    target_asset: str
    precondition: str | None = None
    expected_effect: str | None = None
    confidence: float = 0.5
    result: str | None = None


class RiskScore(BaseModel):
    cvss: float = 0.0
    business_impact: str = "unknown"


class ComplianceRecord(BaseModel):
    framework: str
    control_id: str
    rationale: str


class Remediation(BaseModel):
    iac_type: str = "bicep"
    pr_url: str | None = None
    status: str = "pending"
    diff: str | None = None


class Finding(BaseModel):
    id: str
    run_id: str
    title: str
    technique: str
    severity: Severity = Severity.MEDIUM
    validated: bool = False
    attack_steps: list[AttackStep] = Field(default_factory=list)
    risk: RiskScore | None = None
    compliance: list[ComplianceRecord] = Field(default_factory=list)
    remediation: Remediation | None = None
    evidence_ref: str | None = None
    created_at: datetime = Field(default_factory=_now)


class GraphNode(BaseModel):
    id: str
    kind: str
    label: str
    props: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    relation: str
    confidence: float = 0.5

    model_config = {"populate_by_name": True}


class AttackGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class AgentEvent(BaseModel):
    id: str
    run_id: str
    agent_id: str
    event_type: str
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=_now)
