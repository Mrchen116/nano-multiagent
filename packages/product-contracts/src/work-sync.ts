/** Machine-only durable Work upload protocol; chat never waits for this stream. */
export const workSyncPrefix = '/im/v1/gateway/work-sync';
export const workSyncLimits = {
  batchTargetBytes: 32 * 1024,
  requestMaxBytes: 64 * 1024,
  batchEvents: 100,
  chunkBytes: 16 * 1024,
  eventMaxBytes: 16 * 1024 * 1024,
  nodeStagingBytes: 16 * 1024 * 1024,
  globalStagingBytes: 256 * 1024 * 1024,
  globalConcurrency: 8,
  requestTimeoutMs: 30_000,
  partialTtlMs: 24 * 60 * 60 * 1000,
} as const;

export interface WorkSyncPendingEvent {
  seq: number;
  event_id: string;
  sha256: string;
  received_parts: number[];
  total_parts: number;
}

export interface WorkSyncCursor {
  through_seq: number;
  expected_seq?: number;
  pending_event?: WorkSyncPendingEvent;
  large_detail?: 1;
  detail?: WorkDetailProgress;
}

export interface WorkSyncPart {
  event_id: string;
  sha256: string;
  total_bytes: number;
  total_parts: number;
  part_sha256: string;
  data: string;
}

/** Marker retaining the shared journal position after its execution data is erased. */
export const workRedactedType = 'work_redacted';

export interface WorkRedactionManifest {
  journal_id: string;
  entries: { seq: number; event_id: string }[];
}

export const workDetailLimits = {
  chunkBytes: 256 * 1024,
  maxBytes: 64 * 1024 * 1024,
  projectionBytes: 24 * 1024,
  stagingBytes: 256 * 1024 * 1024,
  retainedBytes: 4 * 1024 * 1024 * 1024,
  workerTimeoutMs: 60_000,
} as const;

export interface WorkDetailManifest {
  total_bytes: number;
  sha256: string | null;
  projection: import('./work-events.js').WorkJournalEvent;
}

export interface WorkDetailProgress {
  state: 'uploading' | 'verifying' | 'complete' | 'pending' | 'local' | 'discarded' | 'rejected';
  offset: number;
}

export interface WorkDetailEntry {
  revision: number;
  event_id: string;
  type: string;
  observed_at: string | null;
  total_bytes: number;
  state: 'complete' | 'pending' | 'local';
}
