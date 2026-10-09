import { Context, Service } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import * as Skills from './capabilities.js';
import { ToolSelection } from './capabilities.js';
import { mountExtensions } from './extensions.js';
import * as Persona from '@deepseek-ai/dsh-persona';
import * as GlobalMode from './global-mode.js';
import * as TaskGraphs from './features/task-graphs.js';
import * as Heartbeat from './features/heartbeat.js';
import * as MemoryCuration from './features/memory-curation.js';
import * as SkillCreation from './features/skill-creation.js';
import * as Cron from './features/cron.js';
import type { AgentConfiguration } from './index.js';

type Fiber = ReturnType<Context['plugin']>;
interface PresetScope { agentId: string; ctx: Context; features: Map<string, Fiber> }
interface AgentScope { agent: Agent; config: AgentConfiguration; persona?: Fiber; skills?: Fiber }
declare module '@deepseek-ai/cordis' { interface Context { nanoConfiguration: ConfigurationScopes } }

/** Keeps inherited tool contributions filterable and history configuration Agent-local. */
export class ConfigurationScopes extends Service {
  private readonly presets = new Set<PresetScope>();
  private readonly agents = new Map<Agent, AgentScope>();
  private readonly tools: ToolSelection;
  private readonly sharedExtensions = new Map<string, Promise<void>>();
  private readonly host: Context;
  constructor(ctx: Context, readonly configurations: Map<string, AgentConfiguration>) { super(ctx, 'nanoConfiguration'); this.host = ctx; this.tools = new ToolSelection(ctx); }
  forAgent(agent: Agent) { return this.agents.get(agent)?.config; }
  async whenIdle(agentId: string) { await Promise.all([...this.agents.values()].filter(scope => scope.config.agentId === agentId).map(scope => scope.agent.whenIdle())); }
  catalog(agent: Agent) { return this.tools.catalog(agent); }
  private allConfigurations() { return new Set([...this.configurations.values(), ...[...this.agents.values()].map(scope => scope.config)]); }
  private config(agentId: string) {
    const config = [...this.configurations.values()].find(config => config.agentId === agentId);
    if (!config) throw new Error(`Missing configuration for ${agentId}`);
    return config;
  }
  /** Called while the native preset generation is assembled, above Agent restrictions. */
  async attach(ctx: Context, agentId: string): Promise<void> {
    const config = this.config(agentId);
    if (config.extensions?.global) {
      const path = config.extensions.global;
      if (!this.sharedExtensions.has(path)) this.sharedExtensions.set(path, mountExtensions(this.host, path));
      await this.sharedExtensions.get(path);
    }
    await mountExtensions(ctx, config.extensions?.workspace);
    const scope: PresetScope = { agentId, ctx, features: new Map() };
    this.presets.add(scope); ctx.effect(() => () => { this.presets.delete(scope); });
    if (config.mode === 'global') await ctx.plugin(GlobalMode).await();
    await ctx.plugin(Cron, { agentId }).await();
    await this.features(scope);
    ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
      const assembly = await next(); const agent = context.agent ?? context.scope as Agent | undefined;
      const selected = agent && this.forAgent(agent); if (!selected) return assembly;
      const disabled = new Set<string>();
      for (const [feature, section] of [['task_graph', 'nano-task-graphs'], ['memory_curation', 'nano-memory'], ['skill_creation', 'nano-skill-creation']] as const) if (selected.features?.[feature] === false) disabled.add(section);
      if (!selected.features?.heartbeat) disabled.add('nano-heartbeat');
      assembly.sections = assembly.sections.filter(section => !disabled.has(section.name));
      assembly.contexts = assembly.contexts.filter(section => !disabled.has(section.name));
      return assembly;
    }, { prepend: true });
  }
  async attachAgent(agent: Agent, config: AgentConfiguration): Promise<void> {
    const scope: AgentScope = { agent, config }; this.agents.set(agent, scope);
    agent.ctx.effect(() => () => { this.agents.delete(agent); });
    for (const preset of this.presets) if (preset.agentId === config.agentId) await this.features(preset);
    if (config.systemPrompt) { scope.persona = agent.ctx.plugin(Persona, { prefix: config.systemPrompt }); await scope.persona.await(); }
    scope.skills = agent.ctx.plugin(Skills, config); await scope.skills.await();
    this.tools.attach(agent, config);
  }
  async setFeatures(agentId: string, features: Record<string, boolean>): Promise<void> {
    for (const config of this.allConfigurations()) if (config.agentId === agentId) config.features = { ...features };
    for (const scope of this.presets) if (scope.agentId === agentId) await this.features(scope);
    this.tools.update(agentId);
  }
  /** Withdraw choices now; additions and the rest of the configuration wait for idle. */
  restrictSelection(next: AgentConfiguration): void {
    for (const config of this.allConfigurations()) if (config.agentId === next.agentId) {
      if (next.toolAllowlist !== undefined) config.toolAllowlist = config.toolAllowlist === undefined ? [...next.toolAllowlist] : config.toolAllowlist.filter(name => next.toolAllowlist!.includes(name));
      if (next.skillSelection?.mode === 'explicit_allowlist') config.skillSelection = { mode: 'explicit_allowlist', names: config.skillSelection?.mode === 'explicit_allowlist' ? config.skillSelection.names.filter(name => next.skillSelection!.names.includes(name)) : [...next.skillSelection.names] };
      Skills.invalidateSkills(config);
    }
    this.tools.update(next.agentId);
  }
  async setConfiguration(next: AgentConfiguration): Promise<void> {
    for (const scope of this.agents.values()) if (scope.config.agentId === next.agentId && scope.config.systemPrompt !== next.systemPrompt) {
      await scope.persona?.dispose(); scope.persona = undefined;
      if (next.systemPrompt) { scope.persona = scope.agent.ctx.plugin(Persona, { prefix: next.systemPrompt }); await scope.persona.await(); }
    }
    for (const config of this.allConfigurations()) if (config.agentId === next.agentId) {
      for (const key of Object.keys(config)) delete (config as unknown as Record<string, unknown>)[key];
      Object.assign(config, next);
    }
    for (const scope of this.agents.values()) if (scope.config.agentId === next.agentId) {
      await scope.skills?.dispose(); scope.skills = scope.agent.ctx.plugin(Skills, scope.config); await scope.skills.await();
    }
    await this.setFeatures(next.agentId, next.features ?? {});
  }
  private async features(scope: PresetScope) {
    // Historical branches may retain a Feature disabled in the current template.
    // The native Agent restriction and prompt view still apply its exact choices.
    const configs = [...this.allConfigurations()].filter(config => config.agentId === scope.agentId);
    for (const [key, plugin] of [['memory_curation', MemoryCuration], ['skill_creation', SkillCreation], ['task_graph', TaskGraphs], ['heartbeat', Heartbeat]] as const) {
      const enabled = configs.some(config => key === 'heartbeat' ? config.features?.[key] === true : config.features?.[key] !== false);
      const existing = scope.features.get(key);
      if (!enabled && existing) { await existing.dispose(); scope.features.delete(key); }
      if (enabled && !existing) { const fiber = scope.ctx.plugin(plugin, { agentId: scope.agentId }); await fiber.await(); scope.features.set(key, fiber); }
    }
  }
}

export const name = 'nano-agent-config';
export const inject = ['nanoConfiguration'];
/** Native presets retain the shared capability layer used by Agent restrictions. */
export function apply(ctx: Context, config: { agentId: string }) { return ctx.nanoConfiguration.attach(ctx, config.agentId); }
