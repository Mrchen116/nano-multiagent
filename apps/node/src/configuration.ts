import { readFileSync } from 'node:fs';
import { readFile, open, rename, mkdir } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { homedir } from 'node:os';
import { load, dump } from 'js-yaml';
import { defaultReasoning } from './providers.js';
import { readApproval } from './approval.js';
import { canonicalAgentConfiguration, agentConfigurationFingerprint, type AgentConfiguration, type CanonicalAgentConfiguration } from '@nano/product-contracts';

export interface LocalAgent extends Record<string, unknown> {
  agent_id: string; workspace_root: string; work_mode?: 'single_thread' | 'global';
  default_model?: string; custom_prompt?: string; features?: Record<string, boolean>;
  group_reply_policy?: string; reasoning_effort?: string; heartbeat?: Record<string, unknown>;
}
export interface NodeConfigurationFile {
  node: { node_id: string; user_id: string; workspace_base?: string };
  im_service: { url: string; token: string;username?:string;password?:string;refresh_token?:string };
  agents: LocalAgent[];
  gateway?: {autostart?:boolean;environment?:Record<string,string>;startup_timeout_seconds?:number;shutdown_grace_seconds?:number;poll_interval_seconds?:number};
  display?: { runtime_footer?: { enabled?: boolean }; platforms?: { feishu?: { runtime_footer?: { enabled?: boolean } } } };
  channels?: { name: string; enabled?: boolean; settings: Record<string, string> }[];
  llm: { default_model: string; tool_approval_model?: string; providers: { name: string; base_url: string; api_key?: string; models: { name: string; context_window?: number; extra_request_body?: Record<string, unknown>; reasoning?: { default?: string; levels?: string[] } | string }[] }[] };
}

/** Owns the existing node file; IM stores operations and mirrors its non-secret projection. */
export class NodeConfiguration {
  private readonly policies = new Map<string, AgentConfiguration['approval']>();
  readonly ownerRoot = process.env.NANO_OWNER_CONFIG_ROOT ?? join(homedir(), '.nanoassistant');
  private persistence: Promise<void> = Promise.resolve();
  private constructor(readonly path: string, readonly value: NodeConfigurationFile) {}
  static async read(path: string) {
    const value=load(await readFile(path,'utf8')) as NodeConfigurationFile;const config=new NodeConfiguration(path,value);
    for(const agent of value.agents){agent.workspace_root=resolve(agent.workspace_root??join(config.ownerRoot,'workspaces',agent.agent_id));await mkdir(agent.workspace_root,{recursive:true});}
    return config;
  }
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
    const effort = agent.reasoning_effort || defaultReasoning(selected);
    if (effort && typeof selected.reasoning === 'object' && selected.reasoning.levels && !selected.reasoning.levels.includes(effort)) throw new Error(`Unsupported reasoning effort for ${model}`);
    const policy = String(agent.group_reply_policy ?? 'manual').toLowerCase();
    const canonical = canonicalAgentConfiguration(agent);
    const workspace = agent.workspace_root!;
    if (!this.policies.has(workspace)) this.policies.set(workspace, readApproval(this.ownerRoot, workspace));
    const approval = { ...this.policies.get(workspace)! };
    let evolution: Record<string, unknown> = {};
    try { evolution = (load(readFileSync(join(workspace, '.nanoassistant', 'config.yaml'), 'utf8')) as { self_evolution?: Record<string, unknown> })?.self_evolution ?? {}; }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
    if (this.value.llm.tool_approval_model) {
      const reviewer = this.value.llm.providers.find(provider => provider.models.some(model => model.name === this.value.llm.tool_approval_model));
      if (!reviewer) throw new Error('Tool approval model is not registered');
      approval.reviewer = { provider: reviewer.name, model: this.value.llm.tool_approval_model };
    }
    return { agentId: agent.agent_id, workspace: agent.workspace_root!, mode: agent.work_mode as AgentConfiguration['mode'] || 'single_thread',
      revision: agentConfigurationFingerprint({ ...agent, display_name: 'title' in agent ? agent.title : agent.display_name }), provider: provider.name, model,
      ...(effort ? { reasoningEffort: effort === 'none' ? 'off' : effort } : {}), systemPrompt: agent.custom_prompt ?? undefined,
      modelFallbacks: (canonical.model_fallbacks ?? []).map(model => {
        const provider = this.value.llm.providers.find(provider => provider.models.some(candidate => candidate.name === model));
        if (!provider) throw new Error(`No configured provider for fallback ${model}`);
        const selected = provider.models.find(candidate => candidate.name === model)!;
        const effort = defaultReasoning(selected);
        return { provider: provider.name, model, ...(effort ? { reasoningEffort: effort === 'none' ? 'off' : effort } : {}) };
      }),
      features: agent.features, groupReplyPolicy: policy === 'always' ? 'always' : 'mention_only',
      workflow: {sizeGuideline: String(this.value.agents.find(item=>item.agent_id===agent.agent_id)?.workflow_size_guideline ?? 'medium')},
      approval, knowledge: { globalSkillRoot: join(this.ownerRoot, 'skills'), enabled: evolution.enabled !== false,
        memoryInterval: evolution.memory_curation === false ? 0 : Number(evolution.memory_nudge_interval ?? 10),
        skillInterval: evolution.skill_creation === false ? 0 : Number(evolution.skill_nudge_interval ?? 10) },
      toolAllowlist: agent.tool_allowlist === undefined ? undefined : canonical.tool_allowlist,
      extensions: { global: join(this.ownerRoot, 'plugins.json'), workspace: join(agent.workspace_root!, '.nanoassistant', 'plugins.json') },
      skillSelection: { mode: canonical.skills_selection_mode === 'explicit_allowlist' ? 'explicit_allowlist' : 'default_discovery', names: canonical.skills ?? [] },
      skillRoots: [
        ...['.nanoassistant', '.claude', '.codex'].map(dir => ({ path: join(agent.workspace_root!, dir, 'skills'), source: 'workspace' })),
        { path: join(this.ownerRoot, 'skills'), source: 'global' },
        { path: join(homedir(), '.agents', 'skills'), source: 'global' },
        ...['.claude', '.codex'].map(dir => ({ path: join(homedir(), dir, 'skills'), source: 'compat' })),
      ],
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
  async setWorkflowGuideline(agentId: string, guideline: string): Promise<AgentConfiguration> {
    if (!['unrestricted', 'small', 'medium', 'large'].includes(guideline)) throw new Error('Invalid Workflow size guideline');
    const task = this.persistence.then(async () => {
      const agent = this.value.agents.find(item => item.agent_id === agentId);
      if (!agent) throw new Error('Unknown Agent');
      await this.write(this.current(agentId)!, {workflow_size_guideline: guideline});
    });
    this.persistence = task.catch(() => {}); await task;
    return this.runtime(this.value.agents.find(item => item.agent_id === agentId)!);
  }
  private async write(candidate: CanonicalAgentConfiguration, local: Record<string, unknown> = {}): Promise<void> {
    const previous = this.value.agents.find(agent => agent.agent_id === candidate.agent_id);
    const agent: LocalAgent = { ...previous, ...candidate, ...local, work_mode: candidate.work_mode as LocalAgent['work_mode'],
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
