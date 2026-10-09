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
interface Scope { agentId: string; ctx: Context; features: Map<string, Fiber>; persona?: Fiber; skills?: Fiber }
declare module '@deepseek-ai/cordis' { interface Context { nanoConfiguration: ConfigurationScopes } }

/** Tracks only Nano's contributions; disposing a Feature preserves the native Agent. */
export class ConfigurationScopes extends Service {
  private readonly scopes = new Set<Scope>();
  private readonly tools: ToolSelection;
  private readonly sharedExtensions = new Map<string, Promise<void>>();
  private readonly host: Context;
  constructor(ctx: Context, readonly configurations: Map<string, AgentConfiguration>) { super(ctx, 'nanoConfiguration'); this.host = ctx; this.tools = new ToolSelection(ctx); }
  attachAgent(agent: Agent, config: AgentConfiguration) { this.tools.attach(agent, config); }
  private config(agentId: string) {
    const config = [...this.configurations.values()].find(config => config.agentId === agentId);
    if (!config) throw new Error(`Missing configuration for ${agentId}`);
    return config;
  }
  async attach(ctx: Context, agentId: string): Promise<void> {
    const config = this.config(agentId);
    if (config.extensions?.global) {
      const path = config.extensions.global;
      if (!this.sharedExtensions.has(path)) this.sharedExtensions.set(path, mountExtensions(this.host, path));
      await this.sharedExtensions.get(path);
    }
    await mountExtensions(ctx, config.extensions?.workspace);
    const scope: Scope = { agentId, ctx, features: new Map() };
    this.scopes.add(scope);
    ctx.effect(() => () => { this.scopes.delete(scope); });
    if (config.systemPrompt) { scope.persona = ctx.plugin(Persona, { prefix: config.systemPrompt }); await scope.persona.await(); }
    if (config.mode === 'global') await ctx.plugin(GlobalMode).await();
    await ctx.plugin(Cron, { agentId }).await();
    await this.features(scope, config.features ?? {});
    scope.skills = ctx.plugin(Skills, config); await scope.skills.await();
  }
  async setFeatures(agentId: string, features: Record<string, boolean>): Promise<void> {
    for (const config of this.configurations.values()) if (config.agentId === agentId) config.features = { ...features };
    for (const scope of this.scopes) if (scope.agentId === agentId) await this.features(scope, features);
  }
  /** Withdraw choices now; additions and the rest of the configuration wait for idle. */
  restrictSelection(next: AgentConfiguration): void {
    const config = this.config(next.agentId);
    if (next.toolAllowlist !== undefined) config.toolAllowlist = config.toolAllowlist === undefined
      ? [...next.toolAllowlist] : config.toolAllowlist.filter(name => next.toolAllowlist!.includes(name));
    if (next.skillSelection?.mode === 'explicit_allowlist') config.skillSelection = {
      mode: 'explicit_allowlist', names: config.skillSelection?.mode === 'explicit_allowlist'
        ? config.skillSelection.names.filter(name => next.skillSelection!.names.includes(name)) : [...next.skillSelection.names],
    };
    this.tools.update(next.agentId);
    Skills.invalidateSkills(config);
  }
  async setConfiguration(next: AgentConfiguration): Promise<void> {
    const previous = this.config(next.agentId);
    for (const scope of this.scopes) if (scope.agentId === next.agentId && previous.systemPrompt !== next.systemPrompt) {
      await scope.persona?.dispose(); scope.persona = undefined;
      if (next.systemPrompt) { scope.persona = scope.ctx.plugin(Persona, { prefix: next.systemPrompt }); await scope.persona.await(); }
    }
    for (const config of new Set(this.configurations.values())) if (config.agentId === next.agentId) {
      for (const key of Object.keys(config)) delete (config as unknown as Record<string, unknown>)[key];
      Object.assign(config, next);
    }
    for (const scope of this.scopes) if (scope.agentId === next.agentId) {
      await scope.skills?.dispose(); scope.skills = scope.ctx.plugin(Skills, this.config(next.agentId)); await scope.skills.await();
    }
    await this.setFeatures(next.agentId, next.features ?? {});
    this.tools.update(next.agentId);
  }
  private async features(scope: Scope, features: Record<string, boolean>) {
    for (const [key, plugin] of [['memory_curation', MemoryCuration], ['skill_creation', SkillCreation]] as const) {
      const existing = scope.features.get(key);
      if (features[key] === false && existing) { await existing.dispose(); scope.features.delete(key); }
      if (features[key] !== false && !existing) { const fiber = scope.ctx.plugin(plugin, { agentId: scope.agentId }); await fiber.await(); scope.features.set(key, fiber); }
    }
    const heartbeat = scope.features.get('heartbeat');
    if (!features.heartbeat && heartbeat) { await heartbeat.dispose(); scope.features.delete('heartbeat'); }
    if (features.heartbeat && !heartbeat) { const fiber = scope.ctx.plugin(Heartbeat); await fiber.await(); scope.features.set('heartbeat', fiber); }
    const taskGraphs = scope.features.get('task_graph');
    if (features.task_graph === false && taskGraphs) { await taskGraphs.dispose(); scope.features.delete('task_graph'); }
    if (features.task_graph !== false && !taskGraphs) {
      const fiber = scope.ctx.plugin(TaskGraphs); await fiber.await(); scope.features.set('task_graph', fiber);
    }
  }
}

export const name = 'nano-agent-config';
export const inject = ['nanoConfiguration'];
/** The saved preset joins the current node-owned configuration for its Agent. */
export function apply(ctx: Context, config: { agentId: string }) { return ctx.nanoConfiguration.attach(ctx, config.agentId); }
