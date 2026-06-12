"use client";

import { isAuthenticated } from "@/lib/auth";
import { TOUR_DONE_KEY, useTourStore } from "@/lib/tourStore";
import { useEffect, useState } from "react";
import Joyride, { CallBackProps, STATUS, Status, Step } from "react-joyride";

// BreachSim onboarding palette (per design spec).
const PRIMARY = "#00D4FF";
const BACKGROUND = "#0B0F1A";
const TEXT = "#E2E8F0";

const STEPS: Step[] = [
  {
    target: "#api-key-panel",
    title: "Your API Key",
    content: "This is your tenant API key. Keep it safe — it controls all your simulation runs.",
    disableBeacon: true,
  },
  {
    target: "#new-run-button",
    title: "Start a Simulation",
    content: "Click here to launch a new red team run against your configured Azure scope.",
  },
  {
    target: "#swarm-console",
    title: "Live Swarm Console",
    content:
      "Watch each of the 8 agents work in real time — Recon, Planner, Validator, and more.",
  },
  {
    target: "#findings-panel",
    title: "Findings & Severity",
    content:
      "Each confirmed exposure is listed here with CVSS score and NIST compliance mapping.",
  },
  {
    target: "#attack-graph",
    title: "Attack Graph",
    content: "This graph shows how individual findings chain into multi-step attack paths.",
  },
];

/**
 * First-run onboarding tour for the dashboard. Auto-starts once per browser
 * (guarded by the `breachsim_tour_done` localStorage flag) and can be replayed
 * on demand via the "Take the tour" nav button (see TourButton + tourStore).
 */
export function OnboardingTour() {
  const run = useTourStore((s) => s.run);
  const start = useTourStore((s) => s.start);
  const stop = useTourStore((s) => s.stop);

  // react-joyride touches the DOM, so only render after mount to avoid any
  // server/client hydration mismatch.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Auto-start on first authenticated visit. The short delay lets the dashboard
  // targets mount before the tour tries to anchor to them.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!isAuthenticated()) return;
    if (window.localStorage.getItem(TOUR_DONE_KEY) === "1") return;
    const timer = window.setTimeout(() => start(), 600);
    return () => window.clearTimeout(timer);
  }, [start]);

  function handleCallback(data: CallBackProps) {
    const finished: Status[] = [STATUS.FINISHED, STATUS.SKIPPED];
    if (finished.includes(data.status)) {
      stop();
    }
  }

  if (!mounted) return null;

  return (
    <Joyride
      steps={STEPS}
      run={run}
      continuous
      showProgress
      showSkipButton
      scrollToFirstStep
      disableScrollParentFix
      callback={handleCallback}
      locale={{ last: "Done", skip: "Skip tour" }}
      styles={{
        options: {
          primaryColor: PRIMARY,
          backgroundColor: BACKGROUND,
          arrowColor: BACKGROUND,
          textColor: TEXT,
          overlayColor: "rgba(3, 7, 18, 0.7)",
          zIndex: 10000,
        },
        tooltipTitle: { color: PRIMARY, fontWeight: 600 },
        buttonNext: { backgroundColor: PRIMARY, color: BACKGROUND, fontWeight: 600 },
        buttonBack: { color: TEXT },
        buttonSkip: { color: "#7C8AA5" },
      }}
    />
  );
}
