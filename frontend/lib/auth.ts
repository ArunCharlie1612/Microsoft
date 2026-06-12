/** Lightweight client-side auth. Two credential types are supported and used
 * identically (sent as the X-API-Key header on every request):
 *
 *   1. A self-service tenant API key (bsk_…), persisted in localStorage.
 *   2. An enterprise SSO session JWT (from "Sign in with Microsoft"), held only in
 *      memory — never written to localStorage, so it disappears when the tab closes.
 *
 * The in-memory session token takes precedence when present. */

const KEY_STORAGE = "breachsim.apiKey";
const TENANT_STORAGE = "breachsim.tenant";

// Enterprise SSO session JWT — kept in memory only (intentionally not persisted).
let sessionToken: string | null = null;
let sessionTenant: { tenantId: string; name: string } | null = null;

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY_STORAGE);
}

export function setApiKey(key: string, tenant?: { tenantId: string; name: string }): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY_STORAGE, key);
  if (tenant) window.localStorage.setItem(TENANT_STORAGE, JSON.stringify(tenant));
}

/** Store the enterprise SSO session JWT in memory (not localStorage). */
export function setSessionToken(token: string, tenantName?: string): void {
  sessionToken = token;
  sessionTenant = tenantName ? { tenantId: "sso", name: tenantName } : null;
}

/** The active credential presented on API calls: SSO token first, then the API key. */
export function activeCredential(): string | null {
  return sessionToken ?? getApiKey();
}

export function getTenant(): { tenantId: string; name: string } | null {
  if (sessionTenant) return sessionTenant;
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(TENANT_STORAGE);
  return raw ? JSON.parse(raw) : null;
}

export function clearAuth(): void {
  sessionToken = null;
  sessionTenant = null;
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY_STORAGE);
  window.localStorage.removeItem(TENANT_STORAGE);
}

export function isAuthenticated(): boolean {
  return !!activeCredential();
}

/** Headers to attach to every authenticated API request. */
export function authHeaders(): Record<string, string> {
  const cred = activeCredential();
  return cred ? { "X-API-Key": cred } : {};
}

/** Begin the enterprise SSO login: full-page redirect to the backend, which 302s to
 * the Microsoft authorize URL. */
export function loginWithMicrosoft(): void {
  if (typeof window === "undefined") return;
  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  window.location.href = `${base}/auth/login`;
}

/** On load after the SSO callback, capture the JWT from the URL fragment into memory
 * and scrub it from the address bar. Returns true if a token was captured. */
export function captureSsoToken(): boolean {
  if (typeof window === "undefined") return false;
  const hash = window.location.hash.replace(/^#/, "");
  if (!hash) return false;
  const params = new URLSearchParams(hash);
  const token = params.get("token");
  if (!token) return false;
  setSessionToken(token, params.get("tenant") ?? undefined);
  // Remove the fragment so the token never lingers in the URL / history.
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return true;
}

