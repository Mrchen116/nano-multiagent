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
  revision: number; excluded_conversation_ids: string[];
}
export interface PersonalAgentState {
  binding: PersonalAgentBinding | null; policy: PersonalAgentPolicy | null;
  creation?: {request_key:string}|null;
}
export interface PersonalDelegation {
  agent_id: string; authorized_by: string; display_name: string; label: string;
}
/** Host-only transport. The tool bridge must not expose review issuance as tools. */
export type PersonalAgentMethod =
  | 'pa.incidents.pending' | 'pa.incident.read' | 'pa.input.context' | 'pa.incident.receipt' | 'pa.runtime.status' | 'pa.state' | 'pa.source.admit'
  | 'pa.observations.read' | 'pa.observations.ack'
  | 'pa.authorization' | 'pa.sources' | 'pa.action.prepare' | 'pa.action.review-result'
  | 'pa.action.commit' | 'pa.action.complete' | 'pa.incident.report';
