"use client";

import { AgentFeed } from "@/components/AgentFeed";
import { AgentRoster } from "@/components/AgentRoster";
import { AttackGraph } from "@/components/AttackGraph";
import { AuthGate } from "@/components/AuthGate";
import { FindingsPanel } from "@/components/FindingsPanel";
import { OnboardingTour } from "@/components/OnboardingTour";
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
} from "@/lib/api";
import { Play } from "lucide-react";
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
      <OnboardingTour />
      <div className="space-y-6">
        <section className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Continuous Red-Team Console</h2>
            <p className="text-sm text-muted">
              Watch the swarm discover → chain → validate → remediate in real time.
            </p>
          </div>
          <button
            id="new-run-button"
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
            <div id="swarm-console">
              <AgentRoster active={active} completed={completed} />
            </div>
            <div id="api-key-panel" className="mt-6">
              <UsagePanel refreshKey={usageKey} />
            </div>
          </div>
          <div id="attack-graph" className="col-span-5">
            <AttackGraph graph={graph} />
          </div>
          <div className="col-span-4">
            <AgentFeed events={events} />
          </div>
        </div>

        <FindingsPanel findings={findings} />
      </div>
    </AuthGate>
  );
}
