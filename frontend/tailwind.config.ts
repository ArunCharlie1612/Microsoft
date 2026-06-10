import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // BreachSim color system — see docs/ui-ux.md
        ink: "#0A0E1A",
        panel: "#111726",
        panelHi: "#18203A",
        breach: "#FF3B5C", // attacker red
        signal: "#00E5FF", // agent cyan
        safe: "#22D39A", // remediation green
        warn: "#FFB020",
        muted: "#7C8AA5",
      },
      fontFamily: {
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      animation: {
        pulseSoft: "pulseSoft 2s ease-in-out infinite",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
