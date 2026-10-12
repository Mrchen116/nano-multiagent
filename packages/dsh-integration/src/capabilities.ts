import { freezeMessage, MessageId, type UserMessage } from '@deepseek-ai/dsh-llm';
import { isUserInvocable, renderSkillContent } from '@deepseek-ai/dsh-skill';
import type {} from '@deepseek-ai/dsh-tool-skill';
import type {} from './policy/approval.js';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { FileSystemSkillProvider } from '@deepseek-ai/dsh-skill-filesystem';
import type { SkillCandidate, SkillProviderControl } from '@deepseek-ai/dsh-skill';
import type { AgentConfiguration } from './index.js';

/** Filters the native callable view after preset contributions are assembled. */
export class ToolSelection {
  private readonly agents = new Map<Agent, { config: AgentConfiguration; dispose?: () => void; presentation?: () => void }>();
  private changing = false;
  constructor(ctx: Context) {
    ctx.on('tools/change', () => {
      if (this.changing) return;
      this.changing = true;
      try { for (const [agent, state] of this.agents) this.refresh(agent, state); }
      finally { this.changing = false; }
    });
  }
  attach(agent: Agent, config: AgentConfiguration) {
    const state = { config }; this.agents.set(agent, state);
    agent.ctx.effect(() => () => { this.agents.delete(agent); });
    this.update(config.agentId);
  }
  catalog(agent: Agent) {
    const state = this.agents.get(agent)!;
    this.changing = true;
    try { state.dispose?.(); state.dispose = undefined; return agent.ctx.tools.schemas(agent); }
    finally { this.refresh(agent, state); this.changing = false; }
  }
  update(agentId: string) {
    this.changing = true;
    try { for (const [agent, state] of this.agents) if (state.config.agentId === agentId) this.refresh(agent, state); }
    finally { this.changing = false; }
  }
  private refresh(agent: Agent, state: { config: AgentConfiguration; dispose?: () => void; presentation?: () => void }) {
    state.dispose?.(); state.dispose = undefined;
    state.presentation?.(); state.presentation = undefined;
    const disabled = Object.entries({ task_graph: 'task_graph', memory: 'memory_curation', skill_manage: 'skill_creation' }).filter(([, feature]) => state.config.features?.[feature] === false).map(([tool]) => tool);
    if (state.config.toolAllowlist === undefined && !disabled.length) return;
    // The native PTC transport lives outside restriction layers. An empty
    // product selection must also withdraw this executable transport.
    if (state.config.toolAllowlist?.length === 0) state.presentation = agent.ctx.tools.presentAs('native');
    const known = new Set(agent.ctx.tools.schemas(agent).map(tool => tool.name));
    // Global root communication is part of the work mode, not an optional selection.
    const fixed = state.config.mode === 'global' && agent.session.header.origin !== 'subagent'
      ? ['inbox', 'conversations', 'send_message', 'subagent'] : [];
    state.dispose = agent.ctx.tools.restrict({ allow: [...new Set([...(state.config.toolAllowlist ?? [...known]), ...fixed])].filter(name => known.has(name) && name !== 'run_code' && !disabled.includes(name)) });
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
/** Native file parsing and resource loading with one selected provider surface. */
export function apply(ctx: Context, config: AgentConfiguration) {
  // Native explicit invocation only scans its own user source. Preserve Nano's
  // human attribution and adapt the gesture through the same selected registry.
  ctx.on('agent/pre-step', async ({ agent, messages, signal }, next) => {
    const decision = await next(); if (decision.kind === 'reject') return decision;
    const invoked = new Set(agent.session.snapshotEvents().flatMap(event => event.type === 'user/message' ? [event.data.id as string] : []));
    const inputs = messages.filter(message => message.source.kind === 'nano-human').map(message => ({ id: message.id as string, content: message.content }));
    // Only successful, host-observed live Inbox reads can supply explicit gestures.
    // Historical conversations and quoted commands never become fresh invocations.
    for (const message of agent.session.deriveMessages()) {
      if (message.role !== 'tool' || message.isError || !ctx.nanoApproval.sources.isLiveInbox(agent.id, message.toolCallId)) continue;
      const body = JSON.parse(message.content.filter(block => block.type === 'text').map(block => block.text).join('')) as {
        messages?: { id: string; sender: { type: string }; partial?: boolean; content: { type: string; text?: string }[] }[];
      };
      for (const input of body.messages ?? []) if (input.sender.type === 'user' && !input.partial) inputs.push({ id: input.id, content: input.content as UserMessage['content'] });
    }
    const additions: UserMessage[] = [];
    for (const input of inputs) for (const block of input.content) {
      if (block.type !== 'text') continue;
      const name = /^(?:\[[^\]]*\]\s*)*\/(?:skill:)?([a-z0-9][a-z0-9-]*)(?:\s|$)/.exec(block.text)?.[1];
      if (!name) continue;
      const id = `nano-skill:${input.id}:${name}`; if (invoked.has(id)) continue;
      const skill = await ctx.skills.get(name, { scope: agent, cwd: agent.session.header.cwd, signal });
      if (skill && isUserInvocable(skill)) {
        invoked.add(id); additions.push(freezeMessage({ id: MessageId(id), role: 'user', content: [{ type: 'text', text: renderSkillContent(skill) }], source: { kind: 'skill-invocation', name, form: 'instructions' } }));
      }
    }
    return additions.length ? { ...decision, messages: [...decision.messages, ...additions] } : decision;
  });
  const allowed = (name: string) => config.skillSelection?.mode !== 'explicit_allowlist' || config.skillSelection.names.includes(name);
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
