/** Nano's sole stdio server inside an unmodified DSH profile. */
import { randomUUID } from 'node:crypto';
import { Context, Service } from '@deepseek-ai/cordis';
import { SessionController } from '@deepseek-ai/dsh-api-session-controller';
import { SessionId } from '@deepseek-ai/dsh-session';
import { freezeMessage, MessageId, ReasoningEffortId, type UserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval';
import type {} from '@deepseek-ai/dsh-agent-preset-registry';
import type {} from '@deepseek-ai/dsh-system-prompt';
import type { PromptContentPart } from '@deepseek-ai/dsh-attachment';
import { RpcError, RpcPeer } from './rpc.js';
import { inputEvidence } from './input-evidence.js';

export interface AgentConfiguration {
  agentId: string;
  revision: string;
  provider: string;
  model: string;
  reasoningEffort?: string;
  maxTokens?: number;
  systemPrompt?: string;
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
  content: PromptContentPart[];
  source: { kind: 'human' | 'system'; actorId: string; channel: string; messageId: string };
}
declare module '@deepseek-ai/dsh-llm' {
  interface MessageSourceMap {
    'nano-human': { kind: 'nano-human'; actorId: string; channel: string; messageId: string };
    'nano-system': { kind: 'nano-system'; actorId: string; channel: string; messageId: string };
  }
}

/** Trusted node configuration is installed before any Session can be resumed. */
export default class NanoRuntime {
  static inject = ['agents', 'sessions', 'agentPresets', 'loader', ...SessionController.inject];
  private readonly peer = new RpcPeer(process.stdin, process.stdout);
  private readonly bindings = new Map<string, SessionBinding>();
  private readonly configurations = new Map<string, AgentConfiguration>();
  private readonly inputs = new Map<string, Promise<unknown>>();
  private readonly approvals = new Map<string, (answer: ApprovalOutcome) => void>();
  private readonly unregisterPresets: (() => Promise<void>)[] = [];
  private accepting = false;
  private readonly controller;
  private readonly sessionController: Promise<SessionController>;

  constructor(private readonly ctx: Context) {
    this.controller = ctx.plugin(SessionController, { nativeOpen: false });
    this.sessionController = new Promise(resolve => {
      ctx.inject(['sessionController'], child => { resolve(child.sessionController); });
    });
    ctx.on('agent/created', ({ agent }) => {
      const preset = agent.session.header.agentPreset;
      if (!preset?.startsWith('nano:')) return;
      const config = this.configurations.get(preset);
      if (!config) throw new Error(`Missing Nano configuration for ${preset}`);
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
      this.peer.notify('session.event', { sessionId: session.id, event });
    });
    ctx.on('agent/status', ({ agent, status }) => this.peer.notify('session.status', { sessionId: agent.id, status }));
    ctx.on('agent/assistant-stream', ({ agent, frame }) => this.peer.notify('session.stream', { sessionId: agent.id, frame }));
    ctx.on('agent/error', ({ agent, error }) => this.peer.notify('session.error', { sessionId: agent.id, message: String(error) }));
    ctx.on('approval/request', async request => {
      const requestId = randomUUID();
      return new Promise<ApprovalOutcome>(resolve => {
        const finish = (answer: ApprovalOutcome) => {
          this.approvals.delete(requestId);
          request.signal?.removeEventListener('abort', cancel);
          resolve(answer);
          this.peer.notify('approval.resolved', { requestId, sessionId: request.agent.id, outcome: answer });
        };
        const cancel = () => finish('cancelled');
        this.approvals.set(requestId, finish);
        if (request.signal?.aborted) return cancel();
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
      await ctx.loader.await();
      for (const agent of config.agents) {
        await ctx.llm.resolveModelInfo(agent.provider, agent.model);
        const id = `nano:${agent.agentId}:${agent.revision}`;
        this.configurations.set(id, agent);
        this.unregisterPresets.push(await ctx.agentPresets.register({ id, plugins: agent.systemPrompt ? [
          { id: 'nano-persona', name: '@deepseek-ai/dsh-persona', config: { prefix: agent.systemPrompt } },
        ] : [] }));
      }
      for (const binding of config.bindings) this.bindings.set(binding.sessionId, binding);
      this.accepting = true;
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
      return { events, throughSeq: events.at(-1)?.seq ?? afterSeq, durable: true };
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
      const { requestId, decision } = value as { requestId: string; decision: ApprovalOutcome };
      if (!['allowed-once', 'rejected'].includes(decision)) throw new RpcError(-32602, 'Invalid approval decision');
      const answer = this.approvals.get(requestId);
      if (!answer) throw new RpcError(-32004, 'Approval is no longer pending');
      answer(decision);
      return { answered: true };
    });
    this.peer.handle('shutdown', async () => {
      this.accepting = false;
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
