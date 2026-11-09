import { createHash } from 'node:crypto';
import { workDetailLimits as limits, workSyncLimits, workRedactedType, type WorkDetailManifest,
  type WorkDetailProgress, type WorkJournalEvent, workObject } from '@nano/product-contracts';
import { WorkDetailWorker } from '@nano/product-contracts/work-detail-worker';
import { all, fail, one, transaction, type ImContext } from './context.js';
import { agentAvailable, ownerAccount, accountEnabled, type RuntimeIdentity } from './identity.js';
import { readWorkBatch } from './work.js';
import { workRedaction } from './work-records.js';

const hash = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');
const digest = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const active = "state IN ('uploading','verifying')";
interface ManifestRow {
  id: number; owner_id: string; node_id: string; node_epoch: number; journal_id: string;
  seq: number; event_id: string; root_agent_id: string; session_id: string; turn_id: string | null;
  total_bytes: number; sha256: string; projection_hash: string; offset: number;
  state: WorkDetailProgress['state']; revision: number | null; updated_at: number;
}

/** Store and resume bounded original Work details alongside the shared journal. */
export class WorkDetailSync {
  private readonly worker = new WorkDetailWorker();
  private verifying = false;
  private closed = false;
  private sweepTimer: NodeJS.Timeout;
  private get db() { return this.ctx.db; }

  constructor(private readonly ctx: ImContext, private readonly logError: (error: unknown) => void) {
    this.cleanup();
    this.scheduleVerification();
    this.sweepTimer = setInterval(() => {
      try { this.cleanup(); this.scheduleVerification(); } catch (error) { this.logError(error); }
    }, 10_000).unref();
  }

  async close(): Promise<void> {
    this.closed = true;
    clearInterval(this.sweepTimer);
    await this.worker.close();
  }

