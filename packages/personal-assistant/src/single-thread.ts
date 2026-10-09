import { randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimeEvent, RuntimePort, SessionBinding } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import { NodeStore } from './store.js';
import { argumentsObject, tokenUsage, toolPresentation } from './presentation.js';

interface RelayPort { request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> }
interface InputEvidence { accepted: boolean; turn?: number; terminal?: unknown }
interface Options {
  nodeId: string;
  ownerId: string;
  agents: AgentConfiguration[];
  store: NodeStore;
  runtime: RuntimePort;
  relay: RelayPort;
  image: (url: string, agentId: string) => Promise<string>;
  onError: (error: unknown) => void;
}

/** Single-thread product routing; DSH remains the only model/turn scheduler. */
export class SingleThread {
  private readonly draining = new Map<string, Promise<void>>();
  private readonly dirty = new Set<string>();
  private readonly pendingApprovals = new Map<string, { sessionId: string; messageId: string; posted: boolean; decision?: string; outcome?: string }>();
  private readonly unsubscribe: () => void;
  private readonly streams = new Map<string, { turn: number; chain: Promise<unknown> }>();
  constructor(private readonly options: Options) {
    this.unsubscribe = options.runtime.onNotification((method, value) => {
      const data = value as { sessionId: string; event?: RuntimeEvent };
      if (method === 'session.event' && data.event) this.reconcile(data.sessionId).catch(options.onError);
      if (method === 'approval.request') this.approval(value as Approval).catch(options.onError);
      if (method === 'approval.resolved') this.resolveApproval(value as { requestId: string; outcome: string }).catch(options.onError);
      if (method === 'session.stream') this.stream(value as Stream);
    });
  }

  /** Store inbound content before acknowledging its durable runtime handoff. */
  async receive(input: RelayInput): Promise<void> {
    const { store, runtime, agents } = this.options;
    const config = agents.find(agent => agent.agentId === input.agent_id);
    if (!config || config.mode !== 'single_thread') throw new Error('Input has no single-thread Agent on this node');
    const binding = store.bindingFor(config.agentId, input.conversation_id) ?? store.bind({
      sessionId: randomUUID(), conversationId: input.conversation_id, agentId: config.agentId,
      ownerId: this.options.ownerId, cwd: config.workspace, revision: config.revision,
    });
    if (input.message.content.trim() === '/stop') {
      await runtime.request('session.ensure', runtimeBinding(binding));
      const result = await runtime.request('session.cancel', { sessionId: binding.sessionId }) as { wasRunning: boolean };
      await this.reconcile(binding.sessionId);
      const ack = await this.delta({ kind: 'turn_start', conversation_id: binding.conversationId, agent_id: binding.agentId,
        idempotency_key: `command:${input.message.id}` });
      await this.delta({ kind: 'message_completed', message_id: ack.payload.message_id,
        final_content: result.wasRunning ? '已停止当前操作。' : '当前没有正在执行的操作。', delivery_status: 'completed' });
      await this.receipt(input, 'completed');
      return;
    }
    const inputId = store.receive(binding.sessionId, input);
    await runtime.request('session.ensure', runtimeBinding(binding));
    const evidence = await runtime.request('session.lookup', { sessionId: binding.sessionId, inputId }) as InputEvidence;
    if (!evidence.accepted) {
      const content: Record<string, unknown>[] = [{ type: 'text', text: input.message.content }];
      for (const attachment of input.message.attachments) {
        if (!attachment.content_type.startsWith('image/')) throw new Error('This input attachment is not an image');
        content.push({ type: 'image', mediaType: attachment.content_type, name: attachment.file_name, data: await this.options.image(attachment.url, binding.agentId) });
      }
      await runtime.request('session.submit', { sessionId: binding.sessionId, inputId, mode: 'followup', content,
        source: { kind: input.message.sender_type === 'user' ? 'human' : 'system', actorId: input.message.sender_user_id, channel: 'web_relay', messageId: input.message.id },
      });
    }
    store.accepted(inputId);
    if (!store.inputs(binding.sessionId).find(item => item.id === inputId)?.terminal) await this.receipt(input, 'sent');
    await this.reconcile(binding.sessionId);
  }

  /** Durable history is replayed on reconnect; display notifications are just hints. */
  async recover(): Promise<void> {
    for (const binding of this.options.store.bindings()) {
      await this.options.runtime.request('session.ensure', runtimeBinding(binding));
      for (const input of this.options.store.inputs(binding.sessionId)) if (!input.accepted) await this.receive(input.input);
      await this.reconcile(binding.sessionId);
    }
  }

