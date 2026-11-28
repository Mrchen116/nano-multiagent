import {globalWorkRole, isOrdinaryChild} from './child-role.js';
import {definitionsForRole, effectiveFeatures, effectiveSelectedTools, fixedTools} from '@nano/product-contracts/capabilities';
import { freezeMessage, MessageId, type UserMessage } from '@deepseek-ai/dsh-llm';
import { isUserInvocable, renderSkillContent } from '@deepseek-ai/dsh-skill';
import type {} from '@deepseek-ai/dsh-tool-skill';
import type {} from './policy/approval.js';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { FileSystemSkillProvider } from '@deepseek-ai/dsh-skill-filesystem';
import type { SkillCandidate, SkillProviderControl } from '@deepseek-ai/dsh-skill';
import type { AgentConfiguration } from './index.js';
import { contextTools } from './agent-context.js';
import { isHumanSource } from './input-source.js';
import type { WorkspaceToolMetadata } from './workspace-tools.js';

export const goalTools = ['create_goal', 'get_goal', 'update_goal'];
export const cordisInspectTools = ['cordis_inspect_list', 'cordis_inspect_query'] as const;
const cordisInspectSet = new Set<string>(cordisInspectTools);
const defaultOff = ['computer_use', ...goalTools, 'subagent_fork', 'exit_plan_mode'];
const userEntryTools = new Set(['ask_user_question', 'present', 'enter_plan_mode', 'exit_plan_mode', 'plugin_manager', 'workflow', ...cordisInspectTools]);

function allowsCordisInspect(config: AgentConfiguration, agent?: Agent): boolean {
  if (!config.workspace) return false;
  if (agent && (isOrdinaryChild(agent) || globalWorkRole(agent, config))) return false;
  return true;
}

/** Check whether the builtin nano-proactive-care Skill is active for a root Global session. */
export function allowsProactiveCareSkill(config: AgentConfiguration, isInternalOrWorker = false): boolean {
  if (isInternalOrWorker || config.mode !== 'global') return false;
  const eff = effectiveFeatures(config.features, definitionsForRole(Boolean(config.personal), undefined, 'global'), {
    tool_allowlist: config.toolAllowlist,
  });
  if (eff.proactive_planning !== true || eff.task_graph === false || (config.toolAllowlist && !config.toolAllowlist.includes('task_graph'))) {
    return false;
  }
  if (config.skillSelection?.mode === 'explicit_denylist') {
    return !config.skillSelection.names.includes('nano-proactive-care');
  }
  if (config.skillSelection?.mode === 'explicit_allowlist') {
    return config.skillSelection.names.includes('nano-proactive-care') || config.features?.proactive_planning === undefined;
  }
  return true;
}

