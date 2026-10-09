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
  update(agentId: string) {
    this.changing = true;
    try { for (const [agent, state] of this.agents) if (state.config.agentId === agentId) this.refresh(agent, state); }
    finally { this.changing = false; }
  }
  private refresh(agent: Agent, state: { config: AgentConfiguration; dispose?: () => void; presentation?: () => void }) {
    state.dispose?.(); state.dispose = undefined;
    state.presentation?.(); state.presentation = undefined;
    if (state.config.toolAllowlist === undefined) return;
    // The native PTC transport lives outside restriction layers. An empty
    // product selection must also withdraw this executable transport.
    if (!state.config.toolAllowlist.length) state.presentation = agent.ctx.tools.presentAs('native');
    const known = new Set(agent.ctx.tools.schemas(agent).map(tool => tool.name));
    state.dispose = agent.ctx.tools.restrict({ allow: state.config.toolAllowlist.filter(name => known.has(name) && name !== 'run_code') });
  }
}

export const name = 'nano-selected-skills';
export const inject = ['skills'];
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
