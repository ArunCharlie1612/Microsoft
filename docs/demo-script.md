# BreachSim — Live Demo Script (3 minutes)

**Goal:** Make judges *feel* an AI swarm break into a cloud environment and fix it — live,
self-contained, repeatable. Maximum wow, zero dependence on external systems.

**Setup before stage:** Backend + frontend running locally (or deployed). Browser full-screen on
the Console. One click does everything.

---

## Scene-by-scene

### Scene 0 — Cold open (0:00–0:15) · 15s
**Screen:** Console at rest. Empty graph. Roster all dim. Big red **Deploy Swarm** button.

**Narration:**
> "Security teams red-team their cloud maybe twice a year. Attackers do it every single day —
> now with AI. This is BreachSim. Watch what happens when we point an autonomous agent swarm at a
> misconfigured cloud environment."

**Action:** Hover the **Deploy Swarm** button.

---

### Scene 1 — Deploy & Recon (0:15–0:45) · 30s
**Action:** Click **Deploy Swarm**. Sandbox seeds; progress bar starts.

**Screen:** `recon` tile lights cyan and pulses. Feed prints:
`recon — 12 resources, 1 public blob with anonymous read, 1 over-privileged identity`.
Graph springs in: **Internet** node + **stbreachdemo** blob node.

**Narration:**
> "First, the Recon Agent maps the attack surface inside the tenant — and immediately flags a
> public storage account with anonymous read access. No human told it where to look."

---

### Scene 2 — Reasoning & Planning (0:45–1:15) · 30s
**Screen:** `research` then `planner` light up. Feed:
`planner — Internet → public blob → leaked connection string → Key Vault access`.
Graph grows edges with confidence-weighted thickness.

**Narration:**
> "Here's the magic: the Planner Agent reasons with GPT-4o over real CVE data and *composes a
> novel attack chain* — anonymous blob, to a leaked connection string, to Key Vault. This isn't a
> script. It discovered a path no rule set anticipated."

---

### Scene 3 — Safety & Exploit (1:15–1:50) · 35s
**Screen:** `security` lights green: `3 approved, 0 vetoed`. Then `execution` lights red.
Feed: `execution — downloaded appsettings.json (AccountKey=***redacted***)`,
`execution — authenticated to Key Vault; listed 4 secrets`.

**Narration:**
> "Before anything runs, the Security Agent reviews every step and can veto it — separation of
> duties, just like a real red team. Approved steps execute in a network-isolated sandbox. And
> there it is: the swarm exfiltrated secrets, end to end."

---

### Scene 4 — Validate, Score, Comply (1:50–2:20) · 30s
**Screen:** `validator` → `risk` → `compliance` light in sequence. Feed:
`risk — CVSS 9.1 (critical)`, `compliance — Evidence across NIST-800-53, SOC2, ISO-27001`.

**Narration:**
> "A separate Validator Agent independently confirms the breach is real — no hallucinated
> findings. The Risk Agent scores it critical, and the Compliance Agent auto-generates NIST and
> SOC 2 evidence — the part every CISO pays $50K a year for."

---

### Scene 5 — Close the loop (2:20–2:45) · 25s
**Screen:** `remediation` lights green. Findings panel appears: **Public blob → secrets exposure /
CRITICAL** with **→ Remediation PR opened (bicep)** link. Progress hits 100%.

**Narration:**
> "And then it does what no other tool does — it fixes it. The Remediation Agent writes a Bicep
> patch that disables public access and opens a GitHub pull request. Discover, exploit, and
> remediate — in ninety seconds."

---

### Scene 6 — The close (2:45–3:00) · 15s
**Screen:** Click the PR link → shows the diff (`allowBlobPublicAccess: true → false`).

**Narration:**
> "Attackers don't sleep. Now neither does your red team. That's BreachSim — the agentic future
> of security, built entirely on Azure."

---

## Timing summary

| Scene | Window | Beat |
|-------|--------|------|
| 0 Cold open | 0:00–0:15 | Hook |
| 1 Recon | 0:15–0:45 | Discovery |
| 2 Planning | 0:45–1:15 | **AI reasoning** |
| 3 Exploit | 1:15–1:50 | **Agent collaboration + veto** |
| 4 Validate/Comply | 1:50–2:20 | Trust + business value |
| 5 Remediation | 2:20–2:45 | **Closed loop** |
| 6 Close | 2:45–3:00 | Tagline |

## Director's notes
- **Pre-seed once** off-camera so the run is warm; the on-stage run should land in ~90s.
- If the network is risky, run **local/demo mode** — identical visuals, zero cloud dependency.
- Keep narration synced to feed lines; let the graph animation breathe.
- Have the PR diff tab pre-opened as a fallback.
