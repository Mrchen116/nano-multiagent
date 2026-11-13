import { realpath as callbackRealpath } from 'node:fs';
import { lstat, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { promisify } from 'node:util';
import { dirname, basename, isAbsolute, join, relative, resolve, sep } from 'node:path';
import type { ApprovalConfiguration } from '@nano/product-contracts';

const directories = new Set(['.git', '.vscode', '.idea', '.claude', '.nano', '.nano-assistant', '.nanocode', '.nanoassistant', '.codex']);
const codexProtectedDirectories = new Set(['.agents', '.aws', '.ssh']);
const files = ['.gitconfig', '.gitmodules', '.bashrc', '.bash_profile', '.zshrc', '.zprofile', '.profile', '.mcp.json', '.ripgreprc', 'AGENTS.md', 'CLAUDE.md'];
const codexProtectedFiles = files.map(file => file.toLowerCase());
const canonicalAlias = (path: string) => process.platform === 'darwin' && (path === '/var' || path.startsWith('/var/')) ? `/private${path}` : path;
const nativeRealpath = promisify(callbackRealpath.native);
function relativeFile(root: string, target: string): string | undefined {
  const path = relative(canonicalAlias(root), canonicalAlias(target));
  return path && path !== '..' && !path.startsWith(`..${sep}`) && !isAbsolute(path) ? path : undefined;
}
function ordinary(root: string, target: string, codex = false): boolean {
  const path = relativeFile(root, target);
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
 *   cwd: Actual execution workspace.
 *   name: Native tool name.
 *   args: Exact pending tool arguments.
 *   policy: Frozen approval configuration.
 */
export async function workspaceFileAllowed(cwd: string, name: string, args: unknown, policy: ApprovalConfiguration): Promise<boolean> {
  if (!policy.enabled || policy.rules !== 'nano' || !['write', 'edit'].includes(name)
    || [policy.allow, policy.softDeny, policy.hardDeny].some(rules => rules.some(rule => rule !== '$defaults'))) return false;
  const path = (args as { file_path?: unknown } | null)?.file_path;
  if (typeof path !== 'string' || !path.trim()) return false;
  const target = resolve(cwd, path);
  if (!ordinary(resolve(cwd), target)) return false;
  try { return ordinary(await realpath(cwd), await resolvedTarget(target)); }
  catch { return false; }
}

/** Check whether Codex Auto can admit an ordinary file operation without a model request.
 *
 * Args:
 *   cwd: Actual execution workspace.
 *   name: Native tool name.
 *   args: Exact pending tool arguments.
 *   policy: Active approval configuration.
 */
export async function codexFileAllowed(cwd: string, name: string, args: unknown, policy: ApprovalConfiguration): Promise<boolean> {
  if (!policy.enabled || policy.rules !== 'codex' || !['write', 'edit'].includes(name)
    || [policy.allow, policy.softDeny, policy.hardDeny, policy.environment].some(rules => rules.some(rule => rule !== '$defaults'))) return false;
  const { file_path: path, sandbox_permissions } = (args ?? {}) as { file_path?: unknown; sandbox_permissions?: unknown };
  // Native POSIX resolution preserves physical parent traversal before realpath.
  if (typeof path !== 'string' || !path.trim() || path.split(/[\\/]/).includes('..') || sandbox_permissions !== undefined) return false;
  const target = resolve(cwd, path);
  const roots = new Set([resolve(cwd), resolve(tmpdir()), ...(process.platform === 'win32' ? [] : ['/tmp'])]);
  try {
    const realTarget = await resolvedTarget(target, nativeRealpath);
    const existing = await lstat(realTarget).catch((error: NodeJS.ErrnoException) => {
      if (error.code === 'ENOENT') return undefined;
      throw error;
    });
    if (existing && !existing.isFile()) return false;
    let allowed = false;
    for (const root of roots) {
      const realRoot = await nativeRealpath(root).catch(() => undefined);
      if (!realRoot) continue;
      const spelledRoot = relativeFile(root, target) ? root : realRoot;
      const lexicalMatch = relativeFile(spelledRoot, target);
      const realMatch = relativeFile(realRoot, realTarget);
      // A narrower workspace root cannot hide a protected component under a temporary root.
      if ((lexicalMatch && !ordinary(spelledRoot, target, true)) || (realMatch && !ordinary(realRoot, realTarget, true))) return false;
      allowed ||= Boolean(lexicalMatch && realMatch);
    }
    return allowed;
  } catch {
    return false;
  }
}
