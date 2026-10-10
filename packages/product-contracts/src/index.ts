/** Product vocabulary. This package deliberately imports no execution runtime. */
export interface AgentConfiguration {
  agentId: string;
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
  skillSelection?: { mode: 'default_discovery' | 'explicit_allowlist'; names: string[] };
  skillRoots?: { path: string; source: string }[];
  extensions?: { global?: string; workspace?: string };
  knowledge?: { enabled?: boolean; globalSkillRoot?: string; memoryInterval?: number; skillInterval?: number };
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
  relay_task_id: string;
  agent_id: string;
  conversation_id: string;
  idempotency_key: string;
  metadata: Record<string, unknown>;
  participants?: { type: string; id: string; user_id: string; display_name: string }[];
  message: {
    id: string;
    content: string;
    sender_user_id: string;
    sender_type: string;
    created_at?: string;
    sender?: {display_name?: string};
    attachments: { url: string; content_type: string; file_name?: string }[];
  };
}
export interface RuntimeEvent {
  seq: number;
  type: string;
  time: number;
  data: Record<string, unknown>;
}
export interface RuntimePort {
  request(method: string, params: unknown): Promise<unknown>;
  onNotification(listener: (method: string, params: unknown) => void): () => void;
}
export type DeliveryState = 'prepared' | 'sending' | 'completing' | 'confirmed' | 'unknown' | 'failed' | 'withheld';

export { canonicalAgentConfiguration, agentConfigurationFingerprint, canonicalJson, type CanonicalAgentConfiguration } from './configuration.js';
export { approvalDefaults, type ApprovalConfiguration } from './approval.js';

/** Native attempts grouped into one product reply and its model notices. */
export interface ModelRunProjection {
  id: string; sessionId: string; turn: number; state: 'running' | 'switching' | 'completed'; terminal?: unknown; switched?: string;
  attempts: { turn: number; route: { provider: string; model: string }; error?: { message: string; code: string } }[];
}

/** One durable native turn, excluding any inherited fork history. */
export interface UsageReport {
  sessionId: string;
  turn: number;
  time: number;
  usage: {prompt_tokens: number; completion_tokens: number; total_tokens: number};
}
