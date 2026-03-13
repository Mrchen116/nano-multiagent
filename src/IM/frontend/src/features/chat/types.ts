export type SenderType = "user" | "agent" | "system";

export type ConversationKind = "direct-agent" | "direct-user" | "group" | "agent-network" | "system";

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  last_message_preview?: string;
  last_message_at?: string;
  unread_count: number;
  participants: string[];
  is_pinned?: boolean;
  is_muted?: boolean;
  node_label?: string;
  node_status?: string;
  agent_label?: string;
  ownership_label?: string;
  kind?: ConversationKind;
  kind_label?: string;
  target_label?: string;
  discoverability_hint?: string;
}

export interface ChatOwnershipSummary {
  nodeId: string | null;
  nodeLabel: string | null;
  nodeStatus: string | null;
  agentLabel: string | null;
  ownershipLabel: string | null;
}

export interface ChatBootstrapState {
  selfUserId: string;
  targetNodeId: string | null;
  targetNodeStatus: string | null;
  initialConversationId: string | null;
  ownership: ChatOwnershipSummary;
}

export interface ChatAttachment {
  url: string;
  content_type?: string;
  file_name?: string;
}

export interface ChatMessage {
  message_id: string;
  sender_type: SenderType;
  sender_name?: string;
  is_mine?: boolean;
  content: string;
  created_at: string;
  attachments?: ChatAttachment[];
  delivery_status?: "sent" | "running" | "completed" | "failed";
}

export interface ConversationDetail {
  conversation_id: string;
  title: string;
  messages: ChatMessage[];
  ownership_label?: string;
  kind_label?: string;
  target_label?: string;
  discoverability_hint?: string;
}

export interface ChatStarter {
  title: string;
  actionLabel: string;
  actionHref: string;
  agentName: string;
  description: string;
  nodeLabel?: string;
  statusLabel?: string;
}

export interface UsageMetricRow {
  scope: string;
  scope_id: string | null;
  owner_id: string | null;
  conversation_id: string | null;
  agent_id: string | null;
  turns: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  last_used_at: string | null;
}

export interface UsageTotals {
  turns: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}
