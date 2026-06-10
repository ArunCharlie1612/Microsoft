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
