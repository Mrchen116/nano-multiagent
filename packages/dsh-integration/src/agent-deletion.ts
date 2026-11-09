import { lstat, mkdir, open, readdir, realpath, rename, rm } from 'node:fs/promises';
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import { SESSION_FORMAT_VERSION, SessionId, type SessionHeader } from '@deepseek-ai/dsh-session/types';
import JsonlSessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl';
import { defineDomain, domainTable } from '@deepseek-ai/dsh-storage-domain';
import { z } from 'zod';
import DeletionCache from './deletion-cache.js';
import type { SessionBinding } from './index.js';

const retirement = z.object({ revision: z.number().int(), sessionIds: z.array(z.string()) });
const domain = defineDomain({ name: 'nano_agent_deletion', version: 1, layout: 'per-record', tables: { owners: domainTable(retirement), reviewers: domainTable(z.string()) } });
const safeId = z.string().regex(/^(?!\.{1,2}$)[a-zA-Z0-9._-]+$/);
const generationPattern = /^session(?:\.v([1-9]\d*))?\.jsonl(?:\.zstd)?$/;
const headerSchema = z.object({
  id: safeId, version: z.literal(SESSION_FORMAT_VERSION), cwd: z.string().optional(), createdAt: z.number(),
  isSeeded: z.boolean(), parentSession: safeId.optional(), origin: z.literal('subagent').optional(),
  delegationDepth: z.number().int().optional(), agentPreset: z.string().optional(),
});
const artifactSchema = z.object({ name: z.string().refine(isGeneration), witness: z.string() });
const planSchema = z.object({
  version: z.literal(1), agentId: z.string(), revision: z.number().int(),
  sessionIds: z.array(safeId),
  entries: z.array(z.object({ header: headerSchema, directory: z.string(), artifacts: z.array(artifactSchema).min(1) })),
});
export type SessionDeletionPlan = z.infer<typeof planSchema>;
type Entry = SessionDeletionPlan['entries'][number];

function isGeneration(name: string): boolean {
  const match = generationPattern.exec(name);
  return !!match && Number(match[1] ?? 0) <= SESSION_FORMAT_VERSION;
}

async function entries(path: string) {
  try { return await readdir(path, { withFileTypes: true }); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []; throw error; }
}

async function witness(path: string): Promise<string | undefined> {
  try {
    const stat = await lstat(path, { bigint: true });
    if (!stat.isFile()) throw new Error('Session artifact must be a regular file');
    return [stat.dev, stat.ino, stat.size, stat.mtimeNs].join(':');
  } catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return; throw error; }
}

function fromHeader(header: Entry['header']): SessionHeader {
  return { ...header, id: SessionId(header.id), parentSession: header.parentSession ? SessionId(header.parentSession) : undefined };
}

async function syncDirectory(path: string): Promise<void> {
  if (process.platform === 'win32') return;
  const directory = await open(path, 'r');
  try { await directory.sync(); } finally { await directory.close(); }
}

/** Owns the runtime retirement fence and the locked JSONL layout used by Nano. */
export class SessionDeletion {
  private readonly state;
  private readonly owners = new Map<string, z.infer<typeof retirement>>();
  private readonly active = new Map<string, Set<Promise<unknown>>>();
  private readonly root: string;

  constructor(private readonly ctx: Context, private readonly cache: DeletionCache, private readonly storage: JsonlSessionPersistence,
    private readonly home: string) {
    this.root = resolve(home, 'sessions');
    if (resolve(storage.config.root) !== this.root) throw new Error('Unsupported session deletion storage root');
    this.state = ctx.storageDomain.open(domain);
    ctx.effect(() => async () => { await (await this.state).close(); });
  }

  /** Activate this capability only for the locked ordinary-host composition. */
  static forRuntime(ctx: Context, home: string): SessionDeletion | undefined {
    const cache = ctx.get('sessionProjectionCache');
    const storage = ctx.sessionPersistence;
    const query = ctx.sessionQuery as typeof ctx.sessionQuery & {config?: {openAt?: string}};
    // The supported profile never opens an FTS index. The optional SQLite
    // service exposes no scoped purge operation in this pinned version.
    if (cache instanceof DeletionCache && storage instanceof JsonlSessionPersistence && query.config?.openAt === 'never')
      return new SessionDeletion(ctx, cache, storage, home);
  }

