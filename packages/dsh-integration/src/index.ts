/** Nano's sole stdio server inside an unmodified DSH profile. */
import { personalEvidenceMessages, personalReviewAction, reviewPersonal, assertPersonalConfiguration } from './personal-security.js';
import { createHash, randomUUID } from 'node:crypto';
import { AsyncLocalStorage } from 'node:async_hooks';
import { OwnedSessions, OwnedSessionController } from './owned-sessions.js';
import type { ProfilePnpmInvocation } from '@deepseek-ai/dsh-app-boot';
import { Context, Service } from '@deepseek-ai/cordis';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import { type ScheduleCatalogEntry } from '@deepseek-ai/dsh-schedule';
import { SessionId, type SessionEvent } from '@deepseek-ai/dsh-session';
import { freezeMessage, MessageId, type UserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-agent-preset-registry';
import { renderPrompt, renderContextSnapshot } from '@deepseek-ai/dsh-system-prompt';
import type {} from '@deepseek-ai/dsh-subagent';
import type {} from '@deepseek-ai/dsh-session-query';
import type { PromptContentPart } from '@deepseek-ai/dsh-attachment';
import type {} from '@deepseek-ai/dsh-jobs';
import type {} from '@deepseek-ai/dsh-terminal';
import { ColdLifecycleBarrier, type RuntimeLifecycle } from './runtime-lifecycle.js';
import { UpdateBarrier } from './update-barrier.js';
import { RpcError, RpcPeer } from './rpc.js';
import { recordToolPresentations } from './tool-presentation.js';
import { scheduleEvidence } from './schedule-evidence.js';
import { inputEvidence } from './input-evidence.js';
import { isHumanSource } from './input-source.js';
import { CapabilityState, capabilityDraft, needsSchedules, configurationBlocks } from './capability-state.js';
import type { RuntimeStopHistory } from '@nano/product-contracts';
import { validateCapabilities, type CapabilityTarget } from '@nano/product-contracts/capabilities';
import { CronOwners } from './cron-owners.js';
import { ConfigurationScopes } from './agent-config.js';
import { TaskExecutionDriver } from './task-execution.js';
import { TaskContextDriver } from './task-context.js';
import { ProductBridge } from './product-bridge.js';
import { skillCatalog } from './capabilities.js';
import * as SelectedSkills from './capabilities.js';
import { createScope } from '@deepseek-ai/dsh-scope';
import { KnowledgeRuntime } from './knowledge/runtime.js';
import { NativeModelSetup } from './model-setup.js';
import { ModelPolicy } from './model-policy.js';
import { NativeHistory } from './history.js';
import { NanoApproval } from './policy/approval.js';
import { CcApproval } from './policy/cc.js';
import { CodexApproval } from './policy/codex.js';
import * as NanoWeb from './web.js';
import { NanoWorkflowEngine } from './workflow/engine.js';
import { registerWorkflowTool } from './workflow/tool.js';
import { installLlmAttribution } from './llm-attribution.js';
import { TrajectoryRuns } from './trajectory-runs.js';
import { NativeTrajectory } from './trajectory.js';
import { TrajectoryAttachments, type AttachmentSource } from './trajectory-attachments.js';
import { DescendantReader } from './descendants.js';

export interface AgentConfiguration {
  personal?: {bindingId:string;ownerId:string;conversationId:string;epoch:number};
  agentId: string;
  workspace?: string;
  revision: string;
  provider: string;
  model: string;
  reasoningEffort?: string;
  maxTokens?: number;
  modelRouteFrozen?: boolean;
  workflow?: { outputTokenTarget?: number; sizeGuideline?: string };
  modelFallbacks?: { provider: string; model: string; reasoningEffort?: string; maxTokens?: number }[];
  systemPrompt?: string;
  features?: Record<string, boolean>;
  toolAllowlist?: string[];
  skillSelection?: { mode: 'default_discovery' | 'explicit_allowlist' | 'explicit_denylist'; names: string[] };
  skillRoots?: { path: string; source: string }[];
  extensions?: { global?: string; workspace?: string };
  knowledge?: import('@nano/product-contracts').AgentConfiguration['knowledge'];
  approval?: import('@nano/product-contracts').ApprovalConfiguration;
  mode?: 'single_thread' | 'global';
}
export interface SessionBinding {
  sessionId: string;
  agentId: string;
  ownerId: string;
  cwd: string;
  revision: string;
}
interface Submit {
  lifecycle_revision?: number;
  attachmentSources?: (AttachmentSource | null)[];
  sessionId: string;
  inputId: string;
  mode: 'followup' | 'steer' | 'inject';
  onlyIfIdle?: boolean;
  content: PromptContentPart[];
  source: { kind: 'human' | 'system'; humanTaskControl?:Record<string,unknown>; lifecycle_revision?: number; contextEnvelope?: string; conversationId?: string; sender?: Record<string, unknown>; pa_agent_id?: string; actorId: string; channel: string; messageId: string; background_returns?: Record<string, unknown>[] };
}
declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    schedule: { kind: 'schedule'; lifecycle_revision?: number; scheduleId?: string; triggerKind?: 'manual' };
    'nano-system': { kind: 'nano-system'; lifecycle_revision?: number; actorId: string; channel: string; messageId: string; conversationId?:string; humanTaskControl?:Record<string,unknown>; background_returns?: Record<string, unknown>[] };
  }
}

/** Trusted node configuration is installed before any Session can be resumed. */
export default class NanoRuntime {
  static inject = ['jobs', 'agents', 'sessions', 'agentPresets', 'loader', 'tools', 'skills', 'systemPrompt', 'subagents', 'sessionQuery', 'sessionPersistence', 'storageDomain', 'llm', 'settings', 'credentials', 'authorization', ...SessionController.inject];
  private readonly peer = new RpcPeer(process.stdin, process.stdout);
  private readonly bindings = new Map<string, SessionBinding>();
  private readonly configurations = new Map<string, AgentConfiguration>();
  private readonly inputs = new Map<string, Promise<unknown>>();
  private readonly approvals = new Map<string, (answer: ApprovalOutcome, reason?: string) => void>();
  private readonly unregisterPresets: (() => Promise<void>)[] = [];
  private accepting = false;
  private readonly lifecycle: ColdLifecycleBarrier;
  private readonly owned: OwnedSessions;
  private readonly ownerOf: (sessionId: string) => string | undefined;
  private admissions = 0;
  private readonly controller;
  private readonly models: Promise<ModelPolicy>;
  private readonly cron: CronOwners;
  private readonly capabilities: CapabilityState;
  private tasks!: TaskExecutionDriver;
  private readonly sessionController: Promise<SessionController>;

