"use client";

import { submitFeedback, toText } from "@/lib/api";
import { Check, ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";

type Verdict = "confirmed" | "dismissed";

interface FindingsPanelProps {
  findings: any[];
}

/**
 * Findings & remediation list with a human-in-the-loop feedback control on every row.
 * Operators confirm (✓) or dismiss (✗) each finding; the verdict is PATCHed to the API
 * and the swarm's Validator agent learns from it to re-calibrate severity on future runs.
 */
export function FindingsPanel({ findings }: Readonly<FindingsPanelProps>) {
  // Per-finding submitted verdict (keyed by finding id), so buttons disable after use.
  const [verdicts, setVerdicts] = useState<Record<string, Verdict>>({});
  const [pending, setPending] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Seed any verdicts already stored on the finding (e.g. after a reload).
  useEffect(() => {
    const seeded: Record<string, Verdict> = {};
    for (const f of findings) {
      if (f?.id && (f.verdict === "confirmed" || f.verdict === "dismissed")) {
        seeded[f.id] = f.verdict;
      }
    }
    setVerdicts(seeded);
  }, [findings]);

  // Auto-dismiss the toast after a short delay.
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  async function sendFeedback(findingId: string, verdict: Verdict) {
    setPending(findingId);
    try {
      await submitFeedback(findingId, verdict);
      setVerdicts((prev) => ({ ...prev, [findingId]: verdict }));
      setToast("Feedback recorded — agents will learn from this.");
    } catch {
      setToast("Could not record feedback — please try again.");
    } finally {
      setPending(null);
    }
  }

  return (
    <section id="findings-panel" className="glass p-5">
      <h3 className="flex items-center gap-2 text-sm uppercase tracking-widest text-breach mb-4">
        <ShieldAlert size={16} /> Findings &amp; Remediation
      </h3>

      {findings.length === 0 ? (
        <p className="text-sm text-muted">
          Confirmed exposures appear here after a run — each with its CVSS score and NIST
          compliance mapping.
        </p>
      ) : (
        findings.map((f, i) => {
          const submitted = f?.id ? verdicts[f.id] : undefined;
          const isPending = pending === f?.id;
          return (
            <div
              key={f?.id ?? i}
              className="border-t border-white/5 pt-4 mt-4 first:border-0 first:pt-0 first:mt-0"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium">{toText(f.title)}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-1 rounded bg-breach/20 text-breach uppercase">
                    {toText(f.severity)}
                  </span>
                  {submitted ? (
                    <span
                      className={`text-xs px-2 py-1 rounded uppercase ${
                        submitted === "confirmed"
                          ? "bg-safe/20 text-safe"
                          : "bg-breach/20 text-breach"
                      }`}
                    >
                      {submitted === "confirmed" ? "Confirmed" : "Dismissed"}
                    </span>
                  ) : (
                    <>
                      <button
                        onClick={() => f?.id && sendFeedback(f.id, "confirmed")}
                        disabled={isPending || !f?.id}
                        title="Confirm this finding"
                        aria-label="Confirm this finding"
                        className="p-1.5 rounded-md bg-safe/10 text-safe hover:bg-safe/20 disabled:opacity-40 transition"
                      >
                        <Check size={15} />
                      </button>
                      <button
                        onClick={() => f?.id && sendFeedback(f.id, "dismissed")}
                        disabled={isPending || !f?.id}
                        title="Dismiss this finding"
                        aria-label="Dismiss this finding"
                        className="p-1.5 rounded-md bg-breach/10 text-breach hover:bg-breach/20 disabled:opacity-40 transition"
                      >
                        <X size={15} />
                      </button>
                    </>
                  )}
                </div>
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
          );
        })
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 glass px-4 py-3 text-sm text-text shadow-lg rounded-lg border border-signal/30">
          {toast}
        </div>
      )}
    </section>
  );
}
