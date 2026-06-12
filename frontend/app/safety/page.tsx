import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Eye, Gauge, Lock, ShieldCheck } from "lucide-react";

export const metadata: Metadata = {
  title: "Safety — BreachSim",
  description: "How BreachSim stays safe: read-only validation, scope consent, and guardrails.",
};

const SIMULATE = [
  "Reconnaissance & asset discovery from cloud metadata",
  "Attack-path planning and MITRE ATT&CK technique chaining",
  "Exploitability reasoning grounded in CVE/NVD data",
  "Risk scoring, compliance mapping, and remediation drafting",
];

const EXECUTE = [
  "Read-only reachability checks (HTTP HEAD) on in-scope assets",
  "Resource-graph reads using least-privilege credentials",
  "Proposing infrastructure-as-code fixes as pull requests",
  "Never: destructive payloads, data exfiltration, or writes to your resources",
];

export default function SafetyPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-signal transition"
      >
        <ArrowLeft size={14} /> Back to console
      </Link>

      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          What BreachSim Does — and Doesn&apos;t Do
        </h1>
        <p className="text-sm text-muted">
          BreachSim is built to find real risk without becoming a risk itself. Here is exactly how
          the swarm stays safe.
        </p>
      </header>

      <Section icon={<ShieldCheck size={18} className="text-safe" />} title="Safe by design">
        <p>
          BreachSim performs <strong className="text-white">read-only validation</strong>. The
          swarm reasons about attack paths and confirms exposure with non-intrusive checks — it
          never deploys exploits or destructive payloads against your environment.
        </p>
        <p>
          When active validation is enabled, the only live action is a lightweight reachability
          probe (an HTTP <code className="text-signal">HEAD</code> request). No credentials are
          brute-forced, no data is written, modified, or exfiltrated, and no resource is taken
          offline.
        </p>
      </Section>

      <Section icon={<Lock size={18} className="text-signal" />} title="Scope & consent">
        <p>
          Every run is bound to an explicit{" "}
          <strong className="text-white">scope allow-list</strong> — subscriptions and resource
          groups you nominate. Assets outside that allow-list are never touched, and cross-tenant
          access is rejected.
        </p>
        <p>
          Runs also require a <strong className="text-white">consent attestation</strong>: the
          operator must acknowledge authorization to test before a simulation can start. Without
          that attestation the API refuses the request.
        </p>
      </Section>

      <Section icon={<Gauge size={18} className="text-warn" />} title="Guardrails">
        <ul className="space-y-3">
          <Guardrail title="SSRF guard">
            The validation probe blocks private, loopback, link-local, and cloud-metadata addresses,
            and rejects any non-HTTP scheme — preventing server-side request forgery.
          </Guardrail>
          <Guardrail title="Rate limiting">
            A per-principal token bucket caps how many runs can be launched per minute, protecting
            both your resources and the platform from abuse.
          </Guardrail>
          <Guardrail title="Sandbox enforcement">
            Demo and evaluation runs are confined to sandbox-only scopes, keeping experimentation
            isolated from production assets.
          </Guardrail>
        </ul>
      </Section>

      <Section
        icon={<Eye size={18} className="text-signal" />}
        title="What we simulate vs. what we execute"
      >
        <div className="overflow-hidden rounded-xl border border-white/5">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-panelHi">
                <th className="px-4 py-3 font-semibold text-signal">We simulate</th>
                <th className="px-4 py-3 font-semibold text-safe">We execute</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: Math.max(SIMULATE.length, EXECUTE.length) }).map((_, i) => (
                // eslint-disable-next-line react/no-array-index-key
                <tr key={i} className="border-t border-white/5 align-top">
                  <td className="px-4 py-3 text-muted">{SIMULATE[i] ?? ""}</td>
                  <td className="px-4 py-3 text-muted">{EXECUTE[i] ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: Readonly<{
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-xl border border-white/5 bg-panel p-6">
      <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
        {icon}
        <span>{title}</span>
      </h2>
      <div className="space-y-3 text-sm leading-relaxed text-muted">{children}</div>
    </section>
  );
}

function Guardrail({ title, children }: Readonly<{ title: string; children: React.ReactNode }>) {
  return (
    <li className="flex flex-col gap-0.5">
      <span className="font-medium text-white">{title}</span>
      <span>{children}</span>
    </li>
  );
}
