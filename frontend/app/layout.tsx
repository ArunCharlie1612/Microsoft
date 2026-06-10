import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BreachSim — Agentic Red Team Swarm",
  description: "Autonomous agents that continuously red-team your cloud posture.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="border-b border-white/5 px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-breach text-2xl">🛡️</span>
              <div>
                <h1 className="font-semibold tracking-tight">BreachSim</h1>
                <p className="text-xs text-muted">Agentic Red Team Swarm</p>
              </div>
            </div>
            <span className="text-xs text-muted">Security in the Agentic Future</span>
          </header>
          <main className="p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
