# BreachSim — Production Readiness Plan

> **Where we are:** A fully working, verified prototype. The complete 10-agent swarm runs
> end-to-end (backend tests green, lint clean, frontend builds clean, live SSE feed verified).
> Today it runs in **demo/stub mode** with in-memory fallbacks for every cloud dependency.
>
> **Where we need to go:** A live, multi-tenant SaaS that safely red-teams real customer Azure
> tenants. This document is the gap list and the plan to close it.

---

## 0. Verified status (what works today)

| Check | Result |
|-------|--------|
| Backend unit/E2E tests (`pytest`) | ✅ 2 passed |
| Lint (`ruff`) | ✅ clean |
| Full swarm run (10 agents) | ✅ completes, CVSS 9.1 finding + remediation PR |
| Live SSE agent feed (paced) | ✅ streams every phase |
| Late-subscribe SSE replay | ✅ 20 events replayed after completion |
| Run stats (resources/findings) | ✅ populated |
| Frontend type-check | ✅ clean |
| Frontend production build | ✅ compiles, 107 kB first load |

**Two bugs found and fixed during verification:**
1. **SSE race condition** — fast runs completed before the UI subscribed, leaving the feed empty.
   Fixed with bounded per-run **event history + replay** in `EventBus`.
2. **No demo pacing** — stub agents returned instantly, so nothing was watchable. Added
   `BREACHSIM_DEMO_PACING_MS` (default 900 ms; set 0 in prod).

---

## 1. The honest gap: prototype → production

Everything below is currently **simulated** and must become **real** for a live product. Each item
is marked with effort (S/M/L) and risk.

### 1.1 AI / Agents
| Gap | Today | Production need | Effort |
|-----|-------|-----------------|:---:|
| LLM calls | Deterministic stubs (`fallback=`) | Real Azure OpenAI GPT-4o with ret/backoff, token budgeting | M |
| Agent runtime | Plain Python classes | Azure AI Foundry agents with tracing + tool calling | L |
| RAG corpus | 1 canned CVE | Real CVE/CWE/MITRE ATT&CK corpus indexed in Azure AI Search | M |
| Reasoning quality | N/A | Prompt eval harness, golden-set regression tests, guardrail evals | L |
| Cost control | None | Per-run + per-tenant token budgets, circuit breakers | M |

### 1.2 Recon (the biggest real-engineering item)
| Gap | Today | Production need | Effort |
|-----|-------|-----------------|:---:|
| Resource discovery | Hard-coded list | **Azure Resource Graph** + ARM queries against the consented tenant | L |
| Identity mapping | Stub | Entra ID / RBAC enumeration (read-only) | L |
| Exposure analysis | Stub | Real public-endpoint, NSG, storage ACL inspection | L |

### 1.3 Execution (highest security risk — handle with care)
| Gap | Today | Production need | Effort |
|-----|-------|-----------------|:---:|
| Payloads | Simulated strings | **Safe, non-destructive validation probes only** in an isolated sandbox | L |
| Sandbox | Returns canned text | Real Azure Functions in a locked-down VNet, no prod peering, egress-deny | L |
| Blast radius | Guardrail stub | Hard caps, dry-run mode, kill-switch, per-step approval | M |

> ⚠️ **Critical:** A production red-team tool that executes against customer tenants is a regulated,
> high-liability capability. Default posture must be **read-only assessment + simulated exploit
> reasoning**. Any *active* exploitation requires explicit written customer authorization, scoped
> Rules of Engagement, and legal review. Ship "assess + reason + remediate" first; gate active
> execution behind a separate, contractually-controlled feature flag.

### 1.4 Data
| Gap | Today | Production need | Effort |
|-----|-------|-----------------|:---:|
| Persistence | In-memory dict | Real Cosmos DB (containers already defined in Bicep) | S |
| Audit log | In-memory | Immutable Cosmos container + change feed → archive | M |
| Artifacts | Fake blob refs | Real Blob Storage with SAS + lifecycle to cold tier | M |
| Multi-tenancy | None | Tenant isolation (partition strategy + RBAC + data residency) | L |

