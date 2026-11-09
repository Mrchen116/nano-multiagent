import { createHash } from 'node:crypto';
import { writeFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import { parentPort } from 'node:worker_threads';
import { decodeWorkEvent } from './work-event-codec.js';
import { projectWorkDetail, workDetailFields } from './work-detail-projection.js';
import { workDetailLimits } from './work-sync.js';
import type { WorkDetailJob } from './work-detail-worker.js';

const digest = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
// The byte limit alone allows millions of small values. Bound the number of
// arrays, objects and slots before V8 materializes them, while allowing large strings.
function canDecode(raw: Buffer): boolean {
  let inString = false, structure = 0;
  for (let i = 0; i < raw.length; i++) {
    const byte = raw[i];
    if (byte === 0x22) inString = !inString;
    else if (inString) { if (byte === 0x5c) i++; }
    else if ((byte === 0x7b || byte === 0x5b || byte === 0x2c || byte === 0x3a) && ++structure > workDetailLimits.structureTokens) return false;
  }
  return true;
}

const decode = (raw: Buffer) => decodeWorkEvent(JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw))).event;

function localProjection(db: DatabaseSync, seq: number) {
  // New large entries already have bounded metadata. Legacy JSON stays in SQLite
  // while SQLite selects a bounded result for this worker.
  const stored = db.prepare('SELECT projection FROM work_detail_local WHERE seq=?').get(seq);
  if (stored) {
    return JSON.parse(String(stored.projection));
  } else {
    const fields = ['seq', 'event_id', 'root_agent_id', 'session_id', 'turn_id', 'observed_at', 'type'];
    const keys = [...fields, ...workDetailFields];
    const columns = keys.map((key, i) => {
      const path = key === 'seq' ? '$.seq' : i < fields.length ? '$.' + key : '$.payload.' + key;
      const value = `json_extract(event,'${path}')`;
      return `CASE json_type(event,'${path}') WHEN 'text' THEN json_quote(substr(${value},1,1025))
        WHEN 'array' THEN CASE WHEN octet_length(${value})<1024 THEN ${value} END
        WHEN 'object' THEN CASE WHEN octet_length(${value})<1024 THEN ${value} END
        WHEN 'true' THEN 'true' WHEN 'false' THEN 'false' WHEN 'null' THEN 'null'
        ELSE json_quote(${value}) END AS "${key}"`;
    });
    const row = db.prepare(`SELECT ${columns.join(',')} FROM journal WHERE seq=?`).get(seq)!;
    const payload = Object.fromEntries(workDetailFields.filter(key => row[key] != null).map(key => [key, JSON.parse(String(row[key]))]));
    const event = Object.fromEntries(fields.filter(key => row[key] != null).map(key => [key, JSON.parse(String(row[key]))]));
    return projectWorkDetail(decodeWorkEvent({...event, payload}).event);
  }
}

parentPort?.on('message', (job: WorkDetailJob) => {
  let db: DatabaseSync | undefined;
  try {
    db = new DatabaseSync(job.dbPath, { readOnly: true });
    db.exec('PRAGMA busy_timeout=1000');
    if (job.kind === 'verify') {
      const raw = Buffer.allocUnsafe(job.totalBytes);
      const part = db.prepare('SELECT bytes FROM work_detail_parts WHERE manifest_id=? AND offset=?');
      for (let offset = 0; offset < raw.length; offset += workDetailLimits.chunkBytes) {
        const bytes = part.get(job.id, offset)?.bytes as Uint8Array | undefined;
        if (!bytes || bytes.length !== Math.min(workDetailLimits.chunkBytes, raw.length - offset)) throw new Error('detail_parts_missing');
        raw.set(bytes, offset);
      }
      if (digest(raw) !== job.sha256) throw new Error('detail_hash_mismatch');
      if (!canDecode(raw)) throw new Error('detail_structure_limit');
      parentPort!.postMessage({ projection: projectWorkDetail(decode(raw)) });
    } else if (job.totalBytes <= workDetailLimits.maxBytes && !job.previewOnly) {
      const bytes = db.prepare('SELECT CAST(event AS BLOB) AS bytes FROM journal WHERE seq=?').get(job.seq)?.bytes as Uint8Array | undefined;
      if (!bytes || bytes.length !== job.totalBytes) throw new Error('detail_source_changed');
      const raw = Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      if (!canDecode(raw)) {
        parentPort!.postMessage({projection: localProjection(db, job.seq), sha256: null, resourceLimited: true});
        return;
      }
      const projection = projectWorkDetail(decode(raw));
      writeFileSync(job.tempPath, raw, { mode: 0o600 });
      parentPort!.postMessage({ projection, sha256: digest(raw) });
    } else {
      parentPort!.postMessage({projection: localProjection(db, job.seq), sha256: null,
        resourceLimited: job.previewOnly});
    }
  } catch (error) {
    parentPort!.postMessage({
      error: error instanceof Error ? error.message : String(error),
      retryable: typeof (error as {code?: string})?.code === 'string',
    });
  } finally { db?.close(); }
});
