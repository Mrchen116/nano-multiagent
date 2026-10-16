import { lstat, realpath } from 'node:fs/promises';
import { dirname, basename, join, relative, resolve, sep } from 'node:path';
import type { ApprovalConfiguration } from '@nano/product-contracts';

const directories = new Set(['.git', '.vscode', '.idea', '.claude', '.nano', '.nano-assistant', '.nanocode', '.nanoassistant', '.codex']);
const files = ['.gitconfig', '.gitmodules', '.bashrc', '.bash_profile', '.zshrc', '.zprofile', '.profile', '.mcp.json', '.ripgreprc', 'AGENTS.md', 'CLAUDE.md'];
const canonicalAlias = (path: string) => process.platform === 'darwin' && (path === '/var' || path.startsWith('/var/')) ? `/private${path}` : path;
function ordinary(root: string, target: string): boolean {
  const path = relative(canonicalAlias(root), canonicalAlias(target));
  if (!path || path === '..' || path.startsWith(`..${sep}`) || path.startsWith(sep)) return false;
  const parts = path.split(sep);
  return !parts.some((part, index) => files.some(file => part === file || part.startsWith(`${file}.`))
    || directories.has(part) && !(part === '.claude' && parts[index + 1] === 'worktrees' && index + 2 < parts.length));
}
async function resolvedTarget(path: string): Promise<string> {
  try { return await realpath(path); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT' || dirname(path) === path) throw error;
    // A dangling symlink exists even though realpath reports ENOENT; it is not a new leaf.
    const existing = await lstat(path).catch(error => { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return undefined; throw error; });
    if (existing) throw error;
    return join(await resolvedTarget(dirname(path)), basename(path));
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
