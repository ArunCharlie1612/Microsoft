# BreachSim — Azure Go-Live Runbook

> Concrete, ordered steps to take BreachSim from local prototype to a deployed Azure environment.
> Infra is already authored: `azure.yaml` (azd), `infra/main.bicep` + modules. Services:
> `api` (Container App), `web` (Container App), `functions` (Azure Functions sandbox).
>
> Read alongside [production-readiness.md](production-readiness.md) — that lists the code gaps;
> this lists the **Azure operations**.

---

## Step 0 — Prerequisites (your machine)

These are **not installed** on this machine yet. Install:

```bash
# macOS
brew install azure-cli            # the `az` CLI
az bicep install                  # Bicep — installs INSIDE the az CLI (~/.azure/bin)
brew tap azure/azd && brew install azd   # Azure Developer CLI
brew install --cask docker        # Docker Desktop (needed to build images)
```

> **Note on Bicep:** `az bicep install` installs Bicep *inside* the Azure CLI, not as a global
> `bicep` command. So `bicep --version` will say "command not found" — that's expected. Verify with
> **`az bicep version`** instead. `azd` and `az deployment` use this bundled Bicep automatically,
> so you do **not** need a standalone `bicep`. (If you want the standalone CLI anyway:
> `brew install bicep`.)

Verify:
```bash
az version && azd version && az bicep version && docker --version
```

> ✅ **Validated:** `infra/main.bicep` compiles cleanly (`az bicep build --file infra/main.bicep`,
> exit 0). There is one benign `BCP334` length warning on the ACR name — harmless, because `prefix`
> (`bsim`) + a 13-char `uniqueString` token always exceeds the 5-char minimum.

---

## Step 1 — Azure account & access

1. An Azure subscription with **Owner** or **Contributor + User Access Administrator** (needed to
   create role assignments for Managed Identity).
2. **Request Azure OpenAI access** for the subscription and confirm **GPT-4o** and
   **text-embedding-3-large** quota in your target region (e.g. `eastus2`, `swedencentral`).
   This approval can take time — start it first.

```bash
az login
azd auth login
az account set --subscription "<SUBSCRIPTION_ID>"
```

---

## Step 2 — Create the azd environment

```bash
cd /Users/arun.s.u/Arun/Microsoft/breachsim
azd env new breachsim-dev
azd env set AZURE_LOCATION eastus2
azd env set AZURE_SUBSCRIPTION_ID "<SUBSCRIPTION_ID>"
```

---

## Step 3 — Preview, then provision + deploy

```bash
azd provision --preview      # dry-run: review what Bicep will create
azd up                       # provision infra + build/push images + deploy
```

`azd up` will:
- Deploy `infra/main.bicep`: Log Analytics + App Insights, Container Apps Environment, Azure OpenAI
  (with `gpt-4o` + `text-embedding-3-large` deployments), AI Search, Cosmos DB (4 containers),
  Event Grid topic, Key Vault, a user-assigned Managed Identity, and the Functions sandbox.
- Build the `api`, `web`, and `functions` Docker images and deploy them.

> If provisioning fails on OpenAI capacity, it's almost always quota — reduce the deployment SKU
> capacity in `infra/main.bicep` or change region.

---

## Step 4 — Grant Managed Identity RBAC (zero-key auth)

The app should use **Managed Identity**, not keys. Assign these data-plane roles to the app's
user-assigned identity (the Bicep should set most of these; verify/add any missing):

| Resource | Role |
|----------|------|
| Azure OpenAI | `Cognitive Services OpenAI User` |
| Cosmos DB | `Cosmos DB Built-in Data Contributor` (data-plane SQL role) |
| AI Search | `Search Index Data Contributor` + `Search Service Contributor` |
| Key Vault | `Key Vault Secrets User` |
| Event Grid topic | `EventGrid Data Sender` |
| Storage (artifacts) | `Storage Blob Data Contributor` |

