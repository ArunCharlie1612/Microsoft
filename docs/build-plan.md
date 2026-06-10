# BreachSim — Build Plan

Four phases, sized for a hackathon sprint but structured for production continuation. Hours are
single-engineer estimates; many tasks parallelize across the team.

Priority: **P0** = demo-critical, **P1** = important, **P2** = nice-to-have.

---

## Phase 1 — Foundation & Walking Skeleton
**Goal:** A runnable end-to-end loop in local/demo mode (no cloud required).

| Task | Hours | Priority | Dependencies |
|------|------:|:--------:|--------------|
| Repo scaffold, env config, CI lint | 2 | P0 | — |
| Pydantic schemas + settings | 2 | P0 | scaffold |
| Cosmos repository (+ in-memory fallback) | 3 | P0 | schemas |
| Event bus (Event Grid + in-proc) | 3 | P0 | schemas |
| Azure OpenAI client wrapper (+ stub mode) | 2 | P0 | config |
| Base agent + orchestrator state machine | 4 | P0 | bus, openai |
| FastAPI app + run/SSE endpoints | 4 | P0 | orchestrator |
| E2E smoke test (offline swarm) | 2 | P0 | endpoints |

**Subtotal: ~22h** · **Exit criteria:** `pytest` green; a run completes offline and streams events.

---

## Phase 2 — The Agent Swarm
**Goal:** All 10 agents implemented with real prompts + tools.

| Task | Hours | Priority | Dependencies |
|------|------:|:--------:|--------------|
| Recon + Research (RAG over AI Search) | 4 | P0 | Phase 1 |
| Planner (GPT-4o chain composition) | 4 | P0 | Recon |
| Security veto + scope guardrails | 3 | P0 | Planner |
| Execution (Functions sandbox) | 4 | P0 | Security |
| Validator + Risk scoring | 3 | P1 | Execution |
| Compliance (NIST/SOC2 mapping) | 3 | P1 | Risk |
| Remediation (IaC + GitHub PR) | 4 | P0 | Risk |
| Memory (Cosmos persistence + recall) | 2 | P1 | all |

**Subtotal: ~27h** · **Exit criteria:** Full discover→chain→exploit→validate→remediate run with PR.

---

## Phase 3 — Frontend & Demo Experience
**Goal:** The jaw-drop dashboard.

| Task | Hours | Priority | Dependencies |
|------|------:|:--------:|--------------|
| Next.js shell + Tailwind design system | 3 | P0 | — |
| Typed API client + SSE hook | 2 | P0 | Phase 1 API |
| Agent roster (live status) | 2 | P0 | client |
| Attack graph (D3 force layout) | 5 | P0 | graph API |
| Agent activity feed | 2 | P0 | SSE |
| Findings + remediation panel | 3 | P1 | findings API |
| Demo "Deploy Swarm" one-click flow | 2 | P0 | all |

**Subtotal: ~19h** · **Exit criteria:** One click → live 90-second visual run.

---

## Phase 4 — Azure Deployment & Hardening
**Goal:** Provisioned, observable, secured.

| Task | Hours | Priority | Dependencies |
|------|------:|:--------:|--------------|
| Bicep modules (all resources) | 5 | P0 | — |
| `azd` config + container builds | 3 | P0 | Bicep |
| Entra ID auth + JWT validation | 4 | P1 | API |
| Managed Identity wiring (no keys) | 3 | P1 | Bicep |
| Azure Monitor + Foundry tracing | 3 | P1 | deploy |
| GitHub Actions CI/CD | 2 | P1 | azd |
| Demo seed Bicep (misconfigured sandbox) | 2 | P0 | Bicep |
| Security review + guardrail tests | 3 | P0 | all |

**Subtotal: ~25h** · **Exit criteria:** `azd up` deploys; demo runs in a real tenant.

---

## Summary

| Phase | Hours | Theme |
|-------|------:|-------|
| 1 — Foundation | 22 | Walking skeleton |
| 2 — Swarm | 27 | Agent intelligence |
| 3 — Frontend | 19 | Demo wow |
| 4 — Deploy | 25 | Production-ready |
| **Total** | **~93h** | |

**Critical path:** Phase 1 → Planner/Security/Execution → Attack graph → Demo seed.
Compliance, Validator, Risk, and full auth can trail without blocking the demo.
