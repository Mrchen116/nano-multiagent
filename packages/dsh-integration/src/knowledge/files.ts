import { mkdir, readFile, writeFile, rename, rm, lstat } from 'node:fs/promises';
import { dirname, join, resolve, relative, isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import lockfile from 'proper-lockfile';
import { load } from 'js-yaml';
import { isSkillName } from '@deepseek-ai/dsh-skill';

export interface MemoryChange { action: 'add' | 'replace' | 'remove'; target: 'memory' | 'user'; content?: string; old_text?: string }
export interface SkillChange { action: 'create' | 'edit' | 'patch' | 'write_file' | 'remove_file'; name: string; scope?: 'agent' | 'global'; content?: string; old_string?: string; new_string?: string; file_path?: string; file_content?: string }
interface Usage { source: string; state: string; use_count: number; uses_since_last_B: number; created_at: string; last_used_at: string | null; archived_at: string | null; recent_call_keys: string[]; session_refs: { session_id: string; tool_call_id: string; timestamp: string; location: string }[]; archive_error?: string | null }
const memoryLimits = { memory: 2200, user: 1375 };
const delimiter = '\n§\n';
const auto = new Set(['F3', 'F4']);
const emptyUsage = (source: string, now: string): Usage => ({ source, state: 'active', use_count: 0, uses_since_last_B: 0, created_at: now, last_used_at: null, archived_at: null, recent_call_keys: [], session_refs: [] });

export async function readText(path: string): Promise<string> {
  try { return await readFile(path, 'utf8'); } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return ''; throw error; }
}
async function readJson<T>(path: string, initial: T): Promise<T> { const text = await readText(path); return text ? JSON.parse(text) as T : initial; }
/** Same-filesystem rename commits complete assets; cancellation precedes the commit. */
export async function atomicWrite(path: string, text: string, signal?: AbortSignal) {
  await mkdir(dirname(path), { recursive: true }); const temporary = `${path}.${randomUUID()}.tmp`;
  try { await writeFile(temporary, text); signal?.throwIfAborted(); await rename(temporary, path); }
  finally { await rm(temporary, { force: true }); }
}
async function locked<T>(root: string, action: () => Promise<T>, signal?: AbortSignal): Promise<T> {
  await mkdir(root, { recursive: true });
  const release = await lockfile.lock(root, { retries: { retries: 30, minTimeout: 20, maxTimeout: 200, factor: 1.2 } });
  try { signal?.throwIfAborted(); return await action(); } finally { await release(); }
}
async function safePath(root: string, path: string) {
  const rel = relative(resolve(root), resolve(path));
  if (rel.startsWith('..') || isAbsolute(rel)) throw new Error('Path leaves the controlled root');
  let current = resolve(root);
  for (const part of ['', ...rel.split('/')]) {
    current = join(current, part);
    try { if ((await lstat(current)).isSymbolicLink()) throw new Error('Knowledge writes cannot follow symlinks'); }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  }
}