  constructor(private readonly ctx: Context) {
    const cleanup = new AsyncLocalStorage<string[]>();
    ctx.logger.exporter({export: message => {
      if (message.type === 'error') cleanup.getStore()?.push(String(message.args[0]?.stack ?? message.args[0] ?? 'Runtime cleanup error'));
    }});
    const liveAgents = new WeakSet<Agent>();
    ctx.on('agent/inbox/inserted', ({agent, message}) => {
      if (!liveAgents.has(agent) || message.source.kind !== 'schedule' || 'lifecycle_revision' in message.source) return;
      const agentId = this.ownerOf(agent.id);
      if (agentId) agent.inbox.replace(message.id, freezeMessage({...message, source: {...message.source, lifecycle_revision: this.lifecycle.current(agentId).revision}}));
    });
    let terminals: Context['terminals'] | undefined;
    ctx.inject(['terminals'], child => { terminals = child.terminals; child.effect(() => () => { terminals = undefined; }); });
    const lifecycle = this.lifecycle = new ColdLifecycleBarrier(ctx);
    this.owned = new OwnedSessions(ctx, this.bindings, agentId => lifecycle.assertEnabled(agentId));
    ctx.provide('nanoSessions', this.owned);
    installLlmAttribution(ctx, sessionId => {
      let session = ctx.sessions.get(SessionId(sessionId));
      while (session && !this.bindings.has(session.id) && session.header.parentSession) {
        const parent = ctx.sessions.get(session.header.parentSession);
        if (!parent) break;
        session = parent;
      }
      return session?.id ?? sessionId;
    });
    new TrajectoryRuns(ctx);
    let configurationService: ConfigurationScopes;
    this.capabilities = new CapabilityState((config, names) => configurationService.selection(config, names));
    const history = new NativeHistory(ctx, process.env.DSH_HOME!);
    this.cron = new CronOwners(ctx, process.env.DSH_HOME!, (agentId, action) => !['catalog', 'history', 'list', 'delete'].includes(action) && (this.capabilities.held(agentId, {kind: 'feature', name: 'cron_scheduling'}) || this.capabilities.held(agentId, {kind: 'tool', name: `schedule_${action}`})));
    ctx.plugin(ConfigurationScopes, this.configurations);
    const descendantReader = new DescendantReader(ctx);
    const boundRoot = (id: string): string | undefined => {
      let current: string | undefined = id;
      while (current) {
        if (this.bindings.has(current)) return current;
        const known = descendantReader.rootOf(current);
        if (known && this.bindings.has(known)) return known;
        current = ctx.sessions.get(SessionId(current))?.header.parentSession;
      }
    };
    this.ownerOf = id => {
      const root = boundRoot(id);
      return root ? this.bindings.get(root)?.agentId : this.configurations.get(ctx.agents.get(SessionId(id))?.session.header.agentPreset ?? '')?.agentId;
    };
    const disabled = (id: string) => { const owner = this.ownerOf(id); return owner ? lifecycle.current(owner).disabled === true : false; };
    const cancelPersisted = async (agentId: string) => {
      const owns = (id: string) => this.ownerOf(id) === agentId;
      await (await models).cancelPersisted(owns);
      await (await workflow).cancelPersisted(owns);
      await (await knowledge).cancelPersisted(agentId);
    };
    const modelVersion = (runs: unknown) => createHash('sha256').update(JSON.stringify(runs)).digest('hex');
    const modelFiber = ctx.plugin(ModelPolicy, { check: (agent: Agent, run: import('./model-fallback.js').ModelRun) => this.peer.request('model.check', { sessionId: agent.id, turn: run.turn, turns: run.attempts.map(attempt => attempt.turn) }) as Promise<{ published: boolean }>, notify: (sessionId: string) => { this.peer.notify('model.changed', { sessionId, rootSessionId: boundRoot(sessionId) }); } });
    const webFiber = ctx.plugin(NanoWeb);
    const workflowFiber = ctx.plugin(NanoWorkflowEngine, { configuration: (agent: Agent) => configurationService.forAgent(agent)!, completed: (record: import('./workflow/state.js').WorkflowRecord) => this.peer.notify('workflow.completed', record) });
    const workflow = new Promise<NanoWorkflowEngine>(resolve => { ctx.inject(['workflowEngine', 'nanoApproval', 'nanoModels'], child => { const engine = child.workflowEngine as NanoWorkflowEngine; registerWorkflowTool(child, engine, agent => configurationService.forAgent(agent)!); resolve(engine); }); });
    const models = this.models = new Promise<ModelPolicy>(resolve => { ctx.inject(['nanoModels'], child => { resolve(child.nanoModels); }); });
    const knowledgeFiber = ctx.plugin(KnowledgeRuntime, { configOf: (agent: Agent) => configurationService.forAgent(agent), configs: this.configurations, bindings: this.bindings, notify: () => this.peer.notify('knowledge.changed', {}), held: (agentId: string, kind: 'memory' | 'skills') => lifecycle.current(agentId).disabled === true || this.capabilities.held(agentId, {kind: 'feature', name: kind === 'memory' ? 'memory_curation' : 'skill_creation'}) });
    const knowledge = new Promise<KnowledgeRuntime>(resolve => { ctx.inject(['nanoKnowledge'], child => { resolve(child.nanoKnowledge); }); });
    let updateServices: { models: ModelPolicy; knowledge: KnowledgeRuntime; workflow: NanoWorkflowEngine } | undefined;
    const update = new UpdateBarrier({
      agents: () => ctx.agents.list(),
      busy: () => !this.accepting || modelSetup.busy || this.admissions > 0 || this.approvals.size > 0 ||
        !updateServices || updateServices.models.busy || updateServices.knowledge.busy || updateServices.workflow.busy,
      pause: async () => {
        updateServices!.knowledge.suspendUpdates(true);
        await this.cron.pause();
        // Cold bindings may contain durable inbox entries before PA recovery.
        for (const id of this.bindings.keys()) if (!disabled(id)) await this.agent(id);
      },
      resume: async () => { updateServices?.knowledge.suspendUpdates(false); await this.cron.resume(); },
    });
    // Track in-flight RPCs before their first await. Read paths resolving an
    // Agent can also restore durable inbox work, so they share admission.
    const handle = (method: string, action: (value: unknown) => unknown) => this.peer.handle(method, async value => {
      if (update.held && method !== 'approval.answer') throw new RpcError(-32003, 'Runtime is held for update');
      this.admissions++;
      try { return await action(value); } finally { this.admissions--; }
    });
    const modelSetup = new NativeModelSetup(ctx, { handle, notify: (method, value) => this.peer.notify(method, value) });
    this.peer.handle('update.prepare', async value => {
      const operationId = (value as { operationId: string }).operationId;
      if (typeof operationId !== 'string' || !operationId) throw new RpcError(-32602, 'Update operation identity is required');
      return update.prepare(operationId);
    });
    this.peer.handle('update.release', value => update.release((value as { operationId: string }).operationId));
    ctx.plugin(CcApproval);
    ctx.plugin(CodexApproval);
    const codex = new Promise<CodexApproval>(resolve => { ctx.inject(['codexApproval'], child => { resolve(child.codexApproval); }); });
    const approvalFiber = ctx.plugin(NanoApproval, (agent: Agent) => configurationService.forAgent(agent));
    const approval = new Promise<NanoApproval>(resolve => { ctx.inject(['nanoApproval'], child => { resolve(child.nanoApproval); }); });
    const configuration = new Promise<ConfigurationScopes>(resolve => { ctx.inject(['nanoConfiguration'], child => { configurationService = child.nanoConfiguration; resolve(configurationService); }); });
    ctx.on('tools/pre-execute', async (exec, next) => {
      if (exec.agent && disabled(exec.agent.id)) return {kind: 'deny', reason: 'agent_disabled'};
      const config = exec.agent && configurationService.forAgent(exec.agent);
      if (!config) return next();
      const key = `${exec.agent!.id}:${exec.callId}`;
      if (!this.capabilities.begin(key, config.agentId, {kind: 'tool', name: exec.name})) return {kind: 'deny', reason: 'Capability is reserved by configuration'};
      const skill = exec.name === 'skill' && (exec.arguments as {name?: string}).name;
      if (skill && !this.capabilities.begin(`${key}:skill`, config.agentId, {kind: 'skill', name: skill})) { this.capabilities.end(key); return {kind: 'deny', reason: 'Skill is reserved by configuration'}; }
      try { return await next(); } catch (error) { this.capabilities.end(key); this.capabilities.end(`${key}:skill`); throw error; }
    }, {prepend: true});
    ctx.on('tools/result', exec => { if (exec.agent) { this.capabilities.end(`${exec.agent.id}:${exec.callId}`); this.capabilities.end(`${exec.agent.id}:${exec.callId}:skill`); } });
    ctx.plugin(ProductBridge, { peer: this.peer, bindings: this.bindings });
    this.tasks=new TaskExecutionDriver(ctx,{peer:this.peer,bindings:this.bindings,configuration:agent=>configurationService.forAgent(agent),lifecycleRevision:agentId=>lifecycle.current(agentId).revision,allowed:agentId=>!lifecycle.current(agentId).disabled});
    // Both hooks prepend: register catch-up last so its authority cut precedes Task decisions.
    new TaskContextDriver(ctx,{bindings:this.bindings,peer:this.peer,availability:(agent,available)=>this.tasks.contextAvailability(agent,available),lifecycleRevision:agentId=>this.lifecycle.current(agentId).revision});
    ctx.on('agent/pre-step', async ({agent}, next) => disabled(agent.id) ? {kind: 'reject'} : next(), {prepend: true});
    this.controller = ctx.plugin(OwnedSessionController, {nativeOpen: false});
    this.sessionController = new Promise(resolve => {
      ctx.inject(['sessionController'], child => { resolve(child.sessionController); });
    });
    new TrajectoryAttachments(ctx);
    const trajectory = new NativeTrajectory(ctx, { controller: this.sessionController, bindings: this.bindings, configurations: this.configurations });
    trajectory.register(this.peer);
    ctx.on('agent/created', async ({ agent, source }) => {
      const agentId = this.ownerOf(agent.id);
      if (agentId) { lifecycle.assertEnabled(agentId); await lifecycle.clean(agentId, agent, source === 'resume'); }
      const preset = agent.session.header.agentPreset;
      if (!preset?.startsWith('nano:')) return;
      const desired = this.configurations.get(preset);
      if (!desired) throw new Error(`Missing Nano configuration for ${preset}`);
      const scopes = await configuration;
      const parent = agent.session.header.parentSession && ctx.agents.get(agent.session.header.parentSession);
      const config = await history.configuration(agent, desired, parent ? (await workflow).childConfiguration(scopes.forAgent(parent)!) : undefined);
      if (desired.personal) { config.personal = desired.personal; assertPersonalConfiguration(config); }
      await scopes.attachAgent(agent, config);
      await (await approval).attach(agent, config);
      const modelPolicy = await models; await modelPolicy.attach(agent, config);
      history.attach(agent, config, () => modelPolicy.route(agent));
      if (agentId) lifecycle.assertEnabled(agentId);
      liveAgents.add(agent);
    });
    const toolViews = recordToolPresentations(ctx);
    ctx.on('session/event', (session, event) => {
      const rootSessionId = boundRoot(session.id);
      if (rootSessionId) descendantReader.remember(session,event,rootSessionId);
      this.peer.notify('session.event', { sessionId: session.id, rootSessionId, event });
    });
    const liveness = setInterval(() => {
      for (const sessionId of this.bindings.keys()) {
        const agent = ctx.agents.get(SessionId(sessionId));
        if (agent?.status === 'running') this.peer.notify('session.liveness', { sessionId });
      }
    }, 15000);
    liveness.unref();
    ctx.effect(() => () => clearInterval(liveness));
    ctx.on('agent/status', ({ agent, status }) => this.peer.notify('session.status', { sessionId: agent.id, status }));
    ctx.on('agent/assistant-stream', ({ agent, frame }) => this.peer.notify('session.stream', { sessionId: agent.id, frame }));
    ctx.on('agent/error', ({ agent, error }) => this.peer.notify('session.error', { sessionId: agent.id, message: String(error) }));
    ctx.on('approval/request', async request => {
      if (disabled(request.agent.id)) return 'cancelled';
      const config = configurationService.forAgent(request.agent);
      const history = request.agent.session.snapshotEvents();
      const turnStart = history.findLast(event => event.type === 'turn/start')?.seq ?? -1;
      const human = history.some(event => event.seq > turnStart && event.type === 'user/message' && isHumanSource(event.data.source));
      const taskTurn=history.some(event=>event.seq>turnStart&&event.type==='user/message'&&event.data.source?.kind==='nano-system'&&['task-execution','task-change'].includes(String(event.data.source.channel)));
      if (request.agent.session.header.origin === 'subagent' || config?.mode === 'global' || !human&&!taskTurn) return 'rejected';
      const approvalSessionId = request.agent.id;
      if(!this.bindings.has(approvalSessionId)) return 'rejected';
      const requestId = randomUUID();
      return new Promise<ApprovalOutcome>(resolve => {
        let timer: ReturnType<typeof setTimeout> | undefined;
        const finish = (answer: ApprovalOutcome, reason?: string) => {
          if (!this.approvals.has(requestId)) return;
          if (timer) clearTimeout(timer);
          this.approvals.delete(requestId);
          request.signal?.removeEventListener('abort', cancel);
          if (answer === 'rejected' && reason?.trim()) request.agent.inject(freezeMessage({ id: MessageId(randomUUID()), role: 'user' as const, content: [{ type: 'text', text: `The human rejected ${request.toolName} (${request.callId ?? requestId}). Their reason: ${reason}` }],
            source: { kind: 'user-approval', form: 'notice', summary: 'The human rejected this tool call with a reason.' } }));
          resolve(answer);
          this.peer.notify('approval.resolved', { requestId, sessionId: approvalSessionId, outcome: answer });
        };
        const cancel = () => finish('cancelled');
        this.approvals.set(requestId, finish);
        if (request.signal?.aborted) return cancel();
        timer = setTimeout(() => finish('unavailable'), Math.max(0, (config?.approval?.askTimeoutSec ?? 600) * 1000));
        request.signal?.addEventListener('abort', cancel, { once: true });
        this.peer.notify('approval.request', {
          requestId, sessionId: approvalSessionId, toolName: request.toolName,
          toolInput: history.findLast(event=>event.type==='tool/call'&&event.data.callId===request.callId)?.data,
          callId: request.callId, reason: request.reason,
        });
      });
    });
    handle('initialize', async value => {
      if (this.accepting) throw new RpcError(-32002, 'Runtime is already initialized');
      const config = value as { lifecycle?: Record<string, RuntimeLifecycle>; blockedScheduleIds?: string[]; protocol: number; pendingConfigurations?: {operationId: string; fingerprint: string; config: AgentConfiguration}[]; taskStops?: string[]; taskStopFences?: (string|{sessionId:string;stoppedAt?:string})[]; packageManager?: ProfilePnpmInvocation; agents: AgentConfiguration[]; bindings: SessionBinding[]; providers?: Parameters<NativeModelSetup['apply']>[0] };
      for (const binding of config.bindings) this.bindings.set(binding.sessionId, binding);
      for (const agent of config.agents) {
        lifecycle.configure(agent.agentId, config.lifecycle?.[agent.agentId] ?? {revision: 1});
        this.cron.block(agent.agentId, lifecycle.current(agent.agentId).disabled === true);
      }
      if (config.protocol !== 1) throw new RpcError(-32002, 'Unsupported Nano runtime protocol');
      await this.sessionController;
      await approvalFiber.await();
      await modelFiber.await();
      await descendantReader.ready;
      await (await models).fallback.ready;
      await webFiber.await();
      await workflowFiber.await();
      await workflow;
      await knowledgeFiber.await();
      await (await knowledge).recover();
      for (const agent of config.agents) await lifecycle.prepare(agent.agentId, async () => {
        await cancelPersisted(agent.agentId);
        await this.cron.skipMissed(agent.agentId, new Set(config.blockedScheduleIds ?? []));
      });
      await ctx.loader.await();
      configurationService.packageManager(config.packageManager);
      if (config.providers !== undefined) await modelSetup.apply(config.providers);
      const personal = config.agents.filter(agent => agent.personal);
      if (personal.length && (config.agents.length !== 1 || config.bindings.some(binding => binding.agentId !== personal[0]!.agentId || binding.ownerId !== personal[0]!.personal!.ownerId))) throw new RpcError(-32002, 'Personal runtime must contain only its trusted binding');
      for (const agent of config.agents) {
        assertPersonalConfiguration(agent);
        await ctx.llm.resolveModelInfo(agent.provider, agent.model);
        const revisions = new Set([agent.revision, ...config.bindings.filter(binding => binding.agentId === agent.agentId).map(binding => binding.revision)]);
        // Existing Sessions retain their native preset identity while receiving
        // the node's current Agent configuration after a cold restart.
        for (const revision of revisions) {
        const id = `nano:${agent.agentId}:${revision}`;
        this.configurations.set(id, agent);
        this.unregisterPresets.push(await ctx.agentPresets.register({ id, plugins: [{ id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: agent.agentId } }] }));
        }
      }
      for(const stop of config.taskStopFences??[])this.tasks.interrupt(typeof stop==='string'?stop:stop.sessionId,typeof stop==='string'?undefined:stop.stoppedAt);
      for(const sessionId of config.taskStops??[])this.tasks.block(sessionId,true);
      for (const binding of config.bindings) this.bindings.set(binding.sessionId, binding);
      updateServices = { models: await models, knowledge: await knowledge, workflow: await workflow };
      for (const pending of config.pendingConfigurations ?? []) await prepare(pending);
      this.accepting = true;
      for (const agent of config.agents) { await this.configureSchedules(agent); this.peer.notify('heartbeat.subscription', { agentId: agent.agentId, enabled: agent.features?.heartbeat === true }); }
      return { protocol: 1, runtime: '@deepseek-ai/dsh', version: '0.2.1-alpha.1' };
    });
    handle('session.ensure', value => this.ensure(value as SessionBinding));
    handle('session.submit', value => {
      const input = value as Submit;
      const key = `${input.sessionId}\0${input.inputId}`;
      const running = this.inputs.get(key);
      if (running) return running;
      const task = this.submit(input).finally(() => { this.inputs.delete(key); });
      this.inputs.set(key, task);
      return task;
    });
    handle('session.capabilities', async value => {
      const agent = await this.agent((value as { sessionId: string }).sessionId);
      return { tools: ctx.tools.schemas(agent).map(tool => tool.name).sort(), skills: await ctx.skills.list({ scope: agent, cwd: agent.session.header.cwd }), prompt: await ctx.systemPrompt.assemble({ scope: agent }) };
    });
    const preview = async (requested: AgentConfiguration, cwd: string, catalogOnly = false) => {
      assertPersonalConfiguration(requested);
      const previewId = `preview-${randomUUID()}`;
      const config = { ...requested, agentId: previewId, ...(catalogOnly ? { features: { task_graph: true, memory_curation: true, skill_creation: true, cron_scheduling: true, heartbeat: true } } : {}) };
      const preset = `nano:${previewId}:preview`;
      this.configurations.set(preset, config);
      const unregister = await ctx.agentPresets.register({ id: preset, plugins: [{ id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: previewId } }] });
      try {
        // Native schedule tools appear only while their scoped service is mounted.
        await this.cron.setEnabled(previewId, true);
        const handle = await ctx.agents.create({ sessionId: SessionId(previewId), meta: { cwd, agentPreset: preset },
          setup: async agentCtx => { await ctx.agentPresets.mount(agentCtx, preset); } });
        try {
          const scopes = await configuration; const scoped = scopes.forAgent(handle.agent)!;
          const catalog = { tools: scopes.catalog(handle.agent), skills: await skillCatalog(scoped, cwd), workflows: (await (await workflow).catalog(handle.agent).list()).map(item=>({name:item.name,description:item.meta.description})) };
          if (catalogOnly) return catalog;
          const invalid = configurationBlocks(requested, [...this.configurations.values()].find(config => config.agentId === requested.agentId), {tools: catalog.tools.map(tool => tool.name), skills: catalog.skills.map(skill => skill.name)});
          if (invalid.length) throw new RpcError(-32602, `Invalid capability dependencies: ${JSON.stringify(invalid)}`);
          const assembly = await ctx.systemPrompt.assemble({ scope: handle.agent });
          return { prompt: [renderPrompt(assembly), renderContextSnapshot(assembly)].filter(Boolean).join('\n\n'), section_count: assembly.sections.length,
            tools: assembly.tools.map(tool => tool.name), skills: await ctx.skills.list({ scope: handle.agent, cwd }), catalog };
        } finally { await handle.dispose(); }
      } finally { await unregister(); this.configurations.delete(preset); await this.cron.disposeAgent(previewId, true); }
    };
    handle('configuration.catalog', async value => {
      const { agentId, cwd, config: candidate } = value as { agentId?: string; cwd: string; config?: AgentConfiguration };
      const config = candidate ?? [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!config) throw new RpcError(-32004, 'Unknown product Agent');
      return preview(config, cwd, true);
    });
    handle('plugins.manage', async value => {
      const command = value as import('./workspace-tools.js').PluginCommand & {agentId: string};
      lifecycle.assertEnabled(command.agentId);
      const entry = [...this.configurations].find(([, config]) => config.agentId === command.agentId);
      if (!entry) throw new RpcError(-32004, 'Unknown product Agent');
      const preset = await ctx.agentPresets.acquireScope(entry[0]);
      try {
        const {view, settled} = await (await configuration).managePlugins(entry[1], command);
        // An accepted background operation must keep its native preset alive through teardown.
        void settled.finally(() => preset[Symbol.asyncDispose]()).catch(error => ctx.logger.error(error));
        return view;
      } catch (error) { await preset[Symbol.asyncDispose](); throw error; }
    });
    handle('configuration.selection', async value => {
      const { agentId, cwd } = value as { agentId: string; cwd: string };
      const entry = [...this.configurations].find(([, config]) => config.agentId === agentId);
      if (!entry) throw new RpcError(-32004, 'Unknown product Agent');
      await using preset = await ctx.agentPresets.acquireScope(entry[0]);
      const key = {}; const diagnostic = createScope(ctx, key, { parent: preset.key });
      try {
        await diagnostic.ctx.plugin(SelectedSkills, entry[1]).await();
        return { tools: (await configuration).selection(entry[1], ctx.tools.schemas(key).map(tool => tool.name)),
          skills: await ctx.skills.list({ scope: key, cwd }) };
      } finally { await diagnostic.dispose(); }
    });
    handle('configuration.preview', value => {
      const { config, cwd } = value as { config: AgentConfiguration; cwd: string };
      return preview(config, cwd);
    });
    handle('session.fork', async value => {
      const { sessionId, messageId, operationId } = value as { sessionId: string; messageId: string; operationId: string };
      const source = await this.agent(sessionId); const binding = this.bindings.get(sessionId)!;
      const desired = this.configurations.get(source.session.header.agentPreset!)!;
      const result = await history.fork(source, messageId, operationId, desired, this.owned);
      this.bindings.set(result.sessionId, { ...binding, sessionId: result.sessionId });
      return { ...result, revision: binding.revision };
    });
    handle('session.export', async value => {
      const { sessionId } = value as { sessionId: string };
      if (!this.bindings.has(sessionId)) throw new RpcError(-32004, 'Session has no trusted product binding');
      return { path: await history.path(sessionId) };
    });
    handle('knowledge.sources.sync', async value => { const input = value as { agentId: string; snapshot: import('./knowledge/memory-documents.js').SourceEligibility }; return (await knowledge).documents.syncSources(input.agentId, input.snapshot); });
    handle('knowledge.sources.pending', async value => { await (await knowledge).documents.sourcesPending((value as { agentId: string }).agentId); return { pending: true }; });
    handle('knowledge.usage', async value => (await knowledge).usage((value as { agentId: string }).agentId));
    handle('knowledge.facts', async () => ({ facts: await (await knowledge).facts(), reviews: await (await knowledge).reviews() }));
    handle('knowledge.acknowledge', async value => { await (await knowledge).acknowledge((value as { id: string }).id); return { acknowledged: true }; });
    handle('session.lookup', async value => {
      const { sessionId, inputId } = value as { sessionId: string; inputId: string };
      const agent = await this.agent(sessionId);
      await this.flush(agent);
      return (await models).fallback.evidence(agent, inputId);
    });
    handle('session.work.check', async value => {
      const {sessionId, cursors = {}, modelVersions = {}} = value as {sessionId:string;cursors?:Record<string,number>;modelVersions?:Record<string,string>};
      if (!this.bindings.has(sessionId)) throw new RpcError(-32004, 'Session has no trusted product binding');
      const fallback = (await models).fallback;
      const refresh = (id:SessionId) => {
        const runs=fallback.list(id);
        return runs.some(run=>run.state!=='completed') || modelVersions[id]!==modelVersion(runs);
      };
      const rootSettled=await descendantReader.settled(SessionId(sessionId),cursors,refresh,false);
      const settled=rootSettled && await descendantReader.settled(SessionId(sessionId),cursors,refresh);
      return {settled,rootSettled};
    });
    handle('session.observe', async value => {
      const { sessionId, afterSeq = -1 } = value as { sessionId: string; afterSeq?: number };
      const agent = await this.agent(sessionId);
      const events = agent.session.snapshotEvents().filter(event => agent.session.isOwnSeq(event.seq) && event.seq > afterSeq);
      await this.flush(agent);
      const runs = structuredClone((await models).fallback.list(sessionId));
      return { status: agent.status, events: await toolViews(sessionId, events), modelRuns: runs, modelVersion: modelVersion(runs), approvals: await (await approval).entries(sessionId), throughSeq: events.at(-1)?.seq ?? afterSeq, durable: true };
    });
    handle('session.descendants', async value => {
      const { sessionId, cursors = {}, modelVersions = {} } = value as { sessionId: string; cursors?: Record<string, number>; modelVersions?: Record<string, string> };
      if (!this.bindings.has(sessionId)) throw new RpcError(-32004, 'Session has no trusted product binding');
      const root = SessionId(sessionId);
      const fallback = (await models).fallback;
      const snapshots = new Map<string, { modelRuns: ReturnType<typeof fallback.list>; modelVersion: string }>();
      const children = await descendantReader.read(root, cursors, id => {
        const modelRuns = structuredClone(fallback.list(id));
        const version = modelVersion(modelRuns);
        snapshots.set(id, { modelRuns, modelVersion: version });
        return modelVersions[id] !== version;
      });
      const workflowRuns = await (await workflow).relationships(root);
      const descendants = [];
      for (const child of children) {
        if (child.kind !== 'child') { descendants.push(child); continue; }
        const workflowRun = workflowRuns.find(run=>run.calls.some(call=>call.attempts.some(attempt=>attempt.id===child.id)));
        descendants.push({ ...child, ...(workflowRun?{workflowRunId:workflowRun.id}:{}), ...snapshots.get(child.id), events: await toolViews(child.id, child.events ?? []) });
      }
      return descendants;
    });
    handle('workflow.pending', async () => (await workflow).pending());
    handle('workflow.acknowledge', async value => { await (await workflow).acknowledge((value as {runId:string}).runId); return {acknowledged:true}; });
    handle('workflow.read', async value => { const {sessionId,runId} = value as {sessionId:string;runId?:string}; return (await workflow).read(await this.agent(sessionId),runId); });
    handle('workflow.control', async value => { const {sessionId,runId,action,ordinal} = value as {sessionId:string;runId:string;action:string;ordinal?:number}; return (await workflow).control(await this.agent(sessionId),runId,action,ordinal); });
    handle('workflow.catalog', async value => (await workflow).catalog(await this.agent((value as {sessionId:string}).sessionId)).list());
    handle('session.command', async value => {
      const request = value as { sessionId: string; id: string; action: string; argument?: string };
      if (request.action === 'config') {
        const match = /^workflowSizeGuideline\s+(unrestricted|small|medium|large)$/.exec(request.argument ?? '');
        if (!match) return {text: '用法: /config workflowSizeGuideline <unrestricted|small|medium|large>'};
        const agent = await this.agent(request.sessionId);
        const config = (await configuration).forAgent(agent)!;
        await this.peer.request('configuration.workflow', {agentId: config.agentId, guideline: match[1]});
        return {text: `Workflow size guideline: ${match[1]}`};
      }
      if(request.action === 'workflows') return (await workflow).command(await this.agent(request.sessionId),request.id,request.argument??'');
      return (await models).command(await this.agent(request.sessionId), request);
    });
    handle('task.execution.state', value=>{
      const {agentId}=value as {agentId:string};
      if(![...this.configurations.values()].some(config=>config.agentId===agentId))throw new RpcError(-32004,'Unknown product Agent');
      return this.tasks.observe(agentId);
    });
    handle('task.execution.changed', value=>{this.tasks.changed((value as {agentId:string}).agentId,(value as {reset?:boolean}).reset!==false);return {ok:true};});
    handle('task.execution.block', value=>{const {sessionId,blocked}=value as {sessionId:string;blocked:boolean};this.tasks.block(sessionId,blocked);return {ok:true};});
    handle('session.cancel', async value => {
      const { sessionId,stoppedAt } = value as { sessionId: string;stoppedAt?:string };
      this.tasks.interrupt(sessionId,stoppedAt);
      const agent = await this.agent(sessionId);
      (await models).cancelCommands(sessionId);
      (await models).fallback.interrupt(agent);
      const workflowCount = await (await workflow).stopSession(sessionId);
      const wasRunning = agent.status === 'running' || workflowCount > 0;
      agent.cancel({ kind: 'user' }, { keepInbox: true });
      await agent.whenIdle();
      await this.flush(agent);
      return { stopped: true, wasRunning };
    });
    handle('approval.answer', value => {
      const { requestId, decision, reason } = value as { requestId: string; decision: ApprovalOutcome; reason?: string };
      if (!['allowed-once', 'rejected'].includes(decision)) throw new RpcError(-32602, 'Invalid approval decision');
      const answer = this.approvals.get(requestId);
      if (!answer) throw new RpcError(-32004, 'Approval is no longer pending');
      answer(decision, reason);
      return { answered: true };
    });
    const personalScopes = async (agentId:string,sessionId:string) => {
      const config = [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!config?.personal) throw new RpcError(-32004,'Unknown personal evidence binding');
      const agent = this.bindings.has(sessionId) ? await this.agent(sessionId) : ctx.agents.get(SessionId(sessionId));
      if (!agent) throw new RpcError(-32004,'Unknown personal evidence binding');
      const lineage = [agent];
      let root = agent;
      // Native children share the product identity, but their own evidence and
      // delegation context must both reach the disclosure reviewer.
      while (!this.bindings.has(root.id) && root.session.header.parentSession) {
        const parent = ctx.agents.get(root.session.header.parentSession);
        if (!parent) throw new RpcError(-32004,'Unknown personal evidence binding');
        lineage.push(parent);
        root = parent;
      }
      if (this.bindings.get(root.id)?.agentId !== agentId) throw new RpcError(-32004,'Unknown personal evidence binding');
      return {config,lineage,root};
    };
    handle('pa.evidence', async value => {
      const {agentId,sessionId} = value as {agentId:string;sessionId:string};
      const {lineage,root}=await personalScopes(agentId,sessionId);
      const evidence = await Promise.all(lineage.map(async scope => {
        const assembly = await ctx.systemPrompt.assemble({scope});
        return {sessionId:scope.id,messages:personalEvidenceMessages(scope),system:renderPrompt(assembly),contexts:renderContextSnapshot(assembly)};
      }));
      return {...evidence[0],rootSessionId:root.id,ancestors:evidence.slice(1)};
    });
    handle('pa.review', async value => {
      const {agentId,kind,evidence,sessionId,callId} = value as {agentId:string;kind:string;evidence:Record<string,unknown>;sessionId?:string;callId?:string};
      const config = [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!config?.personal) throw new RpcError(-32004, 'Unknown personal Agent');
      if(kind==='input')return reviewPersonal(ctx,config,'input',evidence);
      if(kind!=='action'||!sessionId)throw new RpcError(-32602,'Personal disclosure requires a bound session');
      const {lineage}=await personalScopes(agentId,sessionId);
      try {
        return await (await codex).reviewDisclosure({agent:lineage[0]!,config,action:personalReviewAction(evidence),
          evidence:async()=>{
            // Fixed host-validated refusals contain no private task information.
            if(evidence.security_notice)return [];
            const scopes=await Promise.all([...lineage].reverse().map(async scope=>{
              const assembly=await ctx.systemPrompt.assemble({scope});
              const rows=await (await approval).sources.history(scope,scope.id===sessionId?callId:undefined,false,{toolResults:true,fullAssistant:true,privateContext:true});
              return [{context:renderPrompt(assembly),origin:{kind:'runtime-system'},session_id:scope.id},
                {context:renderContextSnapshot(assembly),origin:{kind:'runtime-context'},session_id:scope.id},
                ...rows.map(row=>({...row,session_id:scope.id}))];
            }));
            return scopes.flat();
          }});
      } catch(error) {return {decision:'unavailable',reason:`Independent review unavailable: ${String(error)}`};}
    });
    const usage = async (agentId: string) => {
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new RpcError(-32004, 'Unknown product Agent');
      const schedules = await this.cron.command(agentId, undefined, 'catalog', {}) as ScheduleCatalogEntry[];
      const busy: CapabilityTarget[] = [...this.capabilities.busy(agentId), ...(await knowledge).busyKinds(agentId).map(kind => ({kind: 'feature' as const, name: kind === 'memory' ? 'memory_curation' : 'skill_creation'}))];
      for (const binding of this.bindings.values()) {
        if (binding.agentId !== agentId) continue;
        const agent = ctx.agents.get(SessionId(binding.sessionId));
        if (!agent) continue;
        const events = agent.session.snapshotEvents();
        const lastEnd = events.findLast(event => event.type === 'turn/end')?.seq ?? -1;
        if ([...agent.inbox.nextTurn, ...agent.inbox.nextStep].some(message => message.source.kind === 'nano-system' && message.source.channel === 'heartbeat') || events.some(event => event.seq > lastEnd && event.type === 'user/message' && event.data.source.kind === 'nano-system' && event.data.source.channel === 'heartbeat')) busy.push({kind: 'feature', name: 'heartbeat'});
      }
      return {checked_at: new Date().toISOString(), active_schedules: schedules.filter(task => task.status === 'active').length, busy};
    };
    const prepare = async (input: {operationId: string; fingerprint: string; config: AgentConfiguration}) => {
      if (!input.operationId || !input.fingerprint) throw new RpcError(-32602, 'Configuration operation identity is required');
      const previous = [...this.configurations.values()].find(config => config.agentId === input.config.agentId);
      const catalog = await preview(input.config, input.config.workspace ?? previous?.workspace ?? process.cwd(), true) as {tools: {name: string}[]; skills: {name: string}[]};
      return this.capabilities.prepare(input, previous, {tools: catalog.tools.map(tool => tool.name), skills: catalog.skills.map(skill => skill.name)},
        () => previous ? usage(input.config.agentId) : Promise.resolve({active_schedules: 0, busy: []}));
    };
    handle('configuration.usage', value => usage((value as {agentId: string}).agentId));
    handle('configuration.prepare', value => prepare(value as Parameters<typeof prepare>[0]));
    handle('configuration.release', value => { const {agentId, operationId} = value as {agentId: string; operationId: string}; this.capabilities.release(agentId, operationId); return {released: true}; });
    handle('configuration.apply', async value => {
      const {operationId = `runtime:${(value as AgentConfiguration).revision}`, fingerprint = (value as AgentConfiguration).revision, ...next} = value as AgentConfiguration & {operationId?: string; fingerprint?: string};
      if (!this.capabilities.matches(next.agentId, operationId, fingerprint, next)) {
        const prepared = await prepare({operationId, fingerprint, config: next});
        if (!prepared.ready) return {effective: false, ...prepared};
      }
      try {
      assertPersonalConfiguration(next);
      const host = [...this.configurations.values()][0];
      if (host && (Boolean(host.personal) !== Boolean(next.personal) || host.personal && (host.agentId !== next.agentId || JSON.stringify(host.personal) !== JSON.stringify(next.personal)))) throw new RpcError(-32002, 'Configuration cannot change runtime partition');
      await ctx.llm.resolveModelInfo(next.provider, next.model);
      const previous = [...this.configurations.values()].find(config => config.agentId === next.agentId);
      if (previous && previous.mode !== next.mode) throw new RpcError(-32602, 'Work mode is immutable');
      // A display-name revision does not change execution and must not wait for a long-running goal.
      const scopes = await configuration, modelPolicy = await models;
      const metadataOnly = previous && scopes.applyRevisionOnly(next);
      if (metadataOnly) await modelPolicy.advanceRevision(next);
      if (previous && !metadataOnly) {
        await (await knowledge).dreaming.configurationChanging(next);
        (await configuration).restrictSelection(next);
        const restricted = { ...previous.features };
        for (const [key, enabled] of Object.entries(next.features ?? {})) if (!enabled) restricted[key] = false;
        await (await configuration).setFeatures(next.agentId, restricted);

        await (await configuration).whenIdle(next.agentId);
        await (await models).changed(next);
        await (await configuration).setConfiguration(next);
      }
      const id = `nano:${next.agentId}:${next.revision}`;
      if (!this.configurations.has(id)) {
        this.configurations.set(id, previous ?? next);
        this.unregisterPresets.push(await ctx.agentPresets.register({ id, plugins: [{ id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: next.agentId } }] }));
      }
      await this.configureSchedules(next);
      this.peer.notify('heartbeat.subscription', { agentId: next.agentId, enabled: next.features?.heartbeat === true });
      if (!metadataOnly) this.tasks.configured(next.agentId);
      return { effective: true, revision: next.revision };
      } finally { this.capabilities.release(next.agentId, operationId); }
    });
    for (const method of ['configuration.features', 'schedule.enabled']) handle(method, () => {
      throw new RpcError(-32602, 'Use configuration.prepare and configuration.apply with a complete candidate');
    });
    handle('task.context.passive',async value=>{
      const {agentId,sessionId,messages,revoked}=value as {agentId:string;sessionId:string;messages:{inputId:string;conversationId:string;humanControl?:Record<string,unknown>;content:Submit['content']}[];revoked:string[]};
      if(this.bindings.get(sessionId)?.agentId!==agentId)throw new RpcError(-32602,'Invalid Task context identity');
      this.lifecycle.assertEnabled(agentId);const agent=await this.agent(sessionId);
      for(const id of revoked)agent.inbox.remove(MessageId(id));
      for(const message of messages)await this.submit({sessionId,inputId:message.inputId,content:message.content,mode:'inject',source:{kind:'system',channel:'task-context',actorId:agentId,messageId:message.inputId,conversationId:message.conversationId,...(message.humanControl?{humanTaskControl:message.humanControl}:{})}});
      await this.ctx.sessions.flush(agent.session);return {durable:true};
    });
    handle('task.wait.repair',async value=>{
      const {agentId,sessionId,inputId}=value as {agentId:string;sessionId:string;inputId:string};
      if(this.bindings.get(sessionId)?.agentId!==agentId||!inputId.startsWith('task-wait-repair:'))throw new RpcError(-32602,'Invalid Task repair identity');
      this.lifecycle.assertEnabled(agentId);await this.tasks.repair(await this.agent(sessionId),inputId);return {durable:true};
    });
    handle('schedule.deleted.notify',async value=>{
      const {agentId,sessionId,inputId,content}=value as {agentId:string;sessionId:string;inputId:string;content:Submit['content']};
      if(!inputId.startsWith('schedule-deleted:'))throw new RpcError(-32602,'Invalid Schedule change identity');
      this.lifecycle.assertEnabled(agentId);
      const {agent,root}=await this.owned.resolveManaged(sessionId,agentId);
      if(root.sessionId===sessionId)return this.submit({sessionId,inputId,content,mode:this.tasks.passive(root.sessionId)?'inject':'followup',source:{kind:'system',actorId:agentId,channel:'schedule-change',messageId:inputId}});
      // Preserve the native child's identity and composition; never redirect to root.
      const revision=this.lifecycle.current(agentId).revision;
      const admitted=await ctx.attachments.admitPromptContent(content);
      this.lifecycle.assertEnabled(agentId);
      if(this.lifecycle.current(agentId).revision!==revision)throw new Error('stale_lifecycle');
      // The final evidence check and synchronous enqueue share one admission turn.
      if(!inputEvidence(agent.session.snapshotEvents(),inputId).accepted){
        const message:UserMessage=freezeMessage({id:MessageId(inputId),role:'user' as const,content:admitted,source:{kind:'nano-system',actorId:agentId,channel:'schedule-change',messageId:inputId,lifecycle_revision:revision}});
        if(this.tasks.passive(root.sessionId))agent.inject(message);else agent.followup(message);
      }
      await this.flush(agent);return {durable:true};
    });
    handle('schedule.wait.inspect',async value=>{
      const {agentId,sessionId,scheduleId}=value as {agentId:string;sessionId:string;scheduleId:string};
      const config=[...this.configurations.values()].find(config=>config.agentId===agentId);
      const checked_at=new Date().toISOString();
      if(!config||this.bindings.get(sessionId)?.agentId!==agentId)return {valid:false,checked_at,reason_code:'owner_or_session_mismatch'};
      const catalog=await this.cron.command(agentId,undefined,'catalog',{}) as ScheduleCatalogEntry[];
      const task=catalog.find(t=>t.id===scheduleId);
      if(task&&task.sessionId!==sessionId)return {valid:false,checked_at,reason_code:'owner_or_session_mismatch'};
      const agent=await this.agent(sessionId);await this.flush(agent);
      const pending=scheduleEvidence(agent.session.snapshotEvents()).find(item=>item.scheduleId===scheduleId&&item.trigger==='timed'&&item.pending&&item.consumedSeq===undefined);
      if(pending)return {valid:true,checked_at,owner_agent_id:agentId,session_id:sessionId,next_check_at:pending.scheduledAt,pending_occurrence_id:pending.messageId};
      const reason_code=!task?'missing':task.status!=='active'?'inactive':!(Date.parse(task.scheduledAt)>Date.now())?'expired':undefined;
      return {valid:!reason_code,checked_at,owner_agent_id:agentId,session_id:sessionId,next_check_at:task?.scheduledAt,...(reason_code?{reason_code}:{})};
    });
    handle('schedule.evidence', async value => {
      const agent = await this.agent((value as { sessionId: string }).sessionId); await this.flush(agent);
      return scheduleEvidence(agent.session.snapshotEvents());
    });
    handle('schedule.command', async value => {
      const { agentId, sessionId, action, args = {} } = value as { agentId: string; sessionId?: string; action: string; args?: Record<string, unknown> };
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new RpcError(-32004, 'Unknown product Agent');
      if (sessionId && this.ownerOf(sessionId) !== agentId) throw new RpcError(-32004, 'Schedule Session does not belong to this Agent');
      if (action === 'jobs') {
        const tasks = await this.cron.command(agentId, undefined, 'catalog', {}) as ScheduleCatalogEntry[];
        return tasks.map(({ id, title, prompt, sessionId, status, lastDelivery: _delivery, ...schedule }) => ({
          id, sessionId, name: title, instruction: prompt, schedule,
          enabled: status === 'active', delete_after_run: false,
        }));
      }
      if (action === 'run') {
        const key = `schedule-command:${agentId}:${randomUUID()}`;
        if (!this.capabilities.begin(key, agentId, {kind: 'tool', name: 'schedule_run'})) throw new RpcError(-32003, 'Capability is reserved by configuration');
        try {
        const config = [...this.configurations.values()].find(config => config.agentId === agentId)!;
        if (this.capabilities.held(agentId, {kind: 'feature', name: 'cron_scheduling'}) || this.capabilities.held(agentId, {kind: 'tool', name: 'schedule_run'})) throw new RpcError(-32003, 'Capability is reserved by configuration');
        const tasks = await this.cron.command(agentId, undefined, 'catalog', {}) as ScheduleCatalogEntry[];
        const task = tasks.find(task => task.id === args.id && task.sessionId === sessionId);
        if (!task || task.status !== 'active') throw new RpcError(-32602, 'Schedule does not exist or is inactive');
        if (typeof args.inputId !== 'string' || !args.inputId.startsWith('manual-schedule:')) throw new RpcError(-32602, 'Manual schedule input identity is required');
        const agent = await this.agent(sessionId!);
        if (!inputEvidence(agent.session.snapshotEvents(), args.inputId).accepted) {
          agent.followup(freezeMessage({ id: MessageId(args.inputId), role: 'user' as const,
            content: [{ type: 'text', text: `Manual run of an existing schedule. This is configured work, not live human permission.\nTitle: ${task.title}\nSaved instructions:\n${task.prompt}` }],
            source: { kind: 'schedule' as const, scheduleId: task.id, triggerKind: 'manual' } }));
        }
        await this.flush(agent); return { inputId: args.inputId, ...inputEvidence(agent.session.snapshotEvents(), args.inputId) };
        } finally { this.capabilities.end(key); }
      }
      return this.cron.command(agentId, sessionId, action, args);
    });
    const disabling = new Map<string, Promise<{confirmed: boolean; history: RuntimeStopHistory[]}>>();
    this.peer.handle('agent.disable', value => {
      const {agentId, revision, cursors = {}} = value as {agentId: string; revision: number; cursors?: Record<string, number>};
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new Error('Unknown product Agent');
      if (revision < lifecycle.current(agentId).revision) throw new Error('stale_lifecycle');
      // Admission closes before the first await; shared services and B remain alive.
      lifecycle.configure(agentId, {revision, disabled: true, disabledThroughRevision: revision});
      this.cron.block(agentId, true);
      for (const agent of ctx.agents.list()) if (this.ownerOf(agent.id) === agentId) agent.cancel({kind: 'user'});
      let task = disabling.get(agentId);
      if (!task) {
        const errors: string[] = [];
        let disposingScopes = false;
        task = (async () => {
          await this.owned.settle(agentId);
          const agents = ctx.agents.list().filter(agent => this.ownerOf(agent.id) === agentId);
          const stopped = agents.map(agent => ({agent, rootSessionId: boundRoot(agent.id), parentSessionId: agent.session.header.parentSession}));
          for (const agent of agents) agent.cancel({kind: 'user'});
          // Close owned terminals before cancelling their Jobs. Cancelling a
          // send first can race an exited foreground group and poison native
          // terminal cleanup with ESRCH even after the process tree has exited.
          const terminalService = terminals;
          if (terminalService) await Promise.all(agents.flatMap(agent => terminalService.list(agent).map(async terminal => {
            try { await terminalService.signal(agent, terminal.sessionId, 'SIGINT'); }
            catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error; }
            await terminalService.kill(agent, terminal.sessionId, 'Agent disabled');
          })));
          // Cancel background operations before their terminal/Agent scopes unwind.
          // Every lookup is owner-scoped; shared-host and B jobs are untouched.
          const jobStops = agents.flatMap(agent => ctx.jobs.list(agent.id).map(job => {
            ctx.jobs.kill(job.id, agent.id, 'Agent disabled');
            return ctx.jobs.wait(job.id, 4500, agent.id).then(result => {
              if (result.status === 'running' || result.status === 'stopping') throw new Error('Managed job did not settle');
            });
          }));
          await Promise.all([
            ...jobStops,
            this.cron.disposeAgent(agentId),
            knowledge.then(owner => owner.stopAgent(agentId)),
            workflow.then(owner => Promise.all(agents.map(agent => owner.stopSession(agent.id)))),
            models.then(owner => owner.cancelPersisted(id => this.ownerOf(id) === agentId)),
          ]);
          disposingScopes = true;
          await cleanup.run(errors, async () => {
            await ctx.subagents.drainContinuableDescendants(agents);
            await this.owned.disposeAgent(agentId);
          });
          await lifecycle.prepare(agentId, () => cancelPersisted(agentId));
          if (ctx.agents.list().some(agent => this.ownerOf(agent.id) === agentId)) throw new Error('Managed Agents remain after cleanup');
          if (errors.length) throw new Error(`Runtime cleanup failed: ${errors[0]}`);
          const snapshot = async (sessionId: string, rootSessionId: string, parentSessionId: string | undefined, events: SessionEvent[], throughSeq: number) => {
            const modelRuns = structuredClone((await models).fallback.list(sessionId));
            return {sessionId, rootSessionId, parentSessionId,
              events: (await toolViews(sessionId, events)).map(event => ({...event, data: {...event.data}})),
              modelRuns, modelVersion: modelVersion(modelRuns), throughSeq};
          };
          const finalHistory = await Promise.all(stopped.flatMap(({agent, rootSessionId, parentSessionId}) => {
            const afterSeq = cursors[agent.id] ?? -1;
            const events = agent.session.ownEvents().filter(event => event.seq > afterSeq);
            return rootSessionId ? [snapshot(agent.id, rootSessionId, parentSessionId, events, events.at(-1)?.seq ?? afterSeq)] : [];
          }));
          // An offline disable can arrive after the old host already stopped.
          // Reconcile its durable end events without restoring disabled Agents.
          for (const binding of this.bindings.values()) {
            if (binding.agentId !== agentId || stopped.some(item => item.agent.id === binding.sessionId)) continue;
            const rootId = SessionId(binding.sessionId);
            if (!await ctx.sessionPersistence.stat(rootId)) continue;
            using observation = await ctx.sessionQuery.observeSession(rootId);
            const events = observation.events.slice(observation.inheritedEventCount).filter(event => event.seq > (cursors[rootId] ?? -1));
            finalHistory.push(await snapshot(rootId, rootId, observation.header.parentSession, events, observation.cursor));
            for (const child of await descendantReader.read(rootId, cursors, () => false)) if (child.kind === 'child') {
              const events = (child.events ?? []).filter(event => event.seq > (cursors[child.id] ?? -1));
              finalHistory.push(await snapshot(child.id, rootId, child.parentId, events, child.throughSeq ?? cursors[child.id] ?? -1));
            }
          }
          return {confirmed: true, history: finalHistory};
        })();
        disabling.set(agentId, task);
        void task.catch(() => {
          // A slow managed operation can settle after the first deadline. Once
          // scope disposal begins, lost cleanup evidence must stay unconfirmed.
          if (!disposingScopes && disabling.get(agentId) === task) disabling.delete(agentId);
        });
      }
      return task;
    });
    this.peer.handle('agent.enable', async value => {
      const {agentId, revision, disabledThroughRevision = 0, blockedScheduleIds = []} = value as RuntimeLifecycle & {agentId: string; blockedScheduleIds?: string[]};
      const current = lifecycle.current(agentId);
      if (revision < current.revision) throw new Error('stale_lifecycle');
      const pending = disabling.get(agentId);
      if (pending) await pending;
      if (!current.disabled && current.revision === revision) return {enabled: true};
      // Keep admission closed until old persisted owners and missed timers are fenced.
      lifecycle.configure(agentId, {revision, disabled: true, disabledThroughRevision});
      this.cron.block(agentId, true);
      await lifecycle.prepare(agentId, () => cancelPersisted(agentId));
      if (current.disabled || current.revision !== revision) await this.cron.skipMissed(agentId, new Set(blockedScheduleIds));
      const config = [...this.configurations.values()].find(config => config.agentId === agentId);
      if (!config) throw new Error('Unknown product Agent');
      lifecycle.configure(agentId, {revision, disabledThroughRevision});
      this.cron.block(agentId, false);
      disabling.delete(agentId);
      await this.configureSchedules(config);
      this.peer.notify('heartbeat.subscription', {agentId, enabled: config.features?.heartbeat === true});
      return {enabled: true};
    });
    this.peer.handle('shutdown', async () => {
      this.accepting = false;
      await update.stop();
      trajectory.dispose();
      await this.cron.dispose();
      for (const id of this.bindings.keys()) ctx.agents.get(SessionId(id))?.cancel({ kind: 'user' }, { keepInbox: true });
      await (await models).stop();
      await (await knowledge).stop();
      await (await workflow).stop();
      await Promise.allSettled([...this.inputs.values()]);
      const agents = [...this.bindings.keys()].map(id => ctx.agents.get(SessionId(id))).filter((agent): agent is Agent => !!agent);
      for (const agent of agents) agent.cancel({ kind: 'user' }, { keepInbox: true });
      await Promise.all(agents.map(async agent => { await agent.whenIdle(); await this.flush(agent); }));
      await history.stop();
      await this.controller.dispose();
      for (const unregister of this.unregisterPresets) await unregister();
      return { stopped: true };
    });
  }

  *[Service.init]() { yield () => { this.peer.close(); for (const answer of this.approvals.values()) answer('unavailable'); }; }

  private async ensure(binding: SessionBinding) {
    if (!this.accepting) throw new RpcError(-32003, 'Runtime is not accepting sessions');
    const previous = this.bindings.get(binding.sessionId);
    if (previous && (['sessionId', 'agentId', 'ownerId', 'cwd', 'revision'] as const).some(key => previous[key] !== binding[key])) throw new RpcError(-32002, 'Session binding conflict');
    const preset = `nano:${binding.agentId}:${binding.revision}`;
    const config = this.configurations.get(preset);
    if (config?.personal && (binding.ownerId !== config.personal.ownerId || binding.cwd !== config.workspace)) throw new RpcError(-32004, 'Personal Session must retain its owner and private workspace');
    if (!this.configurations.has(preset)) throw new RpcError(-32002, 'Unknown configuration revision');
    this.bindings.set(binding.sessionId, binding);
    const agent = await this.owned.resolve(binding.sessionId, true);
    await this.flush(agent);
    void this.tasks.poke(agent);
    return { sessionId: agent.id, revision: binding.revision };
  }

  private async agent(sessionId: string): Promise<Agent> {
    if (!this.bindings.has(sessionId)) throw new RpcError(-32004, 'Session has no trusted product binding');
    return this.owned.resolve(sessionId);
  }

  private async configureSchedules(config: AgentConfiguration) {
    if (this.lifecycle.current(config.agentId).disabled) { await this.cron.setEnabled(config.agentId, false); return; }
    const tasks = await this.cron.command(config.agentId, undefined, 'catalog', {}) as ScheduleCatalogEntry[];
    await this.cron.setEnabled(config.agentId, needsSchedules(config) || tasks.some(task => task.status === 'active'));
  }

  private async submit(input: Submit) {
    if (!this.accepting) throw new RpcError(-32003, 'Runtime is not accepting inputs');
    const agentId = this.bindings.get(input.sessionId)?.agentId;
    if (!agentId) throw new Error('Session has no trusted product binding');
    const revision = this.lifecycle.current(agentId).revision;
    this.lifecycle.assertEnabled(agentId);
    if ((input.lifecycle_revision ?? input.source.lifecycle_revision ?? revision) !== revision) throw new RpcError(-32003, 'stale_lifecycle');
    const agent = await this.agent(input.sessionId);
    if (!inputEvidence(agent.session.snapshotEvents(), input.inputId).accepted) {
      if (!['human', 'system'].includes(input.source.kind)) throw new RpcError(-32602, 'Invalid input source');
      const content = await this.ctx.attachments.admitPromptContent(input.content);
      if (input.attachmentSources) await this.ctx.nanoTrajectoryAttachments.record(input.sessionId, content, input.attachmentSources);
      const config = this.configurations.get(agent.session.header.agentPreset!);
      if (input.source.channel === 'heartbeat' && config && this.capabilities.held(config.agentId, {kind: 'feature', name: 'heartbeat'})) return {accepted: false, busy: true};
      if (input.onlyIfIdle && (agent.status !== 'idle' || agent.inbox.nextTurn.length || agent.inbox.nextStep.length)) return { accepted: false, busy: true };
      (await this.models).fallback.interrupt(agent);
      this.lifecycle.assertEnabled(agentId);
      if (this.lifecycle.current(agentId).revision !== revision) throw new Error('stale_lifecycle');
      const source = {...input.source, admittedAt:Date.now(), lifecycle_revision: input.source.lifecycle_revision ?? input.lifecycle_revision ?? revision};
      const message = freezeMessage({ id: MessageId(input.inputId), role: 'user' as const, content,
        source: input.source.kind === 'human' ? { ...source, kind: 'user' as const } : { ...source, kind: 'nano-system' as const } });
      if (input.mode === 'followup') agent.followup(message);
      else if (input.mode === 'steer') agent.steer(message);
      else if (input.mode === 'inject') agent.inject(message);
      else throw new RpcError(-32602, 'Invalid input mode');
    }
    await this.flush(agent);
    return { ...inputEvidence(agent.session.snapshotEvents(), input.inputId), durable: true };
  }

  private async flush(agent: Agent) {
    if (!await this.ctx.sessions.flush(agent.session)) throw new RpcError(-32005, 'Session has no persistence barrier');
  }
}
