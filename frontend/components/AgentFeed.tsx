"use client";

import { AgentEvent } from "@/lib/api";
import clsx from "clsx";

const AGENT_COLORS: Record<string, string> = {
  recon: "text-signal",
  research: "text-signal",
  planner: "text-warn",
  security: "text-safe",
  execution: "text-breach",
  validator: "text-warn",
  risk: "text-breach",
  compliance: "text-safe",
  remediation: "text-safe",
  memory: "text-muted",
  orchestrator: "text-slate-300",
};

export function AgentFeed({ events }: { events: AgentEvent[] }) {
  return (
    <div className="glass p-4 h-[460px] overflow-y-auto font-mono text-sm">
      <h3 className="text-xs uppercase tracking-widest text-muted mb-3">Agent Activity Feed</h3>
      {events.length === 0 && <p className="text-muted">Awaiting swarm deployment…</p>}
      <ul className="space-y-2">
        {events.map((e, i) => (
          <li key={i} className="flex gap-3">
            <span className={clsx("font-semibold w-24 shrink-0", AGENT_COLORS[e.agentId] ?? "text-slate-300")}>
              {e.agentId}
            </span>
            <span className="text-slate-300">{e.summary}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
