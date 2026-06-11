# BreachSim — Live-Ready Assessment & Hackathon Scorecard

**Project:** BreachSim — Agentic Red Team Swarm
**Hackathon:** Microsoft Build AI 2026
**Primary theme:** Security in the Agentic Future · **Secondary:** Agent Swarms
**Live demo:** Azure Container Apps (API + Web), CI via GitHub
**Status:** Working, deployed end-to-end product with self-service onboarding, billing, and safe live validation.

> This document explains what BreachSim is "in and out", scores it honestly against the
> six published evaluation criteria, lists its real flaws, and proposes concrete improvements.

---

## 1. What BreachSim Is (in & out)

BreachSim is an **AI-native adversarial-simulation platform**. A swarm of specialized agents
continuously red-teams a cloud posture, reasons over attack paths, validates exposures with
**benign read-only** probes, and closes the loop by emitting remediation Infrastructure-as-Code
as a GitHub pull request.

### The agent swarm

| Agent | Responsibility |
|---|---|
| Recon | Maps attack surface (resources, configs, identities) via Azure Resource Graph (read-only). |
| Planner | Reasons over a CVE/attack graph to compose exploit *chains*. |
| Execution | Models payloads; for public-exposure checks performs **read-only reachability validation** (never exploits). |
| Validator | Confirms exposure and assigns deterministic risk severity. |
| Security | Enforces scope/consent guardrails; can veto unsafe actions. |
| Compliance | Maps findings to NIST 800-53 / SOC 2 / ISO 27001. |
| Remediation | Emits Bicep/Terraform fixes and opens a GitHub PR (gated). |
| Memory | Persists and recalls the shared threat graph. |

### How it actually runs (the honest flow)

`discover → chain → validate → remediate`. Note we deliberately say **validate**, not
"exploit" — BreachSim **models** dangerous techniques (data access, credential use, DoS) and
only performs **safe, read-only** active checks (e.g. anonymous HTTP HEAD against a storage URL
to confirm public exposure). This is a product decision, not a limitation gap — it's what makes
it safe to point at real tenants.

### Product layer (what makes it "live ready")

- **Self-service onboarding:** `POST /v1/tenants/signup` issues a hashed API key (`bsk_…`),
  shown once. No IdP required for the open demo.
- **Multi-tenant isolation:** runs, usage, and quotas are scoped per tenant.
- **Plans & quotas:** Free (5 runs/day) and Pro (200 runs/day) with live usage tracking.
- **Billing:** Stripe Checkout upgrade-to-Pro + webhook-driven plan changes (optional, lazy-loaded).
- **Guardrails:** consent attestation, scope allow-listing, sandbox-only enforcement, per-caller
  rate limiting, and an **SSRF guard** on every probe (rejects private/loopback/metadata IPs).
- **Cost-safe by default:** every paid/powerful capability is behind a feature flag defaulting to
  the free/safe value; with Azure OpenAI unset, the swarm runs in a free deterministic stub mode.

### Microsoft AI stack usage (eligibility requirement — met)

Azure AI Foundry / Azure OpenAI (GPT-4o reasoning), Azure Container Apps (hosting), Azure
Resource Graph (recon), Azure Cosmos DB (threat memory), Entra ID (enterprise auth), Azure
Monitor / Application Insights (telemetry), and GitHub Copilot in development (disclosed).

---

## 2. Scorecard Against the Six Evaluation Criteria

Self-assessed coverage. Weighted total reflects how complete each dimension is **for a hackathon
prototype**, not against a mature commercial product.

| # | Dimension | Weight | Coverage | Weighted |
|---|---|---:|---:|---:|
| 1 | AI Integration & Intelligence Design | 25% | **85%** | 21.3 |
| 2 | System Architecture & Engineering Quality | 25% | **88%** | 22.0 |
| 3 | Communication, Presentation & UX | 15% | **80%** | 12.0 |
| 4 | Prototype Readiness & Scalability | 15% | **82%** | 12.3 |
| 5 | Problem Depth & Product Clarity | 10% | **85%** | 8.5 |
| 6 | Market Understanding & Product Fit | 10% | **80%** | 8.0 |
| | **Overall** | **100%** | | **≈ 84 / 100** |

### 1 — AI Integration & Intelligence Design — ~85%

**Strong:** A genuine multi-agent swarm with distinct roles, GPT-4o reasoning over an attack
graph, shared threat memory, and a deterministic fallback so it never hard-fails. Maps directly
to the *Agent Swarms* and *Security in the Agentic Future* themes.
**Gap:** Reasoning quality depends on a single model and prompt chain; no learning/feedback loop
yet, and agent-to-agent negotiation is orchestrated rather than emergent.

### 2 — System Architecture & Engineering Quality — ~88%

