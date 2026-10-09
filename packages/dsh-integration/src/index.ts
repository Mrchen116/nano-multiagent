/** Nano's sole stdio server inside an unmodified DSH profile. */
import { randomUUID } from 'node:crypto';
import { Context, Service } from '@deepseek-ai/cordis';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import { type ScheduleCatalogEntry } from '@deepseek-ai/dsh-schedule';
import { SessionId } from '@deepseek-ai/dsh-session';
import { freezeMessage, MessageId, ReasoningEffortId, type UserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-agent-preset-registry';
import { renderPrompt, renderContextSnapshot } from '@deepseek-ai/dsh-system-prompt';
import type {} from '@deepseek-ai/dsh-subagent';
import type {} from '@deepseek-ai/dsh-session-query';
import type { PromptContentPart } from '@deepseek-ai/dsh-attachment';
import { RpcError, RpcPeer } from './rpc.js';
import { scheduleEvidence } from './schedule-evidence.js';
import { inputEvidence } from './input-evidence.js';
import { CronOwners } from './cron-owners.js';
import { ConfigurationScopes } from './agent-config.js';
import { ProductBridge } from './product-bridge.js';
import { skillCatalog } from './capabilities.js';
import { NanoApproval } from './policy/approval.js';

export interface AgentConfiguration {
  agentId: string;
  revision: string;
  provider: string;
  model: string;
  reasoningEffort?: string;
  maxTokens?: number;
  systemPrompt?: string;
  features?: Record<string, boolean>;
  toolAllowlist?: string[];
  skillSelection?: { mode: 'default_discovery' | 'explicit_allowlist'; names: string[] };
  skillRoots?: { path: string; source: string }[];
  extensions?: { global?: string; workspace?: string };
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
  sessionId: string;
  inputId: string;
  mode: 'followup' | 'steer' | 'inject';
  onlyIfIdle?: boolean;
  content: PromptContentPart[];
  source: { kind: 'human' | 'system'; actorId: string; channel: string; messageId: string };
}
declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    schedule: { kind: 'schedule'; scheduleId?: string; triggerKind?: 'manual' };
    'nano-human': { kind: 'nano-human'; actorId: string; channel: string; messageId: string };
    'nano-system': { kind: 'nano-system'; actorId: string; channel: string; messageId: string };
  }
}

/** Trusted node configuration is installed before any Session can be resumed. */
export default class NanoRuntime {
  static inject = ['agents', 'sessions', 'agentPresets', 'loader', 'tools', 'skills', 'systemPrompt', 'subagents', 'sessionQuery', ...SessionController.inject];
  private readonly peer = new RpcPeer(process.stdin, process.stdout);
  private readonly bindings = new Map<string, SessionBinding>();
  private readonly configurations = new Map<string, AgentConfiguration>();
  private readonly inputs = new Map<string, Promise<unknown>>();
  private readonly approvals = new Map<string, (answer: ApprovalOutcome, reason?: string) => void>();
  private readonly unregisterPresets: (() => Promise<void>)[] = [];
  private accepting = false;
  private readonly controller;
  private readonly cron: CronOwners;
  private readonly sessionController: Promise<SessionController>;

