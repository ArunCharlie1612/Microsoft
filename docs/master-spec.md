# BreachSim — Master Product & Engineering Specification

**Status:** Single Source of Truth (SSOT) · **Version:** 1.0 · **Last updated:** 2026-06-12
**Project:** BreachSim — Agentic Red Team Swarm
**Event:** Microsoft Build AI Hackathon 2026
**Primary theme:** Security in the Agentic Future · **Secondary:** Agent Swarms

> This document consolidates and supersedes the design drafts in `docs/` (multi-agent-design,
> api-design, database-design, architecture, build-plan, demo-script) and incorporates the
> corrective findings from `docs/live-ready-assessment.md`. It is the authoritative reference for
> product, architecture, data, API, and demo execution. The root `README.md` is intentionally left
> untouched and is **not** the source of truth for engineering detail — this document is.

---

# 1. PRODUCT STRATEGY & FUNCTIONAL SPECIFICATION

---

## 1.1 Executive Summary & Value Proposition

### The Cloud Security Velocity Gap

Modern cloud teams ship change at machine speed. A single platform team can merge **dozens of
infrastructure commits per day** — a new storage account here, a relaxed network security group
there, a broadened managed-identity role assignment to "unblock" a deploy. Each commit can silently
create or chain into an exploitable exposure within **minutes of merge**.

Security validation, by contrast, moves at **human and calendar speed**:

- **Penetration tests** are point-in-time, scheduled quarterly or annually, and stale the moment
  the next deploy lands.
- **CSPM/CNAPP scanners** emit a high-volume, low-context firehose of "misconfiguration" alerts —
  driving alert fatigue without telling an operator *whether the finding is actually reachable and
  chainable into impact*.
- **Manual red-teaming** is the gold standard for proving real, chained risk, but it does not scale:
  elite operators are scarce, expensive, and cannot be in the loop on every merge.

The result is the **Cloud Security Velocity Gap** — the widening delta between the *rate of change*
in a cloud estate and the *cadence of meaningful adversarial validation* against it. The gap is where
breaches live.

### How BreachSim closes the gap

BreachSim shifts cloud security from **passive, alert-fatigued scanning** to **continuous,
automated, self-healing adversarial validation**. A hierarchical swarm of specialized AI agents
continuously:

1. **Discovers** the live attack surface from cloud metadata (read-only).
2. **Chains** plausible multi-step attack paths with GPT-4o reasoning grounded in CVE/ATT&CK data.
3. **Validates** that an exposure is *actually reachable* using benign, read-only probes — not
   noisy heuristics, and not destructive exploitation.
4. **Remediates** by generating secure Infrastructure-as-Code and opening a gated GitHub Pull
   Request, closing the loop from *finding* to *fix proposal* without a human bottleneck.

The value proposition is therefore not "another scanner." It is **continuous proof of exploitable
risk plus an automated, reviewable fix** — red-team outcomes at deploy cadence.

---

## 1.2 Core Product Mechanics — The "In-and-Out"

BreachSim's operational lifecycle is deliberately phrased as **Discover → Chain → Validate →
Remediate** (we say *validate*, never *exploit* — see §1.3).

```
   ┌──────────┐    ┌────────┐    ┌──────────┐    ┌────────────┐
   │ DISCOVER │ ─▶ │ CHAIN  │ ─▶ │ VALIDATE │ ─▶ │ REMEDIATE  │
   └──────────┘    └────────┘    └──────────┘    └────────────┘
   Recon Agent     Planner/        Execution +     Compliance +
   (Azure          Research        Validator       Remediation
   Resource        Agents          Agents          Agents
   Graph)          (GPT-4o)        (safe probes)   (Bicep + PR)
```

| Phase | Input | Engine | Output |
|-------|-------|--------|--------|
| **Discover** | Tenant scope (subscription + resource-group allow-list) | Recon Agent → Azure Resource Graph | Asset network: resources, configs, identities, public exposure flags |
| **Chain** | Asset network + grounded CVE/ATT&CK context | Planner + Research Agents (GPT-4o) | Ordered attack chain (steps with MITRE technique IDs, preconditions, expected effects) |
| **Validate** | Security-approved chain | Execution + Validator Agents | Confirmed, evidence-backed findings (false positives eliminated) |
| **Remediate** | Validated, risk-scored findings | Compliance + Remediation Agents | Control-mapped evidence + Bicep fix opened as a gated GitHub PR |

The full internal state machine that the orchestrator drives is:

```
RECON → RESEARCH → PLAN → SECURITY_REVIEW → EXECUTE → VALIDATE → RISK
      → (COMPLIANCE ∥ REMEDIATION) → REPORT
```

Compliance and Remediation run **concurrently** after risk scoring to shorten wall-clock run time.

---

## 1.3 The Safe-Validation Stance — Simulation vs. Exploitation

BreachSim's single most important product decision is the **boundary between simulation and
exploitation**. This is what makes it safe to point at *real* tenants.

| | **Simulated (modeled, never performed)** | **Executed (live, read-only)** |
|---|---|---|
| Credential use / privilege escalation | ✅ modeled in the attack chain | ❌ never performed |
| Data access / exfiltration (e.g. `T1530`) | ✅ modeled as a chain step | ❌ no bytes are read beyond a capped confirmation |
| Denial of service / destructive ops | ✅ modeled as expected effect | ❌ never executed |
| Public-exposure reachability | — | ✅ anonymous HTTP `HEAD` (capped `GET` fallback) |
| Cloud asset enumeration | — | ✅ read-only Azure Resource Graph queries |

