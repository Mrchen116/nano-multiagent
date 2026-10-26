import { createHash, randomUUID } from 'node:crypto';
import { join } from 'node:path';
import { atomicWrite, locked, readText, safePath } from './files.js';

export interface PersonalMemoryBinding { ownerId: string; agentId: string; bindingId?: string }
/** Source metadata is resolved by the host; the store does not authorize IM access. */
export interface PersonalMemorySource {
  id: string; kind?: string; authorId?: string; subjectRef?: string; verified: boolean;
  conversationId?: string; createdAt?: string;
}
export interface PersonalMemoryRecord {
  id: string; revision: number; target: 'user' | 'memory'; kind: string; subject_ref: string;
  domain?: string; applicability?: string; content: string; certainty: string;
  valid_from?: string; valid_until?: string; source_refs: PersonalMemorySource[];
  status: 'active' | 'retracted'; created_at: string; updated_at: string; author_session_id: string;
}
interface WriteFields { idempotency_key: string; expected_scope_revision?: number }
interface MemoryFields {
  target?: 'user' | 'memory'; kind: string; subject_ref: string; domain?: string; applicability?: string;
  content: string; certainty: string; valid_from?: string; valid_until?: string; source_refs: string[];
}
export type PersonalMemoryChange =
  | ({ action: 'upsert'; id?: string; expected_revision?: number } & MemoryFields & WriteFields)
  | ({ action: 'retract' | 'forget'; id: string; expected_revision: number } & WriteFields)
  | ({ action: 'migrate' } & WriteFields)
  | ({ action: 'add' | 'replace' | 'remove'; target: 'user' | 'memory'; content?: string; old_text?: string } & WriteFields)
  | { action: 'get'; id: string }
  | { action: 'search'; query?: string; subject_ref?: string; domain?: string; kind?: string; applicability?: string; cursor?: string; limit?: number };
export interface PersonalMemoryContext {
  sessionId: string; sources?: PersonalMemorySource[]; expectedScopeRevision?: number; signal?: AbortSignal;
}
export interface PersonalMemoryReceipt {
  success: true; action: string; revision: number; record_id?: string; record_revision?: number;
  status: 'complete' | 'pending' | 'invalidated'; projection: 'complete' | 'pending';
  cleanup?: { records: 'complete'; contexts: 'complete' | 'pending'; notes: 'complete' | 'pending'; history: 'complete' | 'pending' };
  idempotency_key: string; outside_scope?: string[];
}
export interface PersonalMemoryFence { id: string; revision: number; timestamp: string }
export interface PersonalMemorySnapshot {
  mode: 'legacy' | 'records'; revision: number; records: PersonalMemoryRecord[];
  projections: { user: string; memory: string }; pendingForgets: PersonalMemoryReceipt[]; forgetFence?: PersonalMemoryFence;
}
export interface PersonalMemoryQueryResult {
  revision: number; records: PersonalMemoryRecord[]; next_cursor: string | null;
}
interface Tombstone { record_id: string; content_hash: string; source_ids: string[]; timestamp: string; forgotten: boolean }
interface SavedReceipt { request_hash: string; value: PersonalMemoryReceipt }
interface MemoryState {
  schema_version: 1; binding: PersonalMemoryBinding; revision: number; records: PersonalMemoryRecord[];
  tombstones: Tombstone[]; receipts: Record<string, SavedReceipt>; forgetFence?: PersonalMemoryFence;
}
const limits = { user: 1375, memory: 2200 };
const delimiter = '\n§\n';
const hash = (value: string) => createHash('sha256').update(value).digest('hex');
const contentHash = (content: string) => hash(content.normalize('NFKC').trim().replace(/\s+/g, ' '));
const canonical = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.entries(value).filter(([, value]) => value !== undefined).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`).join(',')}}`;
  return JSON.stringify(value);
};
const current = (record: PersonalMemoryRecord, now: number) => record.status === 'active'
  && (!record.valid_from || Date.parse(record.valid_from) <= now) && (!record.valid_until || Date.parse(record.valid_until) > now);

/** Owns PA records, serialization, migration and projections in one locked transaction boundary. */
export class PersonalMemoryStore {
  readonly memoryRoot: string;
  readonly recordsPath: string;
  constructor(readonly workspace: string, readonly binding: PersonalMemoryBinding) {
    if (!binding.ownerId || !binding.agentId) throw new Error('Personal memory needs an owner scope');
    this.memoryRoot = join(workspace, '.nanoassistant', 'memory');
    this.recordsPath = join(this.memoryRoot, 'records.json');
  }