```bash
# example pattern
az role assignment create \
  --assignee-object-id <MI_PRINCIPAL_ID> --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<aoai>
```

Then leave `AZURE_OPENAI_API_KEY` / `COSMOS_KEY` **blank** so the code uses Managed Identity.

---

## Step 5 — Seed the CVE / knowledge index

The Research agent needs a populated Azure AI Search index (`cve-index`). Create and run a
loader (referenced in the deployment guide; **not yet implemented** — Phase A task):

```bash
# scripts/index_cves.py  (to be created)
python scripts/index_cves.py \
  --search-endpoint $AZURE_SEARCH_ENDPOINT \
  --index cve-index \
  --source nvd   # NVD CVE feed + MITRE ATT&CK + CWE
```

---

## Step 6 — Entra ID app registration (auth + tenant onboarding)

1. Register an app: audience `api://breachsim`, expose an API scope.
2. For multi-tenant onboarding, mark it **multi-tenant** and define the **admin-consent** URL so
   customer tenant admins grant the read-only roles BreachSim needs.
3. Add `PyJWT` to `backend/requirements.txt` and enable JWT validation (the security module exists;
   the `local` bypass must be off in prod).

```bash
azd env set APP_ENV prod
azd env set ENTRA_API_AUDIENCE api://breachsim
azd env set AZURE_TENANT_ID <TENANT_ID>
```

---

## Step 7 — Production environment variables

```bash
azd env set BREACHSIM_DEMO_PACING_MS 0        # no artificial delay in prod
azd env set BREACHSIM_SANDBOX_ONLY true       # keep active exploits sandbox-only
azd env set BREACHSIM_ALLOWED_SUBSCRIPTIONS <allow-listed-sub-ids>
azd env set CORS_ORIGINS https://<your-web-app-domain>
azd deploy                                     # push the new config
```

> ⚠️ Never set `BREACHSIM_SANDBOX_ONLY=false` without the legal Rules-of-Engagement framework in
> place (see production-readiness.md §1.3 / Phase C).

---

## Step 8 — GitHub App for remediation PRs

1. Create a GitHub App with `contents:write` + `pull_requests:write` on target repos.
2. Store its private key in Key Vault; set `GITHUB_APP_ID`, `GITHUB_INSTALLATION_ID`,
   `GITHUB_REMEDIATION_REPO`.
3. Implement real PR creation in `agents/remediation.py` (currently simulated).

---

## Step 9 — Demo / target environment

For demos, stand up an intentionally **misconfigured but isolated** resource group (e.g. a storage
account with public access, an over-permissive NSG) in a throwaway subscription. Point a run at it.
Never demo against a real production tenant.

---

## Step 10 — CI/CD (GitHub Actions OIDC)

`.github/workflows/deploy.yml` exists. Configure repo secrets/vars for keyless OIDC deploy:

```bash
azd pipeline config --provider github
```

This sets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (federated credential) and
vars `AZURE_ENV_NAME`, `AZURE_LOCATION`. Add environment protection rules + a smoke test on deploy.

---

## Step 11 — Observability & guardrails before "live"

- Confirm App Insights is receiving traces (add OpenTelemetry instrumentation to FastAPI — Phase A).
- Create alerts: error rate, token spend, run failures, OpenAI throttling.
- Enable Cosmos continuous backup.
- Add rate limiting (APIM in front, or middleware + Redis).
- Run a load test (50+ concurrent runs) and a security review of BreachSim itself.

---

## Quick reference — minimal "first deploy" path

```bash
brew install azure-cli && az bicep install && brew install azd
az login && azd auth login
cd /Users/arun.s.u/Arun/Microsoft/breachsim
azd env new breachsim-dev
azd env set AZURE_LOCATION eastus2
azd up
```

That gets infra + apps deployed. The code still runs in stub mode for OpenAI/Cosmos/etc. until you
complete the Phase A wiring in [production-readiness.md](production-readiness.md).
