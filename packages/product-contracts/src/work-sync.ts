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
}

export interface WorkSyncPart {
  event_id: string;
  sha256: string;
  total_bytes: number;
  total_parts: number;
  part_sha256: string;
  data: string;
}
