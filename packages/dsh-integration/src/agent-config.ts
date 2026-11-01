import {attachChildRole, isOrdinaryChild, trackForkCreation} from './child-role.js';
import * as PersonalTools from './personal-security.js';
import { assertPersonalConfiguration } from './personal-security.js';
import { realpath } from 'node:fs/promises';
import { isDeepStrictEqual } from 'node:util';
import type { ProfilePnpmInvocation } from '@deepseek-ai/dsh-app-boot';
import { Context, Service } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import * as Skills from './capabilities.js';
import { ToolSelection } from './capabilities.js';
import { mountExtensions } from './extensions.js';
import * as Persona from '@deepseek-ai/dsh-persona';
import * as GlobalMode from './global-mode.js';
import * as ContextOrder from './context-order.js';
import * as TaskGraphs from './features/task-graphs.js';
import * as Heartbeat from './features/heartbeat.js';
import * as IntelligentUI from './features/intelligent-ui.js';
import * as MemoryCuration from './features/memory-curation.js';
import * as SkillCreation from './features/skill-creation.js';
import * as Cron from './features/cron.js';
import type { AgentConfiguration } from './index.js';
import { WorkspaceExtensions, type PluginCommand } from './workspace-tools.js';

type Fiber = ReturnType<Context['plugin']>;
interface PresetScope { agentId: string; ctx: Context; features: Map<string, Fiber> }
interface AgentScope { agent: Agent; config: AgentConfiguration; workspace?: string; persona?: Fiber; skills?: Fiber }
declare module '@deepseek-ai/cordis' { interface Context { nanoConfiguration: ConfigurationScopes } }