**Strong:** Clean FastAPI + Next.js separation, lazy cloud SDK imports (offline-safe), 34 passing
tests, lint-clean, type-checked, multi-tenant data scoping, SSRF guard, rate limiting, telemetry,
and IaC-based deploy. This is the strongest dimension.
**Gap:** In-memory stores are used when Cosmos is absent (no durability there); single-region; no
load/perf testing; no automated security scanning in CI yet.

### 3 — Communication, Presentation & UX — ~80%

**Strong:** Live animated swarm console, auth gate with self-serve signup, usage panel with plan/
quota/cost, clear README and runbook. Sub-90-second "wow" demo.
**Gap:** No guided onboarding tour, limited mobile polish, no in-app docs/help, and findings could
be visualized as an attack graph rather than a log.

### 4 — Prototype Readiness & Scalability — ~82%

**Strong:** Actually deployed and reachable; containerized; stateless API scales horizontally on
Container Apps; quotas protect cost.
**Gap:** Background run execution is in-process (not a durable queue), so a restart drops in-flight
runs; no autoscale rules tuned; billing webhook idempotency is basic.

### 5 — Problem Depth & Product Clarity — ~85%

**Strong:** Real, well-articulated pain (red-teaming cadence vs. cloud change velocity), clear
ICP (security teams/CISOs), and a defensible safety stance.
**Gap:** Outcome metrics (e.g. mean-time-to-remediate improvement) are asserted, not yet measured
with real users.

### 6 — Market Understanding & Product Fit — ~80%

**Strong:** Clear market sizing narrative, pricing tiers, and a self-serve + enterprise path.
**Gap:** No competitive teardown vs. existing CSPM/CNAPP/BAS vendors, and no validated willingness-
to-pay from design partners.

---

## 3. Honest Flaws & Risks

1. **"Exploitation" is modeled, not performed.** Dangerous techniques are simulated; only
   read-only validation is live. This is intentional and safe, but judges expecting real exploit
   execution should understand the boundary. *(Framing risk, not a bug.)*
2. **Durability gaps.** Without Cosmos configured, tenants/runs live in memory; in-flight runs are
   lost on restart because execution isn't backed by a durable queue.
3. **Single model / single region.** Reasoning quality and availability hinge on one Azure OpenAI
   deployment in one region; no fallback model or multi-region failover.
4. **No learning loop.** The swarm doesn't improve from past runs or operator feedback yet.
5. **Webhook & quota hardening.** Stripe webhook idempotency and quota race conditions are
   minimally handled — fine for demo, not for high concurrency.
6. **Limited automated security testing.** No SAST/DAST/dependency-scan gate in CI; secrets
   hygiene relies on convention.
7. **Cost ceiling clarity.** Only Azure OpenAI incurs real spend; on the free tier, GPT-4o
   capacity (1 TPM) bottlenecks concurrent runs — acceptable for demo, not production load.
8. **Auth duality on the public demo.** The demo runs with enterprise auth off and relies on
   self-serve API keys; this is documented but is a posture reviewers should note.

---

## 4. Suggestions to Make It Better

**Quick wins (hackathon polish)**
- Add an attack-graph visualization of findings (nodes = resources, edges = chained techniques).
- Add a guided "Run your first simulation" onboarding tour and in-app help.
- Add a CI gate: `ruff` + `pytest` (already there) **plus** dependency scan (e.g. `pip-audit`)
  and a SAST step.
- Record measured demo metrics (time-to-detect, time-to-PR) and surface them in the UI.

**Architecture hardening**
- Move run execution to a durable queue (Azure Storage Queues / Service Bus) with idempotent
  workers so restarts don't drop runs.
- Persist tenants/runs to Cosmos by default in deployed environments; keep in-memory only for
  local/offline.
- Add Stripe webhook idempotency keys and quota checks behind an atomic counter.

**Intelligence depth**
- Add a feedback/learning loop: operators confirm/dismiss findings; feed signal back into ranking.
- Multi-model strategy: a cheaper model for triage, GPT-4o for deep chains; add a fallback model.
- Ground reasoning with live CVE/NVD enrichment in deployed mode (already scaffolded).

**Market & product fit**
- Publish a competitive teardown vs. CSPM/CNAPP/BAS tools and a clear "why us" wedge.
- Recruit 2–3 design partners and capture willingness-to-pay + a real outcome metric.
- Add an enterprise SSO demo path (MSAL login) so the Entra-auth mode is showable end-to-end.

**Trust & safety**
- Publish a "what we do / don't do" safety page in-app (mirrors the runbook).
- Add audit-log export and a per-finding evidence bundle for compliance reviewers.

---

## 5. Bottom Line

BreachSim is a **genuinely working, deployed, multi-tenant agentic security product** with
billing, guardrails, and a safe live-validation path — not a mockup. Against the published
criteria it self-scores **≈ 84/100**, strongest on engineering quality and AI design. Its main
honest limitations are the modeled-vs-real exploitation boundary (deliberate), durability without
Cosmos, and the absence of a learning loop and competitive validation. The improvements above are
mostly incremental hardening rather than rebuilds — which is itself evidence the foundation is sound.