/** Filters the native callable view after preset contributions are assembled. */
export class ToolSelection {
  private readonly agents = new Map<Agent, { config: AgentConfiguration; isWorkWorker: boolean; dispose?: () => void }>();
  private changing = false;
  private nativeDefaults?: Set<string>;
  constructor(
    private readonly ctx: Context,
    private readonly installed: (config: AgentConfiguration) => string[] = () => [],
    private readonly installedMetadata: (config: AgentConfiguration) => ReadonlyMap<string, WorkspaceToolMetadata> = () => new Map(),
  ) {
    ctx.on('tools/change', () => {
      if (this.changing) return;
      this.changing = true;
      try { for (const [agent, state] of this.agents) this.refresh(agent, state); }
      finally { this.changing = false; }
    });
  }
  /** Snapshot the loaded runtime before Nano mounts product or workspace contributions. */
  captureDefaults(): void { this.nativeDefaults ??= new Set(this.ctx.tools.schemas().map(tool => tool.name)); }
  /** Whether a Global child tool remains available independently of root selection. */
  independentTool(agent: Agent, config: AgentConfiguration, name: string): boolean {
    return !!globalWorkRole(agent, config) && !!this.nativeDefaults?.has(name) && !goalTools.includes(name) && !userEntryTools.has(name);
  }
  /** Resolve the same configured and workspace-installed collection for dispatch and selection previews. */
  selection(config: AgentConfiguration, names: string[], agent?: Agent): string[] {
    const allow = config.toolAllowlist;
    const inspectAllowed = allowsCordisInspect(config, agent);
    if (allow === undefined) return names.filter(name => cordisInspectSet.has(name) ? inspectAllowed : (agent && this.independentTool(agent, config, name) || !defaultOff.includes(name)));
    const effectiveAllow = effectiveSelectedTools({ features: config.features, tool_allowlist: allow, work_mode: config.mode, personal_agent: config.personal }, { tools: names });
    const installed = allow.includes('plugin_manager') ? this.installed(config) : [];
    const selected = new Set([...effectiveAllow, ...installed, ...contextTools]);
    return names.filter(name => cordisInspectSet.has(name) ? (inspectAllowed && selected.has(name)) : (selected.has(name) || agent && this.independentTool(agent, config, name)));
  }
  attach(agent: Agent, config: AgentConfiguration, isWorkWorker: boolean) {
    const state = { config, isWorkWorker }; this.agents.set(agent, state);
    agent.ctx.effect(() => () => { this.agents.delete(agent); });
    this.update(config.agentId);
  }
  catalog(agent: Agent) {
    const state = this.agents.get(agent)!;
    this.changing = true;
    try {
      state.dispose?.(); state.dispose = undefined;
      const inspectAllowed = allowsCordisInspect(state.config, agent);
      const schemas = agent.ctx.tools.schemas(agent).filter(tool => inspectAllowed || !cordisInspectSet.has(tool.name));
      const installed = new Set(this.installed(state.config));
      const metadata = this.installedMetadata(state.config);
      const selected = new Set(this.selection(state.config, schemas.map(tool => tool.name), agent));
      return schemas.map(tool => {
        if (!installed.has(tool.name)) return tool;
        const owner = metadata.get(tool.name);
        return {
          ...tool,
          source_group: 'workspace' as const,
          enabled: selected.has(tool.name),
          ...(owner ? { plugin_bundle: owner.plugin_bundle, plugin_title: owner.plugin_title } : {}),
        };
      });
    }
    finally { this.refresh(agent, state); this.changing = false; }
  }
  update(agentId: string) {
    this.changing = true;
    try { for (const [agent, state] of this.agents) if (state.config.agentId === agentId) this.refresh(agent, state); }
    finally { this.changing = false; }
  }
  private refresh(agent: Agent, state: { config: AgentConfiguration; isWorkWorker: boolean; dispose?: () => void }) {
    // Provider teardown publishes tools/change while sibling Agent scopes are
    // already unloading; rebuilding their restrictions would register new effects.
    if (agent.ctx.fiber.uid === null) return;
    state.dispose?.(); state.dispose = undefined;
    const disabled: string[] = [state.config.knowledge?.memoryMode === 'legacy' ? 'memory_maintenance' : 'memory'];
    if (state.isWorkWorker) disabled.push('memory', 'memory_maintenance');
    if (!allowsCordisInspect(state.config, agent)) disabled.push(...cordisInspectTools);
    if (state.config.toolAllowlist === undefined) disabled.push('computer_use', ...goalTools, 'exit_plan_mode', ...(!globalWorkRole(agent, state.config) ? ['subagent_fork'] : []));
    // Explicit root forks inherit the root declarations, including its delegation boundary.
    if (state.config.mode === 'global' && (agent.session.header.origin !== 'subagent' ||
      agent.session.header.delegationDepth === 1 && !isOrdinaryChild(agent))) disabled.push('subagent');
    if (globalWorkRole(agent, state.config)) disabled.push(...userEntryTools);
    if (isOrdinaryChild(agent) || globalWorkRole(agent, state.config)) disabled.push('computer_use', 'conversations', 'read_messages', 'search_messages', 'threads', 'download_attachment', 'personal_sources', 'agent_creation', 'schedule_run', 'schedule_history');
    if (state.config.toolAllowlist === undefined && !disabled.length) return;
    const known = new Set(agent.ctx.tools.schemas(agent).map(tool => tool.name));
    // Global root communication is part of the work mode, not an optional selection.
    const fixed = fixedTools(state.config.mode, isOrdinaryChild(agent) || globalWorkRole(agent, state.config) ? 'subagent' : state.config.personal ? 'personal' : 'root');
    // Root product tools are scope-local; DSH excludes local-only names from inherited masks.
    state.dispose = agent.ctx.tools.restrict({ allow: [...new Set([...this.selection(state.config, [...known], agent), ...fixed])].filter(name => known.has(name) && name !== 'run_code' && name !== 'send_user_message' && !(state.config.mode === 'global' && ['inbox', 'conversations', 'read_messages', 'search_messages', 'threads', 'download_attachment', 'delegate_worker'].includes(name)) && !disabled.includes(name)) });
  }
}

