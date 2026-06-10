"use client";

import clsx from "clsx";

const AGENTS = [
  { id: "recon", label: "Recon" },
  { id: "research", label: "Research" },
  { id: "planner", label: "Planner" },
  { id: "security", label: "Security" },
  { id: "execution", label: "Execution" },
  { id: "validator", label: "Validator" },
  { id: "risk", label: "Risk" },
  { id: "compliance", label: "Compliance" },
  { id: "remediation", label: "Remediation" },
  { id: "memory", label: "Memory" },
];

export function AgentRoster({ active, completed }: { active: string | null; completed: Set<string> }) {
  return (
    <div className="glass p-4">
      <h3 className="text-xs uppercase tracking-widest text-muted mb-3">Swarm</h3>
      <div className="grid grid-cols-2 gap-2">
        {AGENTS.map((a) => {
          const isActive = active === a.id;
          const isDone = completed.has(a.id);
          return (
            <div
              key={a.id}
              className={clsx(
                "rounded-lg px-3 py-2 text-sm border transition-all",
                isActive && "border-signal text-signal glow-signal animate-pulseSoft",
                isDone && !isActive && "border-safe/40 text-safe",
                !isActive && !isDone && "border-white/5 text-muted"
              )}
            >
              {a.label}
              {isDone && !isActive && <span className="float-right">✓</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