  /** Restore target fences before the Node can use cold runtime reads. */
  async restore(): Promise<void> {
    for (const [id, saved] of (await this.state).table('owners').entries()) {
      this.owners.set(id, saved);
      this.cache.fence(saved.sessionIds);
    }
  }

  retired(agentId: string): boolean { return this.owners.has(agentId); }
  retiredRevision(agentId: string): number | undefined { return this.owners.get(agentId)?.revision; }

  /** Record the ownership of otherwise independent reviewer logs before creation. */
  async rememberReviewer(parent: string, child: string): Promise<void> {
    await (await this.state).table('reviewers').put(child, parent);
  }

  /** Track target activity without holding or counting other Agents' work. */
  async admit(agentId: string | undefined, action: () => unknown): Promise<unknown> {
    if (!agentId) return action();
    if (this.retired(agentId)) throw new Error('Agent execution was deleted');
    const pending = this.active.get(agentId) ?? new Set<Promise<unknown>>();
    const task = Promise.resolve().then(action);
    this.active.set(agentId, pending);
    pending.add(task);
    try { return await task; }
    finally {
      pending.delete(task);
      if (!pending.size) this.active.delete(agentId);
    }
  }

  /** Drain only work that was accepted before this Agent was fenced. */
  async drain(agentId: string): Promise<void> {
    await Promise.allSettled(this.active.get(agentId) ?? []);
  }

  /** Reject new target reads before awaiting readers already admitted. */
  async begin(agentId: string, revision: number): Promise<void> {
    const existing = this.owners.get(agentId);
    if (existing && existing.revision !== revision) throw new Error('Stale Agent deletion revision');
    const saved = existing ?? { revision, sessionIds: [] };
    this.owners.set(agentId, saved);
    await (await this.state).table('owners').put(agentId, saved);
  }

