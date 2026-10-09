import { randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimeEvent, RuntimePort, SessionBinding, ModelRunProjection } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import { RelayDeliveryError } from '@nano/channels';
import { needsAttention } from './attention.js';
import { SessionControls, sessionControl } from './session-controls.js';
import { NodeStore } from './store.js';
import { argumentsObject, tokenUsage, toolPresentation, logicalEvents } from './presentation.js';

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
  private readonly modelRuns = new Map<string, ModelRunProjection[]>();
  private readonly controls: SessionControls;
  private readonly draining = new Map<string, Promise<void>>();
  private readonly dirty = new Set<string>();
  private readonly pendingApprovals = new Map<string, { sessionId: string; messageId: string; posted: boolean; decision?: string; outcome?: string }>();
  private readonly unsubscribe: () => void;
  private readonly streams = new Map<string, { sessionId: string; turn: number; chain: Promise<unknown> }>();
  constructor(private readonly options: Options) {
    this.controls = new SessionControls(options);
    this.unsubscribe = options.runtime.onNotification((method, value) => {
      const data = value as { sessionId: string; event?: RuntimeEvent };
      const binding = options.store.bindings().find(binding => binding.sessionId === data.sessionId);
      if (!binding || options.agents.find(agent => agent.agentId === binding.agentId)?.mode !== 'single_thread') return;
      if ((method === 'session.event' && data.event) || method === 'model.changed') this.reconcile(data.sessionId).catch(options.onError);
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
    const control = sessionControl(input, config);
    const unaddressedControl = /^\/(compact|effort|workflows|config)(?:\s|$)/.test(input.message.content.trim()) && !control;
    if ((unaddressedControl || !needsAttention(input, config)) && !['/stop', '/new'].includes(input.message.content.trim())) {
      store.bufferGroup(input);
      await this.options.relay.request('node.delivery_receipt', { node_id: this.options.nodeId, relay_task_id: input.relay_task_id, delivery_status: 'sent' });
      return;
    }
    const ownerDirect = input.metadata.conversation_type === 'direct' && input.message.sender_type === 'user' && (input.message.sender_user_id === this.options.ownerId || input.metadata.owner_user_id === this.options.ownerId);
    const canonical = ownerDirect ? store.canonical(config.agentId) : undefined;
    const binding = store.bindingFor(config.agentId, input.conversation_id)
      ?? (canonical?.conversationId.startsWith('owner:') ? store.adoptConversation(canonical, input.conversation_id) : undefined) ?? store.bind({
      sessionId: randomUUID(), conversationId: input.conversation_id, agentId: config.agentId,
      ownerId: this.options.ownerId, cwd: config.workspace, revision: config.revision,
    });
    if (ownerDirect) store.markCanonical(binding);
    if (input.message.sender_type === 'user' && ['/stop', '/new'].includes(input.message.content.trim())) {
      const commandId = `${input.agent_id}:${input.message.id}`;
      let text = store.command(commandId);
      if (!text) {
        await runtime.request('session.ensure', runtimeBinding(binding));
        const result = await runtime.request('session.cancel', { sessionId: binding.sessionId }) as { wasRunning: boolean };
        await this.reconcile(binding.sessionId);
        if (input.message.content.trim() === '/new') {
          store.reset(binding, { ...binding, sessionId: randomUUID(), revision: config.revision }, commandId);
          text = store.command(commandId)!;
        } else {
          text = result.wasRunning ? '已停止当前操作。' : '当前没有正在执行的操作。';
          store.saveCommand(commandId, text);
        }
      }
      const ack = await this.delta({ kind: 'turn_start', conversation_id: binding.conversationId, agent_id: binding.agentId,
        idempotency_key: `command:${input.message.id}`, external_reply: input.metadata.external_reply });
      await this.delta({ kind: 'message_completed', message_id: ack.payload.message_id,
        final_content: text, delivery_status: 'completed' });
      await this.options.relay.request('node.delivery_receipt', { node_id: this.options.nodeId, relay_task_id: input.relay_task_id, delivery_status: 'completed' });
      return;
    }
    if (control) { await this.controls.run(binding, input, control.action, control.argument); return; }
    await this.controls.wait(binding.sessionId);
    store.takeGroup(binding);
    store.receive(binding.sessionId, input);
    await runtime.request('session.ensure', runtimeBinding(binding));
    for (const pending of store.inputs(binding.sessionId)) if (!pending.accepted) await this.submit(binding, pending.input);
    await this.reconcile(binding.sessionId);
  }

  async background(sessionId: string, input: RelayInput): Promise<void> {
    const binding=this.binding(sessionId);
    if(binding.agentId!==input.agent_id||binding.conversationId!==input.conversation_id)throw new Error('Background result belongs to another conversation');
    this.options.store.receive(sessionId,input);await this.options.runtime.request('session.ensure',runtimeBinding(binding));
    await this.submit(binding,input);await this.reconcile(sessionId);
  }

  private async submit(binding: SessionBinding, input: RelayInput) {
    const { store, runtime } = this.options;
    const inputId = `${input.agent_id}:${input.message.id}`;
    const evidence = await runtime.request('session.lookup', { sessionId: binding.sessionId, inputId }) as InputEvidence;
    if (!evidence.accepted) {
      const text = input.metadata.conversation_type === 'group' ? `[${input.metadata.sender_display_name ?? input.message.sender_user_id}] ${input.message.content}` : input.message.content;
      const ordered = input.metadata.content_parts as { type: string; text?: string; url?: string }[] | undefined;
      const parts: { type: string; text?: string; url?: string }[] = ordered ?? [{ type: 'text', text }, ...input.message.attachments.map(attachment => ({ type: 'image', url: attachment.url }))];
      const content: Record<string, unknown>[] = [];
      if (ordered && input.metadata.conversation_type === 'group') content.push({ type: 'text', text: `[${input.metadata.sender_display_name ?? input.message.sender_user_id}] ` });
      for (const part of parts) {
        if (part.type === 'text') { content.push({ type: 'text', text: part.text ?? '' }); continue; }
        const attachment = input.message.attachments.find(attachment => attachment.url === part.url);
        if (!attachment?.content_type.startsWith('image/')) throw new Error('This input attachment is not an image');
        content.push({ type: 'image', mediaType: attachment.content_type, name: attachment.file_name, data: await this.options.image(attachment.url, binding.agentId) });
      }
      await runtime.request('session.submit', { sessionId: binding.sessionId, inputId, mode: input.metadata.context_only ? 'inject' : 'followup', content,
        source: { kind: input.message.sender_type === 'user' ? 'human' : 'system', actorId: input.message.sender_user_id, channel: input.metadata.channel ?? 'web_relay', messageId: input.message.id },
      });
    }
    store.accepted(inputId);
    if (!store.inputs(binding.sessionId).find(item => item.id === inputId)?.terminal) await this.receipt(input, 'sent');
  }

  /** A first proactive turn reserves the future owner chat without creating a visible bubble. */
  async heartbeatBinding(config: AgentConfiguration): Promise<SessionBinding> {
    const { store, runtime } = this.options;
    const binding = store.canonical(config.agentId) ?? store.bind({ sessionId: randomUUID(), agentId: config.agentId,
      conversationId: `owner:${this.options.ownerId}`, ownerId: this.options.ownerId, cwd: config.workspace, revision: config.revision });
    store.markCanonical(binding);
    await runtime.request('session.ensure', runtimeBinding(binding));
    return binding;
  }

  /** Durable history is replayed on reconnect; display notifications are just hints. */
  async recover(externalOnly = false): Promise<void> {
    for (const binding of this.options.store.bindings()) {
      if (externalOnly && !binding.conversationId.startsWith('external:')) continue;
      if (this.options.agents.find(agent => agent.agentId === binding.agentId)?.mode !== 'single_thread') continue;
      await this.options.runtime.request('session.ensure', runtimeBinding(binding));
      await this.controls.recover(binding.agentId);
      for (const input of this.options.store.inputs(binding.sessionId)) if (!input.accepted) await this.submit(binding, input.input);
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
    await this.options.runtime.request('approval.answer', { requestId, decision, ...(typeof payload.reason === 'string' ? { reason: payload.reason } : {}) });
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
    const read = await runtime.request('session.observe', { sessionId, afterSeq: store.cursor(sessionId) }) as { events: RuntimeEvent[]; durable: boolean; modelRuns?: ModelRunProjection[] };
    if (!read.durable) throw new Error('Runtime observation lacks a durable barrier');
    store.recordEvents(sessionId, read.events);
    this.modelRuns.set(sessionId, read.modelRuns ?? []);
    for (const input of store.inputs(sessionId)) {
      const evidence = await runtime.request('session.lookup', { sessionId, inputId: input.id }) as InputEvidence;
      store.inputEvidence(input.id, evidence);
    }
    const events = logicalEvents(store.events(sessionId), read.modelRuns ?? []);
    for (const input of store.inputs(sessionId)) {
      if (input.turn === null) continue;
      const turn = input.turn;
      const run = read.modelRuns?.find(run => run.turn === turn);
      if (run) await this.modelNotices(binding, input.input, run);
      let delivery = store.prepareDelivery(sessionId, turn);
      if (delivery.state === 'unknown') { await this.receipt(input.input, 'failed'); continue; }
      if (delivery.state === 'confirmed' || delivery.state === 'failed' || delivery.state === 'withheld') {
        await this.receipt(input.input, delivery.state === 'failed' ? 'failed' : 'completed');
        continue;
      }
      const end = events.find(event => event.type === 'turn/end' && event.data.turn === turn);
      if (run && run.state !== 'completed' && (run.state === 'switching' || run.attempts.length > 1)) continue;
      if (run?.state === 'completed' && (run.terminal as { kind: string })?.kind !== 'completed' && !delivery.messageId && run.attempts.some(attempt => attempt.error)) {
        store.updateDelivery(delivery.operationId, 'failed', null, ''); await this.receipt(input.input, 'failed'); continue;
      }
      const group = store.inputs(sessionId).some(item => item.turn === turn && item.input.metadata.conversation_type === 'group');
      const heartbeatOnly = store.inputs(sessionId).filter(item => item.turn === turn).every(item => item.input.metadata.origin === 'heartbeat');
      if (heartbeatOnly || group) {
        if (!end && heartbeatOnly) continue;
        const last = events.filter(event => event.type === 'assistant/message' && event.data.turn === turn).at(-1)?.data.message as { content: { type: string; text?: string }[] } | undefined;
        const text = last?.content.filter(part => part.type === 'text').map(part => part.text ?? '').join('').trim();
        if (end && ((heartbeatOnly && !text) || text === 'HEARTBEAT_OK' || text === 'NO_REPLY')) {
          if (delivery.messageId) await this.delta({ kind: 'message_discarded', message_id: delivery.messageId, reason: 'silent_reply' });
          store.updateDelivery(delivery.operationId, 'confirmed', null, ''); await this.receipt(input.input, 'completed'); continue;
        }
      }
      if (!delivery.messageId) {
        store.updateDelivery(delivery.operationId, 'sending', null, delivery.content);
        // IM's caller_idempotency_key makes a lost creation ACK recover the same bubble.
        const ack = await this.delta({ kind: 'turn_start', ...(binding.conversationId.startsWith('owner:') ? { to_user_id: binding.ownerId } : { conversation_id: binding.conversationId }),
          agent_id: binding.agentId, idempotency_key: store.command(`model-placeholder:${run?.id}`) ? `${delivery.operationId}:fallback` : delivery.operationId,
          background_returns: input.input.metadata.background_returns,
          external_reply: store.inputs(sessionId).find(item => item.turn === turn && !item.input.metadata.context_only)?.input.metadata.external_reply });
        const messageId = ack.payload.message_id;
        if (typeof messageId !== 'string') throw new Error('IM did not acknowledge the output message identity');
        if (binding.conversationId.startsWith('owner:') && typeof ack.payload.conversation_id === 'string') Object.assign(binding, store.adoptConversation(binding, ack.payload.conversation_id));
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
      if (!end) continue;
      // Closing waits for the stream queue without awaiting our own reconcile task.
      if ([...this.streams.values()].some(stream => stream.sessionId === sessionId && (read.modelRuns?.find(run => run.attempts.some(attempt => attempt.turn === stream.turn))?.turn ?? stream.turn) === turn)) continue;
      const answers = events.filter(event => event.type === 'assistant/message' && event.data.turn === turn);
      const final = answers.at(-1);
      const message = final?.data.message as { id: string; content: { type: string; text?: string }[] } | undefined;
      const publication = this.publication(sessionId, turn);
      const text = message?.content.filter(block => block.type === 'text').map(block => block.text ?? '').join('') || publication?.confirmed || '';
      const reason = end.data.reason as { kind: string };
      const completed = reason.kind === 'completed';
      if (!completed && !text && !publication && run?.attempts.some(attempt => attempt.error) && !events.some(event => event.type === 'tool/call' && event.data.turn === turn)) {
        await this.delta({ kind: 'message_discarded', message_id: delivery.messageId, reason: 'model_failure_notice' });
        store.updateDelivery(delivery.operationId, 'failed', null, ''); await this.receipt(input.input, 'failed'); continue;
      }
      const inputs = store.inputs(sessionId);
      const position = inputs.findLastIndex(item => item.turn === turn);
      const correction = group && !binding.conversationId.startsWith('external:') && inputs.slice(position + 1).some(item => !item.input.metadata.context_only);
      if (completed && correction && text && delivery.state !== 'completing') {
        const identity = `revalidation:${delivery.operationId}`;
        await runtime.request('session.submit', { sessionId, inputId: identity, mode: 'inject', content: [{ type: 'text', text: 'Your previous draft has NOT been sent because newer messages were accepted in this group. Consider the newer messages before publishing the revised answer.' }], source: { kind: 'system', actorId: binding.agentId, channel: 'revalidation', messageId: identity } });
        await this.delta({ kind: 'reply_process', message_id: delivery.messageId, item: { item_id: identity, kind: 'draft', run_id: delivery.operationId, draft_id: identity, text, source: 'assistant' } });
        await this.delta({ kind: 'message_completed', message_id: delivery.messageId, final_content: '', delivery_status: 'completed' });
        store.updateDelivery(delivery.operationId, 'withheld', delivery.messageId, text); await this.receipt(input.input, 'completed'); continue;
      }
      store.updateDelivery(delivery.operationId, 'completing', delivery.messageId, text);
      try { await this.delta({ kind: 'message_completed', message_id: delivery.messageId,
        final_content: publication?.pending && !message?.content.some(block => block.type === 'text' && block.text) ? undefined : text, delivery_status: completed ? 'completed' : 'failed',
        kernel_message_id: message?.id, idempotency_key: `${delivery.operationId}:complete`,
        token_usage: tokenUsage(events, turn),
        elapsed_ms: end.time - (events.find(event => event.type === 'turn/start' && event.data.turn === turn)?.time ?? end.time),
        resolved_model: events.filter(event => event.type === 'request/context' && event.seq <= end.seq).at(-1)?.data.model,
      }); } catch (error) {
        // The external adapter has already persisted and projected its uncertain platform result.
        if (delivery.messageId?.startsWith('external:') && error instanceof RelayDeliveryError && error.delivery === 'unknown') store.updateDelivery(delivery.operationId, 'unknown', delivery.messageId, text);
        throw error;
      }
      store.updateDelivery(delivery.operationId, completed ? 'confirmed' : 'failed', delivery.messageId, text);
      await this.receipt(input.input, completed ? 'completed' : 'failed');
    }
  }

  private publication(sessionId: string, turn: number): { confirmed: string; pending?: string } | undefined {
    const record = this.options.store.command(`published:${sessionId}:${turn}`);
    return record ? JSON.parse(record) as { confirmed: string; pending?: string } : undefined;
  }
  /** Drain in-flight publication before the runtime chooses another model. */
  async modelCheck(request: { sessionId: string; turn: number }): Promise<{ published: boolean }> {
    await Promise.all([...this.streams.values()].filter(stream => stream.sessionId === request.sessionId).map(stream => stream.chain));
    await this.reconcile(request.sessionId);
    // A lost publication acknowledgement is also ineligible for replay.
    return { published: !!this.options.store.command(`published:${request.sessionId}:${request.turn}`) };
  }
  private async modelNotices(binding: SessionBinding, input: RelayInput, run: ModelRunProjection) {
    const notices = run.attempts.flatMap(attempt => attempt.error ? [{ id: `${run.id}:failure:${attempt.turn}`, text: `${attempt.route.model} 暂时无法完成回复：${attempt.error.message}`, failed: true }] : []);
    if (run.switched && run.state === 'completed') notices.push({ id: `${run.id}:switched`, text: `已改用 ${run.switched}，因为主模型不可用。`, failed: false });
    const first = notices[0];
    const placeholder = this.options.store.delivery(binding.sessionId, run.turn);
    const withdrawn = `model-placeholder:${run.id}`;
    if (first?.failed && placeholder?.messageId && placeholder.state === 'sending' && !this.options.store.command(withdrawn)
      && !this.options.store.command(`published:${binding.sessionId}:${run.turn}`)
      && !this.options.store.events(binding.sessionId).some(event => event.type === 'tool/call' && run.attempts.some(attempt => attempt.turn === event.data.turn))) {
      await this.delta({ kind: 'message_completed', message_id: placeholder.messageId, final_content: first.text, delivery_status: 'failed' });
      this.options.store.advanceFallbackDelivery(placeholder.operationId, first.id, withdrawn);
    }
    for (const notice of notices) {
      if (this.options.store.command(notice.id)) continue;
      const start = await this.delta({ kind: 'turn_start', conversation_id: input.conversation_id, agent_id: binding.agentId,
        idempotency_key: notice.id, external_reply: input.metadata.external_reply });
      await this.delta({ kind: 'message_completed', message_id: start.payload.message_id, final_content: notice.text, delivery_status: notice.failed ? 'failed' : 'completed' });
      this.options.store.saveCommand(notice.id, 'delivered');
    }
  }
  private async approval(request: Approval) {
    const pending: { sessionId: string; messageId: string; posted: boolean; decision?: string; outcome?: string } = {
      sessionId: request.sessionId, messageId: '', posted: false,
    };
    this.pendingApprovals.set(request.requestId, pending);
    await this.reconcile(request.sessionId);
    if (pending.outcome) { this.pendingApprovals.delete(request.requestId); return; }
    const input = this.options.store.inputs(request.sessionId).find(input => request.inputIds?.includes(input.id) || !request.childSessionId && input.turn !== null && input.terminal === null);
    const delivery = input?.turn === undefined || input.turn === null ? undefined : this.options.store.delivery(request.sessionId, input.turn);
    if (!delivery?.messageId) throw new Error('Approval has no product output binding');
    pending.messageId = delivery.messageId;
    const call = this.options.store.events(request.sessionId).find(event => event.type === 'tool/call' && event.data.callId === request.callId);
    await this.delta({ kind: 'permission_request', message_id: delivery.messageId, session_id: request.sessionId,
      agent_id: this.binding(request.sessionId).agentId, run_id: request.sessionId,
      permission_request: { request_id: request.requestId, tool_name: request.toolName, reason: request.reason, call_id: request.callId,
        tool_input: argumentsObject(request.toolInput?.arguments ?? call?.data.arguments ?? '{}'), question: request.reason ?? 'Allow this action?', status: 'pending',
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
    const inputId = String(input.metadata.runtime_input_id ?? `${input.agent_id}:${input.message.id}`);
    if (this.options.store.receipt(inputId) === status) return;
    if (!input.metadata.runtime_input_id) await this.options.relay.request('node.delivery_receipt', { node_id: this.options.nodeId, relay_task_id: input.relay_task_id, delivery_status: status });
    // /stop has no model input, so it has no input receipt row.
    if (input.message.content.trim() !== '/stop') this.options.store.confirmReceipt(inputId, status);
  }
  private stream({ sessionId, frame }: Stream) {
    if (this.options.store.inputs(sessionId).some(input => input.input.metadata.conversation_type === 'group')) return;
    if (frame.type === 'start') {
      this.streams.set(frame.attemptId, { sessionId, turn: frame.turn!, chain: this.reconcile(sessionId) });
      return;
    }
    const stream = this.streams.get(frame.attemptId);
    if (!stream) return;
    if (frame.type === 'end') { void stream.chain.finally(() => { this.streams.delete(frame.attemptId); void this.reconcile(sessionId).catch(this.options.onError); }); return; }
    if (frame.chunk?.type !== 'text-delta') return;
    stream.chain = stream.chain.then(async () => {
      const turn = this.modelRuns.get(sessionId)?.find(run => run.attempts.some(attempt => attempt.turn === stream.turn))?.turn ?? stream.turn;
      const delivery = this.options.store.delivery(sessionId, turn);
      if (!delivery?.messageId || delivery.state !== 'sending') return;
      if ((this.modelRuns.get(sessionId)?.find(run => run.turn === turn)?.attempts.length ?? 0) > 1) return;
      if (!frame.chunk!.text) return;
      const published = this.publication(sessionId, turn) ?? { confirmed: '' };
      this.options.store.saveCommand(`published:${sessionId}:${turn}`, JSON.stringify({ ...published, pending: frame.chunk!.text }));
      await this.delta({ kind: 'message_delta', message_id: delivery.messageId, delta_text: frame.chunk!.text,
        idempotency_key: `${frame.attemptId}:${frame.index}` });
      this.options.store.saveCommand(`published:${sessionId}:${turn}`, JSON.stringify({ confirmed: published.confirmed + frame.chunk!.text }));
    }).catch(this.options.onError);
  }
  async stop(): Promise<void> { this.unsubscribe(); await this.controls.stop(); await Promise.allSettled([...this.draining.values(), ...[...this.streams.values()].map(stream => stream.chain)]); }
}
interface Approval { childSessionId?:string;inputIds?:string[];toolInput?:{arguments?:unknown}; requestId: string; sessionId: string; toolName: string; callId?: string; reason?: string }
interface Stream { sessionId: string; frame: { type: string; attemptId: string; turn?: number; index?: number; chunk?: { type: string; text?: string } } }
function runtimeBinding(binding: SessionBinding) {
  const { conversationId: _conversation, ...runtime } = binding;
  return runtime;
}
