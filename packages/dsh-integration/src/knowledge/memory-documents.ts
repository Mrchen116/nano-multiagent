import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { watch, type FSWatcher } from 'node:fs';
import { lstat, mkdir, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import type { FileSystem } from '@deepseek-ai/dsh-fs';
import { fromMarkdown } from 'mdast-util-from-markdown';
import { atomicWrite } from './files.js';

export const memoryEntryLimit = 8000;
export type DocumentVersions = Record<string, string>;
export interface DocumentGitChange { path: string; status: string; supported: boolean }
export interface SourceEligibility { revision: string; allowed: string[]; excluded: string[] }
export interface DocumentOperation { operationId: string; path: string; beforeHash: string | null; content: string }
export interface DocumentReceipt {
  operationId: string; path: string; beforeHash: string | null; afterHash: string | null;
  saved: boolean; versionRecorded: boolean; commit?: string; error?: string;
}
interface DocumentState {
  generation: number; sources?: SourceEligibility;
  receipts: Record<string, DocumentReceipt>;
}
const digest = (text: string) => createHash('sha256').update(text).digest('hex');
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const splitNul = (text: string) => text.split('\0').filter(Boolean);

function memoryEntryPreview(text: string): string {
  let end = 0;
  for (const block of fromMarkdown(text).children) {
    for (const part of block.type === 'list' ? block.children : [block]) {
      const offset = part.position?.end.offset;
      if (offset === undefined || offset > memoryEntryLimit) return text.slice(0, end);
      // A heading belongs with the content it introduces.
      if (part.type !== 'heading') end = offset;
    }
  }
  return text.slice(0, end);
}

function command(cwd: string, args: string[], input?: string, extraEnv?: Record<string, string>,
  {raw = false, signal}: {raw?: boolean; signal?: AbortSignal} = {}): Promise<string> {
  return new Promise((accept, reject) => {
    const child = spawn('git', args, { cwd, env: { ...process.env, ...extraEnv }, stdio: 'pipe', signal });
    let stdout = ''; let stderr = '';
    child.stdout.setEncoding('utf8').on('data', data => { stdout += data; });
    child.stderr.setEncoding('utf8').on('data', data => { stderr += data; });
    child.stdin.on('error', reject);
    child.once('error', reject);
    child.once('close', code => code === 0 ? accept(raw ? stdout : stdout.trim()) : reject(new Error(stderr.trim() || `git exited ${code}`)));
    child.stdin.end(input);
  });
}

/** Owns one business Agent's current Markdown, freshness and durable file receipts. */
export class MemoryDocuments {
  readonly root: string;
  readonly backupRoot: string;
  private readonly statePath: string;
  private state: DocumentState = { generation: 0, receipts: {} };
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
    try {
      const {generation, sources, receipts} = JSON.parse(await readFile(owner.statePath, 'utf8')) as DocumentState;
      owner.state = {generation, sources, receipts};
    }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
    const entry = await fs.resolve(join(owner.root, 'MEMORY.md'));
    if (!await fs.stat(entry)) {
      await fs.writeText(entry, role === 'personal'
        ? '# Personal memory\n\nDurable understanding of the owner, their relationships, preferences and workstreams.\n\n## Topics\n\nNo topics saved yet.\n'
        : '# Expert memory\n\nDomain knowledge, environments, collaboration by audience, and verified work experience. No requester is implicitly the owner.\n\n## Topics\n\nNo topics saved yet.\n', { kind: 'createIfAbsent' }, undefined, owner.writePolicy());
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
  private writePolicy() {
    // Publication belongs to the configured owner, not the runtime process cwd.
    // Preserve the backend mode, including read-only, when selecting that root.
    return this.fs.sandboxMode ? { mode: this.fs.sandboxMode, workspaceRoot: this.workspace } : undefined;
  }
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
  /** Read current saved memory; background verification does not hide foreground knowledge.
   *
   * Args:
   *   options: Request a complete-block prefix of an oversized entry for the main Agent.
   */
  async context({ includePreview = false } = {}) {
    const versions = await this.versions();
    const entry = await readFile(join(this.root, 'MEMORY.md'), 'utf8');
    const fits = entry.length <= memoryEntryLimit;
    return { role: this.role, root: this.root, versions, entry: fits ? entry : undefined,
      entryPreview: includePreview && !fits ? memoryEntryPreview(entry) : undefined,
      backupRoot: this.backupRoot };
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
  async status() { return { generation: this.state.generation, sourcesPending: this.sourcesPending, ...(this.state.sources ? { sources: this.state.sources } : {}), receipts: Object.values(this.state.receipts), backupRoot: this.backupRoot }; }
  /** Return the formal repository's staged, unstaged and untracked changes. */
  async gitChanges(): Promise<DocumentGitChange[]> {
    if (!(await lstat(join(this.root, '.git'))).isDirectory()) throw new Error('The memory Git directory is unavailable.');
    const result = await command(this.root, ['status', '--porcelain=v1', '-z', '--untracked-files=all', '--no-renames'],
      undefined, this.gitEnvironment(), {raw: true});
    const changes = splitNul(result).map(row => ({status:row.slice(0, 2), path:row.slice(3)}));
    return Promise.all(changes.map(async ({status, path}) => {
      let supported = false;
      if (status === '??' || /^[ AMD]{2}$/.test(status)) {
        try {
          const absolute = join(this.root, path);
          const info = await lstat(absolute).catch(error => {
            if (error.code === 'ENOENT') return undefined;
            throw error;
          });
          supported = await this.path(path) === path && (info
            ? info.isFile() && await realpath(absolute) === absolute
            : status.includes('D'));
        } catch { /* Unsupported changes are reported without modifying them. */ }
      }
      return {path, status, supported};
    }));
  }
  /** Report repository issues that the current Dreaming Agent can repair. */
  async repositoryIssues(): Promise<Array<{path: string; reason: string; status?: string}>> {
    const issues: Array<{path: string; reason: string; status?: string}> = (await this.gitChanges()).map(({path,status}) =>
      ({path,status,reason:'Uncommitted change'}));
    const walk = async (directory: string) => {
      for (const item of await readdir(join(this.root, directory), {withFileTypes:true})) {
        if (!directory && item.name === '.git') continue;
        const path = join(directory, item.name);
        if (item.isDirectory()) await walk(path);
        else if (!item.isFile() || !path.endsWith('.md')) issues.push({path,reason:'Expected a regular Markdown file'});
      }
    };
    await walk('');
    return issues;
  }
  private async headSnapshot(paths: ReadonlySet<string>) {
    const env = this.gitEnvironment();
    const head = await command(this.root, ['rev-parse', '--verify', 'HEAD'], undefined, env);
    const rows = splitNul(await command(this.root, ['ls-tree', '-r', '-z', head], undefined, env, {raw:true}));
    const versions: DocumentVersions = {};
    const unsupported = new Set<string>();
    for (const row of rows) {
      const path = row.slice(row.indexOf('\t') + 1);
      if (!paths.has(path)) continue;
      if (!/^100(644|755) blob /.test(row)) unsupported.add(path);
      else versions[path] = digest(await command(this.root, ['show', `${head}:${path}`], undefined, env, {raw:true}));
    }
    return {head, versions, unsupported};
  }
  /** Observe settled native edits, including failures, for Work receipts.
   *
   * Args:
   *   before: Document hashes captured before this run edited the formal library.
   *   runId: Durable identity for this run's per-path receipts.
   */
  observeBatch(before: DocumentVersions, runId: string): Promise<{versions: DocumentVersions; receipts: DocumentReceipt[]}> {
    return this.serial(async () => {
      await this.refresh();
      const versions = await this.versions();
      const changed = [...new Set([...Object.keys(before), ...Object.keys(versions)])].filter(path => before[path] !== versions[path]).sort();
      const receiptPaths = new Set([...changed,...Object.values(this.state.receipts)
        .filter(receipt => receipt.saved && !receipt.versionRecorded && (versions[receipt.path] ?? null) === receipt.afterHash)
        .map(receipt => receipt.path)]);
      let snapshot: Awaited<ReturnType<MemoryDocuments['headSnapshot']>> | undefined;
      let gitError: string | undefined;
      try { if (receiptPaths.size) snapshot = await this.headSnapshot(receiptPaths); } catch (error) { gitError = String(error); }
      // A later batch may commit unchanged files left by an interrupted run.
      for (const receipt of Object.values(this.state.receipts)) {
        if (receipt.saved && !receipt.versionRecorded && snapshot && !snapshot.unsupported.has(receipt.path) &&
            (versions[receipt.path] ?? null) === receipt.afterHash && (snapshot.versions[receipt.path] ?? null) === receipt.afterHash) {
          receipt.versionRecorded = true; receipt.commit = snapshot.head; delete receipt.error;
        }
      }
      const receipts: DocumentReceipt[] = [];
      for (const path of changed) {
        const beforeHash = before[path] ?? null; const afterHash = versions[path] ?? null;
        // An unsupported replacement (for example a symlink) is not a saved deletion.
        const saved = afterHash !== null || await lstat(join(this.root, path)).then(() => false, error => {
          if (error.code === 'ENOENT') return true;
          throw error;
        });
        const versionRecorded = saved && !!snapshot && !snapshot.unsupported.has(path) && (snapshot.versions[path] ?? null) === afterHash;
        const receipt: DocumentReceipt = {operationId:`${runId}:${path}`, path, beforeHash, afterHash, saved, versionRecorded,
          ...(versionRecorded ? {commit:snapshot!.head} : {}), ...(gitError ? {error:gitError} : {})};
        this.state.receipts[receipt.operationId] = receipt; receipts.push(receipt);
      }
      await this.save();
      return {versions, receipts};
    });
  }
  /** Atomically apply a frozen plan; recovery accepts its after hash but never a third version. */
  apply(operation: DocumentOperation, generation?: number, signal?: AbortSignal, options: {recordVersion?: boolean} = {}): Promise<DocumentReceipt> {
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
          await this.fs.writeText(target, operation.content, info ? { kind: 'replaceIfVersion', version: info.version } : { kind: 'createIfAbsent' }, signal, this.writePolicy());
        }
        receipt.saved = true; this.dirty.add(path); await this.save();
        if (options.recordVersion !== false) {
          receipt.commit = await this.recordVersion(path, operation.content); receipt.versionRecorded = true;
        }
        delete receipt.error;
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
  private gitEnvironment(index = join(this.root, '.git/index')) {
    return { GIT_DIR: join(this.root, '.git'), GIT_WORK_TREE: this.root, GIT_INDEX_FILE: index, GIT_AUTHOR_NAME: 'Nano Memory', GIT_AUTHOR_EMAIL: 'memory@localhost', GIT_COMMITTER_NAME: 'Nano Memory', GIT_COMMITTER_EMAIL: 'memory@localhost' };
  }
  private async recordVersion(path: string, content: string): Promise<string> {
    const index = join(this.root, '.git', `nano-index-${randomUUID()}`);
    const env = this.gitEnvironment(index);
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
