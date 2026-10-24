import { createHash } from 'node:crypto';
import { workSyncLimits as limits, workSyncPrefix, type WorkSyncCursor, type WorkSyncPart } from '@nano/product-contracts';
import type { InboxStore } from './inbox.js';

interface Options {
  nodeId: string;
  inbox: InboxStore;
  url: string;
  credentials: () => string;
  available?: () => boolean;
  onError: (error: unknown) => void;
}
class SyncError extends Error {
  constructor(readonly code: string, readonly pause = false, readonly retryAfterMs = 0) { super(code); }
}
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

/** Own the recoverable Work stream without using or reconnecting the chat socket. */
export class WorkSync {
  private readonly base: URL;
  private started = false;
  private paused = false;
  private dirty = false;
  private task?: Promise<void>;
  private lifetime = new AbortController();
  private backoff = 1_000;

  constructor(private readonly options: Options) {
    this.base = new URL(options.url);
    if (this.base.protocol === 'ws:') this.base.protocol = 'http:';
    if (this.base.protocol === 'wss:') this.base.protocol = 'https:';
    if (!['http:', 'https:'].includes(this.base.protocol) || this.base.username || this.base.password) throw new Error('Invalid WorkSync URL');
  }

  /** Start background recovery; this method never waits for network delivery. */
  start(): void {
    if (this.started) return;
    this.started = true; this.paused = false; this.lifetime = new AbortController(); this.signal();
  }

  /** Notify the upload owner of durable local work or newly negotiated capability. */
  signal(): void {
    this.dirty = true;
    if (!this.started || this.paused || this.task || !(this.options.available?.() ?? true)) return;
    this.task = this.run().finally(() => {
      this.task = undefined;
      if (this.dirty && this.started && !this.paused && (this.options.available?.() ?? true)) this.signal();
    });
  }

  /** Cancel HTTP and backoff, leaving every unconfirmed source event intact. */
  async stop(): Promise<void> {
    this.started = false; this.dirty = false; this.lifetime.abort(); await this.task;
  }