**The rule:** BreachSim *reasons about* the full adversarial kill chain — including dangerous,
destructive techniques — but the only thing it ever *executes* against a live target is a
**non-destructive, read-only reachability check**. The canonical example is an **anonymous HTTP
`HEAD` request** against a storage endpoint to confirm it answers an unauthenticated caller, which
*proves public exposure* without reading data, writing data, or using a credential.

This check is:

- **read-only** — `HEAD`, or a tiny byte-capped `GET` fallback; never writes, deletes, or mutates;
- **non-destructive** — a single request with a 5-second timeout; no fuzzing, no load, no retries;
- **non-exfiltrating** — records only the status code and content-type; never the response body;
- **SSRF-guarded** — refuses private, loopback, link-local, reserved, multicast, and non-HTTP(S)
  targets (see §5.2).

This is the same evidentiary standard a mature attack-path-validation tool uses to *confirm* an
exposure is real, rather than *claiming* an exploit was performed.

---

## 1.4 Enterprise Product Layer

BreachSim is a **multi-tenant SaaS**, not a single-user script. The enterprise layer is what makes
it "live-ready."

### Multi-tenant isolation boundaries

- Every `run`, `finding`, `resource`, and usage record is **scoped by `tenantId`**.
- The `runs` Cosmos container is **partitioned by `/tenantId`**; cross-tenant reads are impossible at
  the data layer and are additionally rejected at the API layer (`404` on cross-tenant `runId`
  lookups — we return *not found*, never *forbidden*, to avoid leaking existence).
- API credentials resolve to exactly one tenant; the resolved `tenantId` is stamped onto every
  downstream operation.

### Self-service tenant onboarding

`POST /v1/tenants/signup` (canonical alias of `POST /api/v1/tenants/signup`) provisions a tenant and
issues a single-use, **hashed** API key:

- The raw key (`bsk_<43-char-urlsafe-token>`) is returned **once** and never stored.
- Only the **SHA-256 hash** is persisted; lookup uses `hmac.compare_digest` to defeat timing attacks.
- No external IdP is required for the open demo path; Entra ID / MSAL SSO is the enterprise path
  (see §3 Security & Identity).

### Quota management — Free vs. Pro tiers

| Tier | Daily runs | Requests/min (per principal) | Concurrent runs |
|------|-----------:|-----------------------------:|----------------:|
| **Free** | `5` (`plan_free_daily_runs`) | `10` (`rate_limit_runs_per_minute`) | 1 |
| **Pro** | `200` (`plan_pro_daily_runs`) | `120` | 5 |
| **Enterprise** | custom | 600 | 50 |

Quota is enforced at run-start: `POST /v1/runs` returns **`402 Payment Required`** when the tenant's
`runs_today` count meets its `daily_run_limit`. Live usage (runs today, remaining quota, estimated
cost) is exposed via `GET /v1/tenants/me/usage`.

### Billing lifecycle architecture

- **Upgrade:** `POST /v1/tenants/me/checkout` creates a Stripe Checkout session and returns its URL.
  The Stripe SDK is **lazy-loaded**, so a missing key yields a clean `503` rather than an import-time
  crash — the product runs fully without billing configured.
- **Webhook-driven plan changes:** a Stripe webhook flips the tenant's `plan` between `FREE` and
  `PRO` on `checkout.session.completed` / subscription-cancelled events.
- **Cost-safe by default:** every paid or powerful capability sits behind a feature flag defaulting
  to the free/safe value. With Azure OpenAI unset, the swarm runs in a **deterministic stub mode** —
  it never hard-fails and never incurs spend.

---

# 2. THE MULTI-AGENT SWARM DICTIONARY

---

## 2.1 Why a hierarchical micro-agent swarm beats a monolithic prompt chain

A single mega-prompt that can plan *and* execute *and* remediate is both lower-quality and
structurally unsafe. BreachSim decomposes the workload into specialized agents for four concrete
reasons:

1. **Privilege isolation = defense-in-depth.** Tools are allow-listed per agent. The Recon Agent
   can read the resource graph but **cannot** open a GitHub PR; the Execution Agent can run a probe
   but **cannot** write IaC. A prompt injection that compromises one agent cannot reach tools it was
   never granted. The Security Agent holds a **hard veto** between planning and execution.
2. **Contextual focus = higher quality.** Narrow, role-specific system prompts produce more
   reliable, less hallucinated output than one overloaded context window juggling ten concerns.
3. **Modular, independent validation.** The Validator independently confirms the Execution Agent's
   claims, structurally reducing hallucinated "vulnerabilities" — one agent cannot both assert and
   ratify a finding.
4. **Auditability & parallelism.** Each agent's scoped actions produce a clean, replayable
   chain-of-custody (every step is a typed event), and independent agents (Compliance ∥ Remediation)
   run concurrently.

Agents **never call each other directly**. They publish typed **CloudEvents 1.0** envelopes to
**Azure Event Grid**; the orchestrator subscribes, advances the state machine, and invokes the next
agent. Messaging is therefore async, auditable, and replayable.

---

## 2.2 Agent specifications

> Each agent shares a common contract: it receives a typed input, calls **only** its allow-listed
> tools, persists results to Cosmos DB, and emits a completion event. Each runs as an **Azure AI
> Foundry agent** backed by **Azure OpenAI GPT-4o**.

### 2.2.1 Recon Agent

- **Role:** Build the asset network. Maps the attack surface — resources, configurations, and
  identities — for the consented scope.
- **Inputs:** Run scope (`subscriptionId`, `resourceGroups[]`, `sandboxOnly`).
- **Outputs:** Resource list + threat-graph nodes (resources, identities) with `publicExposure`
  flags; emits `breachsim.recon.completed`.
