/** Persistent human intent and separately confirmed execution state. */
export const AGENT_LIFECYCLE_DESIRED_STATES = ['enabled', 'disabled'] as const;
export type AgentLifecycleDesired = (typeof AGENT_LIFECYCLE_DESIRED_STATES)[number];

export const AGENT_LIFECYCLE_OBSERVED_STATES = [
  'enabling',
  'enabled',
  'stopping',
  'disabled',
  'stop_unconfirmed',
] as const;
export type AgentLifecycleObserved = (typeof AGENT_LIFECYCLE_OBSERVED_STATES)[number];

export interface AgentLifecycleSnapshot {
  agent_id: string;
  desired: AgentLifecycleDesired;
  revision: number;
  disabled_through_revision: number;
  request_id: string | null;
  actor_user_id: string | null;
  requested_at: string;
  applied_revision: number;
  observed: AgentLifecycleObserved;
  process_instance_id: string | null;
  confirmed_at: string | null;
  error_code: string | null;
  error_detail: string | null;
}

/** Node reports are checked against the authenticated connection and current intent. */
export interface AgentLifecycleReport {
  node_id: string;
  agent_id: string;
  revision: number;
  observed: AgentLifecycleObserved;
  process_instance_id: string | null;
  confirmed_at?: string | null;
  error_code?: string | null;
  error_detail?: string | null;
}

export interface AgentLifecycleChange {
  enabled: boolean;
  request_id: string;
  expected_revision: number;
}
