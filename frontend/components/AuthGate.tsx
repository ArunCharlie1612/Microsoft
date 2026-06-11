"use client";

import { signup } from "@/lib/api";
import { clearAuth, getTenant, isAuthenticated, setApiKey } from "@/lib/auth";
import { Check, Copy, KeyRound, LogOut, ShieldCheck, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

/** Gates the app behind a tenant API key. Supports self-service signup (free plan)
 * and pasting an existing key. Stores the key in localStorage and attaches it to all
 * API calls via the api client. */
export function AuthGate({
  children,
  onSignOut,
}: {
  children: React.ReactNode;
  onSignOut?: () => void;
}) {
  const [authed, setAuthed] = useState(false);
  const [mode, setMode] = useState<"signup" | "key">("signup");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [keyInput, setKeyInput] = useState("");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [tenant, setTenant] = useState<{ name: string } | null>(null);

  useEffect(() => {
    setAuthed(isAuthenticated());
    setTenant(getTenant());
  }, []);

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await signup(name.trim(), email.trim());
      setApiKey(res.apiKey, { tenantId: res.tenantId, name: res.name });
      setIssuedKey(res.apiKey);
      setTenant({ name: res.name });
    } catch {
      setError("Signup failed. Is the API reachable?");
    } finally {
      setBusy(false);
    }
  }

  function handleUseKey(e: React.FormEvent) {
    e.preventDefault();
    if (!keyInput.startsWith("bsk_")) {
      setError("That doesn't look like a BreachSim key (bsk_…).");
      return;
    }
    setApiKey(keyInput.trim());
    setAuthed(true);
  }

  async function handleCopy() {
    if (!issuedKey) return;
    try {
      await navigator.clipboard.writeText(issuedKey);
    } catch {
      // Fallback for non-secure contexts where the Clipboard API is unavailable.
      const el = document.createElement("textarea");
      el.value = issuedKey;
      el.style.position = "fixed";
      el.style.opacity = "0";
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleContinue() {
    setIssuedKey(null);
    setAuthed(true);
  }

  function handleLogout() {
    onSignOut?.();
    clearAuth();
    setAuthed(false);
    setIssuedKey(null);
    setTenant(null);
  }

  // Key just issued — show it once and let the user continue.
  if (issuedKey) {
    return (
      <div className="max-w-lg mx-auto mt-16 glass p-6 space-y-4">
        <div className="flex items-center gap-2 text-signal">
          <ShieldCheck size={20} />
          <h2 className="text-lg font-semibold">Your workspace is ready</h2>
        </div>
        <p className="text-sm text-muted">
          Copy your API key now — it will <strong>not</strong> be shown again. It is stored in this
          browser so you can continue immediately.
        </p>
        <div className="flex items-stretch gap-2">
          <code className="flex-1 break-all rounded-lg bg-panel px-3 py-2 text-xs">
            {issuedKey}
          </code>
          <button
            onClick={handleCopy}
            title="Copy API key to clipboard"
            aria-label="Copy API key to clipboard"
            className={`flex items-center gap-1 shrink-0 rounded-lg border px-3 text-xs transition ${
              copied
                ? "border-safe text-safe"
                : "border-white/10 text-muted hover:text-signal hover:border-signal"
            }`}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <button
          onClick={handleContinue}
          className="w-full bg-breach hover:bg-breach/90 text-white font-medium px-4 py-2.5 rounded-lg"
        >
          Continue to console
        </button>
      </div>
    );
  }

  if (authed) {
    return (
      <div>
        <div className="flex items-center justify-end gap-3 mb-2 text-xs text-muted">
          <span>
            Signed in{tenant?.name ? ` — ${tenant.name}` : ""}
          </span>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1 hover:text-breach transition"
          >
            <LogOut size={14} /> Sign out
          </button>
        </div>
        {children}
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto mt-16 glass p-6 space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Welcome to BreachSim</h2>
        <p className="text-sm text-muted">
          Autonomous red-team swarm for your cloud posture. Create a free workspace to begin.
        </p>
      </div>

      <div className="flex gap-2 text-sm">
        <button
          onClick={() => setMode("signup")}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border ${
            mode === "signup" ? "border-breach text-breach" : "border-white/10 text-muted"
          }`}
        >
          <UserPlus size={14} /> New workspace
        </button>
        <button
          onClick={() => setMode("key")}
          className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border ${
            mode === "key" ? "border-breach text-breach" : "border-white/10 text-muted"
          }`}
        >
          <KeyRound size={14} /> I have a key
        </button>
      </div>

      {mode === "signup" ? (
        <form onSubmit={handleSignup} className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Workspace / company name"
            required
            className="w-full rounded-lg bg-panel px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-breach"
          />
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email (optional)"
            type="email"
            className="w-full rounded-lg bg-panel px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-breach"
          />
          <button
            disabled={busy}
            className="w-full bg-breach hover:bg-breach/90 disabled:opacity-50 text-white font-medium px-4 py-2.5 rounded-lg"
          >
            {busy ? "Creating…" : "Create free workspace"}
          </button>
        </form>
      ) : (
        <form onSubmit={handleUseKey} className="space-y-3">
          <input
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="bsk_…"
            className="w-full rounded-lg bg-panel px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-breach"
          />
          <button className="w-full bg-breach hover:bg-breach/90 text-white font-medium px-4 py-2.5 rounded-lg">
            Use this key
          </button>
        </form>
      )}

      {error && <p className="text-sm text-breach">{error}</p>}
    </div>
  );
}