- **Tools:** `query_resource_graph` (Azure Resource Graph, read-only), `write_threat_graph`.
- **System prompt:**
  > You are the Recon Agent of an authorized red-team swarm operating ONLY inside a consented
  > sandbox scope. Using read-only Azure Resource Graph queries, enumerate every resource, its
  > security-relevant configuration, and any attached identity within the provided scope. Flag
  > publicly exposed endpoints and over-privileged role assignments. Output strict JSON: a list of
  > resources `{id, type, name, config, publicExposure}` and identities `{id, type, scope, roles}`.
  > Never query a subscription or resource group outside the provided scope.

### 2.2.2 Planner Agent

- **Role:** Reason over the asset graph to compose the most plausible multi-step attack chain,
  grounded in CVE/ATT&CK context.
- **Inputs:** Recon findings (resources, identities, exposure) + retrieved CVE/ATT&CK context from
  the Research Agent.
- **Outputs:** Ordered attack chain — steps with MITRE technique IDs, preconditions, target assets,
  expected effects, and confidence; emits `breachsim.plan.ready`.
- **Tools:** `search_cve_index` (Azure AI Search vector + semantic), `query_threat_graph`,
  `get_recon_findings`.
- **System prompt:**
  > You are the Planner Agent of an authorized red-team swarm operating ONLY in a consented sandbox.
  > Given the reconnaissance of the target environment and grounded CVE context, compose the most
  > plausible multi-step attack chain an elite adversary would attempt. Output a strict JSON list of
  > steps; each step has `technique` (MITRE ATT&CK ID), `target_asset`, `precondition`,
  > `expected_effect`, and `confidence` (0-1). Prefer chains that escalate privilege or reach
  > sensitive data. Never propose actions outside the provided scope.

### 2.2.3 Execution Agent

- **Role:** Perform safety-constrained, **read-only reachability probes** for the steps the Security
  Agent approved. Models dangerous steps; executes only benign confirmations.
- **Inputs:** Security-approved attack steps.
- **Outputs:** Per-step results (`reachable`, `status`, `contentType`, `anonymous`, evidence note);
  emits `breachsim.exec.completed`.
- **Tools:** `probe_public_endpoint` (SSRF-guarded HTTP `HEAD`/capped `GET`), `collect_artifact`.
- **Guardrail:** Refuses any step not present in the approved plan or any target rejected by the
  SSRF guard; emits a guardrail-violation event instead of improvising.
- **System prompt:**
  > You are the Execution Agent operating under a hard safety constraint. For each explicitly
  > approved step, perform ONLY a non-destructive, read-only reachability check (anonymous HTTP HEAD,
  > or a tiny capped GET fallback). You NEVER use credentials, write or delete data, exfiltrate
  > content, or generate load. Capture only the status code and content-type as evidence. If a target
  > is refused by the SSRF guard or is outside the approved plan, abort that step and emit a
  > guardrail violation. You never improvise new steps.

### 2.2.4 Validator Agent

- **Role:** Analytical gate. Independently confirm proof-of-concept evidence and eliminate false
  positives before anything is reported.
- **Inputs:** Execution results + threat graph.
- **Outputs:** Per-step verdict (`validated: true|false`), reproduction notes, evidence-quality
  score; emits `breachsim.validation.completed`.
- **Tools:** `query_threat_graph`, `verify_artifact`.
- **System prompt:**
  > You are the Validator Agent — the swarm's independent analytical gate. For each executed step,
  > decide whether the captured evidence TRULY demonstrates the claimed exposure. Reject any claim
  > that is unproven, ambiguous, or unsupported by the recorded status code/content-type. Output a
  > verdict (`validated` true/false), a concise reproduction summary, and an evidence-quality score
  > (0-1). You are adversarial toward false positives.

### 2.2.5 Compliance Mapping Agent

- **Role:** Map each verified, risk-scored finding to formal control frameworks for audit-ready
  evidence.
- **Inputs:** Validated, risk-scored findings + audit log.
- **Outputs:** Control-mapped evidence records for **NIST 800-53 Rev 5**, **SOC 2 (CC6–CC7)**, and
  **ISO 27001**; emits `breachsim.compliance.generated`.
- **Tools:** `map_controls`, `render_evidence`.
- **System prompt:**
  > You are the Compliance Mapping Agent. Map each validated finding and its remediation to the
  > relevant NIST 800-53 Rev 5, SOC 2 (CC6–CC7), and ISO 27001 controls. For each mapping output the
  > `framework`, `controlId`, and a one-sentence `rationale` tying the finding to the control intent.
  > Produce audit-ready evidence; never invent a control ID you cannot justify.

### 2.2.6 Remediation Agent

- **Role:** Generate secure Infrastructure-as-Code (Azure Bicep) and open a gated, automated GitHub
  Pull Request that fixes the finding.
- **Inputs:** Validated findings (especially misconfigurations).
- **Outputs:** Minimal IaC diff + (when enabled) a GitHub PR URL and status; emits
  `breachsim.remediation.opened`.
- **Tools:** `generate_iac_fix` (Bicep), `open_github_pr`.
- **Gating:** PR creation is behind `github_pr_enabled`. When disabled, the fix is **proposed**
  (status `proposed`, diff attached) rather than pushed — safe by default.
- **System prompt:**
  > You are the Remediation Agent. For each validated finding, generate a minimal, correct Azure
  > Bicep fix that resolves the exposure using least-privilege, secure-by-default configuration. Then
  > open a GitHub Pull Request whose description states the affected resource, the root cause, and the
  > compliance control the fix satisfies. Change only what is necessary to remediate the finding.

