/** Product vocabulary. This package deliberately imports no execution runtime. */
export interface AgentConfiguration {
  agentId: string;
  revision: string;
  workspace: string;
  mode: 'single_thread' | 'global';
  provider: string;
  model: string;
  reasoningEffort?: string;
  maxTokens?: number;
  systemPrompt?: string;
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
  message: {
    id: string;
    content: string;
    sender_user_id: string;
    sender_type: string;
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
export type DeliveryState = 'prepared' | 'sending' | 'completing' | 'confirmed' | 'unknown' | 'failed';
