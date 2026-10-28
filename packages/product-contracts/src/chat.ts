import type { InteractionSnapshot, MessageInteractive } from './interactive-types.js';

/** Stable chat presentation fields; provider/tool-specific contents remain opaque. */
export interface ChatAttachment {url?: string; content_type?: string; file_name?: string; [field: string]: unknown}
export interface ChatToolCall {
  id: string;
  name?: string;
  status?: string;
  seq?: number;
  input?: unknown;
  output?: unknown;
  detail?: unknown;
  approval?: string;
  reason?: string;
  [field: string]: unknown;
}
export interface ChatPermission {
  agent_id?: string; node_id?: string; node_epoch?: number; lifecycle_revision?: number | null; run_id?: string;
  request_id?: string;
  call_id?: string;
  tool_name?: string;
  status?: string;
  decision?: string;
  decided_by?: string;
  options?: {id: string; label?: string; description?: string; [field: string]: unknown}[];
  tool_input?: unknown;
  [field: string]: unknown;
}
export interface ChatProcessItem {item_id:string;kind?:string;run_id?:string;draft_id?:string;text?:string;source?:string;status?:string;predecessor_message_id?:string|null;successor_message_id?:string;source_messages?:unknown[];[field:string]:unknown}
export interface ChatThinking {seq: number; text: string}
export interface ChatUsage {context_used?:number;context_window?:number;output?:number;total?:number;cache_read_tokens?:number;cache_total_input_tokens?:number;[metric:string]:unknown}
interface StreamCommon {
  node_id?: string;
  lifecycle_revision?: number | null;
  run_id?: string;
  session_id?: string;
  agent_id?: string;
  request_id?: string;
}
interface MessageStream extends StreamCommon {message_id: string; delivery_status?: string}
export interface ChatTurnStart extends StreamCommon {
  kind: 'turn_start'; agent_id: string; agent_user_id?: string;
  conversation_id?: string; to_user_id?: string;
  shadow_message_id?: string; idempotency_key?: string;
  background_returns?: unknown[];
  external_reply?: string;
  reply_process_transition?: {predecessor_message_id?: string | null; run_id?: string; include_handoff?: boolean; source_messages?: unknown[]};
}
export type ChatStreamFact = ChatTurnStart
  | (StreamCommon & {kind: 'run_terminal_reconcile'})
  | (MessageStream & {kind: 'message_delta'; delta_text?: string; idempotency_key?: string})
  | (Omit<MessageStream, 'delivery_status'> & {kind: 'message_completed'; idempotency_key?: string; resolved_model?: string; delivery_status?: 'completed' | 'failed'; final_content?: string; token_usage?: ChatUsage | null; elapsed_ms?: number | null; kernel_message_id?: string | null; pa_incident_ref?: unknown; external_delivery_status?: string})
  | (MessageStream & {kind: 'message_discarded'; reason?: string})
  | (MessageStream & {kind: 'thinking_segment'; text?: string; process_seq?: number})
  | (MessageStream & {kind: 'tool_call_upserted' | 'tool_call_completed'; tool_call: ChatToolCall; process_seq?: number})
  | (MessageStream & ChatPermission & {kind: 'permission_request'; run_id: string; permission_request?: ChatPermission})
  | (MessageStream & ChatPermission & {kind: 'permission_resolved'; permission_request?: ChatPermission})
  | (MessageStream & {kind: 'reply_process'; item: ChatProcessItem})
  | (MessageStream & {kind: 'run_heartbeat'; source?: string});
export interface ChatStreamReceipt {kind?: ChatStreamFact['kind']; run_id?: string; message_id?: string; conversation_id?: string}
export interface AgentPublication {
  node_id?: string;
  lifecycle_revision?: number | null;
  from_session_id: string;
  to: string;
  text: string;
  attachments?: ChatAttachment[];
  background_returns?: unknown[];
  interactive?: unknown;
  pa_incident_ref?: unknown;
}
export interface ChatPublicationReceipt {conversation_id: string; message_id: string; target_kind: string; target_id: string; source_agent_id: string}
export interface ChatActor {type: string; id: string; display_name: string; user_id: string; is_stale: boolean | null; role?: 'personal'}
export interface ChatMessage {
  id: string; conversation_id: string; sender_user_id: string; sender_type: string; lifecycle_revision: number | null;
  content: string; delivery_status: string; created_at: string; timezone: string | null; elapsed_ms: number | null; kernel_message_id: string | null;
  sender: ChatActor;
  attachments: ChatAttachment[]; tool_calls: ChatToolCall[]; thinking: ChatThinking[]; background_returns: unknown[];
  reply_process: ChatProcessItem[]; permission_requests: ChatPermission[]; token_usage: ChatUsage | null;
  system_notice: unknown; interaction_reply: InteractionSnapshot | null; interactive?: MessageInteractive;
  update_wait?: 'updating' | 'recovery_required' | null;
  pa_agent_id?: string;
  delegation?: {agent_id: string; authorized_by: string; display_name: string; label: string};
  /** Internal non-enumerable projection details, never copied into client JSON. */
  awaiting_permission_at?: string | null;
  sender_source_id?: string | null;
}
export type ChatEvent =
  | {type: 'message.created'; data: ChatMessage & {message_id: string}}
  | {type: 'message.delta'; data: {delta: string; delta_text: string; idempotency_key?: string}}
  | {type: 'message.completed'; data: {content: string; token_usage: ChatUsage | null} | ChatMessage}
  | {type: 'message.discarded'; data: {message_id: string; reason?: string}}
  | {type: 'thinking.segment'; data: ChatThinking & {segment: ChatThinking}}
  | {type: 'tool_call.upserted' | 'tool_call.completed'; data: {tool_call: ChatToolCall}}
  | {type: 'permission.request' | 'permission.resolved'; data: ChatPermission & {permission_request: ChatPermission}}
  | {type: 'reply_process.upserted'; data: {item: ChatProcessItem}}
  | {type: 'run.heartbeat'; data: {source?: string}};