> **Supporting agents in the live build:** the swarm also includes a **Research Agent** (grounds the
> Planner with cited CVE/CWE/ATT&CK context), a **Security Agent** (scope/blast-radius veto between
> planning and execution), a **Risk Agent** (deterministic CVSS-style severity + business impact),
> and a **Memory Agent** (persists and semantically recalls the shared threat graph). The six agents
> above are the externally specified core; these four complete the ten-agent topology.

### Tool / access matrix (least privilege)

| Agent | resource_graph | cve_search | probe | github_pr | threat_graph_write | scope_check |
|-------|:--:|:--:|:--:|:--:|:--:|:--:|
| Recon | ✅ | – | – | – | ✅ | – |
| Research | – | ✅ | – | – | – | – |
| Planner | – | ✅ | – | – | ✅ | – |
| Security | – | – | – | – | – | ✅ |
| Execution | – | – | ✅ | – | ✅ | – |
| Validator | – | ✅ | – | – | ✅ | – |
| Risk | – | – | – | – | ✅ | – |
| Compliance | – | – | – | – | ✅ | – |
| Remediation | – | – | – | ✅ | ✅ | – |
| Memory | – | ✅ | – | – | ✅ | – |

The strict separation (Recon ✗ probe, Execution ✗ github_pr) is itself a security control.

---

# 3. ENTERPRISE SYSTEM ARCHITECTURE & STACK

A zero-trust, event-driven architecture built natively on the Microsoft cloud.

```
                         ┌───────────────────────────────────────────────┐
                         │            Azure Entra ID (OAuth2/OIDC)         │
                         │     Managed Identities · MSAL · RBAC roles      │
                         └───────────────────────────────────────────────┘
                                            │ (token / MI)
   ┌──────────────┐   HTTPS    ┌────────────▼─────────────┐   queue    ┌──────────────────┐
   │ Next.js 14   │ ─────────▶ │  FastAPI API (async)     │ ─────────▶ │ Azure Storage    │
   │ App Router   │  SSE/WS    │  Azure Container Apps     │            │ Queue / Svc Bus  │
   │ (web)        │ ◀───────── │  (stateless, autoscale)   │ ◀───────── │ (durable runs)   │
   └──────────────┘            └───────┬──────────┬────────┘            └──────────────────┘
                                       │          │                              │
                          ┌────────────▼──┐   ┌───▼─────────────┐    ┌───────────▼─────────┐
                          │ Azure OpenAI  │   │ Azure Resource  │    │  Swarm worker pool  │
                          │ GPT-4o        │   │ Graph (recon)   │    │  (agents, Event Grid)│
                          │ + AI Search   │   └─────────────────┘    └──────────┬──────────┘
                          │ (vector mem)  │                                     │
                          └───────────────┘                          ┌──────────▼──────────┐
                                                                      │ Azure Cosmos DB     │
                          ┌───────────────┐   ┌──────────────────┐   │ (NoSQL, /tenantId,  │
                          │ Azure Monitor │   │ Azure Event Grid │   │  /runId partitions) │
                          │ App Insights  │   │ (agent event mesh)│  └─────────────────────┘
                          └───────────────┘   └──────────────────┘
```

| Layer | Technology | Role |
|-------|-----------|------|
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS | Live-streaming agent console + interactive threat graph; SSE today, WebSocket gateway as the target transport |
| **Backend** | Python **FastAPI** on `asyncio` event loops | Async API: auth, quota, run orchestration hand-off, SSE/WS streaming |
| **Database & Memory** | **Azure Cosmos DB for NoSQL** | Tenant metadata, quotas, threat history; partitioned by `/tenantId` (runs) and `/runId` (threat graph, findings, events) |
| **AI Ecosystem** | **Azure AI Foundry**, **Azure OpenAI (GPT-4o)**, **Azure AI Search** | Agent reasoning + vector memory (semantic recall of prior findings/CVEs) |
| **Infra & Event Mesh** | **Azure Container Apps**, **Azure Event Grid**, **Azure Storage Queues** | Stateless auto-scaling hosting + transactional swarm orchestration |
| **Security & Identity** | **Azure Entra ID** + **Managed Identities** | Secretless resource-to-resource auth; MSAL user SSO; RBAC roles |

### Zero-trust & secretless posture

- **Managed Identities** authenticate the API to Cosmos DB, Azure OpenAI, and Resource Graph — **no
  connection strings or keys in app config** in deployed environments (`DefaultAzureCredential`).
- **Entra ID** issues user/enterprise tokens (MSAL login flow); RBAC roles (`breachsim.operator`,
  `breachsim.auditor`, `breachsim.admin`) gate every endpoint.
- **Environment guardrail:** in `development`/`production`, a missing Cosmos configuration raises a
  startup `RuntimeError` — the in-memory store is permitted **only** when `ENVIRONMENT=local`.
- **Stateless API:** Container Apps replicas hold no session state, enabling horizontal autoscale;
  durable run state lives in Cosmos and the queue, not in process memory.

---

# 4. DATA MODEL & API CATALOG SPECIFICATIONS

---

## 4.1 Cosmos DB document schemas

### 4.1.1 `Tenants` collection — partition key `/id`

Tracks safety scopes, hashed keys, plan, and live usage quotas.

```json
{
  "id": "tnt_2178487574ad",
  "tenantId": "tnt_2178487574ad",
  "name": "Contoso Security",
  "email": "secops@contoso.com",
  "plan": "free",
  "active": true,
  "apiKeys": [
    {
      "prefix": "bsk_2178",
      "hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      "createdAt": "2026-06-12T08:09:14Z",
      "lastUsedAt": "2026-06-12T08:09:24Z",
      "revoked": false
    }
  ],
  "safetyScopes": {
    "allowedSubscriptions": ["00000000-0000-0000-0000-000000000000"],
    "sandboxOnly": true,
    "consentAttested": true
  },
  "quota": {
    "dailyRunLimit": 5,
    "runsToday": 1,
    "windowDate": "2026-06-12",
    "ratePerMinute": 10
  },
  "billing": {
    "stripeCustomerId": null,
    "subscriptionStatus": "none"
  },
  "createdAt": "2026-06-12T08:09:14Z",
  "updatedAt": "2026-06-12T08:09:24Z"
}
```