  /**
   * Produce a persistent, target-scoped cleanup manifest before removing any data.
   *
   * Args:
   *   agentId: Target product Agent.
   *   revision: Confirmed stopped lifecycle revision.
   *   bindings: Node-owned roots, including other owners' exclusion boundaries.
   *   known: Additional proven native IDs from the target's Work and maintenance records.
   *   foreignPreset: Resolve a registered native preset's product owner.
   *
   * Returns:
   *   A JSON-serializable set of owned IDs and exact artifact witnesses.
   */
  async plan(agentId: string, revision: number, bindings: ReadonlyMap<string, SessionBinding>, known: Iterable<string>,
    foreignPreset: (preset: string) => string | undefined, links: ReadonlyMap<string, ReadonlySet<string>> = new Map()): Promise<SessionDeletionPlan> {
    const saved = this.owners.get(agentId);
    if (!saved || saved.revision !== revision) throw new Error('Agent deletion fence is unavailable');
    const snapshots = await this.storage.list();
    const headers = new Map<string, SessionHeader>(snapshots.map(({header}) => [header.id, header]));
    const children = new Map<string, SessionHeader[]>();
    for (const {header} of snapshots) {
      if (!header.parentSession) continue;
      const related = children.get(header.parentSession) ?? [];
      related.push(header);
      children.set(header.parentSession, related);
    }
    const ownsPreset = (preset?: string) => preset?.startsWith(`nano:${agentId}:`) === true;
    const reviewChildren = new Map<string, string[]>();
    for (const [child, parent] of (await this.state).table('reviewers').entries()) {
      const related = reviewChildren.get(parent) ?? [];
      related.push(child);
      reviewChildren.set(parent, related);
    }
    const pending = [...new Set([...bindings.values()].filter(binding => binding.agentId === agentId).map(binding => binding.sessionId).concat([...known], saved.sessionIds))];
    const owned = new Set<string>();
    for (const id of pending) {
      if (owned.has(id)) continue;
      safeId.parse(id);
      const binding = bindings.get(id), header = headers.get(id);
      const otherOwner = header?.agentPreset && foreignPreset(header.agentPreset);
      if ((binding && binding.agentId !== agentId) || (otherOwner && otherOwner !== agentId))
        throw new Error(`Conflicting Agent ownership for session ${id}`);
      if (binding && header && (header.agentPreset !== `nano:${agentId}:${binding.revision}` || header.cwd !== binding.cwd))
        throw new Error(`Persisted session identity conflicts with binding: ${id}`);
      owned.add(id);
      for (const linked of [...(links.get(id) ?? []), ...(reviewChildren.get(id) ?? [])]) {
        const linkedHeader = headers.get(linked);
        const linkedBinding = bindings.get(linked);
        const linkedOwner = linkedHeader?.agentPreset && foreignPreset(linkedHeader.agentPreset);
        if ((!linkedBinding || linkedBinding.agentId === agentId) && (!linkedOwner || linkedOwner === agentId)) pending.push(linked);
      }
      for (const child of children.get(id) ?? []) {
        const explicit = bindings.get(child.id);
        if (explicit && explicit.agentId !== agentId) continue;
        const childOwner = child.agentPreset && foreignPreset(child.agentPreset);
        if (childOwner && childOwner !== agentId) continue;
        const nativeChild = child.origin === 'subagent' && (!child.agentPreset || ownsPreset(child.agentPreset));
        const fork = child.isSeeded && ownsPreset(child.agentPreset) && child.agentPreset === header?.agentPreset;
        const reviewer = child.agentPreset === 'nano-codex-reviewer' && child.id.startsWith('nano-codex-');
        if (nativeChild || fork || reviewer) pending.push(child.id);
      }
    }
    const sessionIds = [...owned].sort();
    const directories = await this.locate(sessionIds);
    const manifest: Entry[] = [];
    for (const id of sessionIds) {
      if (this.ctx.sessions.get(SessionId(id))) throw new Error(`Target session is still live: ${id}`);
      const directory = directories.get(id);
      const artifacts = directory ? await this.artifacts(directory) : [];
      const header = headers.get(id);
      if (!artifacts.length && !header) continue;
      if (!artifacts.length || !header || !directory)
        throw new Error(`Could not verify stored artifacts for target session ${id}`);
      const current = await this.storage.resolveCurrentLog(SessionId(id));
      if (current && await realpath(dirname(current)) !== directory)
        throw new Error(`Session directory differs from JSONL provider: ${id}`);
      // The public stat check also verifies that a historical header resolves to
      // the same physical path as the provider's per-session lease.
      const selected = await this.storage.stat(SessionId(id));
      if (!selected || JSON.stringify(selected.header) !== JSON.stringify(header))
        throw new Error(`Session changed during deletion planning: ${id}`);
      manifest.push({ header, directory: relative(await realpath(this.root), directory), artifacts });
    }
    this.cache.fence(sessionIds);
    const next = { revision, sessionIds };
    this.owners.set(agentId, next);
    await (await this.state).table('owners').put(agentId, next);
    return { version: 1, agentId, revision, sessionIds, entries: manifest };
  }

  /** Remove only artifacts witnessed by this durable plan, holding each native writer lease. */
  async purge(agentId: string, revision: number, operationId: string, manifest: unknown): Promise<string[]> {
    const plan = planSchema.parse(manifest), saved = this.owners.get(agentId);
    const ids = new Set(plan.sessionIds);
    if (!saved || plan.agentId !== agentId || plan.revision !== revision || saved.revision !== revision ||
      JSON.stringify(saved.sessionIds) !== JSON.stringify(plan.sessionIds) ||
      plan.entries.some(entry => !ids.has(entry.header.id))) throw new Error('Session deletion plan does not match the durable fence');
    if (typeof operationId !== 'string' || !operationId || operationId.length > 160) throw new Error('Invalid deletion operation identity');
    const staging = join(this.home, 'deletion-staging', Buffer.from(operationId).toString('base64url'));
    const directories = await this.locate(plan.sessionIds);
    const selected = new Map(plan.entries.map(entry => [entry.header.id, entry]));
    for (const id of plan.sessionIds) {
      const sessionId = SessionId(id), entry = selected.get(id), directory = directories.get(id);
      if (this.ctx.sessions.get(sessionId)) throw new Error(`Target session is still live: ${id}`);
      if (entry && directory) {
        this.assertDirectory(entry, directory);
        const lease = await this.storage.acquireWriteLease(fromHeader(entry.header));
        try {
          const artifacts = await this.artifacts(directory);
          if (artifacts.some(artifact => !entry.artifacts.some(prior => prior.name === artifact.name && prior.witness === artifact.witness)))
            throw new Error(`Session artifacts changed after deletion planning: ${id}`);
          if (artifacts.length) {
            const header = (await this.storage.stat(sessionId))?.header;
            if (!header || header.cwd !== entry.header.cwd || header.createdAt !== entry.header.createdAt)
              throw new Error(`Could not verify session under its writer lease: ${id}`);
          }
          if (artifacts.length) await mkdir(staging, { recursive: true, mode: 0o700 });
          for (const {name} of artifacts) {
            const staged = join(staging, `${id}-${name}`);
            if (await witness(staged) !== undefined) throw new Error(`Duplicate staged session artifact: ${id}`);
            await rename(join(directory, name), staged);
          }
          if (artifacts.length) await Promise.all([syncDirectory(directory), syncDirectory(staging), syncDirectory(dirname(staging))]);
        } finally { await lease.release(); }
      } else if (directory && (await this.artifacts(directory)).length) {
        throw new Error(`Unplanned stored session appeared: ${id}`);
      }
      await this.cache.forget(sessionId);
      if (await this.storage.stat(sessionId)) throw new Error(`Native session still exists: ${id}`);
    }
    await this.removeCacheBackups(ids);
    await rm(staging, { recursive: true, force: true });
    await syncDirectory(dirname(staging)).catch(error => { if (error.code !== 'ENOENT') throw error; });
    const reviewers = (await this.state).table('reviewers');
    for (const id of ids) await reviewers.delete(id);
    return plan.sessionIds;
  }

