# BreachSim — Production & Per-Tenant Runbook

This runbook explains how to operate BreachSim safely and how to enable the
production capabilities that ship **disabled by default**. The public demo is
intentionally kept open (no login) and offline-safe; everything below is opt-in.

> Golden rule: every powerful capability is behind a feature flag that defaults to
> the safe value. Turning one on is a deliberate, documented action.

---

## 1. Feature flags (environment variables)

| Setting | Default | What it does |
|---|---|---|
| `BREACHSIM_REQUIRE_AUTH` | `false` | Enforce Entra ID JWT auth. Leave **off** for the open demo. |
| `BREACHSIM_PUBLIC_SIGNUP` | `true` | Allow self-service tenant signup (issues API keys). Set `false` for invite-only. |
| `BREACHSIM_LIVE_RECON` | `false` | Real **read-only** Azure Resource Graph scan. Needs `Reader` on target subs. |
| `BREACHSIM_ACTIVE_VALIDATION` | `false` | Benign **read-only** reachability probes to confirm exposures. Never exploits. |
| `BREACHSIM_REQUIRE_CONSENT` | `true` | Require authorization-to-test attestation on every run. Keep **on**. |
| `BREACHSIM_SANDBOX_ONLY` | `true` | Reject non-sandbox targets. |
| `BREACHSIM_ALLOWED_SUBSCRIPTIONS` | `""` | Comma-separated allow-list of subscription IDs. |
| `GITHUB_PR_ENABLED` | `false` | Open real remediation PRs. Off ⇒ status `proposed`. Controls PR sprawl. |
| `RATE_LIMIT_RUNS_PER_MINUTE` | `10` | Per-caller run-creation rate limit. |
| `PLAN_FREE_DAILY_RUNS` | `5` | Daily run quota for the free plan. |
| `PLAN_PRO_DAILY_RUNS` | `200` | Daily run quota for the Pro plan. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `""` | Enable App Insights tracing/metrics (no-op when empty). |
| `STRIPE_API_KEY` / `STRIPE_PRICE_PRO` / `STRIPE_WEBHOOK_SECRET` | `""` | Enable paid upgrades (see §4). |

Cost note: the only setting that incurs real Azure spend is connecting **Azure
OpenAI** (`AZURE_OPENAI_ENDPOINT`). With it unset, the swarm runs in free stub mode.

---

## 2. Authentication options

BreachSim supports two auth paths simultaneously:

1. **API key (default, no IdP).** Tenants self-serve via `POST /v1/tenants/signup`
   and receive a `bsk_…` key (shown once). Send it as `X-API-Key: bsk_…` (or
   `?apiKey=` for the SSE stream). Works even when `BREACHSIM_REQUIRE_AUTH=false`.
2. **Enterprise SSO (Entra ID).** Set `BREACHSIM_REQUIRE_AUTH=true` plus
   `AZURE_TENANT_ID` and `ENTRA_API_AUDIENCE`. Callers then need a Bearer JWT with
   the `breachsim.operator`/`breachsim.admin` app role. The frontend would need an
   MSAL login to acquire that token — **do not enable on the public demo** (the
   demo frontend has no token and would break).

---

## 3. Onboarding a customer into THEIR Azure tenant

To run BreachSim against a customer's own subscription:

1. **Identity:** set `AZURE_TENANT_ID` to their tenant; register an Entra app for the
   API; assign `breachsim.operator`/`breachsim.admin` roles; set `BREACHSIM_REQUIRE_AUTH=true`.
2. **Read-only recon permission:** grant the API's managed identity `Reader` on each
   in-scope subscription. Set `BREACHSIM_LIVE_RECON=true` and restrict targets with
   `BREACHSIM_ALLOWED_SUBSCRIPTIONS=<sub-ids>`.
3. **Active validation (optional):** `BREACHSIM_ACTIVE_VALIDATION=true` to confirm
   public exposures via benign read-only probes.
4. **Remediation PRs (optional):** create a GitHub App (or fine-grained PAT) with
   Contents R/W + Pull requests R/W; store as Key Vault secret `github-token` (or set
   `GITHUB_APP_ID`/`GITHUB_INSTALLATION_ID`/private key). Set
   `GITHUB_REMEDIATION_REPO=<owner/repo>` and `GITHUB_PR_ENABLED=true`.
5. **AI + data:** provision their own Azure OpenAI (GPT-4o, capacity > 1 TPM) and
   Cosmos DB; set the connection settings.
6. **Observability:** set `APPLICATIONINSIGHTS_CONNECTION_STRING`.

Each tenant change means a **new Entra app, new role assignments, new OpenAI/Cosmos,
and new GitHub App**. These are per-customer and not yet automated by a provisioning
pipeline.

---

## 4. Enabling paid plans (Stripe)

Billing is optional and lazy-loaded. With Stripe unset, everyone stays on the free
plan and the upgrade button shows "billing not enabled".

1. In Stripe, create a **Product + recurring Price** for "Pro"; copy the Price ID.
2. Set env: `STRIPE_API_KEY=sk_live_…`, `STRIPE_PRICE_PRO=price_…`,
   `STRIPE_WEBHOOK_SECRET=whsec_…`, and `BILLING_SUCCESS_URL` / `BILLING_CANCEL_URL`.
3. Add a Stripe webhook endpoint pointing at
   `POST https://<api-host>/v1/tenants/billing/webhook` for events
   `checkout.session.completed`, `customer.subscription.deleted`,
   `customer.subscription.paused`.
4. Flow: user clicks **Upgrade to Pro** → `POST /v1/tenants/me/checkout` → Stripe
   Checkout → on success the webhook sets the tenant's plan to `pro` (raising the
   daily run quota). Cancellation/pause downgrades back to `free`.

Stripe handles card data and PCI scope — BreachSim only stores the customer/
subscription IDs, never card details.

---

## 5. Live demo deploy (current setup)

- Build images **locally** (free sub blocks ACR Tasks): Colima + `DOCKER_BUILDKIT=0`
  `--platform linux/amd64`, push to `bsimacrus4uddk7s7yhy.azurecr.io`.
- **Known quirk:** `azd provision` reverts container apps to a placeholder image and
  drops the registry config. After provisioning, re-run:
  ```bash
  az containerapp registry set -n <app> -g rg-breachsim-dev \
    --server bsimacrus4uddk7s7yhy.azurecr.io --identity system
  az containerapp update -n <app> -g rg-breachsim-dev --image <image>
  ```
  for both `bsim-api-*` and `bsim-web-*`.
- Secrets (e.g. `github-token`) are set via `az containerapp secret set` and
  referenced as `secretref:`. Never echo secrets; enter them via a hidden prompt.

---

## 6. Safety posture (what BreachSim does and does NOT do)

- **Does:** read-only recon, benign read-only reachability validation, CVE grounding,
  deterministic risk/compliance scoring, and remediation **pull requests** for review.
- **Does NOT:** run exploits, access/exfiltrate data, use credentials, perform DoS, or
  mutate target resources. Data-access/credential techniques are always *modeled*.
- Consent attestation, scope allow-listing, sandbox-only enforcement, and an SSRF
  guard on probes are the backstops.