export const name = 'nano-selected-skills';
export const inject = ['skills', 'nanoApproval'];
const providers = new WeakMap<AgentConfiguration, Set<{ native: FileSystemSkillProvider; control: SkillProviderControl; index: number; source: string }>>();
export function invalidateSkills(config: AgentConfiguration) { for (const provider of providers.get(config) ?? []) provider.control.invalidate(); }
/** Unselected candidates for settings, using the same native discovery and precedence. */
export async function skillCatalog(config: AgentConfiguration, cwd: string) {
  const found = new Map<string, SkillCandidate>();
  for (const provider of [...(providers.get(config) ?? [])].sort((a, b) => a.index - b.index)) {
    const result = await provider.native.list({ cwd });
    const candidates = (Array.isArray(result) ? result : result.candidates) as SkillCandidate[];
    for (const skill of candidates) {
      if (skill.name === 'skill-creator') continue;
      if (skill.name === 'nano-proactive-care' && (provider.source !== 'builtin' || config.mode !== 'global')) continue;
      if (!found.has(skill.name)) found.set(skill.name, { ...skill, rank: provider.index, source: provider.source });
    }
  }
  return [...found.values()];
}
type SkillGesture = { id: string; name: string };
function skillGestures(inputs: { id: string; content: UserMessage['content'] }[]): SkillGesture[] {
  return inputs.flatMap(input => input.content.flatMap(block => {
    if (block.type !== 'text') return [];
    const name = /^(?:\[[^\]]*\]\s*)*\/(?:skill:)?([a-z0-9][a-z0-9-]*)(?:\s|$)/.exec(block.text)?.[1];
    return name ? [{ id: `nano-skill:${input.id}:${name}`, name }] : [];
  }));
}
/** Native file parsing and resource loading with one selected provider surface. */
export function apply(ctx: Context, {config, isWorkWorker, isInternalChild = false}: {config: AgentConfiguration; isWorkWorker: boolean; isInternalChild?: boolean}) {
  const pending = new WeakMap<Agent, SkillGesture[]>();
  // Consume the complete host value once; later pruning may make its rendered JSON incomplete.
  ctx.on('tools/result', (exec, result) => {
    const agent = exec.agent;
    if (exec.name !== 'inbox' || !agent || result.isError || !ctx.nanoApproval.sources.isLiveInbox(agent.id, exec.callId)) return;
    const body = (result.value as unknown as { body: {
      messages?: { id: string; sender: { type: string }; partial?: boolean; content: UserMessage['content'] }[];
    } }).body;
    const gestures = skillGestures((body.messages ?? []).filter(input => input.sender.type === 'user' && !input.partial));
    if (gestures.length) pending.set(agent, [...(pending.get(agent) ?? []), ...gestures]);
  });
  // Native /name owns direct user gestures. Only bridge Nano's older syntax
  // (/skill:name or an attached [label]) and pending legacy nano-human inputs.
  ctx.on('agent/pre-step', async ({ agent, messages, signal }, next) => {
    const decision = await next(); if (decision.kind === 'reject') return decision;
    // The native middleware may append its injections after this scope returns.
    // Detect its /name syntax here solely to suppress the compatibility copy.
    const nativeNames = new Set(messages.filter(message => message.source.kind === 'user').flatMap(message => message.content.flatMap(block =>
      block.type === 'text' ? [...block.text.matchAll(/(^|\s)\/([a-z0-9]+(?:-[a-z0-9]+)*)(?=\s|$)/g)].map(match => match[2]) : [])));
    const compatibility = messages.filter(message => isHumanSource(message.source) && (message.source.kind === 'nano-human'
      || message.content.some(block => block.type === 'text' && /^(?:\[[^\]]*\]\s*)*\/skill:|^(?:\[[^\]]*\]\s*)+\//.test(block.text))));
    const gestures = [...skillGestures(compatibility).filter(gesture => !nativeNames.has(gesture.name)), ...(pending.get(agent) ?? [])];
    if (!gestures.length) { pending.delete(agent); return decision; }
    const invoked = new Set(agent.session.snapshotEvents().flatMap(event => event.type === 'user/message' ? [event.data.id as string] : []));
    const additions: UserMessage[] = [];
    for (const { id, name } of gestures) {
      if (invoked.has(id)) continue;
      const skill = await ctx.skills.get(name, { scope: agent, cwd: agent.session.header.cwd, signal });
      if (skill && isUserInvocable(skill)) {
        invoked.add(id); additions.push(freezeMessage({ id: MessageId(id), role: 'user', content: [{ type: 'text', text: renderSkillContent(skill) }], source: { kind: 'skill-invocation', name, form: 'instructions' } }));
      }
    }
    pending.delete(agent);
    return additions.length ? { ...decision, messages: [...decision.messages, ...additions] } : decision;
  });
  // Only the host-supplied package root owns fixed guidance; user copies cannot shadow it.
  const allowed = (name: string, source: string) => {
    if (isWorkWorker && name === 'nano-memory') return false;
    if (name === 'skill-creator') return source === 'builtin';
    if (name === 'nano-proactive-care') {
      return source === 'builtin' && allowsProactiveCareSkill(config, isWorkWorker || isInternalChild);
    }
    return config.skillSelection?.mode === 'explicit_denylist'
      ? !config.skillSelection.names.includes(name)
      : config.skillSelection?.mode !== 'explicit_allowlist' || config.skillSelection.names.includes(name);
  };
  for (const [index, root] of (config.skillRoots ?? []).entries()) {
    let native!: FileSystemSkillProvider;
    const providerName = `nano-files-${index}`;
    ctx.skills.registerProvider(control => {
      native = new FileSystemSkillProvider(ctx, control, { providerName, includeDefaultRoots: false, customSkillDirs: [root.path], watch: true });
      let entries = providers.get(config); if (!entries) { entries = new Set(); providers.set(config, entries); }
      const entry = { native, control, index, source: root.source }; entries.add(entry);
      ctx.effect(() => () => { entries.delete(entry); });
      return { name: providerName,
        async list(options) {
          const found = await native.list(options);
          const candidates = (Array.isArray(found) ? found : found.candidates) as SkillCandidate[];
          return { candidates: candidates.filter(candidate => allowed(candidate.name, root.source)).map(candidate => ({ ...candidate, rank: index, source: root.source })),
            complete: Array.isArray(found) || found.complete };
        },
        async get(candidate, options) {
          return allowed(candidate.name, root.source) ? native.get(candidate, options) : undefined;
        },
      };
    });
    ctx.effect(() => async () => { await native.dispose(); });
  }
}
