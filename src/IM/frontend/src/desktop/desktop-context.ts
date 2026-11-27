export type DesktopPlatformId = "darwin-arm64" | "win32-x64";

export interface PendingServerSwitch {
  target_origin: string;
  is_cleartext_http: boolean;
}

export type DesktopOriginSecurityKind =
  | "https"
  | "loopback_http"
  | "private_http"
  | "rejected_public_http"
  | "invalid";

export interface DesktopWindowBootContext {
  imOrigin: string;
  contextEpoch: number;
  platform: DesktopPlatformId;
  seedReady?: boolean;
  seedError?: string | null;
  hostLogPath?: string;
  pendingServerSwitch?: PendingServerSwitch | null;
  deepLinkError?: string | null;
}

declare global {
  interface Window {
    __CREWDEN_DESKTOP__?: DesktopWindowBootContext;
  }
}

let testOverride: DesktopWindowBootContext | null | undefined = undefined;

function parseStrictIpv4(hostname: string): [number, number, number, number] | null {
  if (!/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname)) return null;
  const parts = hostname.split(".");
  if (parts.length !== 4) return null;
  const nums: number[] = [];
  for (const part of parts) {
    if (!/^(0|[1-9]\d*)$/.test(part)) return null;
    const n = Number(part);
    if (!Number.isInteger(n) || n < 0 || n > 255) return null;
    nums.push(n);
  }
  return [nums[0]!, nums[1]!, nums[2]!, nums[3]!];
}

/** Classify a candidate IM server URL using strict literal IP parsing and reserved-domain protection. */
export function classifyDesktopImOrigin(rawUrl: string): {
  kind: DesktopOriginSecurityKind;
  normalizedOrigin?: string;
} {
  const trimmed = rawUrl.trim();
  if (!trimmed) return { kind: "invalid" };
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { kind: "invalid" };
  }
  if (
    (parsed.protocol !== "https:" && parsed.protocol !== "http:") ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    (parsed.pathname !== "/" && parsed.pathname !== "")
  ) {
    return { kind: "invalid" };
  }
  const host = parsed.hostname.toLowerCase();
  if (parsed.protocol === "https:") {
    return { kind: "https", normalizedOrigin: parsed.origin };
  }
  if (host === "crewden.work" || host.endsWith(".crewden.work")) {
    return { kind: "rejected_public_http", normalizedOrigin: parsed.origin };
  }
  if (host === "localhost" || host === "::1" || host === "[::1]") {
    return { kind: "loopback_http", normalizedOrigin: parsed.origin };
  }
  if (host.startsWith("[") && host.endsWith("]")) {
    const inner = host.slice(1, -1);
    if (inner === "::1" || inner === "0:0:0:0:0:0:0:1") {
      return { kind: "loopback_http", normalizedOrigin: parsed.origin };
    }
    if (/^f[cd][0-9a-f]{0,2}:/i.test(inner) || /^fe[89ab][0-9a-f]?:/i.test(inner)) {
      return { kind: "private_http", normalizedOrigin: parsed.origin };
    }
    return { kind: "rejected_public_http", normalizedOrigin: parsed.origin };
  }
  const ipv4 = parseStrictIpv4(host);
  if (ipv4) {
    if (ipv4[0] === 127) return { kind: "loopback_http", normalizedOrigin: parsed.origin };
    if (
      ipv4[0] === 10 ||
      (ipv4[0] === 172 && ipv4[1] >= 16 && ipv4[1] <= 31) ||
      (ipv4[0] === 192 && ipv4[1] === 168)
    ) {
      return { kind: "private_http", normalizedOrigin: parsed.origin };
    }
    return { kind: "rejected_public_http", normalizedOrigin: parsed.origin };
  }
  if (host.endsWith(".local") && host.length > ".local".length && !host.startsWith(".")) {
    return { kind: "private_http", normalizedOrigin: parsed.origin };
  }
  return { kind: "rejected_public_http", normalizedOrigin: parsed.origin };
}

/** Synchronize `html[data-crewden-desktop="true"]` with active Desktop runtime state. */
export function syncDesktopDocumentAttribute(): void {
  if (typeof document === "undefined") return;
  if (getDesktopBootContext() !== null) {
    document.documentElement.dataset.crewdenDesktop = "true";
  } else {
    delete document.documentElement.dataset.crewdenDesktop;
  }
}

/** Override Desktop runtime detection inside unit tests.
 *
 * Args:
 *   context: Simulated boot context, or `undefined` to restore `window.__CREWDEN_DESKTOP__`.
 */
export function setDesktopBootContextForTest(context: DesktopWindowBootContext | null | undefined): void {
  testOverride = context;
  syncDesktopDocumentAttribute();
}

/** Return the active Crewden Desktop boot context injected by the Tauri loopback host.
 *
 * Returns:
 *   Normalized boot context when running inside Crewden Desktop, otherwise `null`.
 */
export function getDesktopBootContext(): DesktopWindowBootContext | null {
  if (testOverride !== undefined) return testOverride;
  if (typeof window === "undefined") return null;
  const raw = window.__CREWDEN_DESKTOP__;
  if (!raw || typeof raw.imOrigin !== "string" || !raw.imOrigin.trim()) return null;
  return {
    imOrigin: raw.imOrigin.replace(/\/+$/, ""),
    contextEpoch: typeof raw.contextEpoch === "number" ? raw.contextEpoch : 1,
    platform: raw.platform === "win32-x64" ? "win32-x64" : "darwin-arm64",
    seedReady: raw.seedReady ?? true,
    seedError: raw.seedError ?? null,
    hostLogPath: raw.hostLogPath,
    pendingServerSwitch: raw.pendingServerSwitch ?? null,
    deepLinkError: raw.deepLinkError ?? null,
  };
}

if (typeof document !== "undefined") {
  syncDesktopDocumentAttribute();
}

/** Check whether the current SPA instance is running inside the Crewden Desktop host. */
export function isDesktopClient(): boolean {
  return getDesktopBootContext() !== null;
}

/** Return the active IM origin managed by Crewden Desktop, or `null` on Web. */
export function getDesktopImOrigin(): string | null {
  return getDesktopBootContext()?.imOrigin ?? null;
}

/** Partition client-side persistence keys by `imOrigin` in Desktop mode.
 *
 * Web mode keeps existing keys unchanged because browser origin isolation already
 * separates different IM deployments. Desktop reuses one fixed loopback origin so
 * pending send attempts survive restarts without mixing across switched servers.
 *
 * Args:
 *   baseKey: Unscoped storage or database name.
 * Returns:
 *   Origin-scoped key in Desktop mode, or `baseKey` unchanged in Web mode.
 */
export function desktopScopedKey(baseKey: string): string {
  const origin = getDesktopImOrigin();
  return origin ? `${baseKey}::${origin}` : baseKey;
}
