/** Verified metadata selects one immutable public or explicitly trusted self-hosted package. */

export type OriginSecurityKind =
  | 'https'
  | 'loopback_http'
  | 'private_http'
  | 'rejected_public_http'
  | 'invalid';

export interface OriginSecurityClassification {
  kind: OriginSecurityKind;
  normalizedOrigin?: string;
}

function parseStrictIpv4Octets(hostname: string): [number, number, number, number] | null {
  if (!/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname)) return null;
  const parts = hostname.split('.');
  if (parts.length !== 4) return null;
  const nums: number[] = [];
  for (const part of parts) {
    if (!/^(0|[1-9]\d*)$/.test(part)) return null;
    const val = Number(part);
    if (!Number.isInteger(val) || val < 0 || val > 255) return null;
    nums.push(val);
  }
  return [nums[0]!, nums[1]!, nums[2]!, nums[3]!];
}

function classifyBracketedIpv6(hostname: string): 'loopback_http' | 'private_http' | 'rejected_public_http' | null {
  if (!hostname.startsWith('[') || !hostname.endsWith(']')) return null;
  const inner = hostname.slice(1, -1).toLowerCase();
  if (inner === '::1' || inner === '0:0:0:0:0:0:0:1') return 'loopback_http';
  if (/^f[cd][0-9a-f]{0,2}:/.test(inner) || /^fe[89ab][0-9a-f]?:/.test(inner)) {
    return 'private_http';
  }
  return 'rejected_public_http';
}

/** Classify an HTTP(S) origin using strict IP literal parsing and reserved-domain protection.
 *
 * Official `crewden.work` / `*.crewden.work` and public hosts always reject cleartext `http://`.
 *
 * Args:
 *   rawUrl: Candidate origin or URL string.
 * Returns:
 *   Security classification and normalized `scheme://host[:port]` origin when valid.
 */
export function classifyOriginSecurity(rawUrl: string): OriginSecurityClassification {
  const trimmed = rawUrl.trim();
  if (!trimmed) return { kind: 'invalid' };
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { kind: 'invalid' };
  }
  if ((parsed.protocol !== 'https:' && parsed.protocol !== 'http:') || !parsed.hostname || parsed.username || parsed.password) {
    return { kind: 'invalid' };
  }
  const host = parsed.hostname.toLowerCase();
  const isOfficialDomain = host === 'crewden.work' || host.endsWith('.crewden.work');
  if (parsed.protocol === 'https:') {
    return { kind: 'https', normalizedOrigin: parsed.origin };
  }
  if (isOfficialDomain) {
    return { kind: 'rejected_public_http', normalizedOrigin: parsed.origin };
  }
  if (host === 'localhost' || host === '::1') {
    return { kind: 'loopback_http', normalizedOrigin: parsed.origin };
  }
  const ipv6Kind = classifyBracketedIpv6(host);
  if (ipv6Kind) {
    return { kind: ipv6Kind, normalizedOrigin: parsed.origin };
  }
  const ipv4 = parseStrictIpv4Octets(host);
  if (ipv4) {
    if (ipv4[0] === 127) {
      return { kind: 'loopback_http', normalizedOrigin: parsed.origin };
    }
    if (
      ipv4[0] === 10 ||
      (ipv4[0] === 172 && ipv4[1] >= 16 && ipv4[1] <= 31) ||
      (ipv4[0] === 192 && ipv4[1] === 168)
    ) {
      return { kind: 'private_http', normalizedOrigin: parsed.origin };
    }
    return { kind: 'rejected_public_http', normalizedOrigin: parsed.origin };
  }
  if (host.endsWith('.local') && host.length > '.local'.length && !host.startsWith('.')) {
    return { kind: 'private_http', normalizedOrigin: parsed.origin };
  }
  return { kind: 'rejected_public_http', normalizedOrigin: parsed.origin };
}

/** Normalize and validate a self-hosted release base URL prefix ending with `/`.
 *
 * Args:
 *   rawBaseUrl: Candidate base URL prefix.
 *   allowPrivateHttp: Whether RFC1918/RFC4193/`.local` cleartext `http://` bases are permitted.
 * Returns:
 *   Canonical trailing-slash base URL, or `null` when disallowed.
 */
export function normalizeReleaseBaseUrl(rawBaseUrl: string, allowPrivateHttp = false): string | null {
  const trimmed = rawBaseUrl.trim();
  if (!trimmed) return null;
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) return null;
  const security = classifyOriginSecurity(parsed.origin);
  const allowed =
    security.kind === 'https' ||
    security.kind === 'loopback_http' ||
    (allowPrivateHttp && security.kind === 'private_http');
  if (!allowed || !security.normalizedOrigin) return null;
  const cleanPath = parsed.pathname.replace(/\/+$/, '');
  return `${security.normalizedOrigin}${cleanPath}/`;
}

