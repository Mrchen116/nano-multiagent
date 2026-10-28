import { createHash } from 'node:crypto';
import { closeSync, createReadStream, fsyncSync, mkdirSync, openSync, readdirSync } from 'node:fs';
import { open, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { workSyncLimits as limits, workSyncPrefix, type WorkSyncPart, type WorkSyncCursor, workObject } from '@nano/product-contracts';
import { all, one, fail, transaction, type ImContext, type Row } from './context.js';
import type { RuntimeIdentity } from './identity.js';
import { readWorkBatch } from './work.js';
import type { Connection } from './gateway.js';

const hash = (bytes: string | Buffer) => createHash('sha256').update(bytes).digest('hex');
const integer = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0;
const sha256 = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);

/** Authenticate the current durable machine binding independently of WebSocket state. */
export function authenticateWorkSync(ctx: ImContext, request: FastifyRequest): RuntimeIdentity {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.authorization ?? '')?.[1];
  const identity = token ? ctx.identity.authenticateRuntime(token) : null;
  if (!identity) fail(401, 'invalid_runtime_token');
  return identity;
}

/** Register bounded machine-only uploads into the existing atomic Work projection.
 *
 * Args:
 *   app: Center serving these three routes with the exact workSync auth flag.
 *   ctx: Existing center database and Work owner; no second event projection is created.
 */