> **Security note:** the raw API key is never stored. Only `apiKeys[].hash` (SHA-256) is persisted;
> lookups use `hmac.compare_digest`. The `prefix` is for human-readable identification only.

### 4.1.2 `Simulations` collection — partition key `/tenantId`

Captures the run, the nested attack-graph nodes/edges, and findings. (Hot-path graph/event detail is
written to `/runId`-partitioned containers; the `Simulations` document is the tenant-partitioned
header + denormalized summary.)

```json
{
  "id": "run_1d2e2d64c4",
  "runId": "run_1d2e2d64c4",
  "tenantId": "tnt_2178487574ad",
  "name": "Live Demo — misconfigured blob",
  "status": "completed",
  "phase": "REPORT",
  "progress": 1.0,
  "scope": {
    "subscriptionId": "00000000-0000-0000-0000-000000000000",
    "resourceGroups": ["rg-breachsim-sandbox"],
    "sandboxOnly": true
  },
  "consent": { "authorizationAcknowledged": true, "authorizedBy": "demo-operator" },
  "graph": {
    "nodes": [
      { "id": "node_internet", "kind": "actor", "label": "Internet" },
      { "id": "node_blob1", "kind": "resource", "label": "stbreachdemo",
        "props": { "publicExposure": true } },
      { "id": "node_configs", "kind": "data", "label": "container:configs" }
    ],
    "edges": [
      { "from": "node_internet", "to": "node_blob1", "relation": "reaches", "confidence": 0.94 },
      { "from": "node_blob1", "to": "node_configs", "relation": "contains", "confidence": 0.88 }
    ]
  },
  "findings": [
    {
      "id": "run_1d2e2d64c4_finding",
      "title": "Public blob with anonymous read → secrets exposure",
      "technique": "T1530",
      "severity": "critical",
      "validated": true,
      "resourceType": "storage",
      "risk": { "cvss": 9.1, "businessImpact": "high" },
      "attackSteps": [
        { "order": 1, "technique": "T1595", "targetAsset": "stbreachdemo",
          "result": "public endpoint answered anonymous HEAD" },
        { "order": 2, "technique": "T1530", "targetAsset": "container:configs",
          "result": "modeled: appsettings.json reachable" }
      ],
      "compliance": [
        { "framework": "NIST-800-53", "controlId": "AC-3", "rationale": "Access enforcement failure" },
        { "framework": "SOC2", "controlId": "CC6.1", "rationale": "Logical access controls" },
        { "framework": "ISO27001", "controlId": "A.5.15", "rationale": "Access control policy" }
      ],
      "remediation": {
        "iacType": "bicep",
        "status": "proposed",
        "prUrl": null,
        "diff": "resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = { properties: { allowBlobPublicAccess: false } }"
      },
      "evidence": ["Endpoint answered an unauthenticated HEAD (200).", "Public access enabled on account."]
    }
  ],
  "stats": { "resources": 12, "findings": 1, "tokensUsed": 84210, "estimatedCostUsd": 0.42 },
  "startedAt": "2026-06-12T08:09:24Z",
  "completedAt": "2026-06-12T08:09:31Z"
}
```

### Indexing policy (operative)

- Composite index `findings`: `(/runId ASC, /severity DESC)` — dashboard sort.
- Composite index `agent_events`: `(/runId ASC, /ts ASC)` — ordered SSE replay.
- Composite index `threat_graph`: `(/runId ASC, /kind ASC)` — fast node/edge split.
- Large `props/*` and `payload/*` blobs are **excluded** from indexing to cut RU cost.
- **Change feed** enabled on `agent_events` (drives the live stream) and `audit_log` (compliance).

---

## 4.2 API specification

Base URL: `https://api.breachsim.io/v1` (local: `http://localhost:8000/v1`). Error envelope is
**RFC 7807** (`type`, `title`, `status`, `detail`, `instance`, `traceId`).

### 4.2.1 `POST /api/v1/tenants/signup`

Self-service onboarding. Gated by `breachsim_public_signup`.

**Request**
```json
{ "name": "Contoso Security", "email": "secops@contoso.com" }
```

**Response `201 Created`** (the raw key is shown exactly once)
```json
{
  "tenantId": "tnt_2178487574ad",
  "name": "Contoso Security",
  "plan": "free",
  "apiKey": "bsk_ny8_Jl-cj6sJ_hzFUf8_B5DjkTeKow8XZL02Gh4K_fU",
  "keyPrefix": "bsk_ny8",
  "dailyRunLimit": 5,
  "createdAt": "2026-06-12T08:09:14Z"
}
```

| Code | Meaning |
|------|---------|
| 201 | Tenant created |
| 400 | Validation error (missing/invalid name or email) |
| 403 | Public signup disabled (invite-only mode) |
| 409 | Email already registered |

### 4.2.2 `POST /api/v1/simulations/start`

Asynchronous worker initialization hook. (Canonical route in the live build: `POST /v1/runs`.)
Requires the `breachsim.operator` role and a consent attestation.

