import { authFetchJson } from '../auth/auth-fetch';

export interface OnboardingNode { node_id: string; node_name: string; alias: string | null; status: string }
export interface OnboardingAgent { agent_id: string; display_name: string; node_id: string; default_model: string; workspace_root: string; work_mode: string }
export interface OnboardingState {
  nodes: OnboardingNode[];
  agents: OnboardingAgent[];
  install: { available: boolean; origin: string; command: string; script_url: string };
}
export type ModelProtocol = 'openai-completions' | 'anthropic-messages' | 'openai-responses';
export interface ServiceModel { id: string; display_name?: string; context_window?: number; max_tokens?: number; input?: ('text' | 'image')[] }
export interface ModelService {
  provider: string; display_name: string; native: boolean; source: string; protocol?: ModelProtocol; base_url?: string;
  credential_stored: boolean; models: (ServiceModel & { name: string })[];
}
export interface CatalogProvider {
  provider: string; display_name: string;
  models: { id: string; name?: string; contextWindow?: number; maxTokens?: number; inputModalities?: ('text' | 'image')[] }[];
}
export interface SetupError { code: string; message: string; dependencies?: { agent_id: string; display_name: string }[] }
export interface SetupStatus {
  revision: string;
  services: ModelService[];
  models: { provider: string; model: string; display_name?: string }[];
  catalog: CatalogProvider[];
  catalog_error?: string;
  default_model: string;
  workspace_base: string;
  operation?: { id: string; state: 'waiting' | 'testing' | 'succeeded' | 'failed' | 'cancelled'; code?: string; url?: string; message?: string; error?: SetupError };
  error?: SetupError;
}
export interface SetupInput {
  action: 'status' | 'save' | 'remove' | 'login' | 'cancel'; revision?: string; provider?: string; source?: string;
  display_name?: string; protocol?: ModelProtocol; base_url?: string; model?: string; models?: ServiceModel[]; api_key?: string;
}
export const getOnboarding = () => authFetchJson<OnboardingState>('/im/v1/onboarding');
export const setupNode = (nodeId: string, input: SetupInput) => authFetchJson<SetupStatus>(`/im/v1/nodes/${encodeURIComponent(nodeId)}/setup`, { method: 'POST', body: JSON.stringify(input) });
