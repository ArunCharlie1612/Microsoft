# BreachSim — API Design

Base URL: `https://api.breachsim.io/v1` (local: `http://localhost:8000/v1`)
Content-Type: `application/json` · Auth: Entra ID Bearer JWT.

---

## 1. Authentication

All endpoints (except `/health`) require an Entra ID-issued bearer token.

```
Authorization: Bearer <jwt>
```

- The JWT audience must equal `ENTRA_API_AUDIENCE` (`api://breachsim`).
- Validated via Entra JWKS; claims `tid` (tenant) and `roles` enforce RBAC.
- **Tenant consent**: `POST /v1/consent/start` returns the admin-consent URL for onboarding a
  target tenant.

### Roles

| Role | Permissions |
|------|-------------|
| `breachsim.operator` | Start/stop runs, view findings |
| `breachsim.auditor` | Read findings + compliance evidence (no run control) |
| `breachsim.admin` | All + tenant consent + settings |

---

## 2. Rate limiting

Token-bucket per tenant + per principal. Headers returned on every response:

```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 118
X-RateLimit-Reset: 1718020800
Retry-After: 30        # only on 429
```

| Tier | Requests/min | Concurrent runs |
|------|-------------|-----------------|
| Free | 60 | 1 |
| Pro | 120 | 5 |
| Enterprise | 600 | 50 |

---

## 3. Endpoints

| Method | Path | Description | Role |
|--------|------|-------------|------|
| GET | `/health` | Liveness/readiness | public |
| POST | `/v1/consent/start` | Begin Entra tenant consent | admin |
| POST | `/v1/runs` | Start a swarm run | operator |
| GET | `/v1/runs` | List runs (paginated) | operator/auditor |
| GET | `/v1/runs/{runId}` | Get run detail + status | operator/auditor |
| POST | `/v1/runs/{runId}/cancel` | Cancel a running swarm | operator |
| GET | `/v1/runs/{runId}/events` | **SSE** live agent feed | operator/auditor |
| GET | `/v1/runs/{runId}/graph` | Attack graph (nodes + edges) | operator/auditor |
| GET | `/v1/runs/{runId}/findings` | List findings | operator/auditor |
| GET | `/v1/findings/{findingId}` | Finding detail + evidence | operator/auditor |
| GET | `/v1/runs/{runId}/compliance` | Compliance evidence export | auditor |
| GET | `/v1/runs/{runId}/remediations` | Remediation PRs | operator |
| POST | `/v1/demo/seed` | Provision misconfigured sandbox (demo) | admin |

---

## 4. Request / response schemas

### POST `/v1/runs`
**Request**
```json
{
  "name": "Q2 prod posture check",
  "scope": {
    "subscriptionId": "00000000-0000-0000-0000-000000000000",
    "resourceGroups": ["rg-breachsim-sandbox"],
    "sandboxOnly": true
  },
  "options": { "maxTokenBudget": 200000, "frameworks": ["NIST-800-53", "SOC2"] }
}
```
**Response `202 Accepted`**
```json
{
  "runId": "run_abc123",
  "status": "queued",
  "createdAt": "2026-06-10T12:00:00Z",
  "links": {
    "self": "/v1/runs/run_abc123",
    "events": "/v1/runs/run_abc123/events",
    "graph": "/v1/runs/run_abc123/graph"
  }
}
```

### GET `/v1/runs/{runId}`
```json
{
  "runId": "run_abc123",
  "name": "Q2 prod posture check",
  "status": "running",
  "phase": "EXECUTE",
  "progress": 0.6,
  "agents": [
    { "agentId": "recon", "status": "completed" },
    { "agentId": "planner", "status": "completed" },
    { "agentId": "execution", "status": "running" }
  ],
  "stats": { "resources": 12, "findings": 3, "tokensUsed": 84210 },
  "startedAt": "2026-06-10T12:00:02Z"
}
```

### GET `/v1/runs/{runId}/events` (SSE)
```
event: agent
data: {"agentId":"recon","eventType":"breachsim.recon.completed","summary":"12 resources, 1 public blob","ts":"2026-06-10T12:00:20Z"}

event: agent
data: {"agentId":"planner","eventType":"breachsim.plan.ready","summary":"3-step chain: recon → public blob → secrets","ts":"2026-06-10T12:00:35Z"}

event: done
data: {"runId":"run_abc123","status":"completed"}
```

### GET `/v1/runs/{runId}/graph`
```json
{
  "nodes": [
    { "id": "node_internet", "kind": "actor", "label": "Internet" },
    { "id": "node_blob1", "kind": "resource", "label": "stbreachdemo", "props": { "publicExposure": true } }
  ],
  "edges": [
    { "from": "node_internet", "to": "node_blob1", "relation": "reaches", "confidence": 0.94 }
  ]
}
```

### GET `/v1/findings/{findingId}`
```json
{
  "id": "find_01",
  "runId": "run_abc123",
  "title": "Public blob with anonymous read → secrets exposure",
  "technique": "T1530",
  "severity": "critical",
  "validated": true,
  "risk": { "cvss": 9.1, "businessImpact": "high" },
  "attackSteps": [
    { "order": 1, "technique": "T1595", "targetAsset": "stbreachdemo", "result": "public endpoint found" },
    { "order": 2, "technique": "T1530", "targetAsset": "container:configs", "result": "downloaded appsettings.json" }
  ],
  "compliance": [
    { "framework": "NIST-800-53", "controlId": "AC-3", "rationale": "Improper access enforcement" },
    { "framework": "SOC2", "controlId": "CC6.1", "rationale": "Logical access controls" }
  ],
  "remediation": { "iacType": "bicep", "prUrl": "https://github.com/org/repo/pull/42", "status": "open" }
}
```

### Error envelope (RFC 7807)
```json
{
  "type": "https://breachsim.io/errors/scope-violation",
  "title": "Scope violation",
  "status": 403,
  "detail": "Subscription is not in the consented allow-list.",
  "instance": "/v1/runs",
  "traceId": "0af7651916cd43dd8448eb211c80319c"
}
```

---

## 5. Status codes

| Code | Meaning |
|------|---------|
| 200 | OK |
| 202 | Run accepted (async) |
| 400 | Validation error |
| 401 | Missing/invalid token |
| 403 | RBAC or scope violation |
| 404 | Not found |
| 409 | Conflict (run already running) |
| 429 | Rate limited |
| 500 | Internal error |

---

## 6. OpenAPI

The FastAPI app auto-generates an OpenAPI 3.1 schema at `/openapi.json` and Swagger UI at `/docs`.