interface ReleaseMetadata {
  version: string;
  source_commit?: string;
  sha256: string;
  download_url: string;
  release_base_url?: string;
  node_major: 24;
  pnpm_version: '11.7.0';
  updater_protocol?: number;
  data_epoch?: number;
  release_notes?: string;
}

export interface PlatformInstaller {
  download_url: string;
  sha256: string;
  size: number;
}

export type DesktopPlatform = 'desktop-darwin-arm64' | 'desktop-win32-x64';

export type MacDistribution = 'unsigned-test' | 'unnotarized' | 'developer-id-notarized';

/** Current Desktop Tauri outer shell protocol supported for in-app split-archive hot updates. */
export const CURRENT_DESKTOP_SHELL_PROTOCOL = 2;

export type ReleaseManifest = ReleaseMetadata & (
  | {package: 'nano-node.tgz'; platform?: undefined; shell_protocol?: undefined}
  | {package: 'windows-x64.json'; platform: 'win32-x64'; size: number; installer: PlatformInstaller; shell_protocol?: undefined}
  | {package: 'desktop-darwin-arm64.json'; platform: 'desktop-darwin-arm64'; macos_distribution?: MacDistribution; size: number; shell_protocol: number; installer: PlatformInstaller}
  | {package: 'desktop-win32-x64.json'; platform: 'desktop-win32-x64'; size: number; shell_protocol: number; installer: PlatformInstaller}
);

export interface ParseReleaseManifestOptions {
  /** Explicitly trusted self-hosted release base URL prefix(es) configured by this deployment or seed install. */
  trustedReleaseBaseUrls?: readonly string[];
  /** Allow private-network HTTP in `trustedReleaseBaseUrls` when private HTTP mode is enabled. */
  allowPrivateHttpReleaseBase?: boolean;
}

const PLATFORM_PACKAGES: Record<string, {platform: 'win32-x64' | DesktopPlatform; installer: string; desktop: boolean}> = {
  'windows-x64.json': {platform: 'win32-x64', installer: 'Crewden-Setup-x64.exe', desktop: false},
  'desktop-darwin-arm64.json': {platform: 'desktop-darwin-arm64', installer: 'Crewden-Desktop-arm64.dmg', desktop: true},
  'desktop-win32-x64.json': {platform: 'desktop-win32-x64', installer: 'Crewden-Desktop-Setup-x64.exe', desktop: true},
};

function validPositiveInt(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1;
}