  private assertDirectory(entry: Entry, directory: string): void {
    const pieces = entry.directory.split(sep);
    if (isAbsolute(entry.directory) || pieces.length !== 2 || pieces.some(piece => !piece || piece === '..' || piece === '.') ||
      pieces[1] !== entry.header.id || basename(directory) !== pieces[1] || basename(dirname(directory)) !== pieces[0])
      throw new Error(`Session directory changed: ${entry.header.id}`);
  }

  private async locate(ids: string[]): Promise<Map<string, string>> {
    const matched = new Map<string, string>();
    const wanted = new Set(ids);
    const projects = await entries(this.root);
    if (!projects.length) return matched;
    const root = await realpath(this.root);
    if ((await lstat(this.root)).isSymbolicLink()) throw new Error('Session storage root cannot be a symbolic link');
    for (const project of projects) {
      if (!project.isDirectory()) continue;
      const folder = join(root, project.name);
      for (const candidate of await entries(folder)) {
        if (!wanted.has(candidate.name)) {
          const legacy = candidate.name.replace(/\.jsonl(?:\.zstd)?$/, '');
          if (legacy !== candidate.name && wanted.has(legacy)) throw new Error(`Unsupported flat session storage: ${legacy}`);
          continue;
        }
        if (!candidate.isDirectory() || matched.has(candidate.name))
          throw new Error(`Ambiguous physical session directory: ${candidate.name}`);
        matched.set(candidate.name, join(folder, candidate.name));
      }
    }
    return matched;
  }

  private async artifacts(directory: string): Promise<Entry['artifacts']> {
    const artifacts = [];
    for (const {name} of await entries(directory)) {
      if (name === 'session.lock') continue;
      if (!isGeneration(name)) throw new Error(`Unsupported session artifact: ${name}`);
      const identity = await witness(join(directory, name));
      if (identity) artifacts.push({ name, witness: identity });
    }
    // Retain the current selected header until the last move.
    const generation = (name: string) => Number(generationPattern.exec(name)?.[1] ?? 0);
    return artifacts.sort((left, right) => generation(left.name) - generation(right.name));
  }

  private async removeCacheBackups(ids: ReadonlySet<string>): Promise<void> {
    const storage = join(this.home, 'storages', 'session_projcache', 'sessions');
    const records = await entries(storage);
    if (!records.length) return;
    if (await realpath(storage) !== join(await realpath(this.home), 'storages', 'session_projcache', 'sessions'))
      throw new Error('Projection cache is outside the supported storage layout');
    for (const record of records) {
      const id = /^(.*?)\.json\.bak\..+$/.exec(record.name)?.[1];
      if (id && ids.has(id)) {
        if (!record.isFile()) throw new Error('Unexpected projection cache backup type');
        await rm(join(storage, record.name), { force: true });
      }
    }
  }
}
