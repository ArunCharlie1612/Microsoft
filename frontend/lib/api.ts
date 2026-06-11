/** Typed API client + SSE helpers for the BreachSim orchestrator. */

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

export async function createRun(name: string, scope: RunScope): Promise<CreateRunResponse> {
  const res = await fetch(`${BASE}/v1/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, scope }),
  });
  if (!res.ok) throw new Error(`createRun failed: ${res.status}`);
  return res.json();
}

export async function seedDemo(): Promise<unknown> {
  const res = await fetch(`${BASE}/v1/demo/seed`, { method: "POST" });
  return res.json();
}

export async function getGraph(runId: string): Promise<AttackGraph> {
  const res = await fetch(`${BASE}/v1/runs/${runId}/graph`);
  return res.json();
}

export async function getFindings(runId: string): Promise<any[]> {
  const res = await fetch(`${BASE}/v1/runs/${runId}/findings`);
  return res.json();
}

/** Subscribe to the live agent SSE stream. Returns an unsubscribe fn. */
export function streamEvents(
  runId: string,
  onEvent: (e: AgentEvent) => void,
  onDone: () => void
): () => void {
  const es = new EventSource(`${BASE}/v1/runs/${runId}/events`);
  es.addEventListener("agent", (ev) => onEvent(JSON.parse((ev as MessageEvent).data)));
  es.addEventListener("done", () => {
    onDone();
    es.close();
  });
  es.onerror = () => es.close();
  return () => es.close();
}
