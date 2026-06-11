/** Lightweight client-side auth: stores the tenant API key in localStorage and
 * exposes it as the X-API-Key header for all API calls. This is the free-tier auth
 * path (no identity provider needed). Enterprise SSO (Entra/MSAL) can be layered on
 * later by sending an Authorization: Bearer token instead. */

const KEY_STORAGE = "breachsim.apiKey";
const TENANT_STORAGE = "breachsim.tenant";

export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(KEY_STORAGE);
}

export function setApiKey(key: string, tenant?: { tenantId: string; name: string }): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY_STORAGE, key);
  if (tenant) window.localStorage.setItem(TENANT_STORAGE, JSON.stringify(tenant));
}

export function getTenant(): { tenantId: string; name: string } | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(TENANT_STORAGE);
  return raw ? JSON.parse(raw) : null;
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(KEY_STORAGE);
  window.localStorage.removeItem(TENANT_STORAGE);
}

export function isAuthenticated(): boolean {
  return !!getApiKey();
}

/** Headers to attach to every authenticated API request. */
export function authHeaders(): Record<string, string> {
  const key = getApiKey();
  return key ? { "X-API-Key": key } : {};
}