  constructor(private readonly ctx: Context) {
    this.cron = new CronOwners(ctx, process.env.DSH_HOME!);
    ctx.plugin(ConfigurationScopes, this.configurations);
    const approvalFiber = ctx.plugin(NanoApproval, this.configurations);
    const approval = new Promise<NanoApproval>(resolve => { ctx.inject(['nanoApproval'], child => { resolve(child.nanoApproval); }); });
    const configuration = new Promise<ConfigurationScopes>(resolve => { ctx.inject(['nanoConfiguration'], child => { resolve(child.nanoConfiguration); }); });
    ctx.plugin(ProductBridge, { peer: this.peer, bindings: this.bindings });
    this.controller = ctx.plugin(SessionController, { nativeOpen: false });
    this.sessionController = new Promise(resolve => {
      ctx.inject(['sessionController'], child => { resolve(child.sessionController); });
    });
    ctx.on('agent/created', async ({ agent }) => {
      const preset = agent.session.header.agentPreset;
      if (!preset?.startsWith('nano:')) return;
      const config = this.configurations.get(preset);
      if (!config) throw new Error(`Missing Nano configuration for ${preset}`);
      (await configuration).attachAgent(agent, config);
      await (await approval).attach(agent, config);
      agent.ctx.on('system-prompt/assemble', async (_assembly, _context, next) => {
        const assembled = await next();
        return { ...assembled, variables: { ...assembled.variables, provider: config.provider, model: config.model } };
      }, { prepend: true });
      agent.ctx.on('agent/request', async (_payload, next) => {
        const { reasoningEffort: _effort, maxTokens: _maxTokens, ...request } = await next();
        return { ...request, provider: config.provider, model: config.model,
          ...(config.reasoningEffort ? { reasoningEffort: ReasoningEffortId(config.reasoningEffort) } : {}),
          ...(config.maxTokens === undefined ? {} : { maxTokens: config.maxTokens }),
        };
      }, { prepend: true });
    });
    ctx.on('session/event', (session, event) => {
      let root = session;
      while (!this.bindings.has(root.id) && root.header.parentSession) {
        const parent = ctx.sessions.get(root.header.parentSession); if (!parent) break; root = parent;
      }
      this.peer.notify('session.event', { sessionId: session.id, rootSessionId: this.bindings.has(root.id) ? root.id : undefined, event });
    });
    ctx.on('agent/status', ({ agent, status }) => this.peer.notify('session.status', { sessionId: agent.id, status }));
    ctx.on('agent/assistant-stream', ({ agent, frame }) => this.peer.notify('session.stream', { sessionId: agent.id, frame }));
    ctx.on('agent/error', ({ agent, error }) => this.peer.notify('session.error', { sessionId: agent.id, message: String(error) }));
    ctx.on('approval/request', async request => {
      const config = this.configurations.get(request.agent.session.header.agentPreset ?? '');
      const history = request.agent.session.snapshotEvents();
      const turnStart = history.findLast(event => event.type === 'turn/start')?.seq ?? -1;
      const human = history.some(event => event.seq > turnStart && event.type === 'user/message' && event.data.source?.kind === 'nano-human');
      if (config?.mode === 'global' || !human) return 'rejected';
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
          this.peer.notify('approval.resolved', { requestId, sessionId: request.agent.id, outcome: answer });
        };
        const cancel = () => finish('cancelled');
        this.approvals.set(requestId, finish);
        if (request.signal?.aborted) return cancel();
        timer = setTimeout(() => finish('unavailable'), Math.max(0, (config?.approval?.askTimeoutSec ?? 600) * 1000));
        request.signal?.addEventListener('abort', cancel, { once: true });
        this.peer.notify('approval.request', {
          requestId, sessionId: request.agent.id, toolName: request.toolName,
          callId: request.callId, reason: request.reason,
        });
      });
    });
    this.peer.handle('initialize', async value => {
      if (this.accepting) throw new RpcError(-32002, 'Runtime is already initialized');
      const config = value as { protocol: number; agents: AgentConfiguration[]; bindings: SessionBinding[] };
      if (config.protocol !== 1) throw new RpcError(-32002, 'Unsupported Nano runtime protocol');
      await this.sessionController;
      await approvalFiber.await();
      await ctx.loader.await();
      for (const agent of config.agents) {
        await ctx.llm.resolveModelInfo(agent.provider, agent.model);
        const revisions = new Set([agent.revision, ...config.bindings.filter(binding => binding.agentId === agent.agentId).map(binding => binding.revision)]);
        // Existing Sessions retain their native preset identity while receiving
        // the node's current Agent configuration after a cold restart.
        for (const revision of revisions) {
        const id = `nano:${agent.agentId}:${revision}`;
        this.configurations.set(id, agent);
        this.unregisterPresets.push(await ctx.agentPresets.register({ id, plugins: [
          { id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: agent.agentId } },
        ] }));
        }
      }
      for (const binding of config.bindings) this.bindings.set(binding.sessionId, binding);
      this.accepting = true;
      for (const agent of config.agents) { await this.cron.setEnabled(agent.agentId, agent.features?.cron_scheduling === true); this.peer.notify('heartbeat.subscription', { agentId: agent.agentId, enabled: agent.features?.heartbeat === true }); }
      return { protocol: 1, runtime: '@deepseek-ai/dsh', version: '0.2.1-alpha.1' };
    });
    this.peer.handle('session.ensure', value => this.ensure(value as SessionBinding));
    this.peer.handle('session.submit', value => {
      const input = value as Submit;
      const key = `${input.sessionId}\0${input.inputId}`;
      const running = this.inputs.get(key);
      if (running) return running;
      const task = this.submit(input).finally(() => { this.inputs.delete(key); });
      this.inputs.set(key, task);
      return task;
    });
    this.peer.handle('session.capabilities', async value => {
      const agent = await this.agent((value as { sessionId: string }).sessionId);
      return { tools: ctx.tools.schemas(agent).map(tool => tool.name).sort(), skills: await ctx.skills.list({ scope: agent, cwd: agent.session.header.cwd }), prompt: await ctx.systemPrompt.assemble({ scope: agent }) };
    });
    this.peer.handle('configuration.catalog', async value => {
      const { agentId, cwd } = value as { agentId: string; cwd: string };
      const entry = [...this.configurations].find(([, config]) => config.agentId === agentId);
      if (!entry) throw new RpcError(-32004, 'Unknown product Agent');
      await using scope = await ctx.agentPresets.acquireScope(entry[0]);
      return { tools: ctx.tools.schemas(scope.key), skills: await skillCatalog(entry[1], cwd) };
    });
    this.peer.handle('configuration.preview', async value => {
      const { config: requested, cwd } = value as { config: AgentConfiguration; cwd: string };
      const previewId = `preview-${randomUUID()}`;
      const config = { ...requested, agentId: previewId };
      const preset = `nano:${previewId}:preview`;
      this.configurations.set(preset, config);
      const unregister = await ctx.agentPresets.register({ id: preset, plugins: [
        { id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: previewId } },
      ] });
      try {
        const handle = await ctx.agents.create({ sessionId: SessionId(previewId), meta: { cwd, agentPreset: preset },
          setup: async agentCtx => { await ctx.agentPresets.mount(agentCtx, preset); } });
        try {
          const assembly = await ctx.systemPrompt.assemble({ scope: handle.agent });
          await using scope = await ctx.agentPresets.acquireScope(preset);
          return { prompt: [renderPrompt(assembly), renderContextSnapshot(assembly)].filter(Boolean).join('\n\n'), section_count: assembly.sections.length,
            tools: assembly.tools.map(tool => tool.name), skills: await ctx.skills.list({ scope: handle.agent, cwd }),
            catalog: { tools: ctx.tools.schemas(scope.key), skills: await skillCatalog(config, cwd) } };
        } finally { await handle.dispose(); }
      } finally { await unregister(); this.configurations.delete(preset); }
    });
    this.peer.handle('session.lookup', async value => {
      const { sessionId, inputId } = value as { sessionId: string; inputId: string };
      const agent = await this.agent(sessionId);
      await this.flush(agent);
      return inputEvidence(agent.session.snapshotEvents(), inputId);
    });
    this.peer.handle('session.observe', async value => {
      const { sessionId, afterSeq = -1 } = value as { sessionId: string; afterSeq?: number };
      const agent = await this.agent(sessionId);
      const events = agent.session.snapshotEvents().filter(event => event.seq > afterSeq);
      await this.flush(agent);
      return { status: agent.status, events, approvals: await (await approval).entries(sessionId), throughSeq: events.at(-1)?.seq ?? afterSeq, durable: true };
    });
    this.peer.handle('session.descendants', async value => {
      const { sessionId, cursors = {} } = value as { sessionId: string; cursors?: Record<string, number> };
      const root = await this.agent(sessionId); await this.flush(root);
      const children = await ctx.subagents.listDescendants(root.id);
      return Promise.all(children.map(async child => {
        if (child.kind !== 'child') return child;
        const live = ctx.sessions.get(child.id);
        if (live && !await ctx.sessions.flush(live)) throw new RpcError(-32005, 'Child Session has no persistence barrier');
        using observation = await ctx.sessionQuery.observeSession(child.id);
        return { ...child, throughSeq: observation.cursor, events: observation.cursor > (cursors[child.id] ?? -1) ? observation.events : [] };
      }));
    });
    this.peer.handle('session.cancel', async value => {
      const { sessionId } = value as { sessionId: string };
      const agent = await this.agent(sessionId);
      const wasRunning = agent.status === 'running';
      agent.cancel({ kind: 'user' }, { keepInbox: true });
      await agent.whenIdle();
      await this.flush(agent);
      return { stopped: true, wasRunning };
    });
    this.peer.handle('approval.answer', value => {
      const { requestId, decision, reason } = value as { requestId: string; decision: ApprovalOutcome; reason?: string };
      if (!['allowed-once', 'rejected'].includes(decision)) throw new RpcError(-32602, 'Invalid approval decision');
      const answer = this.approvals.get(requestId);
      if (!answer) throw new RpcError(-32004, 'Approval is no longer pending');
      answer(decision, reason);
      return { answered: true };
    });
    this.peer.handle('configuration.apply', async value => {
      const next = value as AgentConfiguration;
      await ctx.llm.resolveModelInfo(next.provider, next.model);
      const previous = [...this.configurations.values()].find(config => config.agentId === next.agentId);
      if (previous && previous.mode !== next.mode) throw new RpcError(-32602, 'Work mode is immutable');
      if (previous) {
        (await configuration).restrictSelection(next);
        const restricted = { ...previous.features };
        for (const [key, enabled] of Object.entries(next.features ?? {})) if (!enabled) restricted[key] = false;
        await (await configuration).setFeatures(next.agentId, restricted);
        if (!next.features?.cron_scheduling) await this.cron.setEnabled(next.agentId, false);
        const active = [...this.bindings.values()].filter(binding => binding.agentId === next.agentId)
          .map(binding => ctx.agents.get(SessionId(binding.sessionId))).filter((agent): agent is Agent => !!agent);
        await Promise.all(active.map(agent => agent.whenIdle()));
        await (await configuration).setConfiguration(next);
      }
      const id = `nano:${next.agentId}:${next.revision}`;
      if (!this.configurations.has(id)) {
        this.configurations.set(id, previous ?? next);
        this.unregisterPresets.push(await ctx.agentPresets.register({ id, plugins: [
          { id: 'nano-agent-config', name: '@nano/dsh-integration/agent-config', config: { agentId: next.agentId } },
        ] }));
      }
      await this.cron.setEnabled(next.agentId, next.features?.cron_scheduling === true);
      this.peer.notify('heartbeat.subscription', { agentId: next.agentId, enabled: next.features?.heartbeat === true });
      return { effective: true, revision: next.revision };
    });
    this.peer.handle('configuration.features', async value => {
      const { agentId, features } = value as { agentId: string; features: Record<string, boolean> };
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new RpcError(-32004, 'Unknown product Agent');
      await (await configuration).setFeatures(agentId, features);
      await this.cron.setEnabled(agentId, features.cron_scheduling === true);
      this.peer.notify('heartbeat.subscription', { agentId, enabled: features.heartbeat === true });
      return { effective: true, features };
    });
    this.peer.handle('schedule.enabled', async value => {
      const { agentId, enabled } = value as { agentId: string; enabled: boolean };
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new RpcError(-32004, 'Unknown product Agent');
      await this.cron.setEnabled(agentId, enabled);
      for (const config of this.configurations.values()) if (config.agentId === agentId) config.features = { ...config.features, cron_scheduling: enabled };
      return { effective: true, enabled };
    });
    this.peer.handle('schedule.evidence', async value => {
      const agent = await this.agent((value as { sessionId: string }).sessionId); await this.flush(agent);
      return scheduleEvidence(agent.session.snapshotEvents());
    });
    this.peer.handle('schedule.command', async value => {
      const { agentId, sessionId, action, args = {} } = value as { agentId: string; sessionId?: string; action: string; args?: Record<string, unknown> };
      if (![...this.configurations.values()].some(config => config.agentId === agentId)) throw new RpcError(-32004, 'Unknown product Agent');
      if (sessionId && this.bindings.get(sessionId)?.agentId !== agentId) throw new RpcError(-32004, 'Schedule Session does not belong to this Agent');
      if (action === 'run') {
        const config = [...this.configurations.values()].find(config => config.agentId === agentId)!;
        if (!config.features?.cron_scheduling) throw new RpcError(-32002, 'Cron Feature is disabled');
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
      }
      return this.cron.command(agentId, sessionId, action, args);
    });
    this.peer.handle('shutdown', async () => {
      this.accepting = false;
      await this.cron.dispose();
      await Promise.allSettled([...this.inputs.values()]);
      const agents = [...this.bindings.keys()].map(id => ctx.agents.get(SessionId(id))).filter((agent): agent is Agent => !!agent);
      for (const agent of agents) agent.cancel({ kind: 'user' }, { keepInbox: true });
      await Promise.all(agents.map(async agent => { await agent.whenIdle(); await this.flush(agent); }));
      await this.controller.dispose();
      for (const unregister of this.unregisterPresets) await unregister();
      return { stopped: true };
    });
  }

  *[Service.init]() { yield () => { this.peer.close(); for (const answer of this.approvals.values()) answer('unavailable'); }; }

  private async ensure(binding: SessionBinding) {
    if (!this.accepting) throw new RpcError(-32003, 'Runtime is not accepting sessions');
    const previous = this.bindings.get(binding.sessionId);
    if (previous && JSON.stringify(previous) !== JSON.stringify(binding)) throw new RpcError(-32002, 'Session binding conflict');
    const preset = `nano:${binding.agentId}:${binding.revision}`;
    if (!this.configurations.has(preset)) throw new RpcError(-32002, 'Unknown configuration revision');
    this.bindings.set(binding.sessionId, binding);
    await (await this.sessionController).create({ sessionId: SessionId(binding.sessionId), cwd: binding.cwd, agentPreset: preset });
    const agent = await this.agent(binding.sessionId);
    await this.flush(agent);
    return { sessionId: agent.id, revision: binding.revision };
  }

  private async agent(sessionId: string): Promise<Agent> {
    if (!this.bindings.has(sessionId)) throw new RpcError(-32004, 'Session has no trusted product binding');
    const result = await (await this.sessionController).resolveAgent(SessionId(sessionId));
    if ('error' in result) throw result.error;
    return result.agent;
  }

  private async submit(input: Submit) {
    if (!this.accepting) throw new RpcError(-32003, 'Runtime is not accepting inputs');
    const agent = await this.agent(input.sessionId);
    if (!inputEvidence(agent.session.snapshotEvents(), input.inputId).accepted) {
      if (!['human', 'system'].includes(input.source.kind)) throw new RpcError(-32602, 'Invalid input source');
      const content = await this.ctx.attachments.admitPromptContent(input.content);
      if (input.onlyIfIdle && (agent.status !== 'idle' || agent.inbox.nextTurn.length || agent.inbox.nextStep.length)) return { accepted: false, busy: true };
      const message = freezeMessage({ id: MessageId(input.inputId), role: 'user' as const, content,
        source: { ...input.source, kind: input.source.kind === 'human' ? 'nano-human' as const : 'nano-system' as const } });
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
