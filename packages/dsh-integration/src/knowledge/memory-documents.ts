import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { watch, type FSWatcher } from 'node:fs';
import { mkdir, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import type { FileSystem } from '@deepseek-ai/dsh-fs';
import { atomicWrite } from './files.js';

export type DocumentVersions = Record<string, string>;
export interface SourceEligibility { revision: string; allowed: string[]; excluded: string[] }
export interface DocumentOperation { operationId: string; path: string; beforeHash: string | null; content: string }
export interface DocumentReceipt {
  operationId: string; path: string; beforeHash: string | null; afterHash: string;
  saved: boolean; versionRecorded: boolean; commit?: string; error?: string;
}
interface DocumentState {
  generation: number; sources?: SourceEligibility; exclusions: Array<{ requestRef: string; paths: string[]; sources: string[] }>;
  basis?: { generation: number; versions: DocumentVersions };
  receipts: Record<string, DocumentReceipt>;
}
const digest = (text: string) => createHash('sha256').update(text).digest('hex');
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
function command(cwd: string, args: string[], input?: string, extraEnv?: Record<string, string>): Promise<string> {
  return new Promise((accept, reject) => {
    const child = spawn('git', args, { cwd, env: { ...process.env, ...extraEnv }, stdio: 'pipe' });
    let stdout = ''; let stderr = '';
    child.stdout.on('data', data => { stdout += data; }); child.stderr.on('data', data => { stderr += data; });
    child.once('error', reject); child.once('close', code => code === 0 ? accept(stdout.trim()) : reject(new Error(stderr.trim() || `git exited ${code}`)));
    child.stdin.end(input);
  });
}

/** Owns one business Agent's current Markdown, freshness and durable file receipts. */
export class MemoryDocuments {
  readonly root: string;
  readonly backupRoot: string;
  private readonly statePath: string;
  private state: DocumentState = { generation: 0, exclusions: [], receipts: {} };
  private hashes: DocumentVersions = {};
  private dirty = new Set<string>();
  private rescan = true;
  private watcher?: FSWatcher;
  private tail: Promise<unknown> = Promise.resolve();
  private sourcesPending = false;
  private constructor(readonly workspace: string, readonly role: 'personal' | 'expert', private readonly fs: FileSystem) {
    this.root = join(workspace, '.nanoassistant/memory');
    this.backupRoot = join(workspace, '.nanoassistant/memory-backups');
    this.statePath = join(workspace, '.nanoassistant/maintenance/documents.json');
  }
  /** Open the configured owner workspace, never the executing child's cwd.
   *
   * Args:
   *   workspace: Trusted business configuration root.
   *   role: Trusted personal configuration, not the current requester.
   *   fs: Native filesystem provider used for atomic publication.
   */
  static async open(workspace: string, role: 'personal' | 'expert', fs: FileSystem): Promise<MemoryDocuments> {
    const owner = new MemoryDocuments(await realpath(workspace), role, fs);
    await mkdir(owner.root, { recursive: true });
    if (await realpath(owner.root) !== owner.root) throw new Error('Memory root must not be a symbolic link.');
    try { owner.state = JSON.parse(await readFile(owner.statePath, 'utf8')) as DocumentState; }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
    const entry = await fs.resolve(join(owner.root, 'MEMORY.md'));
    if (!await fs.stat(entry)) {
      await fs.writeText(entry, role === 'personal'
        ? '# Personal memory\n\nDurable understanding of the owner, their relationships, preferences and workstreams.\n\n## Topics\n\nNo topics saved yet.\n'
        : '# Expert memory\n\nDomain knowledge, environments, collaboration by audience, and verified work experience. No requester is implicitly the owner.\n\n## Topics\n\nNo topics saved yet.\n', { kind: 'createIfAbsent' });
    }
    // Exclude the entire private tree from an enclosing repository before initializing ours.
    try {
      const exclude = await command(owner.workspace, ['rev-parse', '--git-path', 'info/exclude']);
      const path = resolve(owner.workspace, exclude); const text = await readFile(path, 'utf8').catch(() => '');
      if (!text.split('\n').includes('.nanoassistant/')) await writeFile(path, `${text}\n.nanoassistant/\n`);
    } catch { /* A workspace need not be a Git repository. */ }
    const git = join(owner.root, '.git');
    try { await readFile(join(git, 'HEAD')); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      const content = await readFile(join(owner.root, 'MEMORY.md'), 'utf8');
      try {
        await command(owner.root, ['init', '--quiet']);
        await owner.recordVersion('MEMORY.md', content);
      } catch (error) {
        owner.state.receipts.initial_entry = { operationId: 'initial_entry', path: 'MEMORY.md', beforeHash: null,
          afterHash: digest(content), saved: true, versionRecorded: false, error: String(error) };
        await owner.save();
      }
    }
    await owner.refresh();
    if (!owner.state.basis && Object.keys(owner.hashes).length === 1 && owner.state.generation === 0) {
      owner.state.basis = { generation: 0, versions: { ...owner.hashes } }; await owner.save();
    }
    try {
      owner.watcher = watch(owner.root, { recursive: true, persistent: false }, (_event, name) => {
        if (!name) { owner.rescan = true; return; }
        const path = String(name); if (path === '.git' || path.startsWith('.git/')) return;
        if (path.endsWith('.md')) owner.dirty.add(path); else owner.rescan = true;
      });
      owner.watcher.on('error', () => { owner.rescan = true; owner.watcher?.close(); owner.watcher = undefined; });
    } catch { owner.rescan = true; }
    return owner;
  }
  private serial<T>(action: () => Promise<T>): Promise<T> {
    const task = this.tail.then(action); this.tail = task.catch(() => {}); return task;
  }
  private save() { return atomicWrite(this.statePath, JSON.stringify(this.state)); }
  /** Resolve a document without allowing aliases to escape its owner library. */
  async path(path: string): Promise<string> {
    const absolute = resolve(this.root, path); const rel = relative(this.root, absolute);
    if (!rel || rel.startsWith('..') || isAbsolute(rel) || !rel.endsWith('.md') || rel.split('/').some(part => part.startsWith('.'))) throw new Error('Expected a Markdown document inside this memory library.');
    const target = await this.fs.resolve(absolute); const root = await this.fs.resolve(this.root);
    if (!this.fs.contains(root, target)) throw new Error('Memory path escapes its library.');
    return rel;
  }
  /** Mark tool writes synchronously; watcher notifications also cover manual edits. */
  async invalidate(path: string): Promise<void> { this.dirty.add(await this.path(path)); }
  /** Reconcile disk versions on startup, recovery or a watcher error. */
  async refresh(): Promise<void> {
    const paths: string[] = [];
    const walk = async (directory: string) => {
      for (const item of await readdir(join(this.root, directory), { withFileTypes: true })) {
        if (item.name.startsWith('.')) continue;
        const path = join(directory, item.name);
        if (item.isDirectory()) await walk(path);
        else if (item.isFile() && path.endsWith('.md')) paths.push(path);
      }
    };
    await walk(''); const hashes: DocumentVersions = {};
    for (const path of paths.sort()) hashes[path] = digest(await readFile(join(this.root, path), 'utf8'));
    this.hashes = hashes; this.dirty.clear(); this.rescan = false;
  }
  /** Return current hashes, updating dirty paths without hashing every unchanged page. */
  async versions(): Promise<DocumentVersions> {
    if (this.rescan || !this.watcher) await this.refresh();
    // The small entry is always read at model assembly, independent of watcher latency.
    this.dirty.add('MEMORY.md');
    for (const path of [...this.dirty]) {
      this.dirty.delete(path);
      try { await this.path(path); this.hashes[path] = digest(await readFile(join(this.root, path), 'utf8')); }
      catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') delete this.hashes[path]; else throw error; }
    }
    return Object.fromEntries(Object.entries(this.hashes).sort(([a], [b]) => a.localeCompare(b)));
  }
  /** Assemble navigation and an entry only when its confirmed basis is still current. */
  async context() {
    const versions = await this.versions(); const basis = this.state.basis;
    const valid = !this.sourcesPending && basis?.generation === this.state.generation && same(basis.versions, versions);
    const entry = valid ? await readFile(join(this.root, 'MEMORY.md'), 'utf8') : undefined;
    return { role: this.role, root: this.root, generation: this.state.generation, versions,
      entry: entry && entry.length <= 8000 ? entry : undefined,
      reason: this.sourcesPending ? 'source_eligibility_pending' : !valid ? 'entry_basis_stale' : entry && entry.length > 8000 ? 'entry_needs_shortening' : undefined,
      exclusions: this.state.exclusions, backupRoot: this.backupRoot };
  }
  /** Confirm versions actually read/written by the caller; the runtime supplies read evidence. */
  checkpoint(versions: DocumentVersions, generation: number) {
    return this.serial(async () => {
      if (this.sourcesPending || generation !== this.state.generation) throw new Error('Source generation changed or has not been verified.');
      await this.refresh();
      if (!same(versions, await this.versions())) throw new Error('Document versions changed; reread the current documents.');
      this.state.basis = { generation, versions: { ...versions } }; await this.save();
      return { synchronized: true, generation };
    });
  }
  /** A reconnect must establish current policy before reusing source-derived summaries. */
  markSourcesPending() { this.sourcesPending = true; }
  /** Synchronize a complete authoritative set; same revision with membership changes matters. */
  syncSources(snapshot: SourceEligibility) {
    return this.serial(async () => {
      const normalized = { revision: snapshot.revision, allowed: [...new Set(snapshot.allowed)].sort(), excluded: [...new Set(snapshot.excluded)].sort() };
      if (!same(normalized, this.state.sources)) {
        const eligibilityChanged = !same(normalized.allowed, this.state.sources?.allowed) || !same(normalized.excluded, this.state.sources?.excluded);
        this.state.sources = normalized;
        if (eligibilityChanged) this.state.generation++;
        await this.save();
      }
      this.sourcesPending = false;
      return this.status();
    });
  }
  /** Persist an authorized stop-use request without erasing source or Git history. */
  exclude(requestRef: string, paths: string[], sources: string[]) {
    return this.serial(async () => {
      for (const path of paths) await this.path(path);
      if (!this.state.exclusions.some(item => item.requestRef === requestRef)) {
        this.state.exclusions.push({ requestRef, paths, sources }); this.state.generation++; await this.save();
      }
      return this.status();
    });
  }
  async status() { return { generation: this.state.generation, sourcesPending: this.sourcesPending, sources: this.state.sources, exclusions: this.state.exclusions, receipts: Object.values(this.state.receipts), backupRoot: this.backupRoot }; }
  /** Atomically apply a frozen plan; recovery accepts its after hash but never a third version. */
  apply(operation: DocumentOperation, generation?: number, signal?: AbortSignal): Promise<DocumentReceipt> {
    return this.serial(async () => {
      const path = await this.path(operation.path); const afterHash = digest(operation.content);
      const old = this.state.receipts[operation.operationId];
      if (old && (old.path !== path || old.afterHash !== afterHash)) throw new Error('Operation identity was reused with another plan.');
      if (old?.saved && old.versionRecorded) return old;
      const receipt: DocumentReceipt = old ?? { operationId: operation.operationId, path, beforeHash: operation.beforeHash, afterHash, saved: false, versionRecorded: false };
      this.state.receipts[operation.operationId] = receipt; await this.save();
      try {
        signal?.throwIfAborted();
        if (generation !== undefined && (this.sourcesPending || generation !== this.state.generation)) throw new Error('Source generation changed before application.');
        const target = await this.fs.resolve(join(this.root, path)); const info = await this.fs.stat(target);
        const current = info ? await this.fs.readText(target) : null;
        const currentHash = current === null ? null : digest(current);
        if (currentHash !== afterHash) {
          if (currentHash !== operation.beforeHash || receipt.saved) throw new Error('Document changed; planned write conflicts with the current version.');
          await this.fs.writeText(target, operation.content, info ? { kind: 'replaceIfVersion', version: info.version } : { kind: 'createIfAbsent' }, signal);
        }
        receipt.saved = true; this.dirty.add(path); await this.save();
        receipt.commit = await this.recordVersion(path, operation.content); receipt.versionRecorded = true; delete receipt.error;
      } catch (error) { receipt.error = String(error); }
      await this.save(); return { ...receipt };
    });
  }
  /** Record a settled ordinary tool write without replaying the mutation. */
  record(operation: DocumentOperation): Promise<DocumentReceipt> {
    return this.serial(async () => {
      const path = await this.path(operation.path);
      const afterHash = digest(operation.content);
      const receipt: DocumentReceipt = { operationId: operation.operationId, path, beforeHash: operation.beforeHash, afterHash, saved: false, versionRecorded: false };
      try {
        if (digest(await readFile(join(this.root, path), 'utf8')) !== afterHash) throw new Error('Document changed after the tool result; version recording deferred.');
        receipt.saved = true; this.dirty.add(path);
        receipt.commit = await this.recordVersion(path, operation.content); receipt.versionRecorded = true;
      } catch (error) { receipt.error = String(error); }
      this.state.receipts[operation.operationId] = receipt; await this.save(); return receipt;
    });
  }
  private async recordVersion(path: string, content: string): Promise<string> {
    const index = join(this.root, '.git', `nano-index-${randomUUID()}`);
    const env = { GIT_DIR: join(this.root, '.git'), GIT_WORK_TREE: this.root, GIT_INDEX_FILE: index, GIT_AUTHOR_NAME: 'Nano Memory', GIT_AUTHOR_EMAIL: 'memory@localhost', GIT_COMMITTER_NAME: 'Nano Memory', GIT_COMMITTER_EMAIL: 'memory@localhost' };
    try {
      const parent = await command(this.root, ['rev-parse', '--verify', 'HEAD'], undefined, env).catch(() => undefined);
      await command(this.root, parent ? ['read-tree', parent] : ['read-tree', '--empty'], undefined, env);
      const blob = await command(this.root, ['hash-object', '-w', '--stdin'], content, env);
      await command(this.root, ['update-index', '--add', '--cacheinfo', '100644', blob, path], undefined, env);
      const tree = await command(this.root, ['write-tree'], undefined, env);
      const commit = await command(this.root, ['commit-tree', tree, ...(parent ? ['-p', parent] : [])], `Record ${path}\n`, env);
      await command(this.root, ['update-ref', 'HEAD', commit, parent ?? '0'.repeat(40)], undefined, env);
      // Update only this path in the ordinary index; unrelated manual files stay untracked.
      await command(this.root, ['update-index', '--add', '--cacheinfo', '100644', blob, path], undefined, { ...env, GIT_INDEX_FILE: join(this.root, '.git/index') });
      return commit;
    } finally { await rm(index, { force: true }); }
  }
  async close() { this.watcher?.close(); this.watcher = undefined; await this.tail; }
}
