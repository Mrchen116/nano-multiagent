import type { MacDistribution } from './node-update.js';
import type { WorkerRuntime } from './worker-runtimes.js';

/** Managed proxy environment keys synchronized atomically from the Desktop proxy form. */
export const DESKTOP_PROXY_MANAGED_KEYS = [
  'NODE_USE_ENV_PROXY',
  'HTTP_PROXY',
  'http_proxy',
  'HTTPS_PROXY',
  'https_proxy',
  'ALL_PROXY',
  'all_proxy',
  'NO_PROXY',
  'no_proxy',
] as const;

/** Internal or proxy-managed keys hidden from the generic user environment table. */
export const DESKTOP_HIDDEN_ENV_KEYS = [
  ...DESKTOP_PROXY_MANAGED_KEYS,
  'NANO_OWNER_CONFIG_ROOT',
] as const;

const HIDDEN_KEY_SET = new Set<string>(DESKTOP_HIDDEN_ENV_KEYS);

/** Executable or bundle extensions that may only be revealed in Finder/Explorer, never launched directly. */
export const DESKTOP_BLOCKED_OPEN_EXTENSIONS = [
  '.app',
  '.exe',
  '.bat',
  '.cmd',
  '.ps1',
  '.sh',
  '.command',
  '.msi',
  '.vbs',
  '.com',
  '.scr',
] as const;

export const DEFAULT_DESKTOP_NO_PROXY = 'localhost,127.0.0.1,::1';

export interface DesktopProxySettings {
  enabled: boolean;
  url: string;
  no_proxy: string;
}

export type DesktopLocalOwnership =
  | 'unbound'
  | 'takeover_available'
  | 'managed_online'
  | 'managed_stopped'
  | 'foreign_owner';

export interface DesktopWorkerProbeItem {
  runtime: WorkerRuntime;
  available: boolean;
  resolved_path: string | null;
  detail: string;
}

export type DesktopBrowserPairingState =
  | 'unsupported'
  | 'not_paired'
  | 'paired'
  | 'verified'
  | 'reconnect';

export interface DesktopBrowserProfileItem {
  profile: string;
  extension_installed: boolean;
}

export interface DesktopBrowserStatus {
  supported: boolean;
  state: DesktopBrowserPairingState;
  chrome_installed: boolean;
  chrome_running: boolean;
  chrome_version_ok: boolean;
  paired_profile?: string;
  selected_profile: string;
  extension_installed: boolean;
  profiles: DesktopBrowserProfileItem[];
  last_checked_at?: string;
}

export type DesktopBrowserActionInput =
  | { action: 'status'; profile?: string }
  | { action: 'open-guide'; profile?: string; target?: 'auto' | 'store' | 'token' }
  | { action: 'pair'; profile?: string; token: string }
  | { action: 'disconnect' };

export interface DesktopBrowserActionResponse {
  browser: DesktopBrowserStatus;
  opened?: 'store' | 'token';
}

export interface DesktopLocalInspectResponse {
  ownership: DesktopLocalOwnership;
  node_id?: string;
  node_name: string;
  owner_id?: string;
  desktop_managed?: boolean;
  running?: boolean;
  ready?: boolean;
  connected?: boolean;
  pid?: number;
  runtime_pid?: number;
  active_tasks?: number;
  version?: string;
  autostart?: boolean;
  worker_runtime?: WorkerRuntime;
  workers?: DesktopWorkerProbeItem[];
  browser?: DesktopBrowserStatus;
  proxy?: DesktopProxySettings;
  tool_approval_model?: string | null;
  registered_models?: { name: string; display_name: string }[];
  environment?: { key: string; value: string }[];
  agents?: { agent_id: string; display_name: string; workspace_root: string }[];
  logs?: string[];
}

export interface DesktopLocalConfigInput {
  worker_runtime: WorkerRuntime;
  proxy: DesktopProxySettings;
  tool_approval_model: string | null;
  environment: { key: string; value: string }[];
  confirm_restart?: boolean;
}

export interface DesktopTrajectoryAuthorizeResponse {
  authorized: true;
  node_id: string;
  owner_id: string;
  node_epoch: number;
  auth_session_id: string;
}

export type DesktopUpdaterPhase =
  | 'idle'
  | 'checking'
  | 'up_to_date'
  | 'unpublished'
  | 'source_mode'
  | 'available'
  | 'preparing'
  | 'ready_to_switch'
  | 'waiting_for_tasks'
  | 'switching'
  | 'downloading_installer'
  | 'installer_ready'
  | 'failed';

export type DesktopUpdaterMode = 'hot_bundle' | 'installer';

export type DesktopUpdaterErrorCode =
  | 'network_unreachable'
  | 'verification_failed'
  | 'disk_or_unpack_failed'
  | 'switch_rolled_back';

export interface DesktopUpdaterTargetInfo {
  version: string;
  release_notes?: string | null;
  size_bytes?: number | null;
  macos_distribution?: MacDistribution | null;
}

export interface DesktopUpdaterProgress {
  downloaded_bytes: number;
  total_bytes: number | null;
  stage: 'downloading' | 'verifying' | 'unpacking';
}