  /** Read the authority and repair disposable projections. Legacy reads never migrate files. */
  async snapshot(): Promise<PersonalMemorySnapshot> {
    return this.transaction(async () => {
      const state = await this.read();
      if (!state) return { mode: 'legacy', revision: 0, records: [], projections: await this.legacy(), pendingForgets: [] };
      const projections = this.project(state);
      await this.writeProjections(projections);
      return { mode: 'records', revision: state.revision, records: state.records, projections,
        pendingForgets: Object.values(state.receipts).map(receipt => receipt.value).filter(receipt => receipt.action === 'forget' && receipt.status === 'pending'),
        forgetFence: state.forgetFence };
    });
  }

  /** Query current records without loading expired or retracted bodies into the model. */
  async search(query: Extract<PersonalMemoryChange, { action: 'search' }>): Promise<PersonalMemoryQueryResult> {
    return this.transaction(async () => this.query(await this.read(), query));
  }

  /** Read an active, currently valid record by stable ID. */
  async get(id: string): Promise<PersonalMemoryQueryResult> {
    return this.transaction(async () => this.query(await this.read(), { action: 'get', id }));
  }

  /** Apply a host-authorized change. Sources and expected maintenance revision come from the caller. */
  async execute(change: PersonalMemoryChange, context: PersonalMemoryContext): Promise<PersonalMemoryReceipt | PersonalMemoryQueryResult> {
    if (change.action === 'search') return this.search(change);
    if (change.action === 'get') return this.get(change.id);
    return this.transaction(async () => {
      let state = await this.read();
      const key = change.idempotency_key?.trim();
      if (!key) throw new Error('Memory writes require an idempotency key');
      const requestHash = hash(canonical(change));
      const saved = state?.receipts[hash(key)];
      if (saved) {
        if (saved.request_hash !== requestHash) throw new Error('Idempotency key already used with different input');
        const projection = await this.writeProjections(this.project(state!));
        if (saved.value.projection !== projection) {
          saved.value.projection = projection; this.finishReceipt(saved.value);
          await this.commit(state!, context.signal);
        }
        return saved.value;
      }
      const expectedScope = context.expectedScopeRevision ?? change.expected_scope_revision;
      if (expectedScope !== undefined && expectedScope !== (state?.revision ?? 0)) throw new Error('Memory scope revision conflict; read current memory again');
      if (!state) {
        const legacy = await this.legacy();
        if (change.action !== 'migrate' && (legacy.user.trim() || legacy.memory.trim())) throw new Error('Explicit memory migration required');
        state = { schema_version: 1, binding: { ...this.binding }, revision: 0, records: [], tombstones: [], receipts: {} };
        if (change.action === 'migrate') await this.migrate(state, legacy, context);
      }
      const now = new Date().toISOString();
      const receipt: PersonalMemoryReceipt = { success: true, action: change.action, revision: state.revision + 1,
        status: 'pending', projection: 'pending', idempotency_key: key };
      if (change.action !== 'migrate') this.apply(state, change, context, receipt, now);
      state.revision++;
      state.receipts[hash(key)] = { request_hash: requestHash, value: receipt };
      await this.commit(state, context.signal);
      receipt.projection = await this.writeProjections(this.project(state));
      this.finishReceipt(receipt);
      // A second authority write records projection outcome; retry is safe after either rename.
      await this.commit(state);
      return receipt;
    }, context.signal);
  }

  /** Acknowledge actual host cleanup. The durable fence remains even after all layers complete. */
  async completeForget(key: string, cleaned: { contexts: boolean; notes: boolean; history: boolean }): Promise<PersonalMemoryReceipt> {
    return this.transaction(async () => {
      const state = await this.read(); const receipt = state?.receipts[hash(key)]?.value;
      if (!state || receipt?.action !== 'forget' || !receipt.cleanup) throw new Error('Forget receipt not found');
      for (const layer of ['contexts', 'notes', 'history'] as const) if (cleaned[layer]) receipt.cleanup[layer] = 'complete';
      receipt.projection = await this.writeProjections(this.project(state));
      this.finishReceipt(receipt); await this.commit(state); return receipt;
    });
  }

