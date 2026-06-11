"use client";

import { createCheckout, getUsage, UsageSummary } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { Activity, Crown, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

/** Shows the tenant's plan, daily run usage vs limit, tokens and estimated cost,
 * plus an Upgrade-to-Pro button that starts Stripe Checkout when billing is
 * configured server-side. */
export function UsagePanel({ refreshKey }: { refreshKey?: number }) {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [upgrading, setUpgrading] = useState(false);
  const [billingOff, setBillingOff] = useState(false);

  const refresh = useCallback(() => {
    if (!isAuthenticated()) return;
    getUsage().then(setUsage).catch(() => setUsage(null));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, refreshKey]);

  async function upgrade() {
    setUpgrading(true);
    try {
      const url = await createCheckout();
      if (url) {
        window.location.href = url;
      } else {
        setBillingOff(true);
      }
    } catch {
      setBillingOff(true);
    } finally {
      setUpgrading(false);
    }
  }

  if (!usage) return null;

  const pct =
    usage.dailyRunLimit > 0
      ? Math.min(100, Math.round((usage.runsToday / usage.dailyRunLimit) * 100))
      : 0;
  const isPro = usage.plan === "pro";

  return (
    <div className="glass p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted">
          <Activity size={14} /> Usage
        </h3>
        <span
          className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded uppercase ${
            isPro ? "bg-signal/20 text-signal" : "bg-white/10 text-muted"
          }`}
        >
          {isPro ? <Crown size={12} /> : null}
          {usage.plan}
        </span>
      </div>

      <div>
        <div className="flex justify-between text-xs text-muted mb-1">
          <span>Runs today</span>
          <span>
            {usage.runsToday} / {usage.dailyRunLimit}
          </span>
        </div>
        <div className="h-1.5 w-full bg-panel rounded-full overflow-hidden">
          <div
            className={`h-full ${pct >= 100 ? "bg-breach" : "bg-signal"} transition-all`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-panel px-3 py-2">
          <div className="text-muted">Tokens</div>
          <div className="font-medium">{usage.tokensUsed.toLocaleString()}</div>
        </div>
        <div className="rounded-lg bg-panel px-3 py-2">
          <div className="text-muted">Est. cost</div>
          <div className="font-medium">${usage.estimatedCostUsd.toFixed(2)}</div>
        </div>
      </div>

      {!isPro && (
        <button
          onClick={upgrade}
          disabled={upgrading}
          className="w-full flex items-center justify-center gap-1.5 bg-signal/90 hover:bg-signal disabled:opacity-50 text-black font-medium px-3 py-2 rounded-lg text-sm transition"
        >
          <Zap size={14} /> {upgrading ? "Starting…" : "Upgrade to Pro"}
        </button>
      )}
      {billingOff && (
        <p className="text-xs text-muted">
          Billing isn’t enabled on this deployment. You’re on the free plan.
        </p>
      )}
    </div>
  );
}
