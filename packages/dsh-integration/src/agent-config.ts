import { Context, Service } from '@deepseek-ai/cordis';
import * as Persona from '@deepseek-ai/dsh-persona';
import * as GlobalMode from './global-mode.js';
import * as TaskGraphs from './features/task-graphs.js';
import * as Heartbeat from './features/heartbeat.js';
import * as Cron from './features/cron.js';
import type { AgentConfiguration } from './index.js';

type Fiber = ReturnType<Context['plugin']>;
interface Scope { agentId: string; ctx: Context; features: Map<string, Fiber>; persona?: Fiber }
declare module '@deepseek-ai/cordis' { interface Context { nanoConfiguration: ConfigurationScopes } }

/** Tracks only Nano's contributions; disposing a Feature preserves the native Agent. */
export class ConfigurationScopes extends Service {
  private readonly scopes = new Set<Scope>();
  constructor(ctx: Context, readonly configurations: Map<string, AgentConfiguration>) { super(ctx, 'nanoConfiguration'); }
  private config(agentId: string) {
    const config = [...this.configurations.values()].find(config => config.agentId === agentId);
    if (!config) throw new Error(`Missing configuration for ${agentId}`);
    return config;
  }
  async attach(ctx: Context, agentId: string): Promise<void> {
    const config = this.config(agentId);
    const scope: Scope = { agentId, ctx, features: new Map() };
    this.scopes.add(scope);
    ctx.effect(() => () => { this.scopes.delete(scope); });
    if (config.systemPrompt) { scope.persona = ctx.plugin(Persona, { prefix: config.systemPrompt }); await scope.persona.await(); }
    if (config.mode === 'global') await ctx.plugin(GlobalMode).await();
    await ctx.plugin(Cron, { agentId }).await();
    await this.features(scope, config.features ?? {});
  }
  async setFeatures(agentId: string, features: Record<string, boolean>): Promise<void> {
    for (const config of this.configurations.values()) if (config.agentId === agentId) config.features = { ...features };
    for (const scope of this.scopes) if (scope.agentId === agentId) await this.features(scope, features);
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
    await this.setFeatures(next.agentId, next.features ?? {});
  }
  private async features(scope: Scope, features: Record<string, boolean>) {
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