**Request**
```json
{
  "name": "Q2 prod posture check",
  "scope": {
    "subscriptionId": "00000000-0000-0000-0000-000000000000",
    "resourceGroups": ["rg-breachsim-sandbox"],
    "sandboxOnly": true
  },
  "authorizationAcknowledged": true,
  "authorizedBy": "demo-operator",
  "options": { "maxTokenBudget": 200000, "frameworks": ["NIST-800-53", "SOC2", "ISO27001"] }
}
```

**Response `202 Accepted`** — the run is enqueued; a background worker advances the state machine.
```json
{
  "runId": "run_1d2e2d64c4",
  "status": "queued",
  "createdAt": "2026-06-12T08:09:24Z",
  "links": {
    "self": "/v1/runs/run_1d2e2d64c4",
    "events": "/v1/runs/run_1d2e2d64c4/events",
    "graph": "/v1/runs/run_1d2e2d64c4/graph"
  }
}
```

| Code | Meaning |
|------|---------|
| 202 | Run accepted (async) |
| 400 | Validation error |
| 401 | Missing/invalid credential |
| 403 | Consent not attested / scope violation / RBAC denial |
| 402 | Daily run quota exhausted |
| 429 | Rate limited (`Retry-After` header set) |

### 4.2.3 `GET /api/v1/simulations/{id}/graph`

Returns the attack graph (nodes + edges). (Canonical route: `GET /v1/runs/{runId}/graph`.)
Requires `breachsim.operator` or `breachsim.auditor`.

**Response `200 OK`**
```json
{
  "runId": "run_1d2e2d64c4",
  "nodes": [
    { "id": "node_internet", "kind": "actor", "label": "Internet" },
    { "id": "node_blob1", "kind": "resource", "label": "stbreachdemo",
      "props": { "publicExposure": true } },
    { "id": "node_configs", "kind": "data", "label": "container:configs" }
  ],
  "edges": [
    { "from": "node_internet", "to": "node_blob1", "relation": "reaches", "confidence": 0.94 },
    { "from": "node_blob1", "to": "node_configs", "relation": "contains", "confidence": 0.88 }
  ]
}
```

| Code | Meaning |
|------|---------|
| 200 | OK |
| 401 | Missing/invalid credential |
| 403 | RBAC denial |
| 404 | Run not found (also returned for cross-tenant `runId` to avoid existence leaks) |

---

# 5. CODE IMPLEMENTATION DEEP DIVE

Complete, production-grade foundation blocks. (Aligned with the live build; the WebSocket console in
§5.3 is the target transport — the current build streams the same envelopes over Server-Sent
Events.)

---

## 5.1 Core API Framework — `main.py`

Async FastAPI app implementing token authentication, dependency injection, quota validation, and a
safe background task hand-off.

```python
"""BreachSim FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.core.cosmos import repository
from app.core.logging import configure_logging, get_logger
from app.security import Principal, get_principal, require_role
from app.services.billing import within_quota
from app.services.run_manager import run_manager
from app.services.tenant_manager import tenant_manager

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect durable stores on startup; release them on shutdown."""
    logger.info("BreachSim orchestrator starting", extra={"trace_id": "boot"})
    await repository.connect()          # raises in non-local envs if Cosmos is unset
    await tenant_manager.load()
    await run_manager.load()
    yield
    await repository.close()
    logger.info("BreachSim orchestrator stopped")


app = FastAPI(
    title="BreachSim — Agentic Red Team Swarm",
    description="Autonomous agent swarm that continuously red-teams your cloud posture.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunScope(BaseModel):
    subscription_id: str = Field(..., alias="subscriptionId")
    resource_groups: list[str] = Field(default_factory=list, alias="resourceGroups")
    sandbox_only: bool = Field(True, alias="sandboxOnly")

    model_config = {"populate_by_name": True}


class StartRunRequest(BaseModel):
    name: str
    scope: RunScope
    authorization_acknowledged: bool = Field(..., alias="authorizationAcknowledged")
    authorized_by: str = Field(..., alias="authorizedBy")

    model_config = {"populate_by_name": True}


class StartRunResponse(BaseModel):
    run_id: str = Field(..., alias="runId")
    status: str
    links: dict[str, str]

    model_config = {"populate_by_name": True}


@app.get("/health")
async def health() -> dict:
    """Liveness/readiness. Reports which durable store is active."""
    return {
        "status": "ok",
        "store": repository.backend,            # "cosmos" | "memory"
        "environment": settings.environment,
        "version": "1.0.0",
        "service": "breachsim-orchestrator",
    }


@app.post(
    "/v1/runs",
    response_model=StartRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(
    payload: StartRunRequest,
    background: BackgroundTasks,
    principal: Principal = Depends(require_role("breachsim.operator")),
) -> StartRunResponse:
    """Validate consent + quota, enqueue the run, and hand off to a background worker."""
    if not payload.authorization_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization-to-test attestation is required.",
        )
    if not settings.is_local_environment and not payload.scope.sandbox_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non-sandbox scopes are not permitted in this environment.",
        )
    if not within_quota(principal.tid):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Daily run quota exhausted. Upgrade to Pro for a higher limit.",
        )

    run = await run_manager.create(
        tenant_id=principal.tid,
        name=payload.name,
        scope=payload.scope.model_dump(by_alias=True),
        authorized_by=payload.authorized_by,
    )
    # Safe hand-off: never block the request thread on the swarm pipeline.
    background.add_task(run_manager.execute, run.run_id, payload.scope.model_dump(by_alias=True))

    return StartRunResponse(
        runId=run.run_id,
        status="queued",
        links={
            "self": f"/v1/runs/{run.run_id}",
            "events": f"/v1/runs/{run.run_id}/events",
            "graph": f"/v1/runs/{run.run_id}/graph",
        },
    )


@app.get("/v1/runs/{run_id}/graph")
async def get_graph(
    run_id: str,
    principal: Principal = Depends(get_principal),
) -> dict:
    """Return the attack graph; 404 on cross-tenant access (no existence leak)."""
    detail = run_manager.get(run_id)
    if detail is None or detail.tenant_id != principal.tid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return await repository.get_graph(run_id)
```