export function registerWorkSyncRoutes(app: FastifyInstance, ctx: ImContext): void {
  const db = ctx.db, directory = `${ctx.dbPath}.work-sync`;
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const parent = openSync(dirname(directory), 'r');
  try { fsyncSync(parent); } finally { closeSync(parent); }
  db.exec(`CREATE TABLE IF NOT EXISTS work_sync_uploads (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, node_id TEXT NOT NULL, node_epoch INTEGER NOT NULL,
    journal_id TEXT NOT NULL, seq INTEGER NOT NULL, event_id TEXT NOT NULL, sha256 TEXT NOT NULL,
    total_bytes INTEGER NOT NULL, total_parts INTEGER NOT NULL, updated_at INTEGER NOT NULL,
    committed INTEGER NOT NULL DEFAULT 0);
    CREATE UNIQUE INDEX IF NOT EXISTS work_sync_one_pending ON work_sync_uploads(node_id) WHERE committed=0;
    CREATE INDEX IF NOT EXISTS work_sync_event ON work_sync_uploads(node_id,journal_id,seq);
    CREATE TABLE IF NOT EXISTS work_sync_parts (
      upload_id TEXT NOT NULL REFERENCES work_sync_uploads(id) ON DELETE CASCADE,
      part INTEGER NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(upload_id,part));
    DROP TRIGGER IF EXISTS work_sync_commit_insert;
    DROP TRIGGER IF EXISTS work_sync_commit_update;
    CREATE TRIGGER work_sync_commit_insert AFTER INSERT ON agent_work_journals BEGIN
      UPDATE work_sync_uploads SET committed=1 WHERE id=(SELECT id FROM work_sync_uploads WHERE node_id=NEW.node_id AND committed=0) AND journal_id=NEW.journal_id AND seq<=NEW.through_seq;
    END;
    CREATE TRIGGER work_sync_commit_update AFTER UPDATE OF through_seq ON agent_work_journals BEGIN
      UPDATE work_sync_uploads SET committed=1 WHERE id=(SELECT id FROM work_sync_uploads WHERE node_id=NEW.node_id AND committed=0) AND journal_id=NEW.journal_id AND seq<=NEW.through_seq;
    END;`);
  let active = 0;
  const activeNodes = new Set<string>(), leases = new WeakMap<FastifyRequest, string>(), handlers = new WeakSet<FastifyRequest>();
  const connections = new WeakMap<FastifyRequest, Connection>();
  const declarations = new WeakMap<FastifyRequest, { journal: string; produced: number; pending: boolean }>();
  const removals = new Set<Promise<void>>();
  const removeFiles = (id: string) => {
    const removal = rm(join(directory, id), { recursive: true, force: true }).catch(error => app.log.error(error));
    removals.add(removal); void removal.finally(() => removals.delete(removal));
  };
  const cleanup = () => {
    const abandoned = all(db, `SELECT u.* FROM work_sync_uploads u WHERE u.committed=0 AND
      (u.updated_at<? OR NOT EXISTS (SELECT 1 FROM node_binding_state b JOIN nodes n ON n.node_id=b.node_id AND n.owner_id=b.owner_id
       JOIN users a ON a.owner_id=b.owner_id AND (a.personal_space_enabled=1 OR a.membership_status='active')
       WHERE b.node_id=u.node_id AND b.owner_id=u.owner_id AND b.node_epoch=u.node_epoch AND b.runtime_token_hash IS NOT NULL))`, Date.now() - limits.partialTtlMs);
    for (const row of abandoned) {
      db.prepare('DELETE FROM work_sync_parts WHERE upload_id=?').run(row.id);
      db.prepare('DELETE FROM work_sync_uploads WHERE id=?').run(row.id);
      removeFiles(row.id);
    }
    for (const row of all(db, 'SELECT DISTINCT upload_id id FROM work_sync_parts p WHERE (SELECT committed FROM work_sync_uploads WHERE id=p.upload_id)=1')) {
      // Keep the small immutable hash receipt after deleting the unconfirmed bytes.
      db.prepare('DELETE FROM work_sync_parts WHERE upload_id=?').run(row.id);
      removeFiles(row.id);
    }
  };
  cleanup();
  const pendingIds = new Set(all(db, 'SELECT id FROM work_sync_uploads WHERE committed=0').map(row => row.id));
  for (const entry of readdirSync(directory)) if (!pendingIds.has(entry)) removeFiles(entry);
  app.addHook('onClose', async () => { await Promise.all(removals); });

  const through = (node: string, journal: string): number => one(db,
    'SELECT through_seq FROM agent_work_journals WHERE node_id=? AND journal_id=?', node, journal)?.through_seq ?? 0;
  const cursor = (identity: RuntimeIdentity, journal: string): WorkSyncCursor => {
    const seq = through(identity.node_id, journal);
    const pending = one(db, 'SELECT * FROM work_sync_uploads WHERE node_id=? AND owner_id=? AND node_epoch=? AND journal_id=? AND committed=0',
      identity.node_id, identity.owner_id, identity.node_epoch, journal);
    return { through_seq: seq, expected_seq: seq + 1, ...(pending ? { pending_event: {
      seq: pending.seq, event_id: pending.event_id, sha256: pending.sha256, total_parts: pending.total_parts,
      received_parts: all(db, 'SELECT part FROM work_sync_parts WHERE upload_id=? ORDER BY part', pending.id).map(row => row.part),
    } } : {}) };
  };
  const scope = (request: FastifyRequest) => {
    const identity = authenticateWorkSync(ctx, request), p = request.params as Row, journal = p.journal_id;
    if (typeof journal !== 'string' || !journal.length || journal.length > 200) fail(400, 'invalid_journal');
    const body = request.body as Row | undefined;
    if (body && ['node_id', 'owner_id', 'node_epoch'].some(key => key in body)) fail(400, 'invalid_arguments');
    const produced = request.headers['x-work-produced-seq'], pending = request.headers['x-work-processing-pending'];
    if (produced !== undefined || pending !== undefined) {
      if (typeof produced !== 'string' || !/^\d+$/.test(produced) || !integer(Number(produced)) || typeof pending !== 'string' || !['true', 'false'].includes(pending)) fail(400, 'invalid_work_progress');
      declarations.set(request, { journal, produced: Number(produced), pending: pending === 'true' });
    }
    return { identity, journal };
  };
  const release = (request: FastifyRequest) => {
    const node = leases.get(request);
    if (node !== undefined) { leases.delete(request); activeNodes.delete(node); active--; }
  };
  app.addHook('onRequestAbort', async request => { if (!handlers.has(request)) release(request); });
  const serve = (handler: (request: FastifyRequest) => Promise<unknown>) => async (request: FastifyRequest) => {
    handlers.add(request);
    try {
      const result = await handler(request), connection = connections.get(request), report = declarations.get(request);
      if (connection && report) ctx.gateway.work.reportProgress(connection, report.journal, report.produced, report.pending);
      return result;
    } finally { handlers.delete(request); release(request); }
  };
  const options = {
    config: { workSync: true }, bodyLimit: limits.requestMaxBytes,
    onRequest: async (request: FastifyRequest) => {
      const identity = authenticateWorkSync(ctx, request);
      const connection = ctx.gateway.nodes.get(identity.node_id);
      if (connection?.owner_id === identity.owner_id && connection.node_epoch === identity.node_epoch) connections.set(request, connection);
      if (active >= limits.globalConcurrency || activeNodes.has(identity.node_id))
        throw Object.assign(new Error('work_sync_busy'), { statusCode: 429, detail: 'work_sync_busy', retry_after: 1 });
      active++; activeNodes.add(identity.node_id); leases.set(request, identity.node_id); cleanup();
      await Promise.all(removals);
    },
    onResponse: async (request: FastifyRequest) => { release(request); },
  };
  const path = `${workSyncPrefix}/journals/:journal_id`;
  app.get(path, options, serve(async request => { const { identity, journal } = scope(request); return cursor(identity, journal); }));
  app.post(`${path}/events`, options, serve(async request => {
    const { identity, journal } = scope(request);
    const payload = readWorkBatch({...(workObject(request.body) ? request.body : {}), journal_id: journal});
    for (const event of payload.events) {
      const receipt = one(db, 'SELECT event_id,sha256 FROM work_sync_uploads WHERE node_id=? AND journal_id=? AND seq=? LIMIT 1', identity.node_id, journal, event.seq);
      if (receipt && (receipt.event_id !== event.event_id || receipt.sha256 !== hash(JSON.stringify(event)))) fail(409, 'event_identity_conflict');
    }
    const result = ctx.gateway.work.append(identity.node_id, { ...payload, journal_id: journal }, true);
    // Hash receipts keep chunk and batch retries on the same immutable event identity.
    transaction(db, () => {
      for (const event of payload.events.filter((event) => event.seq <= result.through_seq)) {
        const raw = JSON.stringify(event), digest = hash(raw);
        const id = hash(JSON.stringify([identity.owner_id, identity.node_id, identity.node_epoch, journal, event.seq, event.event_id, digest]));
        db.prepare('INSERT OR IGNORE INTO work_sync_uploads VALUES(?,?,?,?,?,?,?,?,?,?,?,1)').run(id, identity.owner_id, identity.node_id, identity.node_epoch,
          journal, event.seq, event.event_id, digest, Buffer.byteLength(raw), Math.ceil(Buffer.byteLength(raw) / limits.chunkBytes), Date.now());
      }
    });
    cleanup(); await new Promise<void>(resolve => setImmediate(resolve));
    return result;
  }));
  app.put(`${path}/events/:seq/parts/:part`, options, serve(async request => {
    const { identity, journal } = scope(request), p = request.params as Row;
    const seq = Number(p.seq), part = Number(p.part), payload = request.body as WorkSyncPart;
    if (!integer(seq) || seq < 1 || !integer(part) || !payload || typeof payload.event_id !== 'string' || !payload.event_id.length || payload.event_id.length > 300 ||
      !sha256(payload.sha256) || !sha256(payload.part_sha256) || !integer(payload.total_bytes) || payload.total_bytes < 1 || !integer(payload.total_parts)) fail(400, 'invalid_part');
    if (payload.total_bytes > limits.eventMaxBytes) fail(413, 'event_too_large');
    if (payload.total_parts !== Math.ceil(payload.total_bytes / limits.chunkBytes) || part >= payload.total_parts ||
      typeof payload.data !== 'string' || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(payload.data)) fail(400, 'invalid_part');
    const bytes = Buffer.from(payload.data, 'base64');
    const size = Math.min(limits.chunkBytes, payload.total_bytes - part * limits.chunkBytes);
    if (bytes.length !== size || hash(bytes) !== payload.part_sha256) fail(400, 'part_hash_mismatch');
    const committed = one(db, 'SELECT * FROM work_sync_uploads WHERE node_id=? AND journal_id=? AND seq=? AND committed=1 LIMIT 1', identity.node_id, journal, seq);
    if (committed) {
      if (committed.event_id !== payload.event_id || committed.sha256 !== payload.sha256 || committed.total_bytes !== payload.total_bytes || committed.total_parts !== payload.total_parts)
        fail(409, 'event_identity_conflict');
      return cursor(identity, journal);
    }
    const previous = through(identity.node_id, journal);
    if (seq > previous + 1) return cursor(identity, journal);
    if (seq <= previous) {
      const event = one(db, 'SELECT event_id FROM agent_work_events WHERE node_id=? AND journal_id=? AND seq=?', identity.node_id, journal, seq);
      if (event && event.event_id !== payload.event_id) fail(409, 'event_identity_conflict');
      return cursor(identity, journal);
    }
    const id = hash(JSON.stringify([identity.owner_id, identity.node_id, identity.node_epoch, journal, seq, payload.event_id, payload.sha256]));
    let upload = one(db, 'SELECT * FROM work_sync_uploads WHERE node_id=? AND committed=0', identity.node_id);
    if (upload && (upload.id !== id || upload.total_bytes !== payload.total_bytes || upload.total_parts !== payload.total_parts)) fail(409, 'event_identity_conflict');
    if (!upload) {
      const reserved = one(db, 'SELECT coalesce(sum(total_bytes),0) bytes FROM work_sync_uploads WHERE committed=0')!.bytes;
      if (payload.total_bytes > limits.nodeStagingBytes || reserved + payload.total_bytes > limits.globalStagingBytes)
        throw Object.assign(new Error('work_sync_quota'), { statusCode: 429, detail: 'work_sync_quota', retry_after: 1 });
      db.prepare('INSERT INTO work_sync_uploads VALUES(?,?,?,?,?,?,?,?,?,?,?,0)').run(id, identity.owner_id, identity.node_id, identity.node_epoch,
        journal, seq, payload.event_id, payload.sha256, payload.total_bytes, payload.total_parts, Date.now());
      upload = { id, ...payload };
    }
    const old = one(db, 'SELECT sha256 FROM work_sync_parts WHERE upload_id=? AND part=?', id, part);
    if (old && old.sha256 !== payload.part_sha256) fail(409, 'part_identity_conflict');
    if (!old) {
      const folder = join(directory, id); mkdirSync(folder, { recursive: true, mode: 0o700 });
      const directoryHandle = await open(directory, 'r');
      try { await directoryHandle.sync(); } finally { await directoryHandle.close(); }
      const file = await open(join(folder, String(part)), 'w', 0o600);
      try { await file.writeFile(bytes); await file.sync(); } finally { await file.close(); }
      const folderHandle = await open(folder, 'r');
      try { await folderHandle.sync(); } finally { await folderHandle.close(); }
      // A disk-full error above never creates a durable part receipt.
      db.prepare('INSERT INTO work_sync_parts VALUES(?,?,?)').run(id, part, payload.part_sha256);
      db.prepare('UPDATE work_sync_uploads SET updated_at=? WHERE id=?').run(Date.now(), id);
    }
    const count = one(db, 'SELECT count(*) count FROM work_sync_parts WHERE upload_id=?', id)!.count;
    if (count === payload.total_parts) {
      const digest = createHash('sha256'), raw = Buffer.allocUnsafe(payload.total_bytes);
      let offset = 0;
      for (let index = 0; index < payload.total_parts; index++) {
        for await (const block of createReadStream(join(directory, id, String(index)))) {
          const chunk = block as Buffer; digest.update(chunk); chunk.copy(raw, offset); offset += chunk.length;
        }
      }
      if (offset !== payload.total_bytes || digest.digest('hex') !== payload.sha256) fail(400, 'event_hash_mismatch');
      let event: unknown;
      try { event = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw)); } catch { fail(400, 'invalid_event'); }
      if (!workObject(event) || event.seq !== seq || event.event_id !== payload.event_id) fail(409, 'event_identity_conflict');
      const current = authenticateWorkSync(ctx, request);
      if (current.owner_id !== identity.owner_id || current.node_id !== identity.node_id || current.node_epoch !== identity.node_epoch) fail(401, 'invalid_runtime_token');
      ctx.gateway.work.append(identity.node_id, { journal_id: journal, from_seq: seq, events: [event] }, true);
      cleanup();
    }
    return cursor(identity, journal);
  }));
}