  private async run(): Promise<void> {
    while (this.started && (this.options.available?.() ?? true)) {
      this.dirty = false;
      try {
        await this.synchronize();
        if (!this.dirty) return;
      } catch (error) {
        if (!this.started) return;
        this.options.onError(error);
        if (error instanceof SyncError && error.pause) { this.paused = true; return; }
        const wait = Math.max(error instanceof SyncError ? error.retryAfterMs : 0, Math.min(30_000, this.backoff * (0.8 + Math.random() * 0.4)));
        this.backoff = Math.min(30_000, this.backoff * 2);
        try { await this.delay(wait); } catch { return; }
        this.dirty = true;
      }
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve, reject) => {
      const aborted = () => { clearTimeout(timer); reject(this.lifetime.signal.reason); };
      const timer = setTimeout(() => { this.lifetime.signal.removeEventListener('abort', aborted); resolve(); }, ms);
      this.lifetime.signal.addEventListener('abort', aborted, { once: true });
      if (this.lifetime.signal.aborted) aborted();
    });
  }

  private async request(method: 'GET' | 'POST' | 'PUT', suffix = '', body?: unknown): Promise<WorkSyncCursor> {
    const path = `${workSyncPrefix}/journals/${encodeURIComponent(this.options.inbox.journalId)}${suffix}`;
    const text = body === undefined ? undefined : JSON.stringify(body);
    if (text !== undefined && Buffer.byteLength(text) > limits.requestMaxBytes) throw new SyncError('work_sync_request_too_large', true);
    const response = await fetch(new URL(path, this.base), {
      method, headers: { authorization: `Bearer ${this.options.credentials()}`,
        'x-work-produced-seq': String(this.options.inbox.journalSeq), 'x-work-processing-pending': String(this.options.inbox.workProcessingPending), ...(text ? { 'content-type': 'application/json' } : {}) },
      body: text, signal: AbortSignal.any([this.lifetime.signal, AbortSignal.timeout(limits.requestTimeoutMs)]),
    });
    const result = await response.json() as WorkSyncCursor & { detail?: string };
    if (!response.ok) {
      const retryAfter = Number(response.headers.get('retry-after')) * 1000;
      throw new SyncError(result.detail ?? `work_sync_http_${response.status}`, [400, 409, 413].includes(response.status), Number.isFinite(retryAfter) ? Math.max(0, retryAfter) : 0);
    }
    if (!this.started) throw new SyncError('work_sync_stopped');
    return this.validateCursor(result);
  }

  private validateCursor(cursor: WorkSyncCursor): WorkSyncCursor {
    const highest = this.options.inbox.journalSeq;
    if (!Number.isSafeInteger(cursor.through_seq) || cursor.through_seq < 0 || cursor.through_seq > highest ||
      (cursor.expected_seq !== undefined && cursor.expected_seq !== cursor.through_seq + 1)) throw new SyncError('work_sync_invalid_cursor', true);
    const pending = cursor.pending_event;
    if (pending && (pending.seq !== cursor.through_seq + 1 || typeof pending.event_id !== 'string' || !/^[a-f0-9]{64}$/.test(pending.sha256) ||
      !Number.isSafeInteger(pending.total_parts) || pending.total_parts < 1 || pending.total_parts > limits.eventMaxBytes / limits.chunkBytes ||
      !Array.isArray(pending.received_parts) || pending.received_parts.length > pending.total_parts || new Set(pending.received_parts).size !== pending.received_parts.length ||
      pending.received_parts.some(part => !Number.isSafeInteger(part) || part < 0 || part >= pending.total_parts))) throw new SyncError('work_sync_invalid_cursor', true);
    return cursor;
  }

  private acknowledge(cursor: WorkSyncCursor): void {
    // A restored center may be behind an earlier ACK. Its gap is replayed from
    // the retained journal without silently lowering the local durable watermark.
    if (cursor.through_seq > this.options.inbox.throughSeq) this.options.inbox.acknowledge(cursor.through_seq);
  }

  private async synchronize(): Promise<void> {
    const inbox = this.options.inbox;
    if (!Number.isSafeInteger(inbox.throughSeq) || inbox.throughSeq < 0 || inbox.throughSeq > inbox.journalSeq) throw new SyncError('work_sync_invalid_local_cursor', true);
    let cursor = await this.request('GET');
    if (cursor.through_seq > inbox.throughSeq) this.backoff = 1_000;
    this.acknowledge(cursor);
    while (this.started && (this.options.available?.() ?? true) && cursor.through_seq < inbox.journalSeq) {
      const first = inbox.journal(cursor.through_seq, 1)[0];
      if (!first || first.seq !== cursor.through_seq + 1) throw new SyncError('work_sync_local_journal_gap', true);
      const from = Number(first.seq), events = [first];
      const firstBody = JSON.stringify({ from_seq: from, events });
      const previous = cursor.through_seq;
      if (Buffer.byteLength(firstBody) > limits.batchTargetBytes || cursor.pending_event) {
        cursor = await this.uploadEvent(first, cursor);
      } else {
        while (events.length < limits.batchEvents) {
          const next = inbox.journal(Number(events.at(-1)!.seq), 1)[0];
          if (!next) break;
          if (next.seq !== from + events.length) throw new SyncError('work_sync_local_journal_gap', true);
          if (Buffer.byteLength(JSON.stringify({ from_seq: from, events: [...events, next] })) > limits.batchTargetBytes) break;
          events.push(next);
        }
        cursor = await this.request('POST', '/events', { from_seq: from, events });
      }
      this.acknowledge(cursor);
      if (cursor.through_seq <= previous) throw new SyncError('work_sync_no_progress');
      this.backoff = 1_000;
      await new Promise<void>(resolve => setImmediate(resolve));
    }
  }

  private async uploadEvent(event: Record<string, unknown>, cursor: WorkSyncCursor): Promise<WorkSyncCursor> {
    const raw = Buffer.from(JSON.stringify(event));
    if (raw.length > limits.eventMaxBytes) throw new SyncError('event_too_large', true);
    const hash = sha(raw), count = Math.ceil(raw.length / limits.chunkBytes), seq = Number(event.seq), eventId = String(event.event_id);
    const pending = cursor.pending_event;
    if (pending && (pending.seq !== seq || pending.event_id !== eventId || pending.sha256 !== hash || pending.total_parts !== count)) throw new SyncError('work_sync_event_identity_conflict', true);
    const received = new Set(pending?.received_parts ?? []);
    // The last part may be durable while projection has not committed yet.
    // Repeating it re-enters the server's atomic finalize path after a crash.
    if (received.size === count) received.delete(count - 1);
    for (let part = 0; part < count && this.started; part++) {
      if (received.has(part)) continue;
      const bytes = raw.subarray(part * limits.chunkBytes, Math.min(raw.length, (part + 1) * limits.chunkBytes));
      const payload: WorkSyncPart = { event_id: eventId, sha256: hash, total_bytes: raw.length, total_parts: count, part_sha256: sha(bytes), data: bytes.toString('base64') };
      cursor = await this.request('PUT', `/events/${seq}/parts/${part}`, payload);
      if (cursor.through_seq >= seq) return cursor;
      const accepted = cursor.pending_event;
      if (!accepted || accepted.seq !== seq || accepted.event_id !== eventId || accepted.sha256 !== hash || accepted.total_parts !== count || !accepted.received_parts.includes(part))
        throw new SyncError('work_sync_unconfirmed_part');
      for (const acceptedPart of accepted.received_parts) received.add(acceptedPart);
      this.backoff = 1_000;
    }
    return cursor;
  }
}
