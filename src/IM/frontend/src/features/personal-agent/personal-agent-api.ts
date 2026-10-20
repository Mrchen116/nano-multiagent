import { authFetchJson } from '../auth/auth-fetch';

export interface PersonalAgentPolicy {
  revision: number;
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
  creation?: {request_key: string} | null;
}
export interface CreatePersonalAgent {
  request_key: string;
  node_id: string;
  display_name: string;
}
const base = '/im/v1/personal-agent';
export const getPersonalAgent = () => authFetchJson<PersonalAgentState>(base);
export const createPersonalAgent = (input: CreatePersonalAgent) => authFetchJson<PersonalAgentState>(base, {method: 'POST', body: JSON.stringify(input)});
export const updatePersonalAgentPolicy = (input: Partial<Omit<PersonalAgentPolicy, 'revision'>> & {expected_revision: number}) => authFetchJson<PersonalAgentPolicy>(`${base}/policy`, {method: 'PATCH', body: JSON.stringify(input)});
export const renamePersonalAgent = (display_name: string) => authFetchJson<PersonalAgentState>(base, {method:'PATCH',body:JSON.stringify({display_name})});
export interface PersonalIncident {
  id: string; actor_id: string; actor_name: string; conversation_id: string;
  source_message_id: string; category: string; reason: string; count: number;
  status: string; owner_notice_message_id: string | null; peer_notice_message_id?: string | null;
}
export const getPersonalIncidents = () => authFetchJson<{items: PersonalIncident[]}>(`${base}/incidents`);
export const respondToPersonalIncident = (id: string, action: 'block' | 'misunderstanding' | 'dismiss') => authFetchJson<PersonalIncident>(`${base}/incidents/${encodeURIComponent(id)}`,{method:'POST',body:JSON.stringify({action})});

export interface BlockedPersonalContact {
  actor_id: string; actor_name: string; reason: string;
  evidence: {id: string; reason: string; original: boolean; conversation_id: string; message_id: string | null}[];
}
export const getBlockedPersonalContacts = () => authFetchJson<{items: BlockedPersonalContact[]}>(`${base}/blocked-contacts`);
export const unblockPersonalContact = (actorId: string) => authFetchJson<{ok: boolean}>(`${base}/blocked-contacts/${encodeURIComponent(actorId)}`, {method:'DELETE'});
