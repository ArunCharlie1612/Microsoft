/** Typed API client + SSE helpers for the BreachSim orchestrator. */

import { authHeaders, getApiKey } from "./auth";

export interface RunScope {
  subscriptionId: string;
  resourceGroups: string[];
  sandboxOnly: boolean;
}

export interface CreateRunResponse {
  runId: string;
  status: string;
  links: { self: string; events: string; graph: string };
}

export interface AgentEvent {
  agentId: string;
  eventType: string;
  summary: string;
  phase?: string;
  progress?: number;
}

export interface GraphNode {
  id: string;
  kind: string;
  label: string;
  props?: Record<string, unknown>;
}
export interface GraphEdge {
  from: string;
  to: string;
  relation: string;
  confidence: number;
}
export interface AttackGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/**
 * Coerce any value into a safe, human-readable string for rendering.
 * The LLM may return an object/array where a plain string is expected; rendering
 * such a value directly throws React error #31. This guarantees a renderable string.
 */
export function toText(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(toText).join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${toText(v)}`)
      .join(", ");
  }
  return String(value);
}

export interface SignupResponse {
  tenantId: string;
  name: string;
  plan: string;
  apiKey: string;
  note: string;
}

export interface UsageSummary {
  tenantId: string;
  plan: string;
  runsTotal: number;
  runsToday: number;
  dailyRunLimit: number;
  tokensUsed: number;
  estimatedCostUsd: number;
}

/** Self-service onboarding: returns a tenant + API key (shown once). */
export async function signup(name: string, email = ""): Promise<SignupResponse> {
  const res = await fetch(`${BASE}/v1/tenants/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email }),
  });
  if (!res.ok) throw new Error(`signup failed: ${res.status}`);
  return res.json();
}

export async function getUsage(): Promise<UsageSummary> {
  const res = await fetch(`${BASE}/v1/tenants/me/usage`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`usage failed: ${res.status}`);
  return res.json();
}

/** Start a Stripe Checkout to upgrade to Pro. Returns the redirect URL, or null if
 * billing is not configured on the server (503). */
export async function createCheckout(): Promise<string | null> {
  const res = await fetch(`${BASE}/v1/tenants/me/checkout`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (res.status === 503) return null; // billing not configured
  if (!res.ok) throw new Error(`checkout failed: ${res.status}`);
  const body = await res.json();
  return body.checkoutUrl as string;
}

export async function createRun(
  name: string,
  scope: RunScope,
  authorizedBy = "demo-operator"
): Promise<CreateRunResponse> {
  const res = await fetch(`${BASE}/v1/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      name,
      scope,
      // Authorization-to-test attestation (required by the API).
      authorizationAcknowledged: true,
      authorizedBy,
    }),
  });
  if (!res.ok) throw new Error(`createRun failed: ${res.status}`);
  return res.json();
}

export async function seedDemo(): Promise<unknown> {
  const res = await fetch(`${BASE}/v1/demo/seed`, {
    method: "POST",
    headers: authHeaders(),
  });
  return res.json();
}

export async function getGraph(runId: string): Promise<AttackGraph> {
  const res = await fetch(`${BASE}/v1/runs/${runId}/graph`, { headers: authHeaders() });
  return res.json();
}

export async function getFindings(runId: string): Promise<any[]> {
  const res = await fetch(`${BASE}/v1/runs/${runId}/findings`, { headers: authHeaders() });
  return res.json();
}

/**
 * Submit an operator triage verdict on a finding. The swarm's Validator agent learns
 * from these verdicts to re-calibrate severity on future runs. Returns the updated finding.
 */
export async function submitFeedback(
  findingId: string,
  verdict: "confirmed" | "dismissed",
  note?: string
): Promise<any> {
  const res = await fetch(`${BASE}/v1/findings/${findingId}/feedback`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ verdict, note }),
  });
  if (!res.ok) throw new Error(`feedback failed: ${res.status}`);
  return res.json();
}

/** Cancel an in-flight run. Best-effort: never throws so sign-out is never blocked. */
export async function cancelRun(runId: string): Promise<void> {
  try {
    await fetch(`${BASE}/v1/runs/${runId}/cancel`, {
      method: "POST",
      headers: authHeaders(),
      keepalive: true,
    });
  } catch {
    // ignore — the swarm stops accepting our stream the moment we sign out anyway
  }
}

/** Subscribe to the live agent SSE stream. Returns an unsubscribe fn. */
export function streamEvents(
  runId: string,
  onEvent: (e: AgentEvent) => void,
  onDone: () => void
): () => void {
  // EventSource cannot set headers; pass the API key as a query param when present.
  const key = getApiKey();
  const qs = key ? `?apiKey=${encodeURIComponent(key)}` : "";
  const es = new EventSource(`${BASE}/v1/runs/${runId}/events${qs}`);
  es.addEventListener("agent", (ev) => onEvent(JSON.parse((ev as MessageEvent).data)));
  es.addEventListener("done", () => {
    onDone();
    es.close();
  });
  es.onerror = () => es.close();
  return () => es.close();
}