---

## 5.2 Security Guardrail Engine — `security_gate.py`

Inbound SSRF guardrail: intercepts and evaluates destination probe URIs, resolves DNS, and blocks
private, loopback, link-local, reserved/multicast, and cloud-metadata (`169.254.x.x`) ranges before
any request leaves the process.

```python
"""SSRF guardrail for all outbound validation probes.

Every probe URI passes through `assert_safe_target` before a request is made. The guard
performs scheme validation, DNS resolution, and per-address range checks, blocking the
cloud-metadata endpoint and all non-public address space. Fails closed.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)

# The Azure/AWS/GCP Instance Metadata Service lives here; an SSRF that reaches it can
# steal Managed Identity tokens. It is explicitly denied even though 169.254.0.0/16 is
# already link-local — defence in depth.
_METADATA_IP = ipaddress.ip_address("169.254.169.254")
_ALLOWED_SCHEMES = ("http", "https")


class SSRFBlocked(Exception):
    """Raised when a probe target is rejected by the SSRF guard."""


def _resolve_addresses(hostname: str) -> list[ipaddress._BaseAddress]:
    """Resolve every A/AAAA record for ``hostname``. Raises on resolution failure."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:  # unresolvable host → fail closed
        raise SSRFBlocked(f"Hostname '{hostname}' could not be resolved.") from exc

    addresses: list[ipaddress._BaseAddress] = []
    for info in infos:
        raw = info[4][0]
        try:
            addresses.append(ipaddress.ip_address(raw))
        except ValueError as exc:
            raise SSRFBlocked(f"Unparseable address '{raw}' for host '{hostname}'.") from exc
    return addresses


def _is_disallowed(ip: ipaddress._BaseAddress) -> bool:
    """True if ``ip`` is in any non-public or metadata range."""
    return (
        ip == _METADATA_IP
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_safe_target(url: str) -> None:
    """Validate a probe target. Raises ``SSRFBlocked`` if the URL is unsafe.

    A URL is safe only if (1) its scheme is http/https, (2) it has a hostname, and
    (3) EVERY resolved address is publicly routable and not the metadata endpoint.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise SSRFBlocked(f"Scheme '{parsed.scheme}' is not allowed (http/https only).")
    if not parsed.hostname:
        raise SSRFBlocked("Target URL has no hostname.")

    for ip in _resolve_addresses(parsed.hostname):
        if _is_disallowed(ip):
            logger.warning(
                "SSRF guard blocked target",
                extra={"host": parsed.hostname, "resolved": str(ip)},
            )
            raise SSRFBlocked(
                f"Target '{parsed.hostname}' resolves to a blocked address ({ip})."
            )


def is_safe_target(url: str) -> bool:
    """Non-raising convenience wrapper around :func:`assert_safe_target`."""
    try:
        assert_safe_target(url)
        return True
    except SSRFBlocked:
        return False
```

---

## 5.3 Live UI Log Streamer — `LiveSwarmConsole.tsx`

A React/TypeScript component that opens a WebSocket to stream live agent communication logs into a
scannable console. It auto-reconnects with backoff, auto-scrolls, and colour-codes per agent.

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

export interface SwarmLog {
  agentId: string;
  eventType: string;
  summary: string;
  ts: string;
}

const AGENT_COLOR: Record<string, string> = {
  recon: "text-signal",
  planner: "text-signal",
  research: "text-signal",
  security: "text-warn",
  execution: "text-breach",
  validator: "text-safe",
  risk: "text-warn",
  compliance: "text-signal",
  remediation: "text-safe",
  memory: "text-muted",
};