  begin(identity: RuntimeIdentity, journal: string, seq: number, input: unknown): WorkDetailProgress | undefined {
    if (workObject(input) && input.resume === true) return this.resume(identity, journal, seq, input);
    if (!workObject(input) || !Number.isSafeInteger(input.total_bytes) || Number(input.total_bytes) <= workSyncLimits.eventMaxBytes ||
      typeof input.allow_defer !== 'boolean' || (Number(input.total_bytes) <= limits.maxBytes ? !digest(input.sha256) : input.sha256 !== null) ||
      Buffer.byteLength(JSON.stringify(input.projection ?? null)) > limits.projectionBytes) fail(400, 'invalid_detail_manifest');
    const {total_bytes, sha256, allow_defer} = input as unknown as WorkDetailManifest & {allow_defer: boolean};
    const [event] = readWorkBatch({journal_id: journal, from_seq: seq, events: [input.projection]}).events;
    if (!event || event.seq !== seq || event.event_id.length > 300 || event.payload.large_detail_preview !== true ||
      event.type === workRedactedType) fail(400, 'invalid_detail_manifest');
    const node = identity.node_id, owner = identity.owner_id, epoch = identity.node_epoch;
    const through = this.through(node, journal);
    if (seq > through + 1) return;
    const removed = workRedaction(this.db, node, journal, seq, event.event_id, event.root_agent_id);
    if (removed) {
      this.append(identity, journal, {...event, type: workRedactedType, payload: {}});
      return {state: 'discarded', offset: 0};
    }
    const profile = this.profile(identity, event.root_agent_id);
    const old = this.manifest(node, journal, seq);
    const projectionHash = hash(JSON.stringify(event));
    if (old) {
      if (old.owner_id !== owner || old.event_id !== event.event_id || old.total_bytes !== total_bytes ||
          old.sha256 !== sha256 || old.projection_hash !== projectionHash) fail(409, 'event_identity_conflict');
      if (old.state === 'complete' || old.state === 'local') return this.progress(old);
      if (old.node_epoch !== epoch) {
        if (old.revision !== null) return {state: 'discarded', offset: 0};
        this.db.prepare('DELETE FROM work_detail_uploads WHERE id=?').run(old.id);
        return this.begin(identity, journal, seq, input);
      }
      return this.progress(old);
    }
    if (seq <= through) {
      // Only a prior metadata-only advance legitimately has neither event nor receipt.
      if (one(this.db, 'SELECT 1 FROM agent_work_events WHERE (node_id=? AND journal_id=? AND seq=?) OR event_id=?', node, journal, seq, event.event_id))
        fail(409, 'event_identity_conflict');
      return {state: 'discarded', offset: 0};
    }
    if (one(this.db, 'SELECT 1 FROM work_sync_uploads WHERE node_id=? AND journal_id=? AND seq=?', node, journal, seq))
      fail(409, 'event_identity_conflict');
    if (one(this.db, 'SELECT 1 FROM work_detail_uploads WHERE event_id=?', event.event_id)) fail(409, 'event_identity_conflict');
    if (!agentAvailable(this.db, profile)) {
      this.append(identity, journal, event);
      return {state: 'discarded', offset: 0};
    }
    const insert = (state: string, revision: number | null) => this.db.prepare(`INSERT INTO work_detail_uploads
      (owner_id,node_id,node_epoch,journal_id,seq,event_id,root_agent_id,session_id,turn_id,total_bytes,sha256,projection_hash,updated_at,state,revision)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(owner, node, epoch, journal, seq, event.event_id, event.root_agent_id,
      event.session_id, event.turn_id ?? null, total_bytes, sha256, projectionHash, Date.now(), state, revision);
    if (sha256 && this.canReserve(identity, total_bytes)) {
      insert('uploading', null);
      return {state: 'uploading', offset: 0};
    }
    if (!allow_defer) return {state: 'pending', offset: 0};
    const state = sha256 ? 'pending' : 'local';
    this.append(identity, journal, event, () => {
      const revision = this.revision(node, journal, event);
      if (revision !== undefined) insert(state, revision);
    });
    return {state, offset: 0};
  }

  private resume(identity: RuntimeIdentity, journal: string, seq: number, input: Record<string, unknown>): WorkDetailProgress {
    if (typeof input.event_id !== 'string' || !digest(input.sha256)) fail(400, 'invalid_detail_manifest');
    const row = this.manifest(identity.node_id, journal, seq);
    if (!row || row.node_epoch !== identity.node_epoch) return {state: 'discarded', offset: 0};
    if (row.owner_id !== identity.owner_id || row.event_id !== input.event_id || row.sha256 !== input.sha256)
      fail(409, 'event_identity_conflict');
    if (workRedaction(this.db, row.node_id, journal, seq, row.event_id, row.root_agent_id)) return {state: 'discarded', offset: 0};
    const profile = this.profile(identity, row.root_agent_id);
    if (row.state !== 'pending' || !agentAvailable(this.db, profile) || !this.canReserve(identity, row.total_bytes)) return this.progress(row);
    this.db.prepare("UPDATE work_detail_uploads SET state='uploading',updated_at=? WHERE id=?").run(Date.now(), row.id);
    return {state: 'uploading', offset: 0};
  }

  put(identity: RuntimeIdentity, journal: string, seq: number, offset: number, input: unknown): WorkDetailProgress {
    const row = this.manifest(identity.node_id, journal, seq);
    if (!row || row.owner_id !== identity.owner_id || row.node_epoch !== identity.node_epoch) fail(409, 'detail_not_started');
    const removed = workRedaction(this.db, row.node_id, journal, seq, row.event_id, row.root_agent_id);
    if (removed) return {state: 'discarded', offset: 0};
    const profile = this.profile(identity, row.root_agent_id);
    if (!agentAvailable(this.db, profile) && (row.state === 'uploading' || row.state === 'verifying')) {
      this.reset(row, 'pending');
      if (row.revision !== null) return {state: 'pending', offset: 0};
      fail(429, 'work_detail_scope_changed');
    }
    if (row.state === 'pending' || row.state === 'local' || row.state === 'rejected') return this.progress(row);
    if (!workObject(input) || !digest(input.sha256) || !Number.isSafeInteger(offset) || offset < 0 ||
      offset % limits.chunkBytes !== 0 || offset >= row.total_bytes || typeof input.data !== 'string') fail(400, 'invalid_detail_part');
    const size = Math.min(limits.chunkBytes, row.total_bytes - offset);
    const bytes = Buffer.from(input.data, 'base64');
    if (bytes.length !== size || bytes.toString('base64') !== input.data || hash(bytes) !== input.sha256) fail(400, 'part_hash_mismatch');
    if (offset < row.offset) {
      if (one(this.db, 'SELECT sha256 FROM work_detail_parts WHERE manifest_id=? AND offset=?', row.id, offset)?.sha256 !== input.sha256)
        fail(409, 'part_identity_conflict');
      return this.progress(row);
    }
    if (row.state !== 'uploading' || offset !== row.offset) return this.progress(row);
    const next = offset + size, state = next === row.total_bytes ? 'verifying' : 'uploading';
    transaction(this.db, () => {
      this.db.prepare('INSERT INTO work_detail_parts VALUES(?,?,?,?)').run(row.id, offset, input.sha256 as string, bytes);
      this.db.prepare('UPDATE work_detail_uploads SET offset=?,state=?,updated_at=? WHERE id=?').run(next, state, Date.now(), row.id);
    });
    if (state === 'verifying') this.scheduleVerification();
    return {state, offset: next};
  }

  private progress(row: ManifestRow): WorkDetailProgress { return {state: row.state, offset: row.offset}; }
  private through(node: string, journal: string): number {
    return one(this.db, 'SELECT through_seq FROM agent_work_journals WHERE node_id=? AND journal_id=?', node, journal)?.through_seq ?? 0;
  }
  private manifest(node: string, journal: string, seq: number): ManifestRow | undefined {
    return one(this.db, 'SELECT * FROM work_detail_uploads WHERE node_id=? AND journal_id=? AND seq=?', node, journal, seq) as ManifestRow | undefined;
  }
  private findProfile(identity: RuntimeIdentity, root: string) {
    return one(this.db, `SELECT * FROM agent_profiles p WHERE p.agent_id=? AND node_id=? AND owner_id=?
      AND work_mode='global' AND is_stale=0 AND NOT EXISTS (SELECT 1 FROM agent_deletions d WHERE d.agent_id=p.agent_id)`,
      root, identity.node_id, identity.owner_id);
  }
  private profile(identity: RuntimeIdentity, root: string) {
    const profile = this.findProfile(identity, root);
    if (!profile) fail(403, 'scope_not_allowed');
    return profile;
  }
  private binding(row: ManifestRow): boolean {
    return accountEnabled(ownerAccount(this.db, row.owner_id)) && !!one(this.db, `SELECT 1 FROM node_binding_state b
      JOIN nodes n ON n.node_id=b.node_id AND n.owner_id=b.owner_id
      WHERE b.node_id=? AND b.owner_id=? AND b.node_epoch=? AND b.runtime_token_hash IS NOT NULL`, row.node_id, row.owner_id, row.node_epoch);
  }
  private canReserve(identity: RuntimeIdentity, totalBytes: number): boolean {
    if (one(this.db, `SELECT 1 FROM work_detail_uploads WHERE node_id=? AND ${active}`, identity.node_id)) return false;
    const staged = one(this.db, `SELECT COALESCE(SUM(total_bytes),0) AS bytes FROM work_detail_uploads WHERE ${active}`)!.bytes;
    const retained = one(this.db, "SELECT COALESCE(SUM(total_bytes),0) AS bytes FROM work_detail_uploads WHERE state='complete'")!.bytes;
    return totalBytes + staged <= limits.stagingBytes && totalBytes + staged + retained <= limits.retainedBytes;
  }
  private revision(node: string, journal: string, event: WorkJournalEvent): number | undefined {
    return one(this.db, 'SELECT revision FROM agent_work_events WHERE node_id=? AND journal_id=? AND seq=? AND event_id=?',
      node, journal, event.seq, event.event_id)?.revision;
  }
  private append(identity: RuntimeIdentity, journal: string, event: WorkJournalEvent, commit?: () => void) {
    this.ctx.gateway.work.append(identity.node_id, {journal_id: journal, from_seq: event.seq, events: [event]}, true, commit);
  }
  private reset(row: ManifestRow, state: 'pending' | 'rejected'): void {
    transaction(this.db, () => {
      if (row.revision === null && state === 'pending') {
        this.db.prepare('DELETE FROM work_detail_uploads WHERE id=?').run(row.id);
      } else {
        this.db.prepare('DELETE FROM work_detail_parts WHERE manifest_id=?').run(row.id);
        this.db.prepare('UPDATE work_detail_uploads SET offset=0,state=?,updated_at=? WHERE id=?').run(state, Date.now(), row.id);
      }
    });
  }
  private cleanup(): void {
    for (const row of all(this.db, `SELECT * FROM work_detail_uploads WHERE ${active}`) as ManifestRow[]) {
      const old = row.state === 'uploading' && row.updated_at < Date.now() - workSyncLimits.partialTtlMs;
      if (old || !this.binding(row) || !agentAvailable(this.db, this.findProfile(row, row.root_agent_id)))
        this.reset(row, 'pending');
    }
  }
  private scheduleVerification(): void {
    if (this.closed || this.verifying) return;
    this.verifying = true;
    setImmediate(() => void this.verifyNext().catch(this.logError).finally(() => { this.verifying = false; }));
  }
  private async verifyNext(): Promise<void> {
    while (!this.closed) {
      const row = one(this.db, "SELECT * FROM work_detail_uploads WHERE state='verifying' AND updated_at<=? ORDER BY updated_at,id LIMIT 1", Date.now()) as ManifestRow | undefined;
      if (!row) return;
      try {
        const result = await this.worker.run({kind: 'verify', dbPath: this.ctx.dbPath, id: row.id, totalBytes: row.total_bytes, sha256: row.sha256});
        if (this.closed) return;
        if (!one(this.db, "SELECT 1 FROM work_detail_uploads WHERE id=? AND state='verifying'", row.id)) continue;
        if (!this.binding(row)) { this.reset(row, 'pending'); continue; }
        if (workRedaction(this.db, row.node_id, row.journal_id, row.seq, row.event_id, row.root_agent_id)) {
          this.db.prepare('DELETE FROM work_detail_uploads WHERE id=?').run(row.id);
          continue;
        }
        const event = result.projection;
        if (event.seq !== row.seq || event.event_id !== row.event_id || event.root_agent_id !== row.root_agent_id ||
          event.session_id !== row.session_id || (event.turn_id ?? null) !== row.turn_id ||
          hash(JSON.stringify(event)) !== row.projection_hash) {
          this.reset(row, 'rejected');
          continue;
        }
        const profile = this.profile(row, event.root_agent_id);
        const complete = (revision: number) => this.db.prepare("UPDATE work_detail_uploads SET state='complete',revision=?,updated_at=? WHERE id=?")
          .run(revision, Date.now(), row.id);
        if (row.revision !== null) {
          if (!agentAvailable(this.db, profile)) { this.reset(row, 'pending'); continue; }
          // The initial transaction already validated the session and committed this exact projection.
          transaction(this.db, () => complete(row.revision!));
          this.ctx.gateway.work.notifyUpdated(row.root_agent_id);
        } else {
          if (this.through(row.node_id, row.journal_id) >= row.seq) { this.reset(row, 'pending'); continue; }
          this.append(row, row.journal_id, event, () => {
            const revision = this.revision(row.node_id, row.journal_id, event);
            if (revision === undefined) this.db.prepare('DELETE FROM work_detail_uploads WHERE id=?').run(row.id);
            else complete(revision);
          });
        }
      } catch (error) {
        if (this.closed) return;
        const current = one(this.db, "SELECT 1 FROM work_detail_uploads WHERE id=? AND state='verifying'", row.id);
        if (!current) continue;
        const code = error as {validation?: boolean; statusCode?: number};
        if (code.validation || (code.statusCode && code.statusCode < 500)) this.reset(row, 'rejected');
        else {
          this.logError(error);
          this.db.prepare('UPDATE work_detail_uploads SET updated_at=? WHERE id=?').run(Date.now() + 10_000, row.id);
        }
      }
    }
  }
}
