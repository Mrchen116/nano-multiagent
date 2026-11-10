import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { FsError, type FileSystem } from '@deepseek-ai/dsh-fs';

export const roleLimit = 2000;
const rolePlaceholder = '# Role agreement pending\n\nActively ask the user to clarify your long-term responsibilities, goals and any relevant division of work. Keep asking at suitable interactions until the user confirms the wording.\n';
export const rolePath = (workspace: string) => join(workspace, '.nanoassistant', 'ROLE.md');

type RoleView = { content: string; version: string | null };
type RoleError = { error: 'role_conflict' | 'role_unavailable' | 'role_too_long' };
export type RoleResult = RoleView | RoleError;

const visibleRole = (content: string) => content.trim() === rolePlaceholder.trim() || !content.trim() ? '' : content;
const token = (path: string, version: string) => createHash('sha256').update(path).update('\0').update(version).digest('hex');
const conflicted = (error: unknown) => error instanceof FsError && ['FS_STALE_VERSION', 'FS_NOT_OBSERVED'].includes(error.code);

/** Read or update the one role agreement in the trusted canonical workspace.
 *
 * Args:
 *   fs: The same native filesystem provider used by ordinary Agent file tools.
 *   workspace: Canonical workspace checked by the owning Node.
 *   update: The Markdown and version observed by the settings editor, if saving.
 *   initialize: Whether a bound main request may create a missing placeholder.
 */
export async function roleDocument(fs: FileSystem, workspace: string, update?: RoleView, initialize = false): Promise<RoleResult> {
  if (update && update.content.length > roleLimit) return { error: 'role_too_long' };
  const path = rolePath(workspace);
  try {
    const directory = await fs.lstat(dirname(path));
    const file = await fs.lstat(path);
    if (directory && directory.type !== 'directory' || file && file.type !== 'file') return { error: 'role_unavailable' };
    const target = await fs.resolve(path);
    if (fs.processPath(target) !== path) return { error: 'role_unavailable' };
    const info = await fs.stat(target);
    const version = info ? token(path, info.version) : null;
    if (update && update.version !== version) return { error: 'role_conflict' };
    if (update || initialize && !info) {
      const content = update?.content.trim() ? update.content : rolePlaceholder;
      try {
        const result = await fs.writeText(target, content, info ? { kind: 'replaceIfVersion', version: info.version } : { kind: 'createIfAbsent' },
          undefined, fs.sandboxMode ? { mode: fs.sandboxMode, workspaceRoot: workspace } : undefined);
        return { content: visibleRole(result.after), version: token(path, result.version) };
      } catch (error) {
        if (!conflicted(error)) throw error;
        return update ? { error: 'role_conflict' } : roleDocument(fs, workspace);
      }
    }
    return { content: info ? visibleRole(await fs.readText(target)) : '', version };
  } catch {
    return { error: 'role_unavailable' };
  }
}