/** Keeps inherited tool contributions filterable and history configuration Agent-local. */
export class ConfigurationScopes extends Service {
  static inject = ['tools', 'hmr'];
  private readonly maintenance = new Map<string, Promise<void>>();
  private readonly presets = new Set<PresetScope>();
  private readonly presetReadiness = new Map<string, Set<Promise<void>>>();
  private readonly agents = new Map<Agent, AgentScope>();
  private readonly tools: ToolSelection;
  private readonly sharedExtensions = new Map<string, Promise<void>>();
  private readonly host: Context;
  private readonly extensions: WorkspaceExtensions;
  readonly configurations: Map<string, AgentConfiguration>;
  constructor(ctx: Context, options: {configurations: Map<string, AgentConfiguration>; changed: (agentId: string) => void}) {
    super(ctx, 'nanoConfiguration'); this.host = ctx; this.configurations = options.configurations;
    trackForkCreation(ctx);
    this.extensions = new WorkspaceExtensions(ctx, (id, catalogChanged) => {this.tools.update(id); if (catalogChanged) options.changed(id);});
    this.tools = new ToolSelection(ctx, config => this.extensions.tools(config.agentId));
  }
  /** Configure the trusted Node package invocation before any workspace is mounted.
   *
   * Args:
   *   invocation: Application-owned package command, or the native source default.
   */
  packageManager(invocation?: ProfilePnpmInvocation) { this.extensions.packageManager = invocation; }
  forAgent(agent: Agent) { return this.agents.get(agent)?.config; }
  /** Advance metadata without replacing a historical branch's distinct execution choices.
   *
   * Args:
   *   next: Current requested configuration.
   * Returns:
   *   Whether every live/template scope already has the requested execution settings.
   */
  applyRevisionOnly(next: AgentConfiguration): boolean {
    const configs = [...this.allConfigurations()].filter(config => config.agentId === next.agentId);
    const { revision: _, ...execution } = next;
    if (!configs.length || configs.some(({ revision: _revision, ...current }) => !isDeepStrictEqual(current, execution))) return false;
    for (const config of configs) config.revision = next.revision;
    return true;
  }
  async whenIdle(agentId: string) { await Promise.all([...this.agents.values()].filter(scope => scope.config.agentId === agentId).map(scope => scope.agent.whenIdle())); }
  catalog(agent: Agent) { return this.tools.catalog(agent); }
  /** Apply owner plugin changes only while every Agent sharing the workspace is reserved idle. */
  managePlugins(config: AgentConfiguration, command: PluginCommand) {
    return this.extensions.manage(config, command, (workspace, job) => this.maintain(workspace, job));
  }
  private async maintain(workspace: string, job: () => Promise<void>): Promise<void> {
    const agents = () => [...this.agents.values()].filter(scope => scope.workspace === workspace).map(scope => scope.agent);
    for (;;) {
      await Promise.all(agents().map(agent => agent.whenIdle()));
      let release!: () => void;
      const released = new Promise<void>(resolve => {release = resolve;});
      const tasks: Promise<unknown>[] = [];
      this.maintenance.set(workspace, released);
      let reserved = true;
      // No await between the fresh snapshot and all native idle reservations.
      try { for (const agent of agents()) tasks.push(agent.runMaintenance(() => released)); }
      catch { reserved = false; }
      try { if (reserved) {await job(); return;} }
      finally { this.maintenance.delete(workspace); release(); await Promise.allSettled(tasks); }
    }
  }
  /** Project the callable selection, including authorized workspace installations. */
  selection(config: AgentConfiguration, names: string[]) { return this.tools.selection(config, names); }
  private allConfigurations() { return new Set([...this.configurations.values(), ...[...this.agents.values()].map(scope => scope.config)]); }
  private config(agentId: string) {
    const config = [...this.configurations.values()].find(config => config.agentId === agentId);
    if (!config) throw new Error(`Missing configuration for ${agentId}`);
    return config;
  }
  /** Called while the native preset generation is assembled, above Agent restrictions. */
  attach(ctx: Context, agentId: string): Promise<void> {
    const pending = this.presetReadiness.get(agentId) ?? new Set<Promise<void>>();
    this.presetReadiness.set(agentId, pending);
    const ready = this.attachPreset(ctx, agentId);
    pending.add(ready);
    ctx.effect(() => () => { pending.delete(ready); if (!pending.size) this.presetReadiness.delete(agentId); });
    return ready;
  }
  /** Await Nano's asynchronous workspace composition before projecting a cold preset. */
  async ready(agentId: string): Promise<void> { await Promise.all(this.presetReadiness.get(agentId) ?? []); }
  private async attachPreset(ctx: Context, agentId: string): Promise<void> {
    const config = this.config(agentId);
    assertPersonalConfiguration(config);
    if (config.extensions?.global) {
      const path = config.extensions.global;
      if (!this.sharedExtensions.has(path)) this.sharedExtensions.set(path, mountExtensions(this.host, path));
      await this.sharedExtensions.get(path);
    }
    await mountExtensions(ctx, config.extensions?.workspace);
    const scope: PresetScope = { agentId, ctx, features: new Map() };
    this.presets.add(scope); ctx.effect(() => () => { this.presets.delete(scope); });
    // Product chat tools must not be inherited through the shared Global preset.
    if (config.mode !== 'global') await ctx.plugin(GlobalMode, { mode: config.mode }).await();
    await ctx.inject(['tools', 'nanoProduct', 'nanoKnowledge', 'skills'], child => {
      TaskGraphs.registerTool(child, agent => this.forAgent(agent)); MemoryCuration.registerTool(child); SkillCreation.registerTool(child); child.nanoKnowledge.documents.registerTool(child);
    }).await();
    await ctx.plugin(Cron, { agentId }).await();
    await this.features(scope);
    await this.extensions.attach(ctx, config);
    if (config.personal) await ctx.plugin(PersonalTools, config).await();
    ctx.on('system-prompt/assemble', async (_assembly, context, next) => {
      const assembly = await next(); const agent = context.agent ?? context.scope as Agent | undefined;
      const selected = agent && this.forAgent(agent); if (!selected) return assembly;
      const disabled = new Set<string>();
      for (const [feature, section] of [['intelligent_ui', 'nano-interactive-replies'], ['task_graph', 'nano-task-graphs'], ['memory_curation', 'nano-memory']] as const) if (selected.features?.[feature] === false) disabled.add(section);
      if (!selected.features?.cron_scheduling) disabled.add('nano-cron');
      if (!selected.features?.heartbeat) disabled.add('nano-heartbeat');
      if (!this.tools.selection(selected, Skills.goalTools).length) disabled.add('tool:goal');
      assembly.sections = assembly.sections.filter(section => !disabled.has(section.name));
      for (const section of assembly.sections) if (section.name === 'tool:write' || section.name === 'tool:edit')
        section.text = section.text.replace(' (the default fs-observation-policy requires it)', '');
      assembly.contexts = assembly.contexts.filter(section => !disabled.has(section.name));
      return assembly;
    }, { prepend: true });
  }
  async attachAgent(agent: Agent, config: AgentConfiguration): Promise<void> {
    attachChildRole(agent);
    const workspace = config.workspace ? await realpath(config.workspace) : undefined;
    while (workspace && this.maintenance.has(workspace)) await this.maintenance.get(workspace);
    const scope: AgentScope = { agent, config, workspace }; this.agents.set(agent, scope);
    agent.ctx.effect(() => () => { this.agents.delete(agent); });
    agent.ctx.systemPrompt.section({ name: 'nano-product-identity', order: 5, interpolate: false, text: () => {
      const name = JSON.stringify(scope.config.displayName ?? scope.config.agentId);
      const id = JSON.stringify(scope.config.agentId);
      return isOrdinaryChild(agent)
        ? `You are an internal subagent of this product Agent:\nAgent name: ${name}\nAgent ID: ${id}`
        : `Your Agent name: ${name}\nYour Agent ID: ${id}`;
    } });
    for (const preset of this.presets) if (preset.agentId === config.agentId) await this.features(preset);
    if (config.systemPrompt && !isOrdinaryChild(agent)) { scope.persona = agent.ctx.plugin(Persona, { prefix: config.systemPrompt }); await scope.persona.await(); }
    scope.skills = agent.ctx.plugin(Skills, config); await scope.skills.await();
    if (isOrdinaryChild(agent)) GlobalMode.registerChildGuidance(agent.ctx, config.mode !== 'global');
    else if (config.mode === 'global') await agent.ctx.plugin(GlobalMode, { mode: config.mode }).await();
    if (config.personal && !isOrdinaryChild(agent)) await agent.ctx.inject(['tools', 'nanoProduct'], child => GlobalMode.registerUserMessage(child)).await();
    this.tools.attach(agent, config);
    await agent.ctx.plugin(ContextOrder).await();
  }
  async setFeatures(agentId: string, features: Record<string, boolean>): Promise<void> {
    for (const config of this.allConfigurations()) if (config.agentId === agentId) config.features = { ...features };
    for (const scope of this.presets) if (scope.agentId === agentId) await this.features(scope);
    this.tools.update(agentId);
  }
  /** Withdraw choices now; additions and the rest of the configuration wait for idle. */
  restrictSelection(next: AgentConfiguration): void {
    for (const config of this.allConfigurations()) if (config.agentId === next.agentId) {
      if (next.toolAllowlist !== undefined) config.toolAllowlist = this.tools.selection(config, next.toolAllowlist);
      if (next.skillSelection?.mode === 'explicit_allowlist') config.skillSelection = { mode: 'explicit_allowlist', names: config.skillSelection?.mode === 'explicit_allowlist' ? config.skillSelection.names.filter(name => next.skillSelection!.names.includes(name)) : [...next.skillSelection.names] };
      else if (next.skillSelection?.mode === 'explicit_denylist') {
        if (config.skillSelection?.mode === 'explicit_allowlist') config.skillSelection.names = config.skillSelection.names.filter(name => !next.skillSelection!.names.includes(name));
        else config.skillSelection = { mode: 'explicit_denylist', names: [...new Set([...(config.skillSelection?.mode === 'explicit_denylist' ? config.skillSelection.names : []), ...next.skillSelection.names])] };
      }
      Skills.invalidateSkills(config);
    }
    this.tools.update(next.agentId);
  }
  async setConfiguration(next: AgentConfiguration): Promise<void> {
    for (const scope of this.agents.values()) if (scope.config.agentId === next.agentId && scope.config.systemPrompt !== next.systemPrompt) {
      await scope.persona?.dispose(); scope.persona = undefined;
      if (next.systemPrompt && !isOrdinaryChild(scope.agent)) { scope.persona = scope.agent.ctx.plugin(Persona, { prefix: next.systemPrompt }); await scope.persona.await(); }
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
    for (const [key, plugin] of [['intelligent_ui', IntelligentUI], ['memory_curation', MemoryCuration], ['skill_creation', SkillCreation], ['task_graph', TaskGraphs], ['heartbeat', Heartbeat]] as const) {
      const enabled = configs.some(config => key === 'skill_creation' ? true : key === 'memory_curation' ? config.knowledge?.memoryMode === 'legacy' : key === 'heartbeat' ? config.features?.[key] === true : config.features?.[key] !== false);
      const existing = scope.features.get(key);
      if (!enabled && existing) { await existing.dispose(); scope.features.delete(key); }
      if (enabled && !existing) { const fiber = scope.ctx.plugin(plugin, { agentId: scope.agentId, mode: configs[0]?.mode }); await fiber.await(); scope.features.set(key, fiber); }
    }
  }
}

export const name = 'nano-agent-config';
export const inject = ['nanoConfiguration', 'tools'];
/** Native presets retain the shared capability layer used by Agent restrictions. */
export function apply(ctx: Context, config: { agentId: string }) { return ctx.nanoConfiguration.attach(ctx, config.agentId); }
