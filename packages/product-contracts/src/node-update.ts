/** Verified metadata selects one immutable public package; clients never supply URLs. */
interface ReleaseMetadata {
  version: string;
  source_commit?: string;
  sha256: string;
  download_url: string;
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

export type ReleaseManifest = ReleaseMetadata & (
  | {package: 'nano-node.tgz'; platform?: undefined; shell_protocol?: undefined}
  | {package: 'windows-x64.json'; platform: 'win32-x64'; size: number; installer: PlatformInstaller; shell_protocol?: undefined}
  | {package: 'desktop-darwin-arm64.json'; platform: 'desktop-darwin-arm64'; size: number; shell_protocol: 1; installer: PlatformInstaller}
  | {package: 'desktop-win32-x64.json'; platform: 'desktop-win32-x64'; size: number; shell_protocol: 1; installer: PlatformInstaller}
);

const PLATFORM_PACKAGES: Record<string, {platform: 'win32-x64' | DesktopPlatform; installer: string; shellProtocol?: 1}> = {
  'windows-x64.json': {platform: 'win32-x64', installer: 'Crewden-Setup-x64.exe'},
  'desktop-darwin-arm64.json': {platform: 'desktop-darwin-arm64', installer: 'Crewden-Desktop-arm64.dmg', shellProtocol: 1},
  'desktop-win32-x64.json': {platform: 'desktop-win32-x64', installer: 'Crewden-Desktop-Setup-x64.exe', shellProtocol: 1},
};

function validSize(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

/** Validate the same fixed asset identity for installation and later updates.
 *
 * Args:
 *   input: Untrusted manifest JSON.
 * Returns:
 *   Validated metadata, or null when the package identity is inconsistent.
 */
export function parseReleaseManifest(input: unknown): ReleaseManifest | null {
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
  const base = `https://github.com/Mrchen116/nano-multiagent/releases/download/${tag}/`;
  if (typeof v.package !== 'string' || v.download_url !== base + v.package) return null;
  const common: ReleaseMetadata = {version: v.version, sha256: v.sha256, node_major: 24, pnpm_version: '11.7.0',
    download_url: v.download_url,
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
    || v.source_commit === undefined || (sha.test(v.version) && v.source_commit !== v.version)
    || v.updater_protocol !== 1 || v.data_epoch !== 1) return null;
  if (spec.shellProtocol !== undefined ? v.shell_protocol !== spec.shellProtocol : v.shell_protocol !== undefined) return null;
  const installer = v.installer as Partial<PlatformInstaller> | null;
  if (!installer || installer.download_url !== base + spec.installer
    || typeof installer.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(installer.sha256) || !validSize(installer.size)) return null;
  const parsedInstaller: PlatformInstaller = {download_url: installer.download_url, size: installer.size, sha256: installer.sha256};
  if (v.package === 'windows-x64.json') {
    return {...common, package: 'windows-x64.json', platform: 'win32-x64', size: v.size, installer: parsedInstaller};
  }
  if (v.package === 'desktop-darwin-arm64.json') {
    return {...common, package: 'desktop-darwin-arm64.json', platform: 'desktop-darwin-arm64', size: v.size, shell_protocol: 1, installer: parsedInstaller};
  }
  return {...common, package: 'desktop-win32-x64.json', platform: 'desktop-win32-x64', size: v.size, shell_protocol: 1, installer: parsedInstaller};
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
