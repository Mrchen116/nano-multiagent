import { authFetchJson } from '../auth/auth-fetch';

export interface OnboardingNode { node_id: string; node_name: string; alias: string | null; status: string }
export interface OnboardingAgent { agent_id: string; display_name: string; node_id: string; default_model: string; workspace_root: string; work_mode: string }
export interface OnboardingState {
  nodes: OnboardingNode[];
  agents: OnboardingAgent[];
  install: { available: boolean; origin: string; command: string; script_url: string };
}
export type ModelProtocol = 'openai-completions' | 'anthropic-messages' | 'openai-responses';
export interface SetupStatus {
  models: { provider: string; model: string }[];
  catalog: { provider: string; models: string[] }[];
  discovered: { codex: boolean; proxy?: { base_url: string; models: string[]; protocol: ModelProtocol } };
  default_model: string;
  workspace_base: string;
  operation?: { id: string; state: 'waiting' | 'testing' | 'succeeded' | 'failed' | 'cancelled'; code?: string; url?: string; message?: string };
}
export interface SetupInput { action: 'status' | 'configure' | 'login' | 'cancel'; provider?: string; protocol?: ModelProtocol; base_url?: string; model?: string; api_key?: string }
export const getOnboarding = () => authFetchJson<OnboardingState>('/im/v1/onboarding');
export const setupNode = (nodeId: string, input: SetupInput) => authFetchJson<SetupStatus>(`/im/v1/nodes/${encodeURIComponent(nodeId)}/setup`, { method: 'POST', body: JSON.stringify(input) });