function validSize(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

/** Validate the same fixed asset identity for installation and later updates.
 *
 * Args:
 *   input: Untrusted manifest JSON.
 *   options: Optional trusted self-hosted release base configuration.
 * Returns:
 *   Validated metadata, or null when the package identity is inconsistent.
 */
export function parseReleaseManifest(input: unknown, options?: ParseReleaseManifestOptions): ReleaseManifest | null {
  if (!input || typeof input !== 'object') return null;
  const v = input as Record<string, unknown>;
  if (typeof v.version !== 'string' || typeof v.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(v.sha256)) return null;
  const sha = /^[a-f0-9]{40}$/;
  const tag = sha.test(v.version) ? `node-${v.version}`
    : /^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/.test(v.version)
      && typeof v.source_commit === 'string' && sha.test(v.source_commit) ? `v${v.version}` : null;
  if (!tag || v.node_major !== 24 || v.pnpm_version !== '11.7.0'
    || v.source_commit !== undefined && (typeof v.source_commit !== 'string' || !sha.test(v.source_commit))
    || v.updater_protocol !== undefined && (!Number.isInteger(v.updater_protocol) || Number(v.updater_protocol) < 1)
    || v.data_epoch !== undefined && (!Number.isInteger(v.data_epoch) || Number(v.data_epoch) < 1)
    || v.shell_protocol !== undefined && (!Number.isInteger(v.shell_protocol) || Number(v.shell_protocol) < 1)
    || v.release_notes !== undefined && (typeof v.release_notes !== 'string' || v.release_notes.length > 2000)) return null;

  const allowPrivateHttp = Boolean(options?.allowPrivateHttpReleaseBase);
  let base = `https://github.com/Mrchen116/nano-multiagent/releases/download/${tag}/`;
  let normalizedReleaseBaseUrl: string | undefined;
  if (v.release_base_url !== undefined) {
    if (typeof v.release_base_url !== 'string') return null;
    const candidateBase = normalizeReleaseBaseUrl(v.release_base_url, allowPrivateHttp);
    if (!candidateBase) return null;
    const trustedList = (options?.trustedReleaseBaseUrls ?? [])
      .map(item => normalizeReleaseBaseUrl(item, allowPrivateHttp))
      .filter((item): item is string => item !== null);
    // A manifest may either match the exact configured base or `<trustedBase><tag>/`.
    const matched = trustedList.some(trusted => candidateBase === trusted || candidateBase === `${trusted}${tag}/`);
    if (!matched) return null;
    base = candidateBase;
    normalizedReleaseBaseUrl = candidateBase;
  }

  if (typeof v.package !== 'string' || v.download_url !== base + v.package) return null;
  const common: ReleaseMetadata = {version: v.version, sha256: v.sha256, node_major: 24, pnpm_version: '11.7.0',
    download_url: v.download_url,
    ...(normalizedReleaseBaseUrl === undefined ? {} : { release_base_url: normalizedReleaseBaseUrl }),
    ...(v.source_commit === undefined ? {} : { source_commit: v.source_commit as string }),
    ...(v.updater_protocol === undefined ? {} : { updater_protocol: v.updater_protocol as number }),
    ...(v.data_epoch === undefined ? {} : { data_epoch: v.data_epoch as number }),
    ...(v.release_notes === undefined ? {} : { release_notes: v.release_notes as string }),
  };
  if (v.package === 'nano-node.tgz' && v.platform === undefined && v.shell_protocol === undefined) {
    return {...common, package: v.package};
  }
  const spec = PLATFORM_PACKAGES[v.package];
  if (!spec || v.platform !== spec.platform || !validSize(v.size)
    || v.source_commit === undefined || (sha.test(v.version) && v.source_commit !== v.version)) return null;
  if (spec.desktop) {
    if (!validPositiveInt(v.updater_protocol) || !validPositiveInt(v.data_epoch) || !validPositiveInt(v.shell_protocol)) return null;
  } else if (v.updater_protocol !== 1 || v.data_epoch !== 1 || v.shell_protocol !== undefined) {
    return null;
  }
  const installer = v.installer as Partial<PlatformInstaller> | null;
  if (!installer || installer.download_url !== base + spec.installer
    || typeof installer.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(installer.sha256) || !validSize(installer.size)) return null;
  const parsedInstaller: PlatformInstaller = {download_url: installer.download_url, size: installer.size, sha256: installer.sha256};
  if (v.package === 'windows-x64.json') {
    return {...common, package: 'windows-x64.json', platform: 'win32-x64', size: v.size, installer: parsedInstaller};
  }
  const shellProtocol = v.shell_protocol as number;
  if (v.package === 'desktop-darwin-arm64.json') {
    const mode = v.macos_distribution;
    if (mode !== undefined && mode !== 'unsigned-test' && mode !== 'unnotarized' && mode !== 'developer-id-notarized') return null;
    return {...common, ...(mode === undefined ? {} : {macos_distribution: mode}), package: 'desktop-darwin-arm64.json', platform: 'desktop-darwin-arm64', size: v.size, shell_protocol: shellProtocol, installer: parsedInstaller};
  }
  return {...common, package: 'desktop-win32-x64.json', platform: 'desktop-win32-x64', size: v.size, shell_protocol: shellProtocol, installer: parsedInstaller};
}

export interface NodeRelease {
  platform?: string;
  kind: 'managed' | 'source';
  version: string;
  source_commit?: string;
  sha256?: string;
  updater_protocol?: number;
  data_epoch?: number;
  shell_protocol?: number;
}
export type NodeUpdateState = 'requested' | 'downloading' | 'installing' | 'waiting' | 'switching' | 'verifying'
  | 'succeeded' | 'cancelled' | 'failed' | 'rolling_back' | 'rolled_back' | 'interrupted' | 'recovery_required';
export const nodeUpdateTerminal = (state: NodeUpdateState) =>
  ['succeeded', 'cancelled', 'failed', 'rolled_back', 'interrupted', 'recovery_required'].includes(state);
export const nodeUpdateCancellable = (state: NodeUpdateState) =>
  ['requested', 'downloading', 'installing', 'waiting'].includes(state);
export interface NodeUpdateOperation {
  id: string;
  request_id: string;
  node_id: string;
  owner_id: string;
  node_epoch: number;
  target: ReleaseManifest;
  state: NodeUpdateState;
  cancel_requested: boolean;
  relay_gated: boolean;
  updated_at: string;
  error_code?: string;
}
export interface NodeUpdateView {
  installation: 'managed' | 'legacy' | 'source';
  current: NodeRelease | null;
  target: ReleaseManifest | null;
  available: boolean;
  reason: 'available' | 'current' | 'offline' | 'legacy' | 'source' | 'unpublished' | 'incompatible' | 'active' | 'recovery_required';
  operation: NodeUpdateOperation | null;
  install_command: string;
}
/** Reply from the runtime-authenticated updater endpoint, including registration evidence. */
export interface NodeUpdateReport {
  operation: NodeUpdateOperation;
  registered: { online: boolean; release: NodeRelease | null };
}
