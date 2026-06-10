# BreachSim — Deployment Guide

Two paths: **local/demo** (zero cloud dependencies) and **Azure** (`azd up`).

---

## 1. Local / demo mode

The swarm runs fully offline — Cosmos, OpenAI, and Event Grid all have in-process fallbacks, so
you can demo without any Azure resources.

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # APP_ENV=local is enough for demo mode
APP_ENV=local uvicorn app.main:app --reload --port 8000
```
Swagger UI at http://localhost:8000/docs.

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev                    # http://localhost:3000
```

### One-command demo
```bash
./scripts/seed_demo.sh         # seeds sandbox + starts a run + streams events
```

---

## 2. Azure deployment (`azd`)

### Prerequisites
- Azure subscription with **Azure OpenAI** access (GPT-4o + embeddings quota)
- Azure CLI + Azure Developer CLI (`azd`)
- Docker (for container builds)

### Provision + deploy
```bash
azd auth login
azd env new breachsim-prod
azd env set AZURE_LOCATION eastus2
azd up
```

`azd up`:
1. Runs `infra/main.bicep` (subscription scope) → creates the resource group + all services.
2. Builds the `backend`, `frontend`, and `functions` containers → pushes to ACR.
3. Deploys to Container Apps + Functions.
4. Wires outputs (endpoints) into app settings.

### What gets provisioned

| Resource | Purpose |
|----------|---------|
| Azure OpenAI (GPT-4o + embeddings) | Agent reasoning + vectors |
| Azure AI Search (basic, semantic) | CVE vector index |
| Cosmos DB (serverless, 4 containers) | Threat graph + audit |
| Event Grid topic (CloudEvents) | Agent message bus |
| Container Apps env + 2 apps | API + web |
| Azure Functions | Sandbox execution |
| Key Vault | Secrets |
| Log Analytics + App Insights | Observability |
| Container Registry | Images |

### Post-deploy

1. **Seed the CVE index** (one-time):
   ```bash
   python scripts/index_cves.py      # uploads CVE corpus → Azure AI Search
   ```
2. **Grant Managed Identity roles** (handled by Bicep RBAC assignments):
   - API identity → Cosmos Data Contributor, OpenAI User, Search Index Reader, Key Vault Secrets User.
3. **Configure Entra ID app registration** for `ENTRA_API_AUDIENCE` and tenant consent.

---

## 3. Configuration reference

All settings come from environment variables (see [.env.example](../.env.example)). In Azure,
secrets resolve from **Key Vault** via Managed Identity — no keys in app settings.

| Concern | Local | Azure |
|---------|-------|-------|
| Auth | bypassed (`APP_ENV=local`) | Entra ID JWT |
| Cosmos | in-memory | Managed Identity |
| OpenAI | stub completions | GPT-4o, MI token |
| Events | in-process bus | Event Grid |
| GitHub PR | simulated | GitHub App |

---

## 4. CI/CD

`.github/workflows/deploy.yml` runs tests on every push and `azd up --no-prompt` on `main`
(OIDC federated login — no stored secrets). Configure repo variables `AZURE_ENV_NAME`,
`AZURE_LOCATION` and secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.

---

## 5. Teardown
```bash
azd down --purge --force
```
