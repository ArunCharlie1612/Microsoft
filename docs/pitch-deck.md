# BreachSim — Pitch Deck (10 slides)

Theme: **Security in the Agentic Future** · Tagline: *"Attackers don't sleep. Now neither does your red team."*

Each slide: **Title · Content · Speaker notes · Visual recommendation.**

---

## Slide 1 — Title
**Title:** BreachSim — Agentic Red Team Swarm

**Content:**
- *"An autonomous agent swarm that continuously probes your cloud posture and writes its own attack playbooks — before real attackers do."*
- Built on Azure AI Foundry · Theme: Security in the Agentic Future

**Speaker notes:**
> "Hi, we're [team]. BreachSim is an AI swarm that red-teams your cloud 24/7 and fixes what it finds. Let me show you why that matters."

**Visual:** Dark hero with the shield logo, the tagline, and a faint attack-graph motif.

---

## Slide 2 — Problem
**Title:** Security teams can't red-team fast enough

**Content:**
- New cloud configs ship **hourly**; manual pen-testing is **quarterly** at best.
- DAST tools are **static scanners** — they don't reason, chain exploits, or adapt.
- **No tool** autonomously discovers, chains, and remediates threat vectors in real time.

**Speaker notes:**
> "There's a structural gap: change happens continuously, but testing happens four times a year. Scanners find known misconfigs but can't think like an attacker who chains them together."

**Visual:** Split timeline — "configs change hourly" vs "pen-test quarterly," with a widening red gap.

---

## Slide 3 — Market
**Title:** A $15B market paying for a manual ritual

**Content:**
- CISOs pay **$200K+/yr** for red-team retainers.
- **TAM: $15B+** cybersecurity testing market.
- Clear **enterprise SaaS** model + **$50K/yr compliance** upsell.
- Microsoft runs a **$20B/yr** security business — strategically aligned.

**Speaker notes:**
> "This isn't a vitamin. Enterprises already spend six figures on point-in-time red teams. We turn that into continuous coverage at software margins."

**Visual:** TAM circle ($15B) → SAM → wedge; a price tag callout "$200K/yr retainer → continuous."

---

## Slide 4 — Solution
**Title:** A swarm that discovers, exploits, and fixes — autonomously

**Content:**
- One-click deploy into the target's Azure tenant via Entra ID consent.
- **Recon → Plan → Exploit → Validate → Comply → Remediate**, live.
- Agents share a **threat memory** and learn across runs.
- Output: validated findings + **NIST/SOC2 evidence** + a **remediation PR**.

**Speaker notes:**
> "BreachSim deploys a swarm of specialized agents. They don't just scan — they reason over novel attack paths, prove the exploit in a sandbox, and open a pull request that fixes it."

**Visual:** The 6-step pipeline as a glowing horizontal flow, ending in a GitHub PR icon.

---

## Slide 5 — Architecture
**Title:** Enterprise-grade, Azure-native

**Content:**
- **Frontend:** Next.js · live D3 attack graph · SSE agent feed
- **API:** FastAPI on Container Apps · Azure Functions sandbox · Entra ID
- **AI:** Azure OpenAI GPT-4o · Azure AI Search (CVE vectors) · AI Foundry
- **Data:** Cosmos DB threat graph + audit · Blob · Key Vault
- **Bus:** Event Grid · **Observability:** Azure Monitor

**Speaker notes:**
> "Everything runs on Microsoft's stack. Agents communicate asynchronously over Event Grid — this is genuinely agentic, not a chain of LLM calls."

**Visual:** The layered architecture diagram from `docs/architecture.md` (Frontend→API→Agents→AI→Data→Infra).

---

## Slide 6 — AI System
**Title:** Why a swarm beats a single model

**Content:**
- **Reasoning-native planning** — GPT-4o composes novel chains (no attack trees).
- **True specialization** — distinct roles, tool access, async comms.
- **Separation of duties** — Security Agent can **veto** the Execution Agent.
- **Independent validation** — no hallucinated vulnerabilities.
- **Shared memory** — the swarm gets smarter every run.

**Speaker notes:**
> "A single agent that can plan and execute is one prompt-injection from disaster. We split planning, approval, and execution — that's both safer and smarter. And a separate validator means findings are real."

**Visual:** The 10-agent swarm graph with the tool/access matrix; highlight the veto arrow.

---

## Slide 7 — Demo
**Title:** 5 agents. 1 breach. 90 seconds.

**Content:**
- Spin up a misconfigured blob → swarm discovers anonymous read.
- Chains to a leaked connection string → Key Vault secrets.
- Validates, scores **CVSS 9.1**, maps NIST/SOC2, opens a remediation PR — live.

**Speaker notes:**
> "Let's watch it. [Run demo.] Notice the graph building itself, the feed showing the agents' reasoning, and at the end — a pull request that fixes the hole."

**Visual:** Live demo; fallback = screenshot sequence of roster → graph → findings → PR diff.

---

## Slide 8 — Impact
**Title:** From quarterly ritual to continuous intelligence

**Content:**
- **Coverage:** 4 tests/yr → **always-on**.
- **Time-to-fix:** weeks → a **PR before your next sprint**.
- **Cost:** $200K retainer → software margins.
- **Compliance:** audit evidence generated automatically.

**Speaker notes:**
> "The business case is simple: more coverage, faster fixes, lower cost, and audit evidence for free. That last part alone is a $50K upsell."

**Visual:** Before/after two-column scorecard with green deltas.

---

## Slide 9 — Roadmap
**Title:** Where we go next

**Content:**
- Multi-cloud swarm (AWS, GCP)
- Continuous 24/7 scheduled swarms
- Custom attack-scenario builder
- Red team vs. blue team simulation
- Microsoft Sentinel SOC co-pilot

**Speaker notes:**
> "Today it's Azure and on-demand. Next, multi-cloud, always-on monitoring, and a Sentinel integration so the blue team lives in the same loop."

**Visual:** Horizon timeline (Now / Next / Later) with milestone chips.

---

## Slide 10 — Team
**Title:** The team

**Content:**
| Role | Owns |
|------|------|
| Product / PM | Vision, demo narrative, pitch |
| AI / Agent Engineer | Foundry agents, prompts, RAG |
| Backend Engineer | FastAPI, Cosmos, Event Grid, Functions |
| Frontend Engineer | Dashboard, attack graph, SSE |
| Cloud / DevOps | Bicep, Entra ID, CI/CD, observability |

**Speaker notes:**
> "We're a full-stack team that's shipped this end-to-end on Azure. Thank you — let's build the agentic future of security together."

**Visual:** Team photos + role chips; repo URL + live link footer.

---

## Appendix — design tips
- Dark theme, mono accents, BreachSim color system (breach red / signal cyan / safe green).
- ≤ 15 words per bullet; let the demo carry the weight.
- Keep slides 5–7 (Architecture, AI, Demo) tight — that's where judges score AI + Architecture (50% of weight).
