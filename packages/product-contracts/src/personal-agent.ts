/** Server-authenticated personal identity; never accepted from model arguments. */
export interface PersonalAgentIdentity {
  bindingId: string;
  ownerId: string;
  conversationId: string;
  epoch: number;
}
export interface PersonalAgentBinding {
  binding_id: string; agent_id: string; owner_id: string; owner_user_id: string;
  node_id: string; node_epoch: number; conversation_id: string; display_name: string;
  status: 'pending' | 'active' | 'unavailable';
}
export interface PersonalAgentPolicy {
  revision: number; observation_enabled: boolean; excluded_conversation_ids: string[];
}
export interface PersonalAgentState {
  binding: PersonalAgentBinding | null; policy: PersonalAgentPolicy | null;
  creation?: {request_key:string;initial_goal:string|null}|null;
}
export interface PersonalDecision {
  id: string; task_ref: string | null; kind: 'choice' | 'draft'; question: string;
  options: {id: string; label: string; consequence?: string}[]; recommended: string | null;
  target_conversation_id?: string; source_message_id?: string; content?: string;
  status: 'pending' | 'resolved' | 'declined'; revision: number; snooze_until: string | null;
}
export interface PersonalAssistance {
  task_ref: string; task: {title: string; status: string; result?: unknown} | null;
  next_action: string | null; next_check_at: string | null; waiting_on: string | null;
  decision_id: string | null; paused: boolean; revision: number; status: string;
}
export interface PersonalHistoryQuery {
  conversation_id?: string; participant_id?: string; keyword?: string;
  before?: string; after?: string; cursor?: number; limit?: number;
}
export interface PersonalHistoryItem {
  conversation_id: string; message_id: string; author_id: string; author_name: string;
  content: string; created_at: string; source_policy_revision: number; url: string;
}
export interface PersonalHistoryResult {
  items: PersonalHistoryItem[]; next_cursor: number | null;
  coverage: 'current_authorized_participated_conversations';
}
export interface PersonalDelegation {
  agent_id: string; authorized_by: string; display_name: string; label: string;
}
/** Host-only transport. The tool bridge must not expose review/scope issuance as tools. */
export type PersonalAgentMethod =
  | 'pa.runtime.status' | 'pa.state' | 'pa.source.admit' | 'pa.history.search' | 'pa.history.read'
  | 'pa.observations.read' | 'pa.observations.ack'
  | 'pa.scope.resolve' | 'pa.scope.create' | 'pa.owner.control' | 'pa.assistance.read' | 'pa.assistance.update'
  | 'pa.decision.create' | 'pa.action.prepare' | 'pa.action.review-result'
  | 'pa.action.commit' | 'pa.action.complete' | 'pa.incident.report' | 'pa.cleanup.ack';
