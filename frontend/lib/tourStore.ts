"use client";

import { create } from "zustand";

/** localStorage flag marking the onboarding tour as already seen. */
export const TOUR_DONE_KEY = "breachsim_tour_done";

interface TourState {
  /** Whether the tour is currently running. */
  run: boolean;
  /** Start (or restart) the tour. Clears the "done" flag so it plays again. */
  start: () => void;
  /** Stop the tour and mark it complete so it never auto-starts again. */
  stop: () => void;
}

export const useTourStore = create<TourState>((set) => ({
  run: false,
  start: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(TOUR_DONE_KEY);
    }
    set({ run: true });
  },
  stop: () => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TOUR_DONE_KEY, "1");
    }
    set({ run: false });
  },
}));
