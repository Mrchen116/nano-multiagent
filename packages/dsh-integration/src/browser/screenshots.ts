import { lstat, mkdir, readdir, realpath, rm, stat, writeFile } from 'node:fs/promises';
import { basename, join, relative, resolve, sep } from 'node:path';

export const SCREENSHOT_TTL_MS = 60 * 60 * 1000;
export const SCREENSHOT_LIMIT = 20;
const FILE_PATTERN = /^screen-[A-Za-z0-9._-]+\.png$/;
const READ_LIMIT = 5_000;
const DIRECTORY_LIMIT = 200;

export interface ScreenshotSaved {
  path: string;
  width: number;
  height: number;
}

export interface ScreenshotOmitted {
  omitted: 'outside_workspace' | 'write_failed';
}

export interface ScreenshotStoreOptions {
  ttlMs?: number;
  limit?: number;
  now?: () => number;
}

/** Resolve a screenshot target and prove it stays under the Agent's own root. */
export function resolveScreenshotPath(workspace: string, agentId: string, name: string): { root: string; target: string } | undefined {
  if (!agentId || agentId.includes('/') || agentId.includes('\\') || agentId.includes('..') || name.includes('/') || name.includes('\\') || name.includes('..')) return undefined;
  const root = resolve(workspace, '.nanoassistant', 'browser', agentId);
  const target = resolve(root, name);
  const prefix = root.endsWith(sep) ? root : `${root}${sep}`;
  return target.startsWith(prefix) ? { root, target } : undefined;
}

/** Resolve only real directories below the configured workspace; never follow a child symlink. */
async function safeScreenshotRoot(workspace: string, agentId: string, create: boolean): Promise<string | undefined> {
  let current = await realpath(workspace);
  for (const part of ['.nanoassistant', 'browser', agentId]) {
    current = join(current, part);
    if (create) {
      try { await mkdir(current); }
      catch (error) { if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error; }
    }
    const info = await lstat(current);
    if (info.isSymbolicLink() || !info.isDirectory()) return undefined;
  }
  return current;
}

/** Read the device-pixel dimensions from a PNG IHDR chunk. */
export function pngSize(png: Buffer): { width: number; height: number } {
  if (png.length >= 24 && png.toString('ascii', 12, 16) === 'IHDR') return { width: png.readUInt32BE(16), height: png.readUInt32BE(20) };
  return { width: 0, height: 0 };
}

/** Temporary page evidence with a TTL and per-Agent cap.
 *
 * Screenshots are never removed when an instance ends or its Agent is
 * disposed, because a real-window release happens before the model may still
 * call `read_image`; only the next write and the bounded startup sweep clean
 * this directory.
 */
export class ScreenshotStore {
  private readonly ttlMs: number;
  private readonly limit: number;
  private readonly now: () => number;

  constructor(options: ScreenshotStoreOptions = {}) {
    this.ttlMs = options.ttlMs ?? SCREENSHOT_TTL_MS;
    this.limit = options.limit ?? SCREENSHOT_LIMIT;
    this.now = options.now ?? Date.now;
  }

  /** Save a base64 viewport capture and prune this Agent's directory. */
  async save(input: { workspace?: string; agentId: string; base64: string; name?: string }): Promise<ScreenshotSaved | ScreenshotOmitted> {
    if (!input.workspace) return { omitted: 'outside_workspace' };
    const stamp = new Date(this.now()).toISOString().replace(/[:.]/g, '-');
    const name = input.name ?? `screen-${stamp}-${Math.random().toString(36).slice(2, 8)}.png`;
    const resolved = resolveScreenshotPath(input.workspace, input.agentId, name);
    if (!resolved) return { omitted: 'outside_workspace' };
    try {
      const payload = input.base64.replace(/^data:image\/png;base64,/, '');
      const png = Buffer.from(payload, 'base64');
      const root = await safeScreenshotRoot(input.workspace, input.agentId, true);
      if (!root) return { omitted: 'outside_workspace' };
      const target = join(root, name);
      // Exclusive creation cannot overwrite an existing file or follow a leaf symlink.
      await writeFile(target, png, { flag: 'wx', mode: 0o600 });
      await this.cleanup(root);
      const size = pngSize(png);
      return { path: relative(await realpath(input.workspace), target).split(sep).join('/'), ...size };
    } catch {
      return { omitted: 'write_failed' };
    }
  }

  /** Delete expired and over-cap files this capability wrote in one directory. */
  async cleanup(directory: string): Promise<number> {
    let entries;
    try { entries = await readdir(directory, { withFileTypes: true }); }
    catch { return 0; }
    const files: { name: string; mtime: number }[] = [];
    for (const entry of entries.slice(0, READ_LIMIT)) {
      if (!entry.isFile() || !FILE_PATTERN.test(entry.name)) continue;
      try { files.push({ name: entry.name, mtime: (await stat(join(directory, entry.name))).mtimeMs }); }
      catch { /* A file removed concurrently is already clean. */ }
    }
    const cutoff = this.now() - this.ttlMs;
    const expired = files.filter(file => file.mtime < cutoff);
    for (const file of expired) await rm(join(directory, file.name), { force: true });
    const remaining = files.filter(file => file.mtime >= cutoff).sort((a, b) => b.mtime - a.mtime || b.name.localeCompare(a.name));
    for (const file of remaining.slice(this.limit)) await rm(join(directory, file.name), { force: true });
    return expired.length + Math.max(0, remaining.length - this.limit);
  }

  /** One bounded startup pass over configured Agent workspaces only.
   *
   * It never walks the home directory or the repository, ignores missing or
   * unreadable directories, and reports failures to the caller instead of
   * blocking runtime startup.
   */
  async sweep(agents: readonly { agentId: string; workspace?: string }[], report?: (message: string) => void): Promise<number> {
    let removed = 0;
    for (const agent of agents.slice(0, DIRECTORY_LIMIT)) {
      if (!agent.workspace) continue;
      const resolved = resolveScreenshotPath(agent.workspace, agent.agentId, 'screen-probe.png');
      if (!resolved) continue;
      try {
        const root = await safeScreenshotRoot(agent.workspace, agent.agentId, false);
        if (root) removed += await this.cleanup(root);
      } catch (error) { report?.(`browser screenshot sweep skipped ${basename(resolved.root)}: ${(error as NodeJS.ErrnoException).code ?? 'unavailable'}`); }
    }
    return removed;
  }
}
