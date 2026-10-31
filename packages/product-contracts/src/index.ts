import type { PersonalAgentIdentity } from './personal-agent.js';
export * from './personal-agent.js';
export * from './agent-lifecycle.js';
/** Product vocabulary. This package deliberately imports no execution runtime. */
export interface AgentConfiguration {
  agentId: string;
  displayName?: string;
  /** Server-issued personal identity; ordinary Agent configuration cannot grant this role. */
  personal?: PersonalAgentIdentity;
  revision: string;
  workspace: string;
  mode: 'single_thread' | 'global';
  groupReplyPolicy?: 'always' | 'mention_only';
  provider: string;
  model: string;
  reasoningEffort?: string;
  maxTokens?: number;
  workflow?: {outputTokenTarget?:number;sizeGuideline?:string};
  modelFallbacks?: { provider: string; model: string; reasoningEffort?: string; maxTokens?: number }[];
  systemPrompt?: string;
  features?: Record<string, boolean>;
  toolAllowlist?: string[];
  skillSelection?: { mode: 'default_discovery' | 'explicit_allowlist' | 'explicit_denylist'; names: string[] };
  skillRoots?: { path: string; source: string }[];
  extensions?: { global?: string; workspace?: string };
  knowledge?: import('./knowledge.js').KnowledgeConfiguration;
  approval?: import('./approval.js').ApprovalConfiguration;
}
export interface SessionBinding {
  sessionId: string;
  conversationId: string;
  agentId: string;
  ownerId: string;
  cwd: string;
  revision: string;
}
export interface RelayInput {
  /** Execution epoch captured at first admission, retained on redelivery. */
  lifecycle_revision?: number;
  relay_task_id: string;
  agent_id: string;
  conversation_id: string;
  idempotency_key: string;
  metadata: Record<string, unknown> & { interaction_contexts?: import('./interactive.js').InteractionContext[] };
  participants?: { type: string; id: string; user_id: string; display_name: string }[];
  message: {
    id: string;
    content: string;
    interactive?: import('./interactive.js').MessageInteractive;
    interaction_reply?: import('./interactive.js').InteractionSnapshot;
    sender_user_id: string;
    sender_type: string;
    pa_agent_id?: string;
    system_notice?: {kind:string}|null;
    created_at?: string;
    timezone?: string;
    sender?: {display_name?: string};
    attachments: { url: string; content_type: string; file_name?: string }[];
  };
}
export interface RuntimeEvent {
  /** Model-context placement, not another execution of the original event. */
  surfaceOp?: 'append' | { op: 'replace'; startSeq: number; endSeq: number };
  seq: number;
  type: string;
  time: number;
  data: Record<string, unknown>;
}
export interface RuntimePort {
  request(method: string, params: unknown): Promise<unknown>;
  onNotification(listener: (method: string, params: unknown) => void): () => void;
  /** Capture the current host generation for one asynchronous reconciliation. */
  capture?(): RuntimePort;
}
export type DeliveryState = 'prepared' | 'sending' | 'completing' | 'confirmed' | 'unknown' | 'failed' | 'withheld' | 'cancelled_by_disable';

/** Host-resolved public messaging identity; never supplied by model arguments. */
export interface MessageApprovalContext {
  target: string;
  sender: { type: 'agent'; agent_id: string };
  recipient: { kind: 'owner' | 'user' | 'agent' | 'group' | 'unknown' };
  channel?: string;
}

export { canonicalAgentConfiguration, agentConfigurationFingerprint, type CanonicalAgentConfiguration } from './configuration.js';
export { validateTimeZone, formatLocalTime } from './time.js';
export { approvalDefaults, type ApprovalConfiguration } from './approval.js';
export { parseReleaseManifest, nodeUpdateTerminal, nodeUpdateCancellable,
  type ReleaseManifest, type NodeRelease, type NodeUpdateState, type NodeUpdateOperation,
  type NodeUpdateView, type NodeUpdateReport } from './node-update.js';
export { TRAJECTORY_VERSION, TRAJECTORY_MAX_BYTES, type TrajectoryRun, type TrajectoryJson, type TrajectoryScope, type TrajectoryRequest, type TrajectoryResponse } from './trajectory.js';

/** Native attempts grouped into one product reply and its model notices. */
export interface ModelRunProjection {
  id: string; sessionId: string; turn: number; state: 'running' | 'switching' | 'completed'; terminal?: unknown; switched?: string;
  attempts: { turn: number; route: { provider: string; model: string }; error?: { message: string; code: string } }[];
}

export { encodeTrajectoryValue, TrajectoryValueDecoder } from './trajectory-wire.js';
export * from './interactive.js';
export { interactiveCatalog, interactiveTools } from './interactive-catalog.js';

export * from './work-sync.js';
export * from './task-execution.js';

/** Final durable incremental history returned by a stopped execution host. */
export interface RuntimeStopHistory {
  sessionId: string;
  rootSessionId: string;
  parentSessionId?: string;
  events: RuntimeEvent[];
  modelRuns: ModelRunProjection[];
  modelVersion?: string;
  throughSeq: number;
}

export type { AgentConfigurationFields, ConfigurationIntent, ConfigurationResult } from './configuration-rpc.js';
export {parseAgentConfigurationFields} from './configuration-rpc.js';
export * from './work-events.js';
export {decodeWorkEvent, decodeWorkBatch, WorkEventError, workObject} from './work-event-codec.js';
export * from './chat.js';
export * from './chat-codec.js';

export {normalizeKnowledge, DEFAULT_DREAMING_SCHEDULE, type KnowledgeConfiguration} from './knowledge.js';

export type * from './memory-evaluation.js';