/** Existing memory and Skill assets remain authoritative; no second content database. */
export class KnowledgeFiles {
  readonly memoryRoot: string;
  readonly skillRoot: string;
  constructor(readonly workspace: string, readonly globalSkillRoot?: string) {
    this.memoryRoot = join(workspace, '.nanoassistant', 'memory'); this.skillRoot = join(workspace, '.nanoassistant', 'skills');
  }
  memoryText(target: 'memory' | 'user') { return readText(join(this.memoryRoot, target === 'memory' ? 'MEMORY.md' : 'USER.md')); }
  async memory(change: MemoryChange, sessionId: string, signal?: AbortSignal) {
    if (!(change.target in memoryLimits)) throw new Error('Unknown memory target');
    await safePath(this.workspace, this.memoryRoot);
    return locked(this.memoryRoot, async () => {
      const entries = (await this.memoryText(change.target)).split(delimiter).map(value => value.trim()).filter(Boolean);
      const content = change.content?.trim();
      if (change.action !== 'remove' && !content) throw new Error('Memory content is required');
      const entry = `${content}\n<!-- source: ${JSON.stringify({ session_id: sessionId, timestamp: Date.now() / 1000 })} -->`;
      if (change.action === 'add') entries.push(entry);
      else if (change.action === 'replace' || change.action === 'remove') {
        const index = change.old_text ? entries.findIndex(value => value.split('<!-- source:')[0]!.includes(change.old_text!)) : -1;
        if (index < 0) throw new Error('Memory entry not found');
        if (change.action === 'replace') entries[index] = entry; else entries.splice(index, 1);
      } else throw new Error('Unknown memory action');
      const text = entries.join(delimiter);
      if ([...text].length > memoryLimits[change.target]) throw new Error('Memory character limit exceeded; compact existing entries first');
      const path = join(this.memoryRoot, change.target === 'memory' ? 'MEMORY.md' : 'USER.md'); await safePath(this.memoryRoot, path);
      await atomicWrite(path, text, signal); return { success: true, target: change.target, action: change.action, path };
    }, signal);
  }
  async skill(change: SkillChange, source: string, signal?: AbortSignal) {
    if (!isSkillName(change.name) || change.name.length > 64) throw new Error('Invalid native Skill name');
    const root = change.scope === 'global' ? this.globalSkillRoot : this.skillRoot;
    if (!root) throw new Error('Global Skill root is unavailable');
    await safePath(change.scope === 'global' ? root : this.workspace, root);
    return locked(root, async () => {
      const directory = join(root, change.name); const main = join(directory, 'SKILL.md'); await safePath(root, main);
      const existing = await readText(main); let path = main; let content = change.content;
      if (change.action === 'create' && existing) throw new Error('Skill already exists');
      if (change.action !== 'create' && !existing) throw new Error('Skill does not exist in the selected writable scope');
      if (change.action === 'patch') {
        if (!change.old_string || !existing.includes(change.old_string) || existing.indexOf(change.old_string) !== existing.lastIndexOf(change.old_string)) throw new Error('Skill patch must match exactly once');
        content = existing.replace(change.old_string, () => change.new_string ?? '');
      }
      if (change.action === 'write_file' || change.action === 'remove_file') {
        if (!change.file_path || !/^(references|templates|scripts|assets)\//.test(change.file_path) || change.file_path.split('/').includes('..')) throw new Error('Invalid Skill support-file path');
        path = join(directory, change.file_path); await safePath(root, path); content = change.file_content;
        if (change.action === 'remove_file') { signal?.throwIfAborted(); await rm(path); }
      } else {
        if (!content || [...content].length > 100_000) throw new Error('Skill content is missing or exceeds its limit');
        const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n)([\s\S]*)$/.exec(content);
        const metadata = match && load(match[1]!) as { name?: unknown; description?: unknown } | null;
        if (!match?.[2]?.trim() || metadata?.name !== change.name || typeof metadata?.description !== 'string' || !metadata.description.trim() || metadata.description.length > 1024) throw new Error('Skill needs matching name, description and instructions');
      }
      if (change.action !== 'remove_file') {
        if (content === undefined || [...content].length > 100_000) throw new Error('Skill content is missing or exceeds its limit');
        await atomicWrite(path, content, signal);
      }
      if (change.action === 'create') {
        const usage = await readJson<Record<string, Usage>>(join(root, '.usage.json'), {});
        usage[change.name] ??= emptyUsage(source, new Date().toISOString());
        // The content commit already succeeded. Finish its source record even if cancellation races now.
        await atomicWrite(join(root, '.usage.json'), JSON.stringify(usage, null, 2));
      }
      return { success: true, action: change.action, name: change.name, scope: change.scope ?? 'agent', skill_root: root, path, source };
    }, signal);
  }
  async use(root: string, name: string, sessionId: string, callId: string, location: string, now = new Date().toISOString()) {
    return locked(root, async () => {
      const usage = await readJson<Record<string, Usage>>(join(root, '.usage.json'), {}); const record = usage[name] ??= emptyUsage('F1', now);
      const key = `${sessionId}:${callId}`;
      if (record.recent_call_keys.includes(key)) return { counted: false, batch: false, record };
      record.use_count++; record.uses_since_last_B++; record.last_used_at = now;
      if (record.state === 'stale') record.state = 'active';
      record.recent_call_keys = [...record.recent_call_keys, key].slice(-200);
      record.session_refs = [...record.session_refs, { session_id: sessionId, tool_call_id: callId, timestamp: now, location }].slice(-60);
      await atomicWrite(join(root, '.usage.json'), JSON.stringify(usage, null, 2));
      return { counted: true, batch: auto.has(record.source) && record.uses_since_last_B >= 20, record };
    });
  }
  async usage(roots: string[], belongs: (session: string) => Promise<boolean>) {
    const skills = []; const heatmap_data = Array.from({ length: 30 }, () => 0);
    const health = { created_auto_total: 0, active_auto_total: 0, used_auto_total: 0 };
    const today = Math.floor(Date.now() / 86400000);
    for (const root of [...new Set(roots)]) {
      const records = await readJson<Record<string, Usage>>(join(root, '.usage.json'), {});
      for (const [name, raw] of Object.entries(records)) {
        const record = { ...raw }; let refs = raw.session_refs ?? [];
        if (root !== this.skillRoot) {
          const selected = await Promise.all(refs.map(async ref => await belongs(ref.session_id) ? ref : undefined));
          refs = selected.filter((ref): ref is Usage['session_refs'][number] => !!ref);
          if (!refs.length) continue;
          record.use_count = refs.length; record.last_used_at = refs.map(ref => ref.timestamp).sort().at(-1)!;
        }
        const trend_buckets = Array.from({ length: 30 }, () => 0);
        for (const ref of refs) { const day = today - Math.floor(Date.parse(ref.timestamp) / 86400000); if (day >= 0 && day < 30) { trend_buckets[29 - day]!++; heatmap_data[29 - day]!++; } }
        if (auto.has(record.source)) { health.created_auto_total++; if (record.state !== 'archived') health.active_auto_total++; if (record.use_count > 0) health.used_auto_total++; }
        skills.push({ ...record, skill_id: name, name, session_refs: refs, trend_buckets });
      }
    }
    return { skills, heatmap_data, health };
  }
  async references(sessionId: string, roots: string[]) {
    const found = new Map<string, { name: string; location: string }>();
    for (const root of roots) {
      const usage = await readJson<Record<string, Usage>>(join(root, '.usage.json'), {});
      for (const [name, record] of Object.entries(usage)) {
        const ref = record.session_refs?.findLast(value => value.session_id === sessionId);
        if (ref && !found.has(name)) found.set(name, { name, location: ref.location });
      }
    }
    return [...found.values()];
  }
  async batchAccepted(root: string, name: string) {
    await locked(root, async () => {
      const usage = await readJson<Record<string, Usage>>(join(root, '.usage.json'), {});
      if (usage[name]) usage[name].uses_since_last_B = 0;
      await atomicWrite(join(root, '.usage.json'), JSON.stringify(usage, null, 2));
    });
  }
  async curate(root: string, now = new Date().toISOString()) {
    return locked(root, async () => {
      const statePath = join(root, '.curator_state.json');
      const state = await readJson<{ last_scan_at?: string; reviewed_session_ids?: string[] }>(statePath, {});
      if (state.last_scan_at && Date.parse(now) - Date.parse(state.last_scan_at) < 7 * 86400_000) return;
      const usage = await readJson<Record<string, Usage>>(join(root, '.usage.json'), {});
      for (const [name, record] of Object.entries(usage)) {
        if (!auto.has(record.source) || record.state === 'archived' || !isSkillName(name)) continue;
        const days = (Date.parse(now) - Date.parse(record.last_used_at ?? record.created_at)) / 86400_000;
        if (days >= 90) {
          try { await mkdir(join(root, '.archive'), { recursive: true }); await rename(join(root, name), join(root, '.archive', name)); record.state = 'archived'; record.archived_at = now; record.archive_error = null; }
          catch (error) { record.archive_error = String(error); }
        } else record.state = days >= 30 ? 'stale' : 'active';
      }
      await atomicWrite(join(root, '.usage.json'), JSON.stringify(usage, null, 2));
      await atomicWrite(statePath, JSON.stringify({ ...state, last_scan_at: now }, null, 2));
    });
  }
}
