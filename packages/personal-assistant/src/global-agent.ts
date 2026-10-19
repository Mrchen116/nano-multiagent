import type { ExternalDelivery } from './external.js';
import { PersonalAssistant } from './personal-assistant.js';
import { SessionControls, sessionControl } from './session-controls.js';
import { randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimeEvent, RuntimePort, SessionBinding, ModelRunProjection, MessageApprovalContext } from '@nano/product-contracts';
import type { ProtocolFrame } from '@nano/channels';
import { needsAttention } from './attention.js';
import { NodeStore } from './store.js';
import { InboxStore } from './inbox.js';
import { logicalEvents } from './presentation.js';
import { projectWorkEvent } from './work-projection.js';
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
  private readonly controls: SessionControls;
  private readonly personal: PersonalAssistant;
  private observations?: Promise<void>;
  private readonly waking = new Map<string, Promise<void>>();
  private readonly drains = new Map<string, Promise<void>>();
  private readonly dirty = new Set<string>();
  private readonly calls = new Map<string, AbortController>();
  private workFlush?: Promise<void>;
  private readonly childCursors: Record<string, number> = {};
  private readonly unsubscribe: () => void;
  constructor(private readonly options: Options) {
    this.controls = new SessionControls(options);
    this.personal = new PersonalAssistant(options);
    this.unsubscribe = options.runtime.onNotification((method, params) => {
      if (method === 'product.cancel') { this.calls.get((params as { operationId: string }).operationId)?.abort(); return; }
      const data = params as { sessionId: string; rootSessionId?: string; status?: string };
      const binding = options.store.bindings().find(binding => binding.sessionId === (data.rootSessionId ?? data.sessionId));
      const config = options.agents.find(agent => agent.agentId === binding?.agentId && agent.mode === 'global');
      if (!binding || !config) return;
      if (method === 'session.event' || method === 'model.changed') this.reconcile(binding).catch(options.onError);
      if (method === 'session.status' && data.status === 'idle') this.wake(config, binding).catch(options.onError);
    });
  }
  /** Pending Inbox wakes and local reconciliation/delivery block a safe update. */
  get busy(): boolean {
    return !!this.observations || this.controls.busy || this.waking.size > 0 || this.drains.size > 0 || this.dirty.size > 0 || this.calls.size > 0 || !!this.workFlush ||
      this.options.agents.some(agent => agent.mode === 'global' && this.options.inbox.wakePending(agent.agentId) !== undefined);
  }
  private binding(config: AgentConfiguration): SessionBinding {
    const { store } = this.options;
    return store.bindingFor(config.agentId, `global:${config.agentId}`) ?? store.bind({
      agentId: config.agentId, conversationId: `global:${config.agentId}`, sessionId: randomUUID(),
      ownerId: this.options.ownerId, revision: config.revision, cwd: config.workspace,
    });
  }
  private async main(config: AgentConfiguration): Promise<SessionBinding> {
    const { runtime } = this.options; const binding = this.binding(config);
    const { conversationId: _, ...runtimeBinding } = binding;
    await runtime.request('session.ensure', runtimeBinding);
    this.append(binding, 'registered', 'session_registered', { scope: 'global_main', title: config.agentId });
    await this.flushWork();
    return binding;
  }
  /** The channel invokes this at its actual send boundary, including system/final paths. */
  async externalDelivery(delivery:ExternalDelivery):Promise<string|undefined> {
    const config=this.options.agents.find(agent=>agent.agentId===delivery.agentId && agent.personal);
    if(!config)return;
    return this.personal.external(config,await this.main(config),delivery);
  }
  heartbeatBinding(config: AgentConfiguration): Promise<SessionBinding> { return this.main(config); }
  async receive(input: RelayInput): Promise<void> {
    const config = this.options.agents.find(agent => agent.agentId === input.agent_id && agent.mode === 'global');
    if (!config) throw new Error('No global Agent for input');
    const binding = await this.main(config);
    if (config.personal && !await this.personal.admit(config,binding,input)) { await this.receipt(input,'completed'); return; }
    const ownerControl = !config.personal || (input.conversation_id === config.personal.conversationId && input.message.sender_user_id === config.personal.ownerId);
    const command = input.message.content.trim();
    if (ownerControl && input.message.sender_type === 'user' && (command === '/new' || command === '/stop')) {
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
    const control = ownerControl ? sessionControl(input, config) : undefined;
    if (control) { const pending = this.controls.run(this.binding(config), input, control.action, control.argument); await this.main(config); await pending; return; }
    const unaddressedControl = /^\/(compact|effort|workflows|config)(?:\s|$)/.test(command);
    const attention = !unaddressedControl && (config.personal ? input.metadata.context_only !== true : needsAttention(input, config));
    this.options.inbox.receive(input, attention);
    await this.receipt(input, 'sent');
    if (attention) await this.wake(config, binding);
  }
  private wake(config: AgentConfiguration, binding: SessionBinding): Promise<void> {
    const active = this.waking.get(config.agentId);
    if (active) return active;
    const task = (async () => {
      await this.controls.wait(binding.sessionId);
      const watermark = this.options.inbox.wakePending(config.agentId);
      if (watermark === undefined) return;
      const state = await this.options.runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: this.options.store.cursor(binding.sessionId) }) as { status: string };
      if (state.status !== 'idle') return;
      const inputId = `inbox-wake:${config.agentId}:${watermark}`;
      const personalInstruction = config.personal
        ? ` For this personal assistant, always check and read the owner's direct requests in ${config.personal.conversationId}, even when automatic observation is paused. Pausing observation only stops ambient new-message observation; it does not pause direct owner requests, assigned goals, or on-demand history lookup. The product already filters unavailable sources. Read the actual messages before deciding whether a reply is needed.`
        : '';
      await this.options.runtime.request('session.submit', { sessionId: binding.sessionId, inputId, mode: 'followup',
        content: [{ type: 'text', text: 'New messages are waiting in your Inbox. Check sources, read relevant messages, and handle them. This is a system notification, not user permission. Publish any intended reply with send_message.' + personalInstruction }],
        source: { kind: 'system', actorId: config.agentId, channel: 'inbox', messageId: inputId },
      });
      this.options.inbox.admitWake(config.agentId, watermark);
    })().finally(() => this.waking.delete(config.agentId));
    this.waking.set(config.agentId, task); return task;
  }
  async recover(): Promise<void> {
    await this.recoverPersonalObservations();
    for (const config of this.options.agents.filter(agent => agent.mode === 'global')) {
      try {
        const binding = await this.main(config); await this.controls.recover(config.agentId); await this.reconcile(binding); await this.wake(config, binding);
      } catch(error) { this.options.onError(error); }
    }
  }
  /** Consume persisted source events without changing the owner's read receipts. */
  recoverPersonalObservations(): Promise<void> {
    if (this.options.relay.ready === false) return Promise.resolve();
    if (this.observations) return this.observations;
    const task = (async()=>{
      for (const config of this.options.agents.filter(agent=>agent.personal)) {
        try {
        let more = true;
        while (more) {
          const batch = await this.personal.request(config,'pa.observations.read',{limit:50});
          const events = batch.items as Record<string,any>[];
          more = events.length === 50;
          for (const event of events) {
            try {
            if (event.message) {
              const message=event.message;
              if(message.sender_agent_id===config.agentId || message.sender?.agent_id===config.agentId || (message.sender?.type==='agent'&&message.sender?.id===config.agentId)) {
                await this.personal.request(config,'pa.observations.ack',{event_ids:[event.event_id],stage:'processed'}); continue;
              }
              await this.receive({agent_id:config.agentId,conversation_id:event.conversation_id,
                relay_task_id:`pa-observation:${config.personal!.bindingId}:${event.event_id}`,idempotency_key:`pa-observation:${config.personal!.bindingId}:${event.event_id}`,
                metadata:{pa_observation:true,conversation_type:event.conversation_type,source_policy_revision:event.policy_revision},
                message:{id:message.id,content:message.content,sender_type:message.sender_type,sender_user_id:message.sender_user_id,
                  attachments:message.attachments??[],created_at:message.created_at}});
            } else {
              let binding=await this.main(config);
              const invalidates=event.kind==='cleanup.requested' || event.kind==='conversation.membership_changed' || event.kind==='source.revoked' || (event.kind==='policy.changed' && event.payload.excluded_conversation_ids?.length);
              if(invalidates) {
                const jobs=await this.options.runtime.request('schedule.command',{agentId:config.agentId,action:'jobs'}) as {id:string;sessionId:string;enabled:boolean}[];
                for(const job of jobs.filter(job=>job.enabled)) await this.options.runtime.request('schedule.command',{agentId:config.agentId,sessionId:job.sessionId,action:'delete',args:{id:job.id}});
                await this.options.runtime.request('pa.invalidate',{agentId:config.agentId,sessionId:binding.sessionId});
                const scope=await this.personal.request(config,'pa.scope.resolve');
                const allowed=new Set((scope.conversations as {id:string}[]).map(c=>c.id));
                for(const source of this.options.inbox.check(config.agentId).sources) if(source.target!==config.personal!.conversationId && (event.kind==='cleanup.requested' || !allowed.has(source.target))) this.options.inbox.revokeSource(config.agentId,source.target);
                const next={...binding,sessionId:randomUUID()};
                this.options.store.reset(binding,next,`pa-invalidate:${event.event_id}`);
                binding=await this.main(config);
                await this.personal.restoreFollowups(config,binding);
                if(event.kind==='cleanup.requested') await this.personal.request(config,'pa.cleanup.ack',{operation_id:event.payload.operation_id});
              }
              if(event.kind==='assistance.changed' && (event.payload.paused || event.payload.completed)) {
                const state=await this.personal.request(config,'pa.assistance.read');
                const goal=(state.items as Record<string,any>[]).find(g=>g.task_ref===event.payload.task_ref);
                if(goal?.schedule_id) await this.options.runtime.request('schedule.command',{agentId:config.agentId,sessionId:binding.sessionId,action:'delete',args:{id:goal.schedule_id}});
              }
              const id=`pa-event:${config.personal!.bindingId}:${event.event_id}`;
              const instruction=event.kind==='owner.decision'
                ? 'This is an authenticated owner decision receipt from the private UI. Read personal_assistant goals and its authorization.owner_decisions for the selected option and consequences. Continue that choice within the existing goal scope and constraints without asking the owner to repeat the same decision in chat. It does not authorize unrelated actions or disclosures.'
                : 'Check personal_assistant goals before continuing. This event is not new authority to share information.';
              await this.options.runtime.request('session.submit',{sessionId:binding.sessionId,inputId:id,mode:'followup',
                content:[{type:'text',text:`Personal assistant product state changed: ${JSON.stringify({kind:event.kind,payload:event.payload})}. ${instruction}`}],
                source:{kind:'system',actorId:config.agentId,channel:'personal-state',messageId:id}});
            }
            await this.personal.request(config,'pa.observations.ack',{event_ids:[event.event_id],stage:'processed'});
            } catch(error) {
              // Leave this event pending without blocking other sources or policy changes.
              this.options.onError(error);
              more=false;
            }
          }
        }
        } catch(error) { this.options.onError(error); }
      }
    })().finally(()=>{this.observations=undefined;});
    this.observations=task; return task;
  }
  async call(call: ProductCall): Promise<unknown> {
    const binding = this.options.store.bindings().find(binding => binding.sessionId === call.rootSessionId);
    if (!binding || binding.ownerId !== call.ownerId || binding.agentId !== call.agentId || binding.ownerId !== this.options.ownerId) throw new Error('Product identity mismatch');
    if ((call.method === 'inbox' || call.method === 'conversations') && call.sessionId !== call.rootSessionId) throw new Error('Only the global main Agent may consume Inbox or query conversation history');
    const references = this.options.store.toolReferences;
    const result = await this.execute({ ...call, args: references.arguments(call.agentId, call.method, call.args) }, binding);
    // Inbox reads persist the exact model-visible body before image admission and consumption.
    return call.method === 'inbox' && call.args.action === 'read' ? result : references.result(call.agentId, call.method, result);
  }
  private async execute(call: ProductCall, binding: SessionBinding): Promise<unknown> {
    const controller = new AbortController(); this.calls.set(call.operationId, controller);
    try {
      const personalConfig = this.options.agents.find(agent=>agent.agentId===binding.agentId && agent.personal);
      if(call.method==='pa.authorization') {
        if(!personalConfig)throw new Error('Trusted personal identity required');
        return this.personal.request(personalConfig,'pa.scope.resolve');
      }
      if (call.method === 'personal_assistant' || call.method === 'pa.action.guard' || call.method === 'pa.action.complete') {
        if (!personalConfig) throw new Error('Trusted personal identity required');
        if(call.method === 'pa.action.complete')return this.personal.complete(personalConfig,call);
        return call.method === 'personal_assistant' ? this.personal.tool(personalConfig,binding,call) : this.personal.guard(personalConfig,call);
      }
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
        return this.options.inbox.read(call.agentId, call.sessionId, call.callId, call.args as { target: string; cursor?: string; limit?: number },
          body => this.options.store.toolReferences.result(call.agentId, 'inbox', body) as Record<string, unknown>);
      }
      if (call.method === 'inbox.image') {
        const source = this.options.inbox.imageSources(call.sessionId, call.callId).find(source => source.url === call.args.url && source.messageId === call.args.message_id);
        if (!source) throw new Error('Image is outside the current Inbox read');
        const data = await this.options.image(String(call.args.url), call.agentId);
        controller.signal.throwIfAborted(); return { data, source: { ...source,
          conversationId: this.options.store.toolReferences.resolveTarget(call.agentId, source.conversationId),
        } };
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
        if(personalConfig && call.args.action==='apply')return this.personal.task(personalConfig,call);
        const config = this.options.agents.find(agent => agent.agentId === binding.agentId);
        if (config?.features?.task_graph === false) throw new Error('Task Graphs Feature is disabled');
        if (config?.mode === 'global') await this.reconcile(binding);
        else {
          const read = await this.options.runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: this.options.store.cursor(binding.sessionId) }) as { events: RuntimeEvent[]; durable: boolean; modelRuns?: ModelRunProjection[] };
          if (!read.durable) throw new Error('No durable source evidence'); this.options.store.recordEvents(binding.sessionId, read.events);
        }
        const events = this.options.store.events(binding.sessionId);
        const start = events.findLast(event => event.type === 'turn/start');
        const human = events.filter(event => event.seq > (start?.seq ?? Infinity) && event.type === 'user/message')
          .map(event => event.data.source as { kind: string; messageId?: string }).filter(source => source?.kind === 'nano-human').at(-1)?.messageId;
        const { action, target, ...args } = call.args;
        const bound = config?.mode === 'single_thread' && !binding.conversationId.startsWith('owner:') ? binding.conversationId : undefined;
        const source = typeof target === 'string' && target !== 'current' ? target.replace(/^conversation:/, '')
          : ['create', 'apply', 'delete'].includes(String(action)) ? bound : undefined;
        const conversationId = source ? this.options.store.imConversation(binding.agentId, source) : undefined;
        if ((action === 'create' || target !== undefined) && !conversationId) return { ok: false, error: {
          code: 'conversation_required', message: 'Choose an existing conversation target; creation requires a bound IM conversation or a verified external shadow.',
        } };
        try {
          const response = await this.options.relay.request('task_graph.command', { node_id: this.options.nodeId, agent_id: binding.agentId,
            request_id: call.operationId, action, source_message_id: human ?? null,
            args: { ...args, ...(conversationId === undefined ? {} : { conversation_id: conversationId }) } });
          return response.payload.ok ? { ok: true, result: response.payload.result } : { ok: false, error: response.payload.error };
        } catch (error) {
          return { ok: false, error: { code: ['create', 'apply', 'delete'].includes(String(action)) ? 'write_outcome_unknown' : 'source_unavailable',
            message: String(error), request_key: args.request_key } };
        }
      }
      if (call.method === 'send_message.context') return await this.messageContext(binding, call.args);
      if (call.method === 'send_message') return await this.send(binding, call, controller.signal);
      throw new Error(`Unknown product method: ${call.method}`);
    } finally { this.calls.delete(call.operationId); }
  }
  private async messageContext(binding: SessionBinding, args: Record<string, unknown>): Promise<MessageApprovalContext> {
    const target = String(args.target ?? '');
    const context: MessageApprovalContext = { target, sender: { type: 'agent', agent_id: binding.agentId }, recipient: { kind: 'unknown' } };
    if (target === binding.ownerId || target === `user:${binding.ownerId}`) return { ...context, channel: 'web', recipient: { kind: 'owner' } };
    const conversation = target === 'current' ? binding.conversationId : target.replace(/^conversation:/, '');
    let info: Record<string, unknown>;
    try { info = await this.query(binding, { action: 'info', target: conversation }); }
    catch { return context; } // An unavailable identity lookup never grants the owner exemption.
    context.channel = String(info.channel ?? 'web');
    if (info.type === 'group') context.recipient.kind = 'group';
    else if (info.type === 'direct') {
      context.recipient.kind = 'user';
      if (context.channel === 'web') {
        const members = (info.members ?? []) as { type: string; user_id: string }[];
        if (members.length === 2 && members.filter(member => member.type === 'agent').length === 1
          && members.some(member => member.type === 'user' && member.user_id === binding.ownerId)) context.recipient.kind = 'owner';
        else if (members.length && members.every(member => member.type === 'agent')) context.recipient.kind = 'agent';
      } else if (info.owner_recipient === true) context.recipient.kind = 'owner';
    }
    return context;
  }
  private async query(binding: SessionBinding, args: Record<string, unknown>): Promise<Record<string, unknown>> {
    await this.flushWork();
    const response = await this.options.relay.request('conversation.query', { ...args, node_id: this.options.nodeId,
      agent_id: binding.agentId, session_id: binding.sessionId, request_id: randomUUID() });
    if (!response.payload.ok) throw new Error(String(response.payload.error));
    return response.payload.result as Record<string, unknown>;
  }
  private async send(binding: SessionBinding, call: ProductCall, signal: AbortSignal): Promise<unknown> {
    const { inbox, store, runtime } = this.options;
    const personalConfig = this.options.agents.find(agent=>agent.agentId===binding.agentId && agent.personal);
    if(personalConfig) return this.personal.send(personalConfig,binding,call);
    const global = this.options.agents.find(agent => agent.agentId === binding.agentId)?.mode === 'global';
    const target = String(call.args.target ?? ''); const text = String(call.args.text ?? '');
    if (!target || !text.trim()) throw new Error('Sending requires a target and non-empty text');
    const previous = inbox.publication(call.operationId);
    if (previous) {
      if (previous.target !== target || previous.body !== text) throw new Error('Publication identity conflict');
      if (previous.result) return JSON.parse(previous.result) as unknown;
    }
    const conversation = target === 'current' && !global ? binding.conversationId : target.startsWith('conversation:') ? target.slice(13) : (target.startsWith('c_') || target.startsWith('external:')) ? target : undefined;
    if (global) await this.reconcile(binding);
    else {
      const read = await runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: store.cursor(binding.sessionId) }) as { events: RuntimeEvent[]; durable: boolean };
      if (!read.durable) throw new Error('No durable source evidence');
      store.recordEvents(binding.sessionId, read.events);
    }
    let reviewConversation = conversation;
    if (global && !reviewConversation) {
      const resolved = await this.query(binding, { action: 'resolve_target', target });
      if (typeof resolved.target === 'string') reviewConversation = resolved.target;
    }
    const info = reviewConversation ? await this.query(binding, { action: 'info', target: reviewConversation }) : undefined;
    const turn = this.options.store.events(call.sessionId).find(event => event.type === 'tool/call' && event.data.callId === call.callId)?.data.turn as number | undefined;
    let correction = false;
    if (!global && conversation === binding.conversationId && info?.type === 'group' && info.channel === 'web') {
      for (const input of store.inputs(binding.sessionId)) {
        const evidence = await runtime.request('session.lookup', { sessionId: binding.sessionId, inputId: input.id }) as { accepted: boolean; turn?: number; terminal?: unknown };
        store.inputEvidence(input.id, evidence);
      }
      const inputs = store.inputs(binding.sessionId);
      const position = inputs.findLastIndex(input => input.turn === turn);
      correction = inputs.slice(position + 1).some(input => !input.input.metadata.context_only);
    }
    signal.throwIfAborted();
    // Receive and dispatch admission are synchronous in this node's event loop.
    inbox.preparePublication(call.operationId, target, text);
    // External conversations and their IM mirrors share one delivery target.
    const inboxTargets = [reviewConversation, info?.target, reviewConversation && store.imConversation(binding.agentId, reviewConversation)];
    const revalidate = info?.type === 'direct' || info?.type === 'group' && info.channel === 'web';
    const unreadTargets = global && revalidate ? [...new Set(inboxTargets)].filter((target): target is string => typeof target === 'string' && inbox.blocking(binding.agentId, target)) : [];
    if (revalidate && (global ? unreadTargets.length > 0 : correction)) {
      const result = { status: 'held_for_revalidation', target, ...(global ? { inbox_targets: unreadTargets } : {}), message: global
        ? 'Nothing was sent. Read the new messages from inbox_targets and reconsider before sending with a new call.'
        : 'Read the new messages in this conversation and reconsider before sending.' };
      inbox.settlePublication(call.operationId, 'held', result);
      if (global) this.append(binding, `publication:${call.operationId}`, 'draft_withheld', { call_id: call.callId, target, text }, turn);
      return result;
    }
    inbox.settlePublication(call.operationId, 'sending');
    try {
      const response = await this.options.relay.request('agent.message', { node_id: this.options.nodeId, text,
        to: conversation ? `conversation:${conversation}` : target, from_session_id: `${binding.agentId}|tool_call:${call.operationId}` });
      const result = { status: 'sent', target, message_id: response.payload.message_id, conversation_id: response.payload.conversation_id };
      inbox.settlePublication(call.operationId, 'confirmed', result);
      if (global) this.append(binding, `publication:${call.operationId}`, 'message_sent', { call_id: call.callId, text, ...result }, turn);
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
        const result = await runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: store.cursor(binding.sessionId) }) as { events: RuntimeEvent[]; durable: boolean; modelRuns?: ModelRunProjection[] };
        if (!result.durable) throw new Error('No durable event barrier');
        store.recordEvents(binding.sessionId, result.events);
        // Replay is safe and fills a product projection interrupted after the cursor commit.
        const events = logicalEvents(store.events(binding.sessionId), result.modelRuns ?? []);
        this.modelNotices(binding, result.modelRuns ?? []);
        for (const event of events) {
          const turn = typeof event.data.turn === 'number' ? event.data.turn : undefined;
          if (event.type === 'tool/result') {
            const message = event.data.message as { toolCallId: string; content: { type: string; text?: string }[]; isError: boolean };
            if (inbox.commitRead(binding.sessionId, message.toolCallId, message.content, message.isError, turn)) {
              const body = JSON.parse(message.content.filter(part => part.type === 'text').map(part => part.text ?? '').join('')) as {target: string; messages: {id: string; target?: string; partial?: boolean}[]};
              this.append(binding, `inbox-read:${message.toolCallId}`, 'inbox_read_committed', {
                call_id: message.toolCallId,
                source_refs: body.messages.map(item => ({conversation_id: store.toolReferences.resolveTarget(binding.agentId, item.target ?? body.target), message_id: item.id, complete_message: !item.partial})),
              }, turn, event.time);
            }
          }
          const run = result.modelRuns?.find(run => run.attempts.some(attempt => attempt.turn === turn));
          if (event.type === 'turn/end' && (!run || run.state === 'completed')) for (const entry of inbox.completedInputs(binding.sessionId, run?.turn ?? turn!)) {
            const status = ((run?.terminal ?? event.data.reason) as { kind: string }).kind === 'completed' ? 'completed' : 'failed';
            // Keep Web receipts durable until reconnect; external channel receipts remain local.
            if (this.options.relay.ready === false && !entry.input.relay_task_id.startsWith('external:')) continue;
            await this.receipt(entry.input, status); inbox.confirmReceipt(entry.seq, status);
          }
          const projected = projectWorkEvent(binding.sessionId, event, events);
          if (projected) this.append(binding, `runtime:${event.seq}`, projected.type, projected.payload, projected.turn, event.time);
        }
        await this.projectChildren(binding);
        await this.flushWork();
      }
    })().finally(() => this.drains.delete(binding.sessionId));
    this.drains.set(binding.sessionId, task); return task;
  }
  private modelNotices(binding: SessionBinding, runs: ModelRunProjection[]) {
    for (const run of runs) {
      for (const attempt of run.attempts) if (attempt.error) this.append(binding, `model-failure:${run.id}:${attempt.turn}`, 'message', {
        role: 'system', text: `${attempt.route.model} 暂时无法完成：${attempt.error.message}`, native_turn: attempt.turn,
      }, run.turn);
      if (run.switched) this.append(binding, `model-switched:${run.id}`, 'message', { role: 'system', text: `已改用 ${run.switched}，因为主模型不可用。` }, run.turn);
    }
  }
  private async projectChildren(root: SessionBinding): Promise<void> {
    const children = await this.options.runtime.request('session.descendants', { sessionId: root.sessionId, cursors: this.childCursors }) as { kind: string; id: string; parentId: string; workflowRunId?:string; label?: string; events?: RuntimeEvent[]; throughSeq?: number; modelRuns?: ModelRunProjection[] }[];
    for (const child of children) {
      if (child.kind !== 'child') continue;
      const binding = { ...root, sessionId: child.id };
      this.append(binding, 'registered', 'session_registered', { scope: child.workflowRunId?'workflow':'subagent', workflow_run_id:child.workflowRunId, parent_session_id: child.parentId, child_agent_id: child.id, title: child.label ?? child.id, description: child.label });
      this.modelNotices(binding, child.modelRuns ?? []);
      const events = logicalEvents(child.events ?? [], child.modelRuns ?? []);
      for (const event of events) {
        const projected = projectWorkEvent(child.id, event, events, true);
        if (projected) this.append(binding, `runtime:${event.seq}`, projected.type, projected.payload, projected.turn, event.time);
      }
      if (child.throughSeq !== undefined) this.childCursors[child.id] = child.throughSeq;
    }
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
  private async receipt(input: RelayInput, status: string) { if(input.metadata.pa_observation) return; await this.options.relay.request('node.delivery_receipt', { node_id: this.options.nodeId, relay_task_id: input.relay_task_id, delivery_status: status }); }
  async stop(): Promise<void> {
    await this.controls.stop(); this.unsubscribe(); for (const call of this.calls.values()) call.abort(); await Promise.allSettled([...this.drains.values(), ...this.waking.values()]); await this.workFlush; }
}
