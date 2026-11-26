import { realpath as callbackRealpath } from 'node:fs';
import { lstat, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { promisify } from 'node:util';
import { dirname, basename, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { parsePatch } from '@deepseek-ai/dsh-fs-patch';
import type { ApprovalConfiguration } from '@nano/product-contracts';

export type WorkspaceLocation = string | { workspaceRoot: string; effectiveCwd?: string };

const directories = new Set(['.git', '.vscode', '.idea', '.claude', '.nano', '.nano-assistant', '.nanocode', '.nanoassistant', '.codex']);
const codexProtectedDirectories = new Set(['.agents', '.aws', '.ssh']);
const files = ['.gitconfig', '.gitmodules', '.bashrc', '.bash_profile', '.zshrc', '.zprofile', '.profile', '.mcp.json', '.ripgreprc', 'AGENTS.md', 'CLAUDE.md'];
const codexProtectedFiles = files.map(file => file.toLowerCase());
const canonicalAlias = (path: string) => process.platform === 'darwin' && (path === '/var' || path.startsWith('/var/')) ? `/private${path}` : path;
const nativeRealpath = promisify(callbackRealpath.native);

function normalizeLocation(cwd: WorkspaceLocation): { workspaceRoot: string; effectiveCwd: string } {
  return typeof cwd === 'string'
    ? { workspaceRoot: cwd, effectiveCwd: cwd }
    : { workspaceRoot: cwd.workspaceRoot, effectiveCwd: cwd.effectiveCwd || cwd.workspaceRoot };
}

function extractTargetPaths(name: string, args: unknown): { paths: string[]; sandboxPermissions: unknown } | undefined {
  const record = (args ?? {}) as { file_path?: unknown; input?: unknown; sandbox_permissions?: unknown };
  if (name === 'write' || name === 'edit') {
    if (typeof record.file_path !== 'string' || !record.file_path.trim()) return undefined;
    return { paths: [record.file_path], sandboxPermissions: record.sandbox_permissions };
  }
  if (name === 'apply_patch') {
    if (typeof record.input !== 'string' || !record.input.trim()) return undefined;
    try {
      const operations = parsePatch(record.input);
      if (!operations.length) return undefined;
      const paths: string[] = [];
      for (const operation of operations) {
        if (!operation.path.trim()) return undefined;
        paths.push(operation.path);
        if (operation.kind === 'update' && operation.moveTo !== undefined) {
          if (!operation.moveTo.trim()) return undefined;
          paths.push(operation.moveTo);
        }
      }
      return { paths, sandboxPermissions: record.sandbox_permissions };
    } catch {
      return undefined;
    }
  }
  return undefined;
}

function relativeFile(root: string, target: string, codex = true): string | undefined {
  const path = relative(canonicalAlias(root), canonicalAlias(target));
  return path && path !== '..' && !path.startsWith(`..${sep}`) && !(codex ? isAbsolute(path) : path.startsWith(sep)) ? path : undefined;
}
function ordinary(root: string, target: string, codex = false): boolean {
  const path = relativeFile(root, target, codex);
  if (!path) return false;
  const parts = (codex ? path.toLowerCase() : path).split(sep);
  const protectedFiles = codex ? codexProtectedFiles : files;
  return !parts.some((part, index) => protectedFiles.some(name => part === name || part.startsWith(`${name}.`))
    || codex && codexProtectedDirectories.has(part)
    || directories.has(part) && !(part === '.claude' && parts[index + 1] === 'worktrees' && index + 2 < parts.length));
}
async function resolvedTarget(path: string, resolveReal: (path: string) => Promise<string> = realpath): Promise<string> {
  try { return await resolveReal(path); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT' || dirname(path) === path) throw error;
    // A dangling symlink exists even though realpath reports ENOENT; it is not a new leaf.
    const existing = await lstat(path).catch(error => { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined; throw error; });
    if (existing) throw error;
    return join(await resolvedTarget(dirname(path), resolveReal), basename(path));
  }
}

/** Authorize only ordinary workspace file operations; failures fall through to CC review.
 *
 * Args:
 *   cwd: Immutable workspace boundary root, with optional effective working directory for relative paths.
 *   name: Native tool name.
 *   args: Exact pending tool arguments.
 *   policy: Frozen approval configuration.
 */
export async function workspaceFileAllowed(cwd: WorkspaceLocation, name: string, args: unknown, policy: ApprovalConfiguration): Promise<boolean> {
  if (!policy.enabled || policy.rules !== 'nano' || !['write', 'edit', 'apply_patch'].includes(name)
    || [policy.allow, policy.softDeny, policy.hardDeny].some(rules => rules.some(rule => rule !== '$defaults'))) return false;
  const extracted = extractTargetPaths(name, args);
  if (!extracted || extracted.sandboxPermissions !== undefined) return false;
  const { workspaceRoot, effectiveCwd } = normalizeLocation(cwd);
  const resolvedRoot = resolve(workspaceRoot);
  try {
    const realRoot = await realpath(workspaceRoot);
    for (const rawPath of extracted.paths) {
      const target = resolve(effectiveCwd, rawPath);
      if (!ordinary(resolvedRoot, target)) return false;
      const existingLeaf = await lstat(target).catch((error: NodeJS.ErrnoException) => {
        if (error.code === 'ENOENT') return undefined;
        throw error;
      });
      if (existingLeaf && !existingLeaf.isFile()) return false;
      if (!ordinary(realRoot, await resolvedTarget(target))) return false;
    }
    return true;
  } catch {
    return false;
  }
}

/** Check whether Codex Auto can admit an ordinary file operation without a model request.
 *
 * Args:
 *   cwd: Immutable workspace boundary root, with optional effective working directory for relative paths.
 *   name: Native tool name.
 *   args: Exact pending tool arguments.
 *   policy: Active approval configuration.
 */
export async function codexFileAllowed(cwd: WorkspaceLocation, name: string, args: unknown, policy: ApprovalConfiguration): Promise<boolean> {
  if (!policy.enabled || policy.rules !== 'codex' || !['write', 'edit', 'apply_patch'].includes(name)
    || [policy.allow, policy.softDeny, policy.hardDeny, policy.environment].some(rules => rules.some(rule => rule !== '$defaults'))) return false;
  const extracted = extractTargetPaths(name, args);
  // Native POSIX resolution preserves physical parent traversal before realpath.
  if (!extracted || extracted.sandboxPermissions !== undefined
    || extracted.paths.some(rawPath => rawPath.split(/[\\/]/).includes('..'))) return false;
  const { workspaceRoot, effectiveCwd } = normalizeLocation(cwd);
  const roots = new Set([resolve(workspaceRoot), resolve(tmpdir()), ...(process.platform === 'win32' ? [] : ['/tmp'])]);
  try {
    const resolvedRoots: Array<{ root: string; realRoot: string }> = [];
    for (const root of roots) {
      const realRoot = await nativeRealpath(root).catch(() => undefined);
      if (realRoot) resolvedRoots.push({ root, realRoot });
    }
    for (const rawPath of extracted.paths) {
      const target = resolve(effectiveCwd, rawPath);
      const existingLeaf = await lstat(target).catch((error: NodeJS.ErrnoException) => {
        if (error.code === 'ENOENT') return undefined;
        throw error;
      });
      if (existingLeaf && !existingLeaf.isFile()) return false;
      const realTarget = await resolvedTarget(target, nativeRealpath);
      const existing = await lstat(realTarget).catch((error: NodeJS.ErrnoException) => {
        if (error.code === 'ENOENT') return undefined;
        throw error;
      });
      if (existing && !existing.isFile()) return false;
      let allowed = false;
      for (const { root, realRoot } of resolvedRoots) {
        const spelledRoot = relativeFile(root, target) ? root : realRoot;
        const lexicalMatch = relativeFile(spelledRoot, target);
        const realMatch = relativeFile(realRoot, realTarget);
        // A narrower workspace root cannot hide a protected component under a temporary root.
        if ((lexicalMatch && !ordinary(spelledRoot, target, true)) || (realMatch && !ordinary(realRoot, realTarget, true))) return false;
        allowed ||= Boolean(lexicalMatch && realMatch);
      }
      if (!allowed) return false;
    }
    return true;
  } catch {
    return false;
  }
}