### 1.5 Auth & Security
| Gap | Today | Production need | Effort |
|-----|-------|-----------------|:---:|
| API auth | Bypassed in `local` mode | Entra ID JWT validation (code exists, needs PyJWT dep + wiring) | S |
| Tenant onboarding | Stub endpoint | Real Entra **admin-consent** multi-tenant app + least-priv roles | L |
| Secrets | `.env` | Key Vault + Managed Identity everywhere (no keys) | M |
| GitHub PRs | Simulated URL | Real GitHub App auth (PyGithub) creating branches/PRs | M |
| Network | Open | Private endpoints, WAF, VNet for sandbox, egress control | L |
| AppSec | Basic | SAST/DAST, dependency scanning, secret scanning, pen-test of BreachSim itself | M |

### 1.6 Reliability & Ops
| Gap | Today | Production need | Effort |
|-----|-------|-----------------|:---:|
| State | In-process `RunManager` | Durable orchestration (Durable Functions or queue + Cosmos state) | L |
| Concurrency | Single process | Horizontal scale on Container Apps (KEDA), idempotent handlers | M |
| Observability | JSON logs | App Insights traces, dashboards, alerts, SLOs | M |
| Rate limiting | Documented only | Real token-bucket (APIM or middleware + Redis) | M |
| CI/CD | Workflow written | Wire OIDC secrets, environments, approvals, smoke tests | S |
| Backups/DR | None | Cosmos continuous backup, multi-region, runbooks | M |

### 1.7 Product / Compliance / GTM
| Gap | Need | Effort |
|-----|------|:---:|
| Compliance mappings | Validate NIST/SOC2/ISO mappings with a GRC expert | M |
| Your own SOC 2 | BreachSim itself needs SOC 2 Type II to sell to CISOs | L |
| Legal | Rules of Engagement, liability, customer authorization contracts | L |
| Billing | Stripe/marketplace, metering on runs/tokens | M |
| Pricing & packaging | Tiers (Free/Pro/Enterprise) + compliance upsell | S |

---

## 2. Recommended path to live (phased)

### Phase A — "Real but read-only" MVP (closes biggest gaps, lowest risk)
1. Wire **real Azure OpenAI** (drop stubs).
2. Wire **real Cosmos DB** persistence (Bicep already provisions it).
3. **Real Recon** via Azure Resource Graph (read-only) on a single consented tenant.
4. **Entra ID auth** on the API (turn off `local` bypass).
5. Keep Execution **simulated/reasoning-only**; remediation PRs **real** (GitHub App).
6. Deploy via `azd up`; enable App Insights.
> Outcome: a genuinely useful posture-assessment + remediation product with zero active-exploit
> liability. Sellable to design partners.

### Phase B — Hardened multi-tenant SaaS
1. Multi-tenant Entra app + admin consent onboarding.
2. Durable orchestration + horizontal scale + rate limiting.
3. Key Vault + Managed Identity end-to-end; private networking.
4. Real CVE corpus + prompt eval harness.
5. Billing + tiers; observability dashboards + alerts; DR.

### Phase C — Active exploitation (gated, contractual)
1. Isolated sandbox Functions (VNet, egress-deny) with **non-destructive** validation probes.
2. Rules of Engagement engine, kill-switch, per-step human approval.
3. Legal + insurance + customer authorization workflow.
4. BreachSim's own SOC 2 Type II.

---

## 3. "Definition of done" for production

- [ ] No stub/fallback code paths reachable in `prod` env.
- [ ] All secrets in Key Vault; zero keys in config; Managed Identity only.
- [ ] Entra ID auth enforced on every endpoint; multi-tenant consent live.
- [ ] Cosmos persistence + immutable audit + backups.
- [ ] Durable, horizontally-scaled orchestration; idempotent event handlers.
- [ ] Rate limiting + per-tenant token budgets + cost alerts.
- [ ] App Insights traces, dashboards, alerts, SLOs.
- [ ] Security: private networking, WAF, SAST/DAST/dep-scan in CI, threat model.
- [ ] Execution defaults to read-only; active mode gated + contractually controlled.
- [ ] Legal ROE, customer authorization, SOC 2 roadmap.
- [ ] Load tested (50+ concurrent runs); chaos/DR tested.

See [azure-go-live.md](azure-go-live.md) for the concrete Azure setup steps.
