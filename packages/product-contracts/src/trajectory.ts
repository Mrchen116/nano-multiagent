/** Opaque, ephemeral carrier for a single authorized native execution. */
export type TrajectoryJson = null | boolean | number | string | TrajectoryJson[] | { [key: string]: TrajectoryJson };
export const TRAJECTORY_VERSION = '0.2.1-alpha.1';
export const TRAJECTORY_MAX_BYTES = 1024 * 1024;
export interface TrajectoryScope {
  observerId: string;
  rootAgentId: string;
  rootSessionId: string;
  sessionId: string;
  ownerId: string;
  nodeId: string;
  nodeEpoch: number;
}
export interface TrajectoryRequest {
  type: 'call' | 'open' | 'next' | 'abort';
  requestId: string;
  method?: string;
  params?: TrajectoryJson;
  streamId?: string;
}
export type TrajectoryResponse =
  | { type: 'result'; requestId: string; value: TrajectoryJson }
  | { type: 'error'; requestId: string; code: string; message: string };

/** One native subagent residency epoch, observed without copying its conversation. */
export interface TrajectoryRun {
  runId: string;
  parentSessionId: string;
  sessionId: string;
  provider: string;
  label?: string;
  kind: 'tool' | 'memory' | 'skills' | 'unknown';
  delegation: 'foreground' | 'background' | 'unknown';
  launchSeq?: number;
  callId?: string;
  /** Inclusive first new native offset; fork inheritance precedes this coordinate. */
  startSeq?: number;
  /** Inclusive final accepted native offset, present only for observed terminal runs. */
  endSeq?: number;
  /** Lifecycle observation time in Unix milliseconds. */
  startedAt: number;
  endedAt?: number;
  stopReason?: string;
  state: 'running' | 'completed' | 'failed' | 'cancelled' | 'unknown';
}