  /** Permission responses use the independent runtime control path. */
  async permission(payload: Record<string, unknown>): Promise<void> {
    const requestId = String(payload.request_id);
    const pending = this.pendingApprovals.get(requestId);
    if (!pending) throw new Error('Permission is no longer pending');
    pending.decision = String(payload.decision);
    const decision = payload.decision === 'allow' || payload.decision === 'allow_once' ? 'allowed-once' : 'rejected';
    await this.options.runtime.request('approval.answer', { requestId, decision });
  }

  private reconcile(sessionId: string): Promise<void> {
    this.dirty.add(sessionId);
    const active = this.draining.get(sessionId);
    if (active) return active;
    const task = (async () => {
      while (this.dirty.delete(sessionId)) await this.drain(sessionId);
    })().finally(() => { this.draining.delete(sessionId); });
    this.draining.set(sessionId, task);
    return task;
  }

  private async drain(sessionId: string): Promise<void> {
    const { store, runtime } = this.options;
    const binding = store.bindings().find(item => item.sessionId === sessionId);
    if (!binding) return;
    const read = await runtime.request('session.observe', { sessionId, afterSeq: store.cursor(sessionId) }) as { events: RuntimeEvent[]; durable: boolean };
    if (!read.durable) throw new Error('Runtime observation lacks a durable barrier');
    store.recordEvents(sessionId, read.events);
    for (const input of store.inputs(sessionId)) {
      const evidence = await runtime.request('session.lookup', { sessionId, inputId: input.id }) as InputEvidence;
      store.inputEvidence(input.id, evidence);
    }
    const events = store.events(sessionId);
    for (const input of store.inputs(sessionId)) {
      if (input.turn === null) continue;
      const turn = input.turn;
      let delivery = store.prepareDelivery(sessionId, turn);
      if (delivery.state === 'confirmed' || delivery.state === 'failed') {
        await this.receipt(input.input, delivery.state === 'confirmed' ? 'completed' : 'failed');
        continue;
      }
      if (!delivery.messageId) {
        store.updateDelivery(delivery.operationId, 'sending', null, delivery.content);
        // IM's caller_idempotency_key makes a lost creation ACK recover the same bubble.
        const ack = await this.delta({ kind: 'turn_start', conversation_id: binding.conversationId,
          agent_id: binding.agentId, idempotency_key: delivery.operationId });
        const messageId = ack.payload.message_id;
        if (typeof messageId !== 'string') throw new Error('IM did not acknowledge the output message identity');
        store.updateDelivery(delivery.operationId, 'sending', messageId, delivery.content);
        delivery = store.delivery(sessionId, turn)!;
      }
      for (const event of events.filter(event => event.data.turn === turn)) {
        if (store.eventDelivered(delivery.operationId, event.seq)) continue;
        const tool = toolPresentation(event, events);
        if (tool) await this.delta({ kind: event.type === 'tool/call' ? 'tool_call_upserted' : 'tool_call_completed',
          message_id: delivery.messageId, tool_call: tool, process_seq: event.seq });
        if (event.type === 'assistant/message') {
          const message = event.data.message as { content: { type: string; text?: string }[] };
          const reasoning = message.content.filter(block => block.type === 'reasoning').map(block => block.text ?? '').join('');
          if (reasoning) await this.delta({ kind: 'thinking_segment', message_id: delivery.messageId, text: reasoning, process_seq: event.seq });
        }
        store.confirmEvent(delivery.operationId, event.seq);
      }
      const end = events.find(event => event.type === 'turn/end' && event.data.turn === turn);
      if (!end) continue;
      const answers = events.filter(event => event.type === 'assistant/message' && event.data.turn === turn);
      const final = answers.at(-1);
      const message = final?.data.message as { id: string; content: { type: string; text?: string }[] } | undefined;
      const text = message?.content.filter(block => block.type === 'text').map(block => block.text ?? '').join('') ?? '';
      const reason = end.data.reason as { kind: string };
      const completed = reason.kind === 'completed';
      store.updateDelivery(delivery.operationId, 'completing', delivery.messageId, text);
      await this.delta({ kind: 'message_completed', message_id: delivery.messageId,
        final_content: text, delivery_status: completed ? 'completed' : 'failed',
        kernel_message_id: message?.id, idempotency_key: `${delivery.operationId}:complete`,
        token_usage: tokenUsage(events, turn),
      });
      store.updateDelivery(delivery.operationId, completed ? 'confirmed' : 'failed', delivery.messageId, text);
      await this.receipt(input.input, completed ? 'completed' : 'failed');
    }
  }

