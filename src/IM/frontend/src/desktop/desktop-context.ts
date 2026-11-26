export type DesktopPlatformId = "darwin-arm64" | "win32-x64";

export interface DesktopWindowBootContext {
  imOrigin: string;
  contextEpoch: number;
  platform: DesktopPlatformId;
}

declare global {
  interface Window {
    __CREWDEN_DESKTOP__?: DesktopWindowBootContext;
  }
}

let testOverride: DesktopWindowBootContext | null | undefined = undefined;

/** Override Desktop runtime detection inside unit tests.
 *
 * Args:
 *   context: Simulated boot context, or `undefined` to restore `window.__CREWDEN_DESKTOP__`.
 */
export function setDesktopBootContextForTest(context: DesktopWindowBootContext | null | undefined): void {
  testOverride = context;
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
  };
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
