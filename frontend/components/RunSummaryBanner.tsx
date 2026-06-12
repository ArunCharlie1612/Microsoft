export interface RunSummary {
  /** Seconds from launch to the first scored finding (null if none observed). */
  timeToFirstFindingSec: number | null;
  /** Number of validated attack chains discovered. */
  attackChains: number;
  /** Count of findings rated critical severity. */
  criticalExposures: number;
  /** Remediation pull-request URL, if one was opened. */
  prUrl: string | null;
  /** Total wall-clock run time in seconds. */
  totalRunTimeSec: number;
}

function fmtSeconds(value: number | null): string {
  if (value == null) return "—";
  return `${value.toFixed(1)}s`;
}

export default function RunSummaryBanner({ summary }: Readonly<{ summary: RunSummary }>) {
  return (
    <section
      id="run-summary"
      className="rounded-xl border border-white/5 bg-[#1E293B] p-5 shadow-lg"
    >
      <h3 className="mb-4 text-xs font-semibold uppercase tracking-[0.2em] text-[#00D4FF]">
        Run Summary
      </h3>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <Metric icon="⏱" label="Time to first finding">
          <span className="text-2xl font-bold text-[#00D4FF]">
            {fmtSeconds(summary.timeToFirstFindingSec)}
          </span>
        </Metric>

        <Metric icon="🔗" label="Attack chains discovered">
          <span className="text-2xl font-bold text-[#00D4FF]">{summary.attackChains}</span>
        </Metric>

        <Metric icon="🚨" label="Critical exposures">
          <span className="text-2xl font-bold text-[#00D4FF]">{summary.criticalExposures}</span>
        </Metric>

        <Metric icon="📋" label="GitHub PR opened">
          {summary.prUrl ? (
            <a
              href={summary.prUrl}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-semibold text-[#00D4FF] underline decoration-dotted underline-offset-4 hover:text-white"
            >
              Yes — view PR
            </a>
          ) : (
            <span className="text-2xl font-bold text-[#00D4FF]">No</span>
          )}
        </Metric>

        <Metric icon="⏱" label="Total run time">
          <span className="text-2xl font-bold text-[#00D4FF]">
            {fmtSeconds(summary.totalRunTimeSec)}
          </span>
        </Metric>
      </div>
    </section>
  );
}

function Metric({
  icon,
  label,
  children,
}: Readonly<{
  icon: string;
  label: string;
  children: React.ReactNode;
}>) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted">
        <span aria-hidden>{icon}</span>
        <span>{label}</span>
      </div>
      {children}
    </div>
  );
}
