import type { AgentConfigurationFields, ConfigurationIntent, ConfigurationResult } from '@nano/product-contracts';
import type { TaskWaitInspection } from '@nano/product-contracts';

/** Catalog entries belong to runtime providers; only the catalog envelope is stable. */
export interface NodeCapabilities {
  models?: unknown[];
  skills?: unknown[];
  tools?: unknown[];
  commands?: unknown[];
  features?: unknown[];
  fixed_tools?: string[];
  platform_default_model?: string | null;
  default_workspace_template?: string | null;
  inherited_approval_rules?: unknown;
}
export interface CapabilitiesResult extends NodeCapabilities { capabilities?: NodeCapabilities }
interface AgentTarget { agent_id: string; workspace_root?: string | null }
interface PreviewInput {
  features: Record<string, boolean>;
  custom_prompt: string | null;
  tool_ids: string[];
  skill_ids: string[];
  skills_selection_mode: string;
  scenario: string;
  work_mode?: string;
  workspace_root?: string | null;
  workspace_mode?: string;
  agent_id_hint?: string | null;
  heartbeat_enabled?: boolean;
  cron_enabled?: boolean;
}
interface PreviewResult {
  preview?: {prompt?: string; section_count?: number};
  error?: {code: string; detail?: string};
  error_code?: string;
  message?: string;
}
export interface PluginCommand extends AgentTarget {
  action: 'list_bundles' | 'set_bundle' | 'remove_bundle';
  target?: string;
  enabled?: boolean;
}
export interface SetupCommand {
  action: 'status' | 'save' | 'remove' | 'login' | 'cancel';
  revision?: string;
  provider?: string;
  source?: string;
  display_name?: string;
  protocol?: string;
  base_url?: string;
  model?: string;
  api_key?: string;
  models?: {id: string; display_name?: string; context_window?: number; max_tokens?: number; input?: string[]}[];
}
interface SkillUsage {skills?: unknown[]; heatmap_data?: unknown[]; health?: Record<string, unknown>}

/** All center-initiated RPCs; unsolicited node events do not use this port. */
export interface NodeCommandMap {
  'agent.create': {input: ConfigurationIntent; output: ConfigurationResult};
  'agent.config.apply': {input: ConfigurationIntent; output: ConfigurationResult};
  'agent.config.operation.status': {input: {operation_id: string}; output: ConfigurationResult};
  'agent.config.get': {input: {agent_id: string}; output: AgentConfigurationFields & {agent?: AgentConfigurationFields | null}};
  'agent.capabilities.resolve': {input: AgentTarget; output: CapabilitiesResult};
  'node.capabilities.resolve': {input: {workspace_root?: string; agent_id_hint?: string}; output: CapabilitiesResult};
  'node.approval.resolve': {input: {workspace_root: string}; output: {inherited_approval_rules?: unknown}};
  'agent.prompt.preview.request': {input: PreviewInput & AgentTarget; output: PreviewResult};
  'node.prompt.preview.request': {input: PreviewInput; output: PreviewResult};
  'node.plugins.request': {input: PluginCommand; output: {plugins?: Record<string, unknown>; error?: string}};
  'node.skills.usage.request': {input: AgentTarget; output: {usage?: SkillUsage; error?: string}};
  'agent.capability-usage.request': {input: {agent_id: string}; output: {usage?: {checked_at: string; active_schedules: number; busy: {kind: string; name: string}[]}; error?: unknown}};
  'node.heartbeat.md.request': {input: AgentTarget; output: {content?: string}};
  'node.cron.jobs.request': {input: AgentTarget; output: {jobs?: unknown[]; error?: string}};
  'node.cron.delete.request': {input: AgentTarget & {job_id: string;actor_user_id:string;operation_id:string}; output: {deleted?: boolean}};
  'node.setup.request': {input: SetupCommand; output: Record<string, unknown>};
  'node.distill.prompt.request': {input: {sources: {conversation_id: string; [key: string]: unknown}[]; execution_agent_id: string; target_scope: string}; output: {prompt?: string; message?: string; error_code?: string}};
  'session.fork.request': {input: {source_conversation_id: string; new_conversation_id: string; agent_id: string; fork_point: {message_id: string}; source_external_source?: string; source_external_chat_id?: string}; output: {ok?: boolean; error?: string; id_map?: Record<string, string>}};
  'agent.work.permission': {input: {root_agent_id: string; lifecycle_revision?: number; session_id: string; decision: string; reason: string}; output: {ok?: boolean; error?: string}};
  'task.execution.state': {input: {agent_id: string}; output: {state?: string}};
  'task.wait.validate': {input: {agent_id: string; conversation_id: string; graph_id: string; node_id: string; schedule_id: string}; output: Partial<TaskWaitInspection> & {error?: string}};
}
export type NodeCommand = keyof NodeCommandMap;
export type NodeInput<K extends NodeCommand> = NodeCommandMap[K]['input'] & {request_id?: string};
export type NodeOutput<K extends NodeCommand> = NodeCommandMap[K]['output'];
/** Consumer port: command inference cannot be widened by an unrelated payload. */
export type NodeRequest = <K extends NodeCommand>(nodeId: string, command: K, payload: NodeInput<NoInfer<K>>, signal?: AbortSignal) => Promise<NodeOutput<K>>;

export type ConfigurationCommand = 'agent.create' | 'agent.config.apply' | 'agent.config.operation.status';
export type ConfigurationRequest = <K extends ConfigurationCommand>(nodeId: string, command: K, payload: NodeInput<NoInfer<K>>) => Promise<NodeOutput<K>>;

/** Explicit response names are also the correlation allowlist. */
export const nodeResponseTypes = {
  'agent.create': 'agent.created',
  'agent.config.apply': 'agent.config.apply.result',
  'agent.config.operation.status': 'agent.config.operation.status.result',
  'agent.config.get': 'agent.config',
  'agent.capabilities.resolve': 'agent.capabilities',
  'node.capabilities.resolve': 'node.capabilities',
  'node.approval.resolve': 'node.approval.resolve.result',
  'agent.prompt.preview.request': 'agent.prompt.preview',
  'node.prompt.preview.request': 'node.prompt.preview',
  'node.plugins.request': 'node.plugins',
  'node.skills.usage.request': 'node.skills.usage',
  'agent.capability-usage.request': 'agent.capability-usage',
  'node.heartbeat.md.request': 'node.heartbeat.md',
  'node.cron.jobs.request': 'node.cron.jobs',
  'node.cron.delete.request': 'node.cron.delete',
  'node.setup.request': 'node.setup',
  'node.distill.prompt.request': 'node.distill.prompt',
  'session.fork.request': 'session.fork.result',
  'agent.work.permission': 'agent.work.permission.result',
  'task.execution.state': 'task.execution.state.result',
  'task.wait.validate': 'task.wait.validate.result',
} as const satisfies Record<NodeCommand, string>;