function wsUrl(runId: string): string {
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
  const proto = base.startsWith("https") ? "wss" : "ws";
  const host = base.replace(/^https?:\/\//, "");
  return `${proto}://${host}/v1/runs/${runId}/ws`;
}

export default function LiveSwarmConsole({
  runId,
  credential,
}: Readonly<{ runId: string; credential: string }>) {
  const [logs, setLogs] = useState<SwarmLog[]>([]);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let closedByUs = false;

    function connect() {
      socket = new WebSocket(`${wsUrl(runId)}?apiKey=${encodeURIComponent(credential)}`);

      socket.onopen = () => {
        setConnected(true);
        retryRef.current = 0;
      };

      socket.onmessage = (event) => {
        try {
          const log = JSON.parse(event.data as string) as SwarmLog;
          setLogs((prev) => [...prev, log]);
        } catch {
          // Ignore malformed frames rather than tearing down the stream.
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (closedByUs) return;
        // Exponential backoff capped at 10s.
        const delay = Math.min(1000 * 2 ** retryRef.current, 10_000);
        retryRef.current += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => socket?.close();
    }

    connect();

    return () => {
      closedByUs = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [runId, credential]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [logs]);

  return (
    <section className="rounded-xl border border-white/5 bg-panel p-4">
      <header className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
          Live Swarm Console
        </h3>
        <span
          className={`flex items-center gap-1.5 text-xs ${connected ? "text-safe" : "text-breach"}`}
        >
          <span
            className={`h-2 w-2 rounded-full ${connected ? "bg-safe animate-pulseSoft" : "bg-breach"}`}
          />
          {connected ? "streaming" : "reconnecting…"}
        </span>
      </header>

      <div
        ref={scrollRef}
        className="h-72 overflow-y-auto font-mono text-xs leading-relaxed"
      >
        {logs.length === 0 ? (
          <p className="text-muted">Waiting for the swarm to report…</p>
        ) : (
          logs.map((log, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <div key={`${log.ts}-${i}`} className="flex gap-2 py-0.5">
              <span className="text-muted">{new Date(log.ts).toLocaleTimeString()}</span>
              <span className={AGENT_COLOR[log.agentId] ?? "text-white"}>
                [{log.agentId}]
              </span>
              <span className="text-white/90">{log.summary}</span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
```

---

# 6. PLAYBOOK, ROADMAP & LIVE DEMO RUNBOOK

---

## 6.1 Hackathon Build Plan — 4-phase milestone timeline

| Phase | Milestone | Key deliverables | Est. effort | Dependencies |
|------:|-----------|------------------|------------:|--------------|
| **1** | **Core Infrastructure** | FastAPI skeleton, async lifespan, Cosmos repository (+ in-memory fallback), tenant manager, API-key auth, SSRF guard, run manager + background hand-off | ~16 h | Azure subscription, Container Apps env, Cosmos account |
| **2** | **Agent Prompt Tuning** | 10-agent swarm, Event-Grid/event envelopes, Planner/Research grounding via AI Search, deterministic stub mode, Validator false-positive gate, deterministic risk scoring | ~20 h | Phase 1; Azure OpenAI GPT-4o deployment |
| **3** | **Telemetry & UI** | Next.js console, live SSE/WS stream, attack-graph visualization, usage/quota panel, auth gate + self-serve signup, onboarding tour, App Insights wiring | ~18 h | Phase 1 API contracts; Phase 2 event stream |
| **4** | **CI/CD & Deploy** | Bicep IaC, GitHub Actions (`ruff` + `pytest` + dependency scan), Container Apps deploy, Entra ID/MSAL SSO path, health/readiness, runbook | ~12 h | Phases 1–3; GitHub repo + Azure service principal |

**Critical path:** Phase 1 → Phase 2 (agents need the run manager + stores) → Phase 3 (UI needs the
event stream) → Phase 4 (deploy needs a green test suite). Telemetry instrumentation in Phase 3 can
proceed in parallel with late Phase 2 prompt tuning.

---

## 6.2 Three-Minute High-Impact Demo Script

A minute-by-minute runbook designed to show **real AI collaboration** and **business value**.

### 0:00 – 0:30 · Intro — the gap

- **On screen:** the BreachSim dashboard (dark console), empty, "Deploy Swarm" button visible.
- **Narration:** *"Your cloud changes dozens of times a day. Your pen tests happen once a quarter.
  Everything in between is a blind spot. BreachSim is an autonomous red-team swarm that closes that
  gap — continuously, and safely."*
- **Action:** point to the live `/health` badge showing the deployed environment — *"this is running
  right now on Azure Container Apps."*

### 0:30 – 1:45 · Swarm in action — real collaboration

- **Action:** click **Deploy Swarm**. The Live Swarm Console begins streaming.
- **On screen:** agents light up in sequence — `[recon]` discovers 12 resources and a public blob,
  `[planner]` composes a 3-step chain (`recon → public blob → secrets`), `[security]` approves the
  in-scope steps, `[execution]` runs a **read-only HEAD** and confirms the endpoint answers
  anonymously, `[validator]` ratifies the finding.
- **Narration:** *"These aren't scripted steps — each agent is a specialized GPT-4o reasoner with its
  own tools. Notice the Security Agent gates execution, and the Execution Agent only ever performs a
  benign reachability check. We model the attack; we never exploit it."*
- **On screen:** the attack graph renders nodes/edges live as the chain forms.

### 1:45 – 2:45 · Automated remediation — closing the loop

- **On screen:** the Run Summary banner appears — *time to first finding*, *critical exposures*,
  *attack chains discovered*, and **GitHub PR opened**.
- **Action:** click the finding → show severity `critical (CVSS 9.1)`, the NIST/SOC 2/ISO mappings,
  and the **Bicep diff** that sets `allowBlobPublicAccess: false`.
- **Narration:** *"BreachSim didn't just find it — it wrote the fix as Infrastructure-as-Code and
  opened a pull request, mapped to the exact compliance controls an auditor cares about. Finding to
  reviewable fix, with zero human in the loop."*

### 2:45 – 3:00 · The close — business value

- **Narration:** *"Continuous, safe, self-healing cloud validation — red-team outcomes at deploy
  speed, built entirely on the Microsoft AI stack. That's BreachSim."*
- **On screen:** the dashboard with the completed run, green PR link, and usage/quota panel showing
  the multi-tenant SaaS layer.

---

## Appendix A — Corrections applied from `live-ready-assessment.md`

This spec incorporates the assessment's hardening recommendations as **first-class requirements**:

- **Durable execution** (§3, §6.1): run execution moves to an Azure Storage Queue / Service Bus with
  idempotent workers so restarts never drop in-flight runs.
- **Cosmos-by-default** (§3, §5.1): deployed environments require Cosmos; the in-memory store is
  permitted only when `ENVIRONMENT=local` (enforced at startup).
- **Learning loop** (§2.2.4): operator confirm/dismiss feedback feeds finding ranking and severity.
- **Attack-graph visualization** (§5.3, §6.2): findings render as a node/edge graph, not a flat log.
- **Enterprise SSO** (§3): Entra ID / MSAL login is a showable, end-to-end path.
- **CI security gate** (§6.1): `ruff` + `pytest` **plus** a dependency scan are required to merge.
- **Safety transparency** (§1.3): the in-app `/safety` page mirrors the simulate-vs-execute boundary.
```
