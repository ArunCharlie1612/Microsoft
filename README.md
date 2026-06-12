# BreachSim — Agentic Red Team Swarm

> An autonomous, always-on AI agent swarm that continuously red-teams your Azure cloud posture — discovering exposures, chaining real attack paths, validating exploitability, and opening the remediation pull request for you.

---

## Overview

**BreachSim** is an AI-native adversarial simulation platform that replaces point-in-time penetration tests with a continuous, autonomous red-team loop. A swarm of specialized GPT-4o agents maps your live cloud attack surface, reasons about how a real attacker would chain misconfigurations into a breach, validates each step safely in a sandbox, and then generates an infrastructure-as-code fix as a GitHub pull request. It is built for cloud security engineers, platform teams, and CISOs who need defensible, audit-ready posture assurance between their annual pentests. By turning every operator triage decision into a learning signal, BreachSim gets sharper the more your team uses it — closing the gap between "we think we're secure" and "we proved it this morning."

## Problem

- **Cadence gap** — Penetration tests happen once or twice a year, but cloud infrastructure changes hourly; attackers exploit the months of drift in between.
- **Skill scarcity** — Senior offensive-security talent is expensive and rare, so most organizations simply cannot afford continuous manual red-teaming.
- **Zero remediation loop** — Traditional scanners dump a PDF of findings and stop; nobody closes the loop from "vulnerability found" to "fix merged," so risk lingers.

## Solution

A four-step autonomous loop runs end-to-end on every trigger:

1. **Discover** — The Recon agent queries Azure Resource Graph to map the live attack surface and flag publicly-exposed or misconfigured resources.
2. **Chain** — The Planner agent uses GPT-4o, grounded in real CVE/ATT&CK evidence, to chain individual weaknesses into a plausible multi-step attack path.
3. **Validate** — The Execution and Validator agents safely confirm exploitability with benign, read-only sandbox probes, rejecting any unproven claim.
4. **Remediate** — The Risk, Compliance, and Remediation agents score the finding, map it to NIST/SOC 2/ISO controls, and open a GitHub PR with the infrastructure-as-code fix.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend  (Next.js 14 + TypeScript + Tailwind)                        │
│  • Live agent console (SSE)   • Force-directed attack graph (D3)       │
│  • API-key auth  +  "Sign in with Microsoft" (Entra ID / MSAL)         │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │  HTTPS / Server-Sent Events
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│  API Gateway  (FastAPI on Azure Container Apps)                        │
│  • Multi-tenant RBAC   • Authorization-to-test guardrails   • /health  │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │  Orchestrator state machine
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AI Agent Swarm  (10 specialized GPT-4o agents)                        │
│  Recon → Research → Planner → Security → Execution → Validator         │
│         → Risk → (Compliance ∥ Remediation) → Memory                   │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────────┐
        ▼                        ▼                             ▼
┌────────────────┐   ┌────────────────────────┐   ┌────────────────────┐
│ Azure OpenAI   │   │ Azure Cosmos DB        │   │ Azure Resource     │
│ (GPT-4o)       │   │ (findings/graph/audit) │   │ Graph (live recon) │
└────────────────┘   └────────────────────────┘   └────────────────────┘
        │                        │                             │
        ▼                        ▼                             ▼
┌────────────────┐   ┌────────────────────────┐   ┌────────────────────┐
│ Azure Entra ID │   │ Azure Service Bus      │   │ Azure Monitor /    │
│ (enterprise    │   │ (durable run queue)    │   │ App Insights       │
│  SSO)          │   │                        │   │ (telemetry)        │
└────────────────┘   └────────────────────────┘   └────────────────────┘
        │                                                       │
        ▼                                                       ▼
┌────────────────┐                                  ┌────────────────────┐
│ GitHub Actions │                                  │ Azure Event Grid   │
│ (CI/CD + PRs)  │                                  │ (agent event bus)  │
└────────────────┘                                  └────────────────────┘
```

## Microsoft AI Stack

| Service | Usage | Required? |
| --- | --- | --- |
| **Azure OpenAI (GPT-4o)** | Core reasoning engine — attack-path chaining, validation narratives, remediation synthesis | Yes |
| **Azure AI Foundry** | Project hosting, model deployment, and prompt/agent orchestration scaffolding | Yes |
| **Azure Container Apps** | Serverless hosting for the FastAPI API and Next.js frontend (scale-to-zero) | Yes |
| **Azure Cosmos DB** | Persistent store for findings, threat graph, audit log, runs, and tenants | Yes |
| **Azure Resource Graph** | Live, read-only reconnaissance of the target subscription's attack surface | Optional* |
| **Azure Entra ID** | Enterprise SSO ("Sign in with Microsoft") via MSAL OAuth2 | Optional |
| **Azure Monitor / App Insights** | Distributed tracing, structured logs, and run telemetry | Optional |
| **Azure Event Grid** | Decoupled agent-to-agent event bus for the swarm message fabric | Optional |
| **GitHub Actions** | CI/CD, dependency (pip-audit) and SAST (bandit) security scans, deploy | Yes |
| **GitHub Copilot** | AI pair-programmer used throughout development (see AI Tools Disclosure) | Dev-time |

\* Optional services degrade gracefully: without them BreachSim runs fully offline in local/demo mode using an in-memory store and stubbed recon.

## AI Agent Swarm

| Agent | Responsibility |
| --- | --- |
| **Recon** | Maps the live cloud attack surface via Azure Resource Graph; flags public exposure and misconfiguration. |
| **Research** | Grounds planning in real CVE / MITRE ATT&CK evidence (Azure AI Search + NVD), citing source IDs. |
| **Planner** | Chains individual weaknesses into multi-step exploit paths using GPT-4o reasoning and a threat graph. |
| **Security** | Enforces scope and sandbox guardrails; can veto any step that would exceed authorization. |
| **Execution** | Safely runs benign, read-only payload tests in a sandbox to probe each step. |
| **Validator** | Independently confirms exploitability, rejects unproven claims, and folds in operator feedback. |
| **Risk** | Deterministically scores CVSS severity and business impact for auditability. |
| **Compliance** | Generates NIST 800-53 / SOC 2 / ISO 27001 control-mapping evidence. |
| **Remediation** | Synthesizes an infrastructure-as-code fix and opens a GitHub pull request. |
| **Memory** | Persists discoveries to Cosmos DB threat history and recalls semantically similar prior findings. |

## Tech Stack

| Frontend | Backend |
| --- | --- |
| Next.js 14 (App Router) | Python 3.11+ with FastAPI |
| TypeScript | Pydantic v2 settings & schemas |
| Tailwind CSS | Azure OpenAI / Semantic Kernel |
| D3.js (force-directed attack graph) | MSAL + PyJWT (Entra SSO / session JWTs) |
| Zustand (state) + react-joyride (onboarding) | Azure SDKs (Cosmos, Resource Graph, Service Bus) |
| Server-Sent Events (live agent feed) | Uvicorn ASGI server |

## Installation (Local)

```bash
# 1. Clone the repository
git clone https://github.com/ArunCharlie1612/Microsoft.git
cd Microsoft/breachsim

