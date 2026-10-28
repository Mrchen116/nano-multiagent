import type { AgentPublication, ChatAttachment, ChatPermission, ChatProcessItem, ChatStreamFact, ChatToolCall } from './chat.js';

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('chat field must be an object');
  return value as Record<string, unknown>;
}
function fields(value: Record<string, unknown>, names: string[], type: 'string' | 'number' | 'boolean', nullable = false): void {
  for (const key of names) {
    const v = value[key];
    if (v === undefined || nullable && v === null) continue;
    if (typeof v !== type || type === 'number' && !Number.isFinite(v)) throw new Error(`invalid chat ${key}`);
  }
}
function required(value: Record<string, unknown>, key: string): void {
  if (typeof value[key] !== 'string' || !value[key]) throw new Error(`chat ${key} required`);
}
/** Validate attachment fields at transport entry without copying or normalizing extensions. */
export function chatAttachments(value: unknown): ChatAttachment[] {
  if (!Array.isArray(value)) throw new Error('invalid chat attachments');
  for (const item of value) { const row = object(item); required(row, 'url'); fields(row, ['content_type', 'file_name'], 'string'); }
  return value as ChatAttachment[];
}
function tool(value: unknown): ChatToolCall {
  const row = object(value); required(row, 'id'); fields(row, ['name', 'status', 'approval', 'reason'], 'string'); fields(row, ['seq'], 'number');
  return row as unknown as ChatToolCall;
}
function permission(value: unknown): ChatPermission {
  const row = object(value); fields(row, ['request_id', 'call_id', 'tool_name', 'status', 'decision', 'decided_by', 'agent_id', 'node_id', 'run_id'], 'string');
  fields(row, ['node_epoch'], 'number'); fields(row, ['lifecycle_revision'], 'number', true);
  if (row.options !== undefined) {
    if (!Array.isArray(row.options)) throw new Error('invalid chat permission options');
    for (const option of row.options) { const entry = object(option); required(entry, 'id'); fields(entry, ['label', 'description'], 'string'); }
  }
  return row as ChatPermission;
}
function process(value: unknown): ChatProcessItem {
  const row = object(value); required(row, 'item_id'); fields(row, ['kind','run_id','draft_id','text','source','status','successor_message_id'], 'string'); fields(row, ['predecessor_message_id'], 'string', true);
  if(row.source_messages!==undefined&&!Array.isArray(row.source_messages))throw new Error('invalid chat source_messages');
  return row as unknown as ChatProcessItem;
}
/** Decode stable fields before persistence/idempotency. Return the original wire object.
 * Args:
 *   value: Untrusted WS payload or persisted external outbox frame.
 * Returns:
 *   A kind-associated fact, preserving omitted fields, extension data and property order.
 * Throws:
 *   Error: The kind or a field consumed by that kind is malformed.
 */
export function decodeChatStream(value: unknown): ChatStreamFact {
  const row = object(value);
  fields(row, ['node_id', 'run_id', 'session_id', 'agent_id', 'request_id'], 'string'); fields(row, ['lifecycle_revision'], 'number', true);
  if (row.kind === 'turn_start') {
    required(row, 'agent_id'); fields(row, ['agent_user_id', 'conversation_id', 'to_user_id', 'shadow_message_id', 'idempotency_key', 'external_reply'], 'string');
    if (!row.conversation_id && !row.to_user_id) throw new Error('chat target required');
    if (row.background_returns !== undefined && !Array.isArray(row.background_returns)) throw new Error('invalid chat background_returns');
    if (row.reply_process_transition !== undefined) {
      const transition = object(row.reply_process_transition); fields(transition, ['predecessor_message_id'], 'string', true); fields(transition, ['run_id'], 'string'); fields(transition, ['include_handoff'], 'boolean');
      if (transition.source_messages !== undefined && !Array.isArray(transition.source_messages)) throw new Error('invalid chat source_messages');
    }
  } else if (row.kind !== 'run_terminal_reconcile') {
    required(row, 'message_id'); fields(row, ['delivery_status'], 'string');
    switch (row.kind) {
      case 'message_delta': fields(row, ['delta_text', 'idempotency_key'], 'string'); break;
      case 'message_completed':
        fields(row, ['final_content', 'idempotency_key', 'resolved_model'], 'string'); fields(row, ['kernel_message_id'], 'string', true); fields(row, ['elapsed_ms'], 'number', true);
        if (row.token_usage != null) fields(object(row.token_usage),['context_used','context_window','output','total','cache_read_tokens','cache_total_input_tokens'],'number');
        if (row.delivery_status !== undefined && !['completed', 'failed'].includes(String(row.delivery_status))) throw new Error('invalid delivery status');
        break;
      case 'message_discarded': fields(row, ['reason'], 'string'); break;
      case 'thinking_segment': fields(row, ['text'], 'string'); fields(row, ['process_seq'], 'number'); break;
      case 'tool_call_upserted': case 'tool_call_completed': tool(row.tool_call); fields(row, ['process_seq'], 'number'); break;
      case 'permission_request': case 'permission_resolved': {
        permission(row); const item = row.permission_request === undefined ? row : permission(row.permission_request);
        if (!item.request_id && !row.request_id) throw new Error('chat request_id required');
        if (row.kind === 'permission_request') required(row, 'run_id');
        break;
      }
      case 'reply_process': process(row.item); break;
      case 'run_heartbeat': fields(row, ['source'], 'string'); break;
      default: throw new Error('unsupported streaming kind');
    }
  }
  return row as unknown as ChatStreamFact;
}
/** Check the Agent publication envelope; interactive schema remains owned by its existing decoder. */
export function decodeAgentPublication(value: unknown): AgentPublication {
  const row = object(value); required(row, 'from_session_id'); required(row, 'to');
  if (typeof row.text !== 'string') throw new Error('invalid_agent_message');
  fields(row, ['node_id'], 'string'); fields(row, ['lifecycle_revision'], 'number', true);
  if (row.attachments != null) chatAttachments(row.attachments);
  if (row.background_returns != null && !Array.isArray(row.background_returns)) throw new Error('invalid chat background_returns');
  if (!row.text.trim() && !(row.background_returns as unknown[] | undefined)?.length) throw new Error('invalid_agent_message');
  if (row.reply_draft !== undefined) throw new Error('reply_draft is retired; use ComposeMessage');
  return row as unknown as AgentPublication;
}
