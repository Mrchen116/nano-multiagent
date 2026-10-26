import {fixedTools} from '@nano/product-contracts/capabilities';
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

export const goalTools = ['create_goal', 'get_goal', 'update_goal'];

/** Filters the native callable view after preset contributions are assembled. */
export class ToolSelection {
  private readonly agents = new Map<Agent, { config: AgentConfiguration; dispose?: () => void; presentation?: () => void }>();
  private changing = false;
  constructor(ctx: Context, private readonly installed: (config: AgentConfiguration) => string[] = () => []) {
    ctx.on('tools/change', () => {
      if (this.changing) return;
      this.changing = true;
      try { for (const [agent, state] of this.agents) this.refresh(agent, state); }
      finally { this.changing = false; }
    });
  }
  /** Resolve the same configured and workspace-installed collection for dispatch and selection previews. */
  selection(config: AgentConfiguration, names: string[]): string[] {
    const allow = config.toolAllowlist;
    if (allow === undefined) return names.filter(name => !goalTools.includes(name));
    const installed = allow.includes('plugin_manager') ? this.installed(config) : [];
    const selected = new Set([...allow, ...installed, ...contextTools]);
    return names.filter(name => selected.has(name));
  }
  attach(agent: Agent, config: AgentConfiguration) {
    const state = { config }; this.agents.set(agent, state);
    agent.ctx.effect(() => () => { this.agents.delete(agent); });
    this.update(config.agentId);
  }
  catalog(agent: Agent) {
    const state = this.agents.get(agent)!;
    this.changing = true;
    try {
      state.dispose?.(); state.dispose = undefined;
      const schemas = agent.ctx.tools.schemas(agent);
      const installed = new Set(this.installed(state.config));
      const selected = new Set(this.selection(state.config, schemas.map(tool => tool.name)));
      return schemas.map(tool => installed.has(tool.name)
        ? { ...tool, source_group: 'workspace' as const, enabled: selected.has(tool.name) } : tool);
    }
    finally { this.refresh(agent, state); this.changing = false; }
  }
  update(agentId: string) {
    this.changing = true;
    try { for (const [agent, state] of this.agents) if (state.config.agentId === agentId) this.refresh(agent, state); }
    finally { this.changing = false; }
  }
  private refresh(agent: Agent, state: { config: AgentConfiguration; dispose?: () => void; presentation?: () => void }) {
    // Provider teardown publishes tools/change while sibling Agent scopes are
    // already unloading; rebuilding their restrictions would register new effects.
    if (agent.ctx.fiber.uid === null) return;
    state.dispose?.(); state.dispose = undefined;
    state.presentation?.(); state.presentation = undefined;
    const disabled: string[] = [];
    if (state.config.toolAllowlist === undefined) disabled.push(...goalTools);
    if (state.config.toolAllowlist === undefined && !disabled.length) return;
    // The native PTC transport lives outside restriction layers. An empty
    // product selection must also withdraw this executable transport.
    if (state.config.toolAllowlist?.length === 0) state.presentation = agent.ctx.tools.presentAs('native');
    const known = new Set(agent.ctx.tools.schemas(agent).map(tool => tool.name));
    // Global root communication is part of the work mode, not an optional selection.
    const fixed = fixedTools(state.config.mode, agent.session.header.origin === 'subagent' ? 'subagent' : state.config.personal ? 'personal' : 'root');
    // Root PA representation is scope-local; DSH excludes local tools from inherited masks.
    state.dispose = agent.ctx.tools.restrict({ allow: [...new Set([...this.selection(state.config, [...known]), ...fixed])].filter(name => known.has(name) && name !== 'run_code' && name !== 'send_user_message' && !disabled.includes(name)) });
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
    for (const skill of candidates) if (!found.has(skill.name)) found.set(skill.name, { ...skill, rank: provider.index, source: provider.source });
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
export function apply(ctx: Context, config: AgentConfiguration) {
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
    const invoked = new Set(agent.session.snapshotEvents().flatMap(event => event.type === 'user/message' ? [event.data.id as string] : []));
    // The native middleware may append its injections after this scope returns.
    // Detect its /name syntax here solely to suppress the compatibility copy.
    const nativeNames = new Set(messages.filter(message => message.source.kind === 'user').flatMap(message => message.content.flatMap(block =>
      block.type === 'text' ? [...block.text.matchAll(/(^|\s)\/([a-z0-9]+(?:-[a-z0-9]+)*)(?=\s|$)/g)].map(match => match[2]) : [])));
    const compatibility = messages.filter(message => isHumanSource(message.source) && (message.source.kind === 'nano-human'
      || message.content.some(block => block.type === 'text' && /^(?:\[[^\]]*\]\s*)*\/skill:|^(?:\[[^\]]*\]\s*)+\//.test(block.text))));
    const gestures = [...skillGestures(compatibility).filter(gesture => !nativeNames.has(gesture.name)), ...(pending.get(agent) ?? [])];
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
  const allowed = (name: string) => config.skillSelection?.mode === 'explicit_denylist'
    ? !config.skillSelection.names.includes(name)
    : config.skillSelection?.mode !== 'explicit_allowlist' || config.skillSelection.names.includes(name);
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
          return { candidates: candidates.filter(candidate => allowed(candidate.name)).map(candidate => ({ ...candidate, rank: index, source: root.source })),
            complete: Array.isArray(found) || found.complete };
        },
        async get(candidate, options) { return allowed(candidate.name) ? native.get(candidate, options) : undefined; },
      };
    });
    ctx.effect(() => async () => { await native.dispose(); });
  }
}