  private async approval(request: Approval) {
    const pending: { sessionId: string; messageId: string; posted: boolean; decision?: string; outcome?: string } = {
      sessionId: request.sessionId, messageId: '', posted: false,
    };
    this.pendingApprovals.set(request.requestId, pending);
    await this.reconcile(request.sessionId);
    if (pending.outcome) { this.pendingApprovals.delete(request.requestId); return; }
    const input = this.options.store.inputs(request.sessionId).find(input => input.turn !== null && input.terminal === null);
    const delivery = input?.turn === undefined || input.turn === null ? undefined : this.options.store.delivery(request.sessionId, input.turn);
    if (!delivery?.messageId) throw new Error('Approval has no product output binding');
    pending.messageId = delivery.messageId;
    const call = this.options.store.events(request.sessionId).find(event => event.type === 'tool/call' && event.data.callId === request.callId);
    await this.delta({ kind: 'permission_request', message_id: delivery.messageId, session_id: request.sessionId,
      agent_id: this.binding(request.sessionId).agentId, run_id: request.sessionId,
      permission_request: { request_id: request.requestId, tool_name: request.toolName, reason: request.reason, call_id: request.callId,
        tool_input: argumentsObject(call?.data.arguments ?? '{}'), question: request.reason ?? 'Allow this action?', status: 'pending',
        options: [{ id: 'allow_once', label: 'Allow once', description: '' }, { id: 'deny', label: 'Deny', description: '' }],
      },
    });
    pending.posted = true;
    if (pending.outcome) await this.resolveApproval({ requestId: request.requestId, outcome: pending.outcome });
  }
  private async resolveApproval(result: { requestId: string; outcome: string }) {
    const pending = this.pendingApprovals.get(result.requestId);
    if (!pending) return;
    pending.outcome = result.outcome;
    if (!pending.posted) return;
    await this.delta({ kind: 'permission_resolved', message_id: pending.messageId, request_id: result.requestId,
      decision: pending.decision ?? (result.outcome === 'allowed-once' ? 'allow_once' : result.outcome === 'rejected' ? 'deny' : result.outcome),
      session_id: pending.sessionId, run_id: pending.sessionId, agent_id: this.binding(pending.sessionId).agentId });
    this.pendingApprovals.delete(result.requestId);
  }
  private binding(sessionId: string): SessionBinding {
    const binding = this.options.store.bindings().find(item => item.sessionId === sessionId);
    if (!binding) throw new Error('Unknown session');
    return binding;
  }
  private delta(payload: Record<string, unknown>) { return this.options.relay.request('node.streaming_delta', { node_id: this.options.nodeId, ...payload }); }
  private async receipt(input: RelayInput, status: string) {
    const inputId = `${input.agent_id}:${input.message.id}`;
    if (this.options.store.receipt(inputId) === status) return;
    await this.options.relay.request('node.delivery_receipt', { node_id: this.options.nodeId, relay_task_id: input.relay_task_id, delivery_status: status });
    // /stop has no model input, so it has no input receipt row.
    if (input.message.content.trim() !== '/stop') this.options.store.confirmReceipt(inputId, status);
  }
  private stream({ sessionId, frame }: Stream) {
    if (frame.type === 'start') {
      this.streams.set(frame.attemptId, { turn: frame.turn!, chain: this.reconcile(sessionId) });
      return;
    }
    const stream = this.streams.get(frame.attemptId);
    if (!stream) return;
    if (frame.type === 'end') { void stream.chain.finally(() => this.streams.delete(frame.attemptId)); return; }
    if (frame.chunk?.type !== 'text-delta') return;
    stream.chain = stream.chain.then(async () => {
      const delivery = this.options.store.delivery(sessionId, stream.turn);
      if (!delivery?.messageId || delivery.state !== 'sending') return;
      await this.delta({ kind: 'message_delta', message_id: delivery.messageId, delta_text: frame.chunk!.text,
        idempotency_key: `${frame.attemptId}:${frame.index}` });
    }).catch(this.options.onError);
  }
  async stop(): Promise<void> { this.unsubscribe(); await Promise.allSettled([...this.draining.values(), ...[...this.streams.values()].map(stream => stream.chain)]); }
}
interface Approval { requestId: string; sessionId: string; toolName: string; callId?: string; reason?: string }
interface Stream { sessionId: string; frame: { type: string; attemptId: string; turn?: number; index?: number; chunk?: { type: string; text?: string } } }
function runtimeBinding(binding: SessionBinding) {
  const { conversationId: _conversation, ...runtime } = binding;
  return runtime;
}
