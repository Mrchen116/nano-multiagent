/** Stable product references are independent from each provider's upstream model ID. */
export interface ModelDefinition {
  name: string;
  id?: string;
  display_name?: string;
  context_window?: number;
  max_tokens?: number;
  input?: ('text' | 'image')[];
  extra_request_body?: Record<string, unknown>;
  reasoning?: { default?: string; levels?: string[] } | string;
}
export type ModelProtocol = 'openai-completions' | 'anthropic-messages' | 'openai-responses';
export interface ModelProvider {
  name: string;
  display_name?: string;
  native?: boolean;
  protocol?: ModelProtocol;
  base_url?: string;
  api_key?: string;
  credential_stored?: boolean;
  models: ModelDefinition[];
}
export interface ModelConfiguration {
  revision?: string;
  default_model: string;
  tool_approval_model?: string;
  providers: ModelProvider[];
}
/** Only errors constructed by the product layer may be shown across the setup relay. */
export class ModelSetupError extends Error {
  constructor(readonly code: 'invalid' | 'conflict' | 'in_use' | 'busy', message: string, readonly dependencies?: {agent_id: string; display_name: string}[]) {
    super(message);
  }
}