# 2. Backend — create a virtual environment and install dependencies
cd backend
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment variables
cp ../.env.example .env          # then fill in values (all optional for local demo)

# 4. Run the API (in-memory store, no cloud dependencies needed)
APP_ENV=local uvicorn app.main:app --reload --port 8000

# 5. Frontend — in a second terminal
cd ../frontend
npm install
npm run dev                      # serves http://localhost:3000
```

Open `http://localhost:3000`, create a free workspace, and click **Deploy Swarm**. The
backend health endpoint is available at `http://localhost:8000/health`.

## Deployment (Azure)

```bash
# 1. Authenticate
az login
az account set --subscription <your-subscription-id>

# 2. Provision + deploy all infrastructure (Bicep)
cd infra
az deployment sub create \
  --location centralus \
  --template-file main.bicep \
  --parameters environmentSuffix=prod

# (or, with the Azure Developer CLI)
azd up

# 3. Verify the deployment is healthy and connected to Cosmos
curl https://<your-api-fqdn>.azurecontainerapps.io/health
# → {"status":"ok","store":"cosmos","environment":"production",...}
```

In `production` the API requires a Cosmos connection (`store: "cosmos"`); the in-memory
fallback is only permitted when `ENVIRONMENT=local`.

## Live Demo

- **URL:** `[PLACEHOLDER — https://breachsim.example.azurecontainerapps.io]`
- **Test API key:** `bsk_demo_xxxx` (free tier, 5 runs/day)
- **Test Microsoft login:** `demo@breachsim.io` / `[PLACEHOLDER]`

## AI Tools Disclosure

**GitHub Copilot** was used during development for:
- Scaffolding FastAPI routes, Pydantic schemas, and the agent base classes.
- Generating React/TypeScript components (attack graph, findings panel, onboarding tour).
- Authoring unit and end-to-end tests, and writing Bicep infrastructure modules.
- Drafting docstrings, inline comments, and this documentation.

**Azure OpenAI GPT-4o** is used at runtime for:
- Chaining discovered weaknesses into coherent multi-step attack paths (Planner agent).
- Producing reproduction narratives and validation reasoning (Validator agent).
- Synthesizing infrastructure-as-code remediation diffs (Remediation agent).

**Azure AI Foundry** is used for:
- Hosting the GPT-4o model deployment and project configuration.
- Providing the agent orchestration and prompt-management scaffolding for the swarm.

## Data & Privacy

- **What data is used:** Read-only metadata about the target Azure subscription's resources (types, names, configuration flags) gathered via Azure Resource Graph, plus public CVE/ATT&CK reference data. BreachSim never reads, copies, or exfiltrates customer data — validation probes are benign and read-only.
- **How it is stored:** Findings, the threat graph, the audit log, and tenant records are persisted in Azure Cosmos DB, scoped per tenant. In local/demo mode an ephemeral in-memory store is used and nothing is persisted.
- **How it is protected:** All access is authenticated (per-tenant API keys hashed with SHA-256, or short-lived Entra ID session JWTs) and authorized via RBAC. Managed Identity is used for service-to-service auth in Azure; secrets live in environment variables / Key Vault, never in code. Every run requires an explicit authorization-to-test attestation, and a hard sandbox guardrail rejects out-of-scope or non-sandbox targets.

## Team

| Name | Role | Responsibilities |
| --- | --- | --- |
| Alex Carter | Lead Engineer / Backend | Agent swarm orchestration, FastAPI API, Azure integration |
| Priya Nair | Frontend Engineer | Next.js console, D3 attack graph, auth & onboarding UX |
| Jordan Lee | Cloud / Security Architect | Bicep infrastructure, CI/CD security scans, threat modeling |

## Future Work

- **Autonomous remediation merge** — gate and auto-merge low-risk IaC fixes behind policy, closing the loop without human intervention.
- **Multi-cloud recon** — extend the Recon agent beyond Azure Resource Graph to AWS and GCP attack-surface mapping.
- **Continuous scheduling & drift alerts** — run the swarm on a cron/event trigger and alert on newly-introduced exposures in near-real-time.

## License

MIT
