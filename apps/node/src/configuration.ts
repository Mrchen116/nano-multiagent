import { readFile, open, rename, mkdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { load, dump } from 'js-yaml';
import { canonicalAgentConfiguration, agentConfigurationFingerprint, type AgentConfiguration, type CanonicalAgentConfiguration } from '@nano/product-contracts';

export interface LocalAgent extends Record<string, unknown> {
  agent_id: string; workspace_root: string; work_mode?: 'single_thread' | 'global';
  default_model?: string; custom_prompt?: string; features?: Record<string, boolean>;
  group_reply_policy?: string; reasoning_effort?: string; heartbeat?: Record<string, unknown>;
}
export interface NodeConfigurationFile {
  node: { node_id: string; user_id: string; workspace_base?: string };
  im_service: { url: string; token: string };
  agents: LocalAgent[];
  display?: { runtime_footer?: { enabled?: boolean }; platforms?: { feishu?: { runtime_footer?: { enabled?: boolean } } } };
  channels?: { name: string; enabled?: boolean; settings: Record<string, string> }[];
  llm: { default_model: string; providers: { name: string; base_url: string; api_key?: string; models: { name: string; context_window?: number; reasoning?: { default?: string; levels?: string[] } | string }[] }[] };
}

/** Owns the existing node file; IM stores operations and mirrors its non-secret projection. */
export class NodeConfiguration {
  private persistence: Promise<void> = Promise.resolve();
  private constructor(readonly path: string, readonly value: NodeConfigurationFile) {}
  static async read(path: string) { return new NodeConfiguration(path, load(await readFile(path, 'utf8')) as NodeConfigurationFile); }
  current(agentId: string): CanonicalAgentConfiguration | undefined {
    const agent = this.value.agents.find(agent => agent.agent_id === agentId);
    return agent ? canonicalAgentConfiguration({ ...agent, display_name: agent.title ?? agent.display_name ?? agent.agent_id,
      skills: agent.skills ?? [], heartbeat_json: agent.heartbeat ? JSON.stringify(agent.heartbeat) : null }) : undefined;
  }
  runtime(agent: LocalAgent | CanonicalAgentConfiguration): AgentConfiguration {
    const model = agent.default_model || this.value.llm.default_model;
    const provider = this.value.llm.providers.find(provider => provider.models.some(candidate => candidate.name === model));
    if (!provider) throw new Error(`No configured provider for ${model}`);
    const selected = provider.models.find(candidate => candidate.name === model)!;
    const effort = agent.reasoning_effort || (typeof selected.reasoning === 'object' ? selected.reasoning.default : undefined);
    if (effort && typeof selected.reasoning === 'object' && selected.reasoning.levels && !selected.reasoning.levels.includes(effort)) throw new Error(`Unsupported reasoning effort for ${model}`);
    const policy = String(agent.group_reply_policy ?? 'manual').toLowerCase();
    return { agentId: agent.agent_id, workspace: agent.workspace_root!, mode: agent.work_mode as AgentConfiguration['mode'] || 'single_thread',
      revision: agentConfigurationFingerprint({ ...agent, display_name: 'title' in agent ? agent.title : agent.display_name }), provider: provider.name, model,
      ...(effort ? { reasoningEffort: effort === 'none' ? 'off' : effort } : {}), systemPrompt: agent.custom_prompt ?? undefined,
      features: agent.features, groupReplyPolicy: policy === 'always' ? 'always' : 'mention_only',
    };
  }
  async resolve(candidate: CanonicalAgentConfiguration, creating: boolean): Promise<CanonicalAgentConfiguration> {
    if (!candidate.agent_id || !/^[a-zA-Z0-9_.-]+$/.test(candidate.agent_id)) throw new Error('Invalid Agent identity');
    if (!['single_thread', 'global'].includes(candidate.work_mode)) throw new Error('Invalid work mode');
    const previous = this.current(candidate.agent_id);
    if (!creating && !previous) throw new Error('Agent does not exist on this node');
    if (previous && previous.work_mode !== candidate.work_mode) throw new Error('Work mode is immutable');
    const workspace = candidate.workspace_root || previous?.workspace_root || join(this.value.node.workspace_base ?? join(dirname(this.path), '.dsh-runtime', 'workspaces'), candidate.agent_id);
    if (previous?.work_mode === 'global' && resolve(workspace) !== resolve(previous.workspace_root!)) throw new Error('Global Agent workspace is immutable');
    const resolved = { ...candidate, workspace_root: resolve(workspace) };
    this.runtime(resolved);
    return resolved;
  }
  persist(candidate: CanonicalAgentConfiguration): Promise<void> {
    const task = this.persistence.then(() => this.write(candidate));
    this.persistence = task.catch(() => {}); return task;
  }
  private async write(candidate: CanonicalAgentConfiguration): Promise<void> {
    const previous = this.value.agents.find(agent => agent.agent_id === candidate.agent_id);
    const agent: LocalAgent = { ...previous, ...candidate, work_mode: candidate.work_mode as LocalAgent['work_mode'],
      workspace_root: candidate.workspace_root!, title: candidate.display_name, default_model: candidate.default_model ?? undefined,
      custom_prompt: candidate.custom_prompt ?? undefined, reasoning_effort: candidate.reasoning_effort ?? undefined,
      heartbeat: candidate.heartbeat_json ? JSON.parse(candidate.heartbeat_json) as Record<string, unknown> : undefined };
    delete agent.heartbeat_json;
    const agents = this.value.agents.filter(item => item.agent_id !== candidate.agent_id).concat(agent);
    await mkdir(agent.workspace_root, { recursive: true });
    const temporary = join(dirname(this.path), `.nano-config-${randomUUID()}.tmp`);
    const file = await open(temporary, 'wx', 0o600);
    try { await file.writeFile(dump({ ...this.value, agents }, { noRefs: true })); await file.sync(); } finally { await file.close(); }
    await rename(temporary, this.path);
    const directory = await open(dirname(this.path), 'r');
    try { await directory.sync(); } finally { await directory.close(); }
    this.value.agents = agents;
  }
}
