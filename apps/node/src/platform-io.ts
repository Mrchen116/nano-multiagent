import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chmod, mkdir, open, readFile } from 'node:fs/promises';
import { dirname, join, posix, win32 } from 'node:path';
import { windowsHost } from './windows-platform.js';

export interface LocalNodeBridgeEndpointOptions {
  platform?: NodeJS.Platform;
  tmpdir?: string;
}

/** Compute the current-user local IPC endpoint path for a node configuration file.
 *
 * Byte-for-byte counterpart to `local_node_bridge_endpoint` in `apps/desktop/src/config.rs`,
 * verified across platforms by `src/IM/shared/local-ipc-endpoint-test-cases.json`.
 *
 * Args:
 *   configPath: Absolute path to the node's `config.yaml`.
 *   options: Optional platform/tmpdir overrides for deterministic cross-OS testing.
 * Returns:
 *   Windows Named Pipe path or POSIX Unix Domain Socket path (`<= 96` UTF-8 bytes or TMPDIR hash fallback).
 */
export function localNodeBridgeEndpoint(
  configPath: string,
  options: LocalNodeBridgeEndpointOptions = {},
): string {
  const platform = options.platform ?? process.platform;
  if (platform === 'win32') {
    const digest = createHash('sha256').update(configPath.toLowerCase()).digest('hex').slice(0, 24);
    return `\\\\.\\pipe\\crewden-desktop-node-${digest}`;
  }
  const digest = createHash('sha256').update(configPath).digest('hex').slice(0, 20);
  const usePosix = options.platform !== undefined || process.platform !== 'win32';
  const candidate = usePosix
    ? posix.join(posix.dirname(configPath), '.desktop-node.sock')
    : join(dirname(configPath), '.desktop-node.sock');
  // Unix domain sockets have a ~104 byte sun_path limit on macOS; fall back to TMPDIR when deep.
  if (Buffer.byteLength(candidate, 'utf8') <= 96) return candidate;
  const tmp = options.tmpdir ?? process.env.TMPDIR ?? '/tmp';
  return usePosix
    ? posix.join(tmp, `crewden-node-${digest}.sock`)
    : join(tmp, `crewden-node-${digest}.sock`);
}

/** Flush a parent directory entry after atomic rename on POSIX filesystems.
 *
 * Windows flushes metadata prior to rename and rejects `fsync` on directory handles.
 *
 * Args:
 *   dirPath: Directory path whose metadata entry should be durable.
 *   platform: Target platform (defaults to `process.platform`).
 */
export async function syncDirectoryIfSupported(
  dirPath: string,
  platform: NodeJS.Platform = process.platform,
): Promise<void> {
  if (platform === 'win32') return;
  const directory = await open(dirPath, 'r');
  try {
    await directory.sync();
  } finally {
    await directory.close();
  }
}

/** Create a user-private directory (`0700` on POSIX, current-user ACL on Windows).
 *
 * Args:
 *   dirPath: Target directory path.
 *   options: Optional platform or Windows ACL helper override for testing.
 */
export async function ensurePrivateDirectory(
  dirPath: string,
  options: {
    platform?: NodeJS.Platform;
    runWindowsHost?: (command: string, ...args: string[]) => Promise<string>;
  } = {},
): Promise<void> {
  const platform = options.platform ?? process.platform;
  await mkdir(dirPath, { recursive: true, mode: 0o700 });
  if (platform === 'win32') {
    await (options.runWindowsHost ?? windowsHost)('private-directory', dirPath);
    return;
  }
  await chmod(dirPath, 0o700).catch(() => {});
}

/** Check whether `target` resolves to `root` itself or a strict descendant of `root`.
 *
 * Applies case-insensitive boundary matching on Windows and case-sensitive matching on POSIX.
 *
 * Args:
 *   target: Resolved candidate path.
 *   root: Resolved workspace root path.
 *   platform: Target platform (defaults to `process.platform`).
 * Returns:
 *   True iff `target` cannot escape `root` via sibling-prefix confusion.
 */
export function isPathWithinRoot(
  target: string,
  root: string,
  platform: NodeJS.Platform = process.platform,
): boolean {
  if (platform === 'win32') {
    const normTarget = win32.resolve(target).toLowerCase();
    const normRoot = win32.resolve(root).toLowerCase();
    if (normTarget === normRoot) return true;
    const prefix = normRoot.endsWith('\\') ? normRoot : `${normRoot}\\`;
    return normTarget.startsWith(prefix);
  }
  const normTarget = posix.resolve(target);
  const normRoot = posix.resolve(root);
  if (normTarget === normRoot) return true;
  const prefix = normRoot === '/' ? '/' : `${normRoot}/`;
  return normTarget.startsWith(prefix);
}

/** Read a stable host boot epoch token across Windows, macOS, and Linux.
 *
 * Args:
 *   options: Optional platform and probe overrides for deterministic testing.
 * Returns:
 *   Trimmed boot epoch identifier for detecting host restarts across runs.
 */
export async function readMachineBootToken(
  options: {
    platform?: NodeJS.Platform;
    runWindowsHost?: (command: string, ...args: string[]) => Promise<string>;
    execDarwinBootTime?: () => string;
    readLinuxBootId?: () => Promise<string>;
  } = {},
): Promise<string> {
  const platform = options.platform ?? process.platform;
  if (platform === 'win32') {
    return (await (options.runWindowsHost ?? windowsHost)('boot')).trim();
  }
  if (platform === 'darwin') {
    const raw = options.execDarwinBootTime
      ? options.execDarwinBootTime()
      : execFileSync('/usr/sbin/sysctl', ['-n', 'kern.boottime'], { encoding: 'utf8' });
    return raw.trim();
  }
  const raw = options.readLinuxBootId
    ? await options.readLinuxBootId()
    : await readFile('/proc/sys/kernel/random/boot_id', 'utf8');
  return raw.trim();
}
