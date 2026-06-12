"use client";

import { useTourStore } from "@/lib/tourStore";
import { HelpCircle } from "lucide-react";

/**
 * "Take the tour" control for the top nav bar. Resets the seen flag and
 * restarts the onboarding tour on demand (see tourStore.start).
 */
export function TourButton() {
  const start = useTourStore((s) => s.start);

  return (
    <button
      onClick={start}
      className="flex items-center gap-1.5 text-xs text-muted hover:text-signal border border-white/10 hover:border-signal rounded-lg px-3 py-1.5 transition"
    >
      <HelpCircle size={14} /> Take the tour
    </button>
  );
}
