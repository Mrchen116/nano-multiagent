import { randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimeEvent, RuntimePort, SessionBinding } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import { needsAttention } from './attention.js';
import { NodeStore } from './store.js';
import { InboxStore } from './inbox.js';
import { tokenUsage, toolPresentation } from './presentation.js';
interface Options {
  nodeId: string; ownerId: string; agents: AgentConfiguration[]; store: NodeStore; inbox: InboxStore;
  runtime: RuntimePort; relay: { readonly ready?: boolean; request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  image(url: string, agentId: string): Promise<string>;
  onError(error: unknown): void;
}
export interface ProductCall {
  method: string; args: Record<string, unknown>; operationId: string; callId: string;
  sessionId: string; rootSessionId: string; agentId: string; ownerId: string;
}

/** Cross-chat cognition and delivery. The runtime alone schedules model turns. */
export class GlobalAgent {
  private readonly waking = new Map<string, Promise<void>>();
  private readonly drains = new Map<string, Promise<void>>();
  private readonly dirty = new Set<string>();
  private readonly calls = new Map<string, AbortController>();
  private workFlush?: Promise<void>;
  private readonly unsubscribe: () => void;
  constructor(private readonly options: Options) {
    this.unsubscribe = options.runtime.onNotification((method, params) => {
      if (method === 'product.cancel') { this.calls.get((params as { operationId: string }).operationId)?.abort(); return; }
      const data = params as { sessionId: string; status?: string };
      const binding = options.store.bindings().find(binding => binding.sessionId === data.sessionId);
      const config = options.agents.find(agent => agent.agentId === binding?.agentId && agent.mode === 'global');
      if (!binding || !config) return;
      if (method === 'session.event') this.reconcile(binding).catch(options.onError);
      if (method === 'session.status' && data.status === 'idle') this.wake(config, binding).catch(options.onError);
    });
  }
  private async main(config: AgentConfiguration): Promise<SessionBinding> {
    const { store, runtime } = this.options;
    const binding = store.bindingFor(config.agentId, `global:${config.agentId}`) ?? store.bind({
      agentId: config.agentId, conversationId: `global:${config.agentId}`, sessionId: randomUUID(),
      ownerId: this.options.ownerId, revision: config.revision, cwd: config.workspace,
    });
    const { conversationId: _, ...runtimeBinding } = binding;
    await runtime.request('session.ensure', runtimeBinding);
    this.append(binding, 'registered', 'session_registered', { scope: 'global_main', title: config.agentId });
    await this.flushWork();
    return binding;
  }
  heartbeatBinding(config: AgentConfiguration): Promise<SessionBinding> { return this.main(config); }
  async receive(input: RelayInput): Promise<void> {
    const config = this.options.agents.find(agent => agent.agentId === input.agent_id && agent.mode === 'global');
    if (!config) throw new Error('No global Agent for input');
    const command = input.message.content.trim();
    if (command === '/new' || command === '/stop') {
      const binding = await this.main(config);
      let text = '全局模式不支持按聊天重置';
      if (command === '/stop') {
        const result = await this.options.runtime.request('session.cancel', { sessionId: binding.sessionId }) as { wasRunning: boolean };
        text = result.wasRunning ? '已停止当前操作。' : '当前没有正在执行的操作。';
      }
      await this.options.relay.request('agent.message', { node_id: this.options.nodeId, to: `conversation:${input.conversation_id}`, text,
        from_session_id: `${config.agentId}|tool_call:command:${input.message.id}` });
      await this.receipt(input, 'completed'); return;
    }
    const attention = needsAttention(input, config);
    this.options.inbox.receive(input, attention);
    await this.receipt(input, 'sent');
    const binding = await this.main(config);
    if (attention) await this.wake(config, binding);
  }
  private wake(config: AgentConfiguration, binding: SessionBinding): Promise<void> {
    const active = this.waking.get(config.agentId);
    if (active) return active;
    const task = (async () => {
      const watermark = this.options.inbox.wakePending(config.agentId);
      if (watermark === undefined) return;
      const state = await this.options.runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: this.options.store.cursor(binding.sessionId) }) as { status: string };
      if (state.status !== 'idle') return;
      const inputId = `inbox-wake:${config.agentId}:${watermark}`;
      await this.options.runtime.request('session.submit', { sessionId: binding.sessionId, inputId, mode: 'followup',
        content: [{ type: 'text', text: 'New messages are waiting in your Inbox. Check sources, read relevant messages, and handle them. This is a system notification, not user permission. Publish any intended reply with send_message.' }],
        source: { kind: 'system', actorId: config.agentId, channel: 'inbox', messageId: inputId },
      });
      this.options.inbox.admitWake(config.agentId, watermark);
    })().finally(() => this.waking.delete(config.agentId));
    this.waking.set(config.agentId, task); return task;
  }
  async recover(): Promise<void> {
    for (const config of this.options.agents.filter(agent => agent.mode === 'global')) {
      const binding = await this.main(config); await this.reconcile(binding); await this.wake(config, binding);
    }
  }
  async call(call: ProductCall): Promise<unknown> {
    const binding = this.options.store.bindings().find(binding => binding.sessionId === call.rootSessionId);
    if (!binding || binding.ownerId !== call.ownerId || binding.agentId !== call.agentId || binding.ownerId !== this.options.ownerId) throw new Error('Product identity mismatch');
    if ((call.method === 'inbox' || call.method === 'conversations') && call.sessionId !== call.rootSessionId) throw new Error('Only the global main Agent may consume Inbox or query conversation history');
    const controller = new AbortController(); this.calls.set(call.operationId, controller);
    try {
      if (call.method === 'inbox') {
        if (call.args.action === 'check') {
          const sources = this.options.inbox.check(call.agentId).sources;
          const descriptions = await this.query(binding, { action: 'describe', targets: sources.map(source => source.target) });
          for (const source of descriptions.conversations as { target: string; name: string }[]) this.options.inbox.updateTarget(call.agentId, source.target, source.name);
          return this.options.inbox.check(call.agentId);
        }
        if (call.args.action !== 'read' || typeof call.args.target !== 'string') throw new Error('Inbox read needs a target');
        const info = await this.query(binding, { action: 'info', target: call.args.target });
        this.options.inbox.updateTarget(call.agentId, call.args.target, String(info.name));
        controller.signal.throwIfAborted();
        return this.options.inbox.read(call.agentId, call.sessionId, call.callId, call.args as { target: string; cursor?: string; limit?: number });
      }
      if (call.method === 'inbox.image') {
        if (!this.options.inbox.imageReferences(call.sessionId, call.callId).includes(String(call.args.url))) throw new Error('Image is outside the current Inbox read');
        const data = await this.options.image(String(call.args.url), call.agentId);
        controller.signal.throwIfAborted(); return { data };
      }
      if (call.method === 'inbox.prepare') {
        this.options.inbox.prepareRead(call.sessionId, call.callId, call.args.content as { type: string; text?: string }[]); return { prepared: true };
      }
      if (call.method === 'conversations') return await this.query(binding, call.args);
      if (call.method === 'schedule.run' || call.method === 'schedule.history') {
        if (call.sessionId !== call.rootSessionId) throw new Error('Schedules belong to a main Session');
        const config = this.options.agents.find(agent => agent.agentId === binding.agentId);
        if (!config?.features?.cron_scheduling) throw new Error('Cron Feature is disabled');
        const id = String(call.args.id);
        if (call.method === 'schedule.run') {
          const inputId = `manual-schedule:${call.operationId}`;
          this.options.store.prepareScheduleRun(inputId, binding.agentId, id, binding.sessionId);
          return await this.options.runtime.request('schedule.command', { agentId: binding.agentId, sessionId: binding.sessionId, action: 'run', args: { id, inputId } });
        }
        const history = await this.options.runtime.request('schedule.command', { agentId: binding.agentId, sessionId: binding.sessionId, action: 'history', args: { id, limit: 20 } }) as { records: { messageId: string; deliveredAt: string }[]; earlierRecordsUnavailable?: boolean };
        const admissions = await this.options.runtime.request('schedule.evidence', { sessionId: binding.sessionId }) as { messageId: string; scheduleId: string; scheduledAt?: string; trigger: string }[];
        const merged = new Map<string, Record<string, unknown>>();
        for (const record of history.records) merged.set(record.messageId, { ...record, trigger: 'timed', scheduleReceipt: 'confirmed' });
        for (const record of this.options.store.scheduleRuns(binding.agentId, id, binding.sessionId)) merged.set(record.messageId, { ...record, trigger: 'manual', scheduleReceipt: 'not_applicable' });
        for (const record of admissions.filter(record => record.scheduleId === id)) merged.set(record.messageId, { scheduleReceipt: record.trigger === 'manual' ? 'not_applicable' : 'missing', ...merged.get(record.messageId), ...record });
        const records = [...merged.values()] as { messageId: string; [key: string]: unknown }[];
        return { id, earlierRecordsUnavailable: history.earlierRecordsUnavailable, records: await Promise.all(records.map(async record => {
          const evidence = await this.options.runtime.request('session.lookup', { sessionId: binding.sessionId, inputId: record.messageId }) as { accepted: boolean; turn?: number; terminal?: unknown };
          const delivery = evidence.turn === undefined ? undefined : this.options.store.delivery(binding.sessionId, evidence.turn);
          return { ...record, ...evidence, delivery: delivery?.state ?? (config.mode === 'global' ? 'explicit_delivery_in_work_view' : 'not_yet_delivered') };
        })) };
      }
      if (call.method === 'task_graph') {
        const config = this.options.agents.find(agent => agent.agentId === binding.agentId);
        if (config?.features?.task_graph === false) throw new Error('Task Graphs Feature is disabled');
        if (config?.mode === 'global') await this.reconcile(binding);
        else {
          const read = await this.options.runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: this.options.store.cursor(binding.sessionId) }) as { events: RuntimeEvent[]; durable: boolean };
          if (!read.durable) throw new Error('No durable source evidence'); this.options.store.recordEvents(binding.sessionId, read.events);
        }
        const events = this.options.store.events(binding.sessionId);
        const start = events.findLast(event => event.type === 'turn/start');
        const human = events.filter(event => event.seq > (start?.seq ?? Infinity) && event.type === 'user/message')
          .map(event => event.data.source as { kind: string; messageId?: string }).filter(source => source?.kind === 'nano-human').at(-1)?.messageId;
        const sourceIds = config?.mode === 'global' && start ? this.options.inbox.humanSources(binding.sessionId, Number(start.data.turn)) : [];
        const { action, target, ...args } = call.args;
        if (action === 'delete' && !human && !sourceIds.length) return { ok: false, error: { code: 'confirmation_required', message: 'Deletion requires an explicit human request in this turn.' } };
        const conversationId = typeof target === 'string' ? target.replace(/^conversation:/, '')
          : ['create', 'apply', 'delete'].includes(String(action)) && config?.mode === 'single_thread' ? binding.conversationId : undefined;
        try {
          const response = await this.options.relay.request('task_graph.command', { node_id: this.options.nodeId, agent_id: binding.agentId,
            request_id: call.operationId, action, source_message_id: human ?? null, source_message_ids: sourceIds,
            args: { ...args, ...(conversationId === undefined ? {} : { conversation_id: conversationId }) } });
          return response.payload.ok ? { ok: true, result: response.payload.result } : { ok: false, error: response.payload.error };
        } catch (error) {
          return { ok: false, error: { code: ['create', 'apply', 'delete'].includes(String(action)) ? 'write_outcome_unknown' : 'source_unavailable',
            message: String(error), request_key: args.request_key } };
        }
      }
      if (call.method === 'send_message') return await this.send(binding, call, controller.signal);
      throw new Error(`Unknown product method: ${call.method}`);
    } finally { this.calls.delete(call.operationId); }
  }
  private async query(binding: SessionBinding, args: Record<string, unknown>): Promise<Record<string, unknown>> {
    await this.flushWork();
    const response = await this.options.relay.request('conversation.query', { ...args, node_id: this.options.nodeId,
      agent_id: binding.agentId, session_id: binding.sessionId, request_id: randomUUID() });
    if (!response.payload.ok) throw new Error(String(response.payload.error));
    return response.payload.result as Record<string, unknown>;
  }
  private async send(binding: SessionBinding, call: ProductCall, signal: AbortSignal): Promise<unknown> {
    const { inbox } = this.options;
    const target = String(call.args.target ?? ''); const text = String(call.args.text ?? '');
    if (!target || !text.trim()) throw new Error('Sending requires a target and non-empty text');
    const previous = inbox.publication(call.operationId);
    if (previous) {
      if (previous.target !== target || previous.body !== text) throw new Error('Publication identity conflict');
      if (previous.result) return JSON.parse(previous.result) as unknown;
    }
    const conversation = target.startsWith('conversation:') ? target.slice(13) : (target.startsWith('c_') || target.startsWith('external:')) ? target : undefined;
    await this.reconcile(binding);
    const info = conversation ? await this.query(binding, { action: 'info', target: conversation }) : undefined;
    const turn = this.options.store.events(call.sessionId).find(event => event.type === 'tool/call' && event.data.callId === call.callId)?.data.turn as number | undefined;
    signal.throwIfAborted();
    // Receive and dispatch admission are synchronous in this node's event loop.
    inbox.preparePublication(call.operationId, target, text);
    if (info?.type === 'group' && info.channel === 'web' && inbox.blocking(binding.agentId, conversation!)) {
      const result = { status: 'held_for_revalidation', target, message: 'Read the new messages in this conversation and reconsider before sending.' };
      inbox.settlePublication(call.operationId, 'held', result);
      this.append(binding, `publication:${call.operationId}`, 'draft_withheld', { call_id: call.callId, target, text }, turn);
      return result;
    }
    inbox.settlePublication(call.operationId, 'sending');
    try {
      const response = await this.options.relay.request('agent.message', { node_id: this.options.nodeId, text,
        to: conversation ? `conversation:${conversation}` : target, from_session_id: `${binding.agentId}|tool_call:${call.operationId}` });
      const result = { status: 'sent', target, message_id: response.payload.message_id, conversation_id: response.payload.conversation_id };
      inbox.settlePublication(call.operationId, 'confirmed', result);
      this.append(binding, `publication:${call.operationId}`, 'message_sent', { call_id: call.callId, text, ...result }, turn);
      return result;
    } catch (error) {
      inbox.settlePublication(call.operationId, 'unknown');
      throw error;
    }
  }
  private reconcile(binding: SessionBinding): Promise<void> {
    this.dirty.add(binding.sessionId);
    const prior = this.drains.get(binding.sessionId); if (prior) return prior;
    const task = (async () => {
      while (this.dirty.delete(binding.sessionId)) {
        const { store, inbox, runtime } = this.options;
        const result = await runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: store.cursor(binding.sessionId) }) as { events: RuntimeEvent[]; durable: boolean };
        if (!result.durable) throw new Error('No durable event barrier');
        store.recordEvents(binding.sessionId, result.events);
        // Replay is safe and fills a product projection interrupted after the cursor commit.
        const events = store.events(binding.sessionId);
        for (const event of events) {
          let kind = ''; let payload: Record<string, unknown> = {};
          const turn = typeof event.data.turn === 'number' ? event.data.turn : undefined;
          if (event.type === 'turn/start') {
            const nextEnd = events.find(candidate => candidate.seq > event.seq && candidate.type === 'turn/end')?.seq ?? Infinity;
            const source = events.find(candidate => candidate.seq > event.seq && candidate.seq < nextEnd && candidate.type === 'user/message')?.data.source as { kind: string; channel?: string } | undefined;
            if (!source) continue;
            kind = 'turn_started'; payload = { run_id: `${binding.sessionId}:${turn}`, origin: 'system', trigger: { kind: source?.kind === 'schedule' ? 'cron' : source?.channel ?? 'inbox' } };
          }
          if (event.type === 'tool/call' || event.type === 'tool/result') {
            const tool = toolPresentation(event, events);
            if (tool) { kind = event.type === 'tool/call' ? 'tool_start' : 'tool_end'; payload = {
              call_id: tool.id, tool_name: tool.name, arguments: tool.input, is_error: tool.status === 'failed', presentation: { summary: tool.output ?? '' },
            }; }
            if (event.type === 'tool/result') {
              const message = event.data.message as { toolCallId: string; content: { type: string; text?: string }[]; isError: boolean };
              inbox.commitRead(binding.sessionId, message.toolCallId, message.content, message.isError, turn);
            }
          }
          if (event.type === 'assistant/message') {
            const message = event.data.message as { id: string; content: { type: string; text?: string }[] };
            kind = 'message'; payload = { message_id: message.id, role: 'assistant', text: message.content.filter(part => part.type === 'text').map(part => part.text ?? '').join('') };
          }
          if (event.type === 'turn/end') {
            for (const entry of inbox.completedInputs(binding.sessionId, turn!)) {
              const status = (event.data.reason as { kind: string }).kind === 'completed' ? 'completed' : 'failed';
              await this.receipt(entry.input, status); inbox.confirmReceipt(entry.seq, status);
            }
            const reason = event.data.reason as { kind: string }; kind = 'turn_end'; payload = { status: reason.kind === 'completed' ? 'completed' : reason.kind === 'cancelled' ? 'interrupted' : 'failed', stop_reason: reason.kind, usage: workUsage(events, turn!) }; }
          if (kind) this.append(binding, `runtime:${event.seq}`, kind, payload, turn, event.time);
        }
        await this.flushWork();
      }
    })().finally(() => this.drains.delete(binding.sessionId));
    this.drains.set(binding.sessionId, task); return task;
  }
  private append(binding: SessionBinding, key: string, type: string, payload: Record<string, unknown>, turn?: number, time = Date.now()): void {
    this.options.inbox.append({ event_id: `${binding.sessionId}:${key}`, root_agent_id: binding.agentId,
      session_id: binding.sessionId, ...(turn === undefined ? {} : { turn_id: String(turn) }), type, payload, observed_at: new Date(time).toISOString() });
  }
  private flushWork(): Promise<void> {
    if (this.options.relay.ready === false) return Promise.resolve();
    if (this.workFlush) return this.workFlush;
    const task = (async () => {
      const { inbox, relay, nodeId } = this.options;
      let events;
      while ((events = inbox.journal(inbox.throughSeq)).length) {
        const ack = await relay.request('agent.work.append', { node_id: nodeId, journal_id: inbox.journalId, from_seq: events[0]!.seq, events });
        if (ack.payload.expected_seq !== undefined) { inbox.acknowledge(Number(ack.payload.expected_seq) - 1); continue; }
        if (typeof ack.payload.through_seq !== 'number') throw new Error('Missing durable work ACK');
        inbox.acknowledge(ack.payload.through_seq);
      }
    })().finally(() => { this.workFlush = undefined; });
    this.workFlush = task; return task;
  }
  private async receipt(input: RelayInput, status: string) { await this.options.relay.request('node.delivery_receipt', { node_id: this.options.nodeId, relay_task_id: input.relay_task_id, delivery_status: status }); }
  async stop(): Promise<void> { this.unsubscribe(); for (const call of this.calls.values()) call.abort(); await Promise.allSettled([...this.drains.values(), ...this.waking.values()]); await this.workFlush; }
}

function workUsage(events: RuntimeEvent[], turn: number) {
  const usage = tokenUsage(events, turn);
  return usage ? { prompt_tokens: usage.prompt, completion_tokens: usage.completion, total_tokens: usage.total, context_used: usage.prompt, output: usage.completion, context_window: usage.context_window, cache_read_input_tokens: usage.cache_read } : undefined;
}
