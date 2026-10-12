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
