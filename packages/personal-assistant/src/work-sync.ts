import { createHash } from 'node:crypto';
import { open, rm } from 'node:fs/promises';
import { WorkDetailWorker } from '@nano/product-contracts/work-detail-worker';
import { workSyncLimits as limits, workSyncPrefix, workRedactedType, workDetailLimits as detailLimits, type WorkJournalEvent, type WorkSyncCursor, type WorkSyncPart } from '@nano/product-contracts';
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
  private redactionGeneration = 0;
  private readonly detailWorker = new WorkDetailWorker();
  private detailRetry?: NodeJS.Timeout;
  private detailBackoff = 5_000;
  private detailAfter = 0;
  private detailNeedsCleanup = false;
  private detailInFlight?: Promise<WorkSyncCursor>;
  private detailAbort?: AbortController;

  private get detailPath() { return `${this.options.inbox.path}.work-detail.tmp`; }

  constructor(private readonly options: Options) {
    this.base = new URL(options.url);
    if (this.base.protocol === 'ws:') this.base.protocol = 'http:';
    if (this.base.protocol === 'wss:') this.base.protocol = 'https:';
    if (!['http:', 'https:'].includes(this.base.protocol) || this.base.username || this.base.password) throw new Error('Invalid WorkSync URL');
  }

  /** Start background recovery; this method never waits for network delivery. */
  start(): void {
    if (this.started) return;
    this.started = true; this.paused = false; this.lifetime = new AbortController();
    this.detailNeedsCleanup = true;
    this.signal();
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

  /** Re-read the cursor after a deletion replaced local bodies with acknowledged markers. */
  async redacted(): Promise<void> {
    this.redactionGeneration++;
    const active = this.detailInFlight;
    this.detailAbort?.abort();
    if (active) {
      await this.detailWorker.close();
      await active.catch(() => {});
    }
    this.paused = false;
    this.signal();
  }

  /** Cancel HTTP and backoff, leaving every unconfirmed source event intact. */
  async stop(): Promise<void> {
    this.started = false; this.dirty = false; this.lifetime.abort();
    clearTimeout(this.detailRetry); this.detailRetry = undefined;
    await this.detailWorker.close();
    await this.task;
    await rm(this.detailPath, { force: true });
  }

  private async run(): Promise<void> {
    while (this.started && (this.options.available?.() ?? true)) {
      this.dirty = false;
      const generation = this.redactionGeneration;
      try {
        await this.synchronize();
        if (!this.dirty) return;
      } catch (error) {
        if (!this.started) return;
        if (generation !== this.redactionGeneration) continue;
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

  private async request(method: 'GET' | 'POST' | 'PUT', suffix = '', body?: unknown, cancel = this.lifetime.signal): Promise<WorkSyncCursor> {
    const path = `${workSyncPrefix}/journals/${encodeURIComponent(this.options.inbox.journalId)}${suffix}`;
    const text = body === undefined ? undefined : JSON.stringify(body);
    const maxBytes = suffix.startsWith('/large/') ? Math.ceil(detailLimits.chunkBytes / 3) * 4 + 1024 : limits.requestMaxBytes;
    if (text !== undefined && Buffer.byteLength(text) > maxBytes) throw new SyncError('work_sync_request_too_large', true);
    const response = await fetch(new URL(path, this.base), {
      method, headers: { authorization: `Bearer ${this.options.credentials()}`,
        'x-work-produced-seq': String(this.options.inbox.journalSeq), 'x-work-processing-pending': String(this.options.inbox.workProcessingPending), ...(text ? { 'content-type': 'application/json' } : {}) },
      body: text, signal: AbortSignal.any([cancel, this.lifetime.signal, AbortSignal.timeout(limits.requestTimeoutMs)]),
    });
    const result = await response.json() as WorkSyncCursor & { detail?: string };
    if (!response.ok) {
      const retryAfter = Number(response.headers.get('retry-after')) * 1000;
      throw new SyncError(result.detail ?? `work_sync_http_${response.status}`, [400, 409, 413].includes(response.status) && result.detail !== 'detail_not_started', Number.isFinite(retryAfter) ? Math.max(0, retryAfter) : 0);
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
    if (this.detailNeedsCleanup) { await rm(this.detailPath, {force: true}); this.detailNeedsCleanup = false; }
    let cursor = await this.request('GET');
    if (cursor.through_seq > inbox.throughSeq) this.backoff = 1_000;
    this.acknowledge(cursor);
    while (this.started && (this.options.available?.() ?? true) && cursor.through_seq < inbox.journalSeq) {
      const entry = inbox.nextJournalEntry(cursor.through_seq);
      if (!entry || entry.seq !== cursor.through_seq + 1) throw new SyncError('work_sync_local_journal_gap', true);
      if (entry.bytes > limits.eventMaxBytes) {
        if (cursor.large_detail !== 1) throw new SyncError('event_too_large');
        cursor = await this.uploadDetail(entry, false);
        this.acknowledge(cursor);
        if (cursor.through_seq < entry.seq) throw new SyncError('work_sync_no_progress');
        this.backoff = 1_000;
        continue;
      }
      const first = inbox.journal(cursor.through_seq, 1)[0]!;
      if (first.type === workRedactedType && cursor.pending_event?.event_id === first.event_id) {
        // A response issued before the redaction may still advertise the old partial.
        const previous = cursor.through_seq;
        cursor = await this.request('GET');
        this.acknowledge(cursor);
        if (cursor.through_seq !== previous) continue;
      }
      const from = Number(first.seq), events = [first];
      const firstBody = JSON.stringify({ from_seq: from, events });
      const previous = cursor.through_seq;
      if (Buffer.byteLength(firstBody) > limits.batchTargetBytes || cursor.pending_event) {
        cursor = await this.uploadEvent(first, cursor);
      } else {
        while (events.length < limits.batchEvents) {
          const after = Number(events.at(-1)!.seq);
          const entry = inbox.nextJournalEntry(after);
          if (!entry) break;
          if (entry.seq !== from + events.length) throw new SyncError('work_sync_local_journal_gap', true);
          if (entry.bytes > limits.batchTargetBytes) break;
          const next = inbox.journal(after, 1)[0]!;
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
    if (this.started && !this.detailRetry && cursor.large_detail === 1 && cursor.through_seq === inbox.journalSeq) {
      let pending = inbox.pendingWorkDetail(this.detailAfter, cursor.through_seq);
      if (!pending && this.detailAfter) {
        this.detailAfter = 0;
        pending = inbox.pendingWorkDetail(0, cursor.through_seq);
      }
      if (pending) {
        this.detailAfter = pending.seq;
        const entry = inbox.nextJournalEntry(pending.seq - 1);
        if (entry?.seq === pending.seq && entry.event_id === pending.event_id && entry.bytes > limits.eventMaxBytes)
          await this.uploadDetail(entry, true, pending.sha256);
        else inbox.confirmWorkDetail(pending.seq);
        if (!inbox.pendingWorkDetail(pending.seq - 1, pending.seq)) this.detailBackoff = 5_000;
        if (inbox.pendingWorkDetail(0, cursor.through_seq)) this.scheduleDetailRetry();
      }
    }
  }

  private scheduleDetailRetry(): void {
    if (this.detailRetry || !this.started) return;
    this.detailRetry = setTimeout(() => {
      this.detailRetry = undefined;
      this.signal();
    }, this.detailBackoff);
    this.detailBackoff = Math.min(60_000, this.detailBackoff * 2);
    this.detailRetry.unref();
  }

  private async uploadDetail(entry: {seq: number; event_id: string; bytes: number}, background: boolean, digest?: string): Promise<WorkSyncCursor> {
    const cancel = this.detailAbort = new AbortController();
    const transfer = this.detailInFlight = this.transferDetail(entry, background, digest, cancel.signal);
    try { return await transfer; }
    finally { this.detailInFlight = undefined; this.detailAbort = undefined; }
  }

  private async transferDetail(entry: {seq: number; event_id: string; bytes: number}, background: boolean, digest: string | undefined, signal: AbortSignal): Promise<WorkSyncCursor> {
    const { inbox } = this.options;
    const generation = this.redactionGeneration;
    const path = `/large/${entry.seq}`;
    let resumed: WorkSyncCursor | undefined;
    if (background) {
      resumed = await this.request('POST', path, {resume: true, event_id: entry.event_id, sha256: digest}, signal);
      if (resumed.detail?.state !== 'uploading') {
        if (resumed.detail?.state === 'complete' || resumed.detail?.state === 'discarded' || resumed.detail?.state === 'rejected')
          inbox.confirmWorkDetail(entry.seq);
        return resumed;
      }
    }
    try {
      signal.throwIfAborted();
      const { projection, sha256 } = await this.detailWorker.run({
        kind: 'prepare', dbPath: inbox.path, seq: entry.seq, totalBytes: entry.bytes, tempPath: this.detailPath,
      });
      if (!this.started || generation !== this.redactionGeneration) throw new SyncError('work_detail_source_changed');
      if (projection.seq !== entry.seq || projection.event_id !== entry.event_id || (digest && digest !== sha256))
        throw new SyncError('work_sync_event_identity_conflict', true);
      if (sha256) inbox.rememberWorkDetail(entry.seq, entry.event_id, sha256);
      const manifest = { total_bytes: entry.bytes, projection, sha256: sha256 ?? null, allow_defer: !background };
      const begin = () => this.request('POST', path, manifest, signal);
      let cursor = resumed ?? await begin();
      const file = sha256 && cursor.detail?.state === 'uploading' ? await open(this.detailPath, 'r') : undefined;
      try {
        while (cursor.detail?.state === 'uploading') {
          if (!this.started || generation !== this.redactionGeneration) throw new SyncError('work_detail_source_changed');
          if (background && cursor.through_seq < inbox.journalSeq) return cursor;
          const offset = cursor.detail.offset;
          if (!file || !Number.isSafeInteger(offset) || offset < 0 || offset >= entry.bytes || offset % detailLimits.chunkBytes !== 0)
            throw new SyncError('work_sync_invalid_detail_cursor', true);
          const bytes = Buffer.allocUnsafe(Math.min(detailLimits.chunkBytes, entry.bytes - offset));
          const { bytesRead } = await file.read(bytes, 0, bytes.length, offset);
          if (bytesRead !== bytes.length) throw new SyncError('work_detail_source_changed');
          cursor = await this.request('PUT', `${path}/${offset}`, { data: bytes.toString('base64'), sha256: sha(bytes) }, signal);
          if (cursor.detail?.state === 'uploading' && cursor.detail.offset !== offset + bytes.length)
            throw new SyncError('work_sync_unconfirmed_part');
        }
      } finally { await file?.close(); }
      if (cursor.detail?.state === 'verifying' && !background) {
        // Verification is deliberately outside the HTTP lease. A lost reply only repeats a status request.
        await this.delay(250);
        do {
          cursor = await begin();
          if (cursor.detail?.state === 'verifying') await this.delay(250);
        } while (cursor.detail?.state === 'verifying' && this.started && generation === this.redactionGeneration);
      }
      if (cursor.detail?.state === 'rejected') throw new SyncError('work_detail_rejected', true);
      if (cursor.detail?.state === 'complete' || cursor.detail?.state === 'discarded') inbox.confirmWorkDetail(entry.seq);
      return cursor;
    } finally { await rm(this.detailPath, { force: true }); }
  }

  private async uploadEvent(event: WorkJournalEvent, cursor: WorkSyncCursor): Promise<WorkSyncCursor> {
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
