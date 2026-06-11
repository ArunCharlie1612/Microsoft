"use client";

import { AgentFeed } from "@/components/AgentFeed";
import { AgentRoster } from "@/components/AgentRoster";
import { AttackGraph } from "@/components/AttackGraph";
import { AuthGate } from "@/components/AuthGate";
import { UsagePanel } from "@/components/UsagePanel";
import {
  AgentEvent,
  AttackGraph as Graph,
  cancelRun,
  createRun,
  getFindings,
  getGraph,
  seedDemo,
  streamEvents,
  toText,
} from "@/lib/api";
import { Play, ShieldAlert } from "lucide-react";
import { useRef, useState } from "react";

const DEMO_SCOPE = {
  subscriptionId: "00000000-0000-0000-0000-000000000000",
  resourceGroups: ["rg-breachsim-sandbox"],
  sandboxOnly: true,
};

export default function DashboardPage() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [graph, setGraph] = useState<Graph>({ nodes: [], edges: [] });
  const [findings, setFindings] = useState<any[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [progress, setProgress] = useState(0);
  const [running, setRunning] = useState(false);
  const [usageKey, setUsageKey] = useState(0);

  // Track the in-flight run so we can terminate it (e.g. on sign-out).
  const activeRunId = useRef<string | null>(null);
  const unsubscribe = useRef<(() => void) | null>(null);

  async function launch() {
    setEvents([]);
    setGraph({ nodes: [], edges: [] });
    setFindings([]);
    setCompleted(new Set());
    setProgress(0);
    setRunning(true);

    await seedDemo();
    const run = await createRun("Live Demo — misconfigured blob", DEMO_SCOPE);
    activeRunId.current = run.runId;

    unsubscribe.current = streamEvents(
      run.runId,
      (e) => {
        setEvents((prev) => [...prev, e]);
        if (e.progress != null) setProgress(e.progress);
        if (e.agentId && e.agentId !== "orchestrator") {
          setActive(e.agentId);
          setCompleted((prev) => new Set(prev).add(e.agentId));
        }
        getGraph(run.runId).then(setGraph);
      },
      async () => {
        setActive(null);
        setRunning(false);
        setProgress(1);
        activeRunId.current = null;
        unsubscribe.current = null;
        setFindings(await getFindings(run.runId));
        setGraph(await getGraph(run.runId));
        setUsageKey((k) => k + 1);
      }
    );
  }

  // Terminate any in-flight scan and reset the console when the user signs out.
  function handleSignOut() {
    unsubscribe.current?.();
    unsubscribe.current = null;
    if (activeRunId.current) {
      cancelRun(activeRunId.current);
      activeRunId.current = null;
    }
    setRunning(false);
    setActive(null);
    setProgress(0);
    setEvents([]);
    setFindings([]);
    setGraph({ nodes: [], edges: [] });
    setCompleted(new Set());
  }

  return (
    <AuthGate onSignOut={handleSignOut}>
      <div className="space-y-6">
        <section className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Continuous Red-Team Console</h2>
            <p className="text-sm text-muted">
              Watch the swarm discover → chain → validate → remediate in real time.
            </p>
          </div>
          <button
            onClick={launch}
            disabled={running}
            className="flex items-center gap-2 bg-breach hover:bg-breach/90 disabled:opacity-50 text-white font-medium px-5 py-2.5 rounded-lg glow-breach transition"
          >
            <Play size={18} />
            {running ? "Swarm running…" : "Deploy Swarm"}
          </button>
        </section>

        <div className="h-1.5 w-full bg-panel rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-signal to-breach transition-all duration-500"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>

        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-3">
            <AgentRoster active={active} completed={completed} />
            <div className="mt-6">
              <UsagePanel refreshKey={usageKey} />
            </div>
          </div>
          <div className="col-span-5">
            <AttackGraph graph={graph} />
          </div>
          <div className="col-span-4">
            <AgentFeed events={events} />
          </div>
        </div>

        {findings.length > 0 && (
          <section className="glass p-5">
            <h3 className="flex items-center gap-2 text-sm uppercase tracking-widest text-breach mb-4">
              <ShieldAlert size={16} /> Findings & Remediation
            </h3>
            {findings.map((f, i) => (
              <div key={i} className="border-t border-white/5 pt-4 mt-4 first:border-0 first:pt-0 first:mt-0">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{toText(f.title)}</p>
                  <span className="text-xs px-2 py-1 rounded bg-breach/20 text-breach uppercase">
                    {toText(f.severity)}
                  </span>
                </div>
                {f.remediation?.pr_url && (
                  <a
                    href={f.remediation.pr_url}
                    className="text-safe text-sm underline mt-2 inline-block"
                    target="_blank"
                    rel="noreferrer"
                  >
                    → Remediation PR opened ({toText(f.remediation.iac_type)})
                  </a>
                )}
              </div>
            ))}
          </section>
        )}
      </div>
    </AuthGate>
  );
}