export interface DesktopUpdaterSnapshot {
  current_version: string;
  platform: 'darwin-arm64' | 'win32-x64';
  auto_update: boolean;
  phase: DesktopUpdaterPhase;
  mode: DesktopUpdaterMode | null;
  target: DesktopUpdaterTargetInfo | null;
  progress: DesktopUpdaterProgress | null;
  active_tasks: number;
  just_updated_version: string | null;
  capsule_dismissed: boolean;
  active_ui_sha256: string | null;
  reload_generation: number;
  error_code: DesktopUpdaterErrorCode | null;
  last_checked_at: string | null;
}

export interface DesktopUpdaterPreferencesInput {
  auto_update: boolean;
}

export interface DesktopUpdaterDismissInput {
  kind: 'just_updated' | 'capsule';
}

/** Validate an HTTP(S) proxy URL and reject unsupported schemes such as socks://.
 *
 * Args:
 *   raw: User-supplied proxy URL string.
 * Returns:
 *   Normalized HTTP(S) URL string without trailing whitespace.
 */
export function validateDesktopProxyUrl(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) throw new Error('Proxy URL is required when proxy is enabled');
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error('Proxy URL must be a valid http:// or https:// address');
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('Only http:// and https:// proxies are supported; socks:// is not supported');
  }
  if (!parsed.hostname) {
    throw new Error('Proxy URL must include a hostname');
  }
  return trimmed;
}

/** Split `gateway.environment` into structured proxy settings and editable user variables.
 *
 * Args:
 *   environment: Raw `gateway.environment` map from `config.yaml`.
 * Returns:
 *   Structured proxy state and filtered non-internal user environment entries.
 */
export function extractDesktopProxySettings(environment?: Record<string, string>): {
  proxy: DesktopProxySettings;
  userEnvironment: { key: string; value: string }[];
} {
  const env = environment ?? {};
  const url = (
    env.HTTPS_PROXY ??
    env.HTTP_PROXY ??
    env.ALL_PROXY ??
    env.https_proxy ??
    env.http_proxy ??
    env.all_proxy ??
    ''
  ).trim();
  const noProxy = (env.NO_PROXY ?? env.no_proxy ?? DEFAULT_DESKTOP_NO_PROXY).trim();
  const enabled = env.NODE_USE_ENV_PROXY === '1' && url.length > 0;
  const userEnvironment = Object.entries(env)
    .filter(([key]) => !HIDDEN_KEY_SET.has(key))
    .map(([key, value]) => ({ key, value }));
  return {
    proxy: { enabled, url, no_proxy: noProxy },
    userEnvironment,
  };
}

/** Merge structured proxy settings and user environment rows back into `gateway.environment`.
 *
 * Args:
 *   existing: Existing `gateway.environment` from `config.yaml` (to preserve owner root).
 *   proxy: Structured HTTP(S) proxy configuration.
 *   userEnvironment: Editable non-proxy environment entries.
 * Returns:
 *   Canonical `gateway.environment` map ready for persistence.
 */
export function mergeDesktopEnvironment(
  existing: Record<string, string> | undefined,
  proxy: DesktopProxySettings,
  userEnvironment: readonly { key: string; value: string }[],
): Record<string, string> {
  const next: Record<string, string> = {};
  if (existing?.NANO_OWNER_CONFIG_ROOT) {
    next.NANO_OWNER_CONFIG_ROOT = existing.NANO_OWNER_CONFIG_ROOT;
  }
  const seen = new Set<string>();
  for (const row of userEnvironment) {
    const key = row.key.trim();
    if (!key) throw new Error('Environment variable name cannot be empty');
    if (key.includes('=') || key.includes('\0') || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) {
      throw new Error(`Invalid environment variable name: ${key}`);
    }
    if (HIDDEN_KEY_SET.has(key)) {
      throw new Error(`${key} is managed automatically and cannot be edited here`);
    }
    if (row.value.includes('\0')) {
      throw new Error(`Invalid value for environment variable ${key}`);
    }
    if (seen.has(key)) {
      throw new Error(`Duplicate environment variable name: ${key}`);
    }
    seen.add(key);
    next[key] = row.value;
  }
  if (proxy.enabled) {
    const normalizedUrl = validateDesktopProxyUrl(proxy.url);
    const noProxy = proxy.no_proxy.trim();
    if (noProxy.includes('\0')) throw new Error('Invalid NO_PROXY value');
    next.NODE_USE_ENV_PROXY = '1';
    next.HTTP_PROXY = normalizedUrl;
    next.http_proxy = normalizedUrl;
    next.HTTPS_PROXY = normalizedUrl;
    next.https_proxy = normalizedUrl;
    next.ALL_PROXY = normalizedUrl;
    next.all_proxy = normalizedUrl;
    if (noProxy) {
      next.NO_PROXY = noProxy;
      next.no_proxy = noProxy;
    }
  }
  return next;
}

/** Determine whether a workspace target must be restricted to folder reveal instead of direct open.
 *
 * Args:
 *   targetPath: Resolved or relative path inside an Agent workspace.
 * Returns:
 *   True when launching the path directly could execute code or an application bundle.
 */
export function isBlockedDesktopOpenPath(targetPath: string): boolean {
  const normalized = targetPath.toLowerCase();
  const segments = normalized.split(/[\\/]/).filter(Boolean);
  if (segments.some(segment => segment.endsWith('.app'))) return true;
  const leaf = segments.at(-1) ?? '';
  return DESKTOP_BLOCKED_OPEN_EXTENSIONS.some(ext => leaf.endsWith(ext));
}