  private async transaction<T>(action: () => Promise<T>, signal?: AbortSignal): Promise<T> {
    await safePath(this.workspace, this.memoryRoot);
    return locked(this.memoryRoot, action, signal);
  }
  private async read(): Promise<MemoryState | undefined> {
    await safePath(this.workspace, this.recordsPath);
    const text = await readText(this.recordsPath); if (!text) return undefined;
    const state = JSON.parse(text) as MemoryState;
    if (state.schema_version !== 1 || !Array.isArray(state.records) || !Array.isArray(state.tombstones) || !state.receipts || !Number.isInteger(state.revision)) throw new Error('Unsupported personal memory schema');
    if (canonical(state.binding) !== canonical(this.binding)) throw new Error('Personal memory owner/binding scope mismatch');
    return state;
  }
  private async legacy() {
    const values = await Promise.all((['user', 'memory'] as const).map(async target => {
      const path = join(this.memoryRoot, target === 'user' ? 'USER.md' : 'MEMORY.md');
      await safePath(this.workspace, path); return readText(path);
    }));
    return { user: values[0]!, memory: values[1]! };
  }
  private async commit(state: MemoryState, signal?: AbortSignal) { await atomicWrite(this.recordsPath, `${JSON.stringify(state, null, 2)}\n`, signal); }
  private project(state: MemoryState) {
    const result = { user: '', memory: '' }; const now = Date.now();
    for (const target of ['user', 'memory'] as const) {
      const entries = state.records.filter(record => record.target === target && current(record, now))
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at) || a.id.localeCompare(b.id))
        .map(record => `[${record.id} r${record.revision}; ${record.certainty}; subject=${record.subject_ref}${record.domain ? `; domain=${record.domain}` : ''}${record.applicability ? `; when=${record.applicability}` : ''}] ${record.content}`);
      result[target] = [...entries.join(delimiter)].slice(0, limits[target]).join('');
    }
    return result;
  }
  private async writeProjections(projections: { user: string; memory: string }): Promise<'complete' | 'pending'> {
    try {
      for (const target of ['user', 'memory'] as const) {
        const path = join(this.memoryRoot, target === 'user' ? 'USER.md' : 'MEMORY.md');
        await safePath(this.workspace, path); await atomicWrite(path, projections[target]);
      }
      return 'complete';
    } catch { return 'pending'; }
  }
  private finishReceipt(receipt: PersonalMemoryReceipt) {
    if (receipt.status === 'invalidated') return;
    receipt.status = receipt.projection === 'complete' && (!receipt.cleanup || Object.values(receipt.cleanup).every(value => value === 'complete')) ? 'complete' : 'pending';
  }
  private query(state: MemoryState | undefined, query: Extract<PersonalMemoryChange, { action: 'search' | 'get' }>): PersonalMemoryQueryResult {
    if (!state) return { revision: 0, records: [], next_cursor: null };
    let records = state.records.filter(record => current(record, Date.now()));
    if (query.action === 'get') return { revision: state.revision, records: records.filter(record => record.id === query.id), next_cursor: null };
    for (const key of ['subject_ref', 'domain', 'kind', 'applicability'] as const) if (query[key]) records = records.filter(record => record[key] === query[key]);
    if (query.query?.trim()) {
      const words = query.query.toLocaleLowerCase().trim().split(/\s+/);
      records = records.filter(record => words.every(word => `${record.content} ${record.domain ?? ''} ${record.applicability ?? ''}`.toLocaleLowerCase().includes(word)));
    }
    records.sort((a, b) => a.id.localeCompare(b.id));
    let offset = 0;
    if (query.cursor) {
      const match = /^(\d+):(\d+)$/.exec(query.cursor);
      if (!match || Number(match[1]) !== state.revision) throw new Error('Memory search cursor revision conflict');
      offset = Number(match[2]);
    }
    const limit = Math.min(50, Math.max(1, Math.floor(query.limit ?? 10)));
    return { revision: state.revision, records: records.slice(offset, offset + limit).map(record => ({ ...record, content: [...record.content].slice(0, 400).join('') })),
      next_cursor: offset + limit < records.length ? `${state.revision}:${offset + limit}` : null };
  }
  private apply(state: MemoryState, original: Exclude<PersonalMemoryChange, { action: 'search' | 'get' | 'migrate' }>, context: PersonalMemoryContext, receipt: PersonalMemoryReceipt, now: string) {
    let change = original;
    if (change.action === 'add' || change.action === 'replace' || change.action === 'remove') {
      const legacy = change;
      const existing = legacy.action === 'add' ? [] : state.records.filter(record => record.status === 'active' && record.target === legacy.target && !!legacy.old_text && record.content.includes(legacy.old_text));
      if (change.action !== 'add' && existing.length !== 1) throw new Error('Legacy memory update must match exactly one record uniquely');
      const record = existing[0];
      if (change.action === 'remove') change = { action: 'retract', id: record!.id, expected_revision: record!.revision, idempotency_key: change.idempotency_key };
      else change = { action: 'upsert', id: record?.id, expected_revision: record?.revision, idempotency_key: change.idempotency_key,
        target: change.target, content: change.content ?? '', kind: record?.kind ?? 'fact', subject_ref: record?.subject_ref ?? this.binding.ownerId,
        domain: record?.domain, applicability: record?.applicability, certainty: record?.certainty ?? 'reported', source_refs: context.sources?.map(source => source.id) ?? [] };
    }
    if (change.action !== 'upsert' && change.action !== 'retract' && change.action !== 'forget') throw new Error('Unknown personal memory action');
    const record = change.id ? state.records.find(record => record.id === change.id) : undefined;
    if (change.id && (!record || record.revision !== change.expected_revision)) throw new Error('Memory record revision conflict; read current memory again');
    if (record && record.status !== 'active' && change.action !== 'forget') throw new Error('Memory record is retracted');
    if (change.action === 'upsert') {
      if (!change.content.trim() || !change.kind || !change.subject_ref || !change.certainty || (change.target && !(change.target in limits))) throw new Error('Memory content, kind, subject and certainty are required');
      for (const date of [change.valid_from, change.valid_until]) if (date && !Number.isFinite(Date.parse(date))) throw new Error('Invalid memory validity timestamp');
      if (change.valid_from && change.valid_until && Date.parse(change.valid_until) <= Date.parse(change.valid_from)) throw new Error('Invalid memory validity interval');
      const sources = change.source_refs.map(id => context.sources?.find(source => source.id === id));
      if (!sources.length || sources.some(source => !source?.verified)) throw new Error('Memory upsert requires verified current sources');
      const content = change.content.trim();
      if (state.tombstones.some(tombstone => tombstone.content_hash === contentHash(content) || tombstone.forgotten && sources.some(source => tombstone.source_ids.includes(source!.id)))) throw new Error('Memory source/content was forgotten or superseded; replay refused');
      if (record && contentHash(record.content) !== contentHash(content)) this.tombstone(state, record, now, false);
      const next: PersonalMemoryRecord = { id: record?.id ?? randomUUID(), revision: (record?.revision ?? 0) + 1, target: change.target ?? record?.target ?? 'memory',
        kind: change.kind, subject_ref: change.subject_ref, domain: change.domain, applicability: change.applicability, content, certainty: change.certainty,
        valid_from: change.valid_from, valid_until: change.valid_until, source_refs: sources as PersonalMemorySource[], status: 'active',
        created_at: record?.created_at ?? now, updated_at: now, author_session_id: context.sessionId };
      if (record) state.records[state.records.indexOf(record)] = next; else state.records.push(next);
      receipt.record_id = next.id; receipt.record_revision = next.revision;
    } else {
      if (!record) throw new Error('Memory record not found');
      this.tombstone(state, record, now, change.action === 'forget');
      receipt.record_id = record.id; receipt.record_revision = record.revision + 1;
      if (change.action === 'retract') { record.status = 'retracted'; record.revision++; record.updated_at = now; }
      else {
        // Remove every copy tied to this fact, including old revisions of corrected records.
        const related = state.tombstones.filter(tombstone => tombstone.record_id === record.id);
        for (const tombstone of related) tombstone.forgotten = true;
        const removedIds = new Set(state.records.filter(item => item.id === record.id || related.some(tombstone => tombstone.content_hash === contentHash(item.content))).map(item => item.id));
        for (const item of state.records) if (removedIds.has(item.id) && item.id !== record.id) this.tombstone(state, item, now, true);
        state.records = state.records.filter(item => !removedIds.has(item.id));
        for (const saved of Object.values(state.receipts)) if (saved.value.record_id && removedIds.has(saved.value.record_id)) saved.value.status = 'invalidated';
        state.forgetFence = { id: randomUUID(), revision: state.revision + 1, timestamp: now };
        receipt.status = 'pending'; receipt.cleanup = { records: 'complete', contexts: 'pending', notes: 'pending', history: 'pending' };
        receipt.outside_scope = ['Original IM messages', 'Independent audit records and backups'];
      }
    }
  }
  private tombstone(state: MemoryState, record: PersonalMemoryRecord, now: string, forgotten: boolean) {
    state.tombstones.push({ record_id: record.id, content_hash: contentHash(record.content), source_ids: record.source_refs.map(source => source.id), timestamp: now, forgotten });
  }
  private async migrate(state: MemoryState, legacy: { user: string; memory: string }, context: PersonalMemoryContext) {
    const now = new Date().toISOString();
    for (const target of ['user', 'memory'] as const) {
      const path = join(this.memoryRoot, 'legacy-backup', target === 'user' ? 'USER.md' : 'MEMORY.md');
      await safePath(this.workspace, path);
      const backup = await readText(path);
      if (backup && backup !== legacy[target]) throw new Error('Legacy migration backup differs; resolve before retrying');
      await atomicWrite(path, legacy[target], context.signal);
      for (const [index, entry] of legacy[target].split(delimiter).entries()) {
        const content = entry.replace(/\n?<!-- source:[\s\S]*?-->/g, '').trim(); if (!content) continue;
        const id = `legacy-${hash(`${target}:${index}:${entry}`).slice(0, 24)}`;
        state.records.push({ id, revision: 1, target, kind: 'legacy', subject_ref: this.binding.ownerId, content, certainty: 'legacy_unverified',
          source_refs: [{ id, kind: 'legacy_unverified', verified: false }], status: 'active', created_at: now, updated_at: now, author_session_id: context.sessionId });
      }
    }
  }
}
