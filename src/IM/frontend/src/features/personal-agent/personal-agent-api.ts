import { authFetchJson } from '../auth/auth-fetch';

export interface PersonalAgentPolicy {
  revision: number;
  observation_enabled: boolean;
  excluded_conversation_ids: string[];
}
export interface PersonalAgentBinding {
  binding_id: string;
  agent_id: string;
  owner_id: string;
  owner_user_id: string;
  node_id: string;
  node_epoch: number;
  conversation_id: string;
  display_name: string;
  status: string;
}
export interface PersonalAgentState {
  binding: PersonalAgentBinding | null;
  policy: PersonalAgentPolicy | null;
  creation?: {request_key: string; initial_goal: string | null} | null;
}
export interface CreatePersonalAgent {
  request_key: string;
  node_id: string;
  display_name: string;
  initial_goal?: string;
  observation_enabled: boolean;
}
const base = '/im/v1/personal-agent';
export const getPersonalAgent = () => authFetchJson<PersonalAgentState>(base);
export const createPersonalAgent = (input: CreatePersonalAgent) => authFetchJson<PersonalAgentState>(base, {method: 'POST', body: JSON.stringify(input)});
export const updatePersonalAgentPolicy = (input: Partial<Omit<PersonalAgentPolicy, 'revision'>> & {expected_revision: number}) => authFetchJson<PersonalAgentPolicy>(`${base}/policy`, {method: 'PATCH', body: JSON.stringify(input)});
export interface PersonalAgentCleanup {
  operation_id: string;
  status: 'pending' | 'completed';
}
export const getPersonalAgentCleanup = () => authFetchJson<{items: PersonalAgentCleanup[]}>(`${base}/cleanup`);
export const cleanupPersonalAgent = (input: {request_key: string; conversation_id?: string}) => authFetchJson<PersonalAgentCleanup>(`${base}/cleanup`, {method:'POST', body:JSON.stringify(input)});
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
export const getPersonalAssistance = () => authFetchJson<{items: PersonalAssistance[]}>(`${base}/assistance`);
export const getPersonalDecisions = () => authFetchJson<{items: PersonalDecision[]}>(`${base}/decisions`);
export const setPersonalAssistancePaused = (taskRef: string, paused: boolean, expected_revision: number) => authFetchJson<{items: PersonalAssistance[]}>(`${base}/assistance/${encodeURIComponent(taskRef)}/${paused ? 'pause' : 'resume'}`, {method:'POST', body:JSON.stringify({expected_revision})});
export const resolvePersonalDecision = (id: string, input: {expected_revision: number; request_key: string; option?: string; snooze_until?: string; decline?: boolean}) => authFetchJson<PersonalDecision>(`${base}/decisions/${encodeURIComponent(id)}`, {method:'POST', body:JSON.stringify(input)});
export const renamePersonalAgent = (display_name: string) => authFetchJson<PersonalAgentState>(base, {method:'PATCH',body:JSON.stringify({display_name})});
export interface PersonalIncident {
  id: string; actor_id: string; actor_name: string; conversation_id: string;
  source_message_id: string; category: string; reason: string; count: number;
  status: string; owner_notice_message_id: string | null; peer_notice_message_id?: string | null;
}
export const getPersonalIncidents = () => authFetchJson<{items: PersonalIncident[]}>(`${base}/incidents`);
export const respondToPersonalIncident = (id: string, action: 'block' | 'misunderstanding') => authFetchJson<PersonalIncident>(`${base}/incidents/${encodeURIComponent(id)}`,{method:'POST',body:JSON.stringify({action})});
