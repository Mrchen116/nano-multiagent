import type { ExternalDelivery } from './external.js';
import { PersonalAssistant } from './personal-assistant.js';
import { SessionControls, sessionControl } from './session-controls.js';
import { randomUUID } from 'node:crypto';
import type { AgentConfiguration, RelayInput, RuntimeEvent, RuntimePort, SessionBinding, ModelRunProjection, MessageApprovalContext } from '@nano/product-contracts';
import { canonicalJson, interactiveResponse } from '@nano/product-contracts';
import { RelayDeliveryError, type ProtocolFrame } from '@nano/channels';
import { needsAttention, controlText } from './attention.js';
import { NodeStore } from './store.js';
import { InboxStore } from './inbox.js';
import { logicalEvents } from './presentation.js';
import { projectWorkEvent } from './work-projection.js';
interface Options {
  nodeId: string; ownerId: string; agents: AgentConfiguration[]; store: NodeStore; inbox: InboxStore;
  runtime: RuntimePort; relay: { readonly ready?: boolean; request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  image(url: string, agentId: string): Promise<string>;
  onError(error: unknown): void;
  onWork?(): void;
  authorityEpoch?(): number | undefined;
  taskStop?:(binding:SessionBinding,input:RelayInput)=>Promise<{wasRunning:boolean;paused:number}>;
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
  private backgroundTimer?: ReturnType<typeof setTimeout>;
  private backgroundDrain?: Promise<void>;
  private stopped = false;
  private readonly backgroundRequested = new Set<string>();
  private readonly waitingForIdle = new Set<string>();
  private readonly waking = new Map<string, Promise<void>>();
  private readonly drains = new Map<string, Promise<void>>();
  private readonly dirty = new Set<string>();
  private readonly childDrains = new Map<string, Promise<void>>();
  private readonly childrenDirty = new Set<string>();
  private readonly calls = new Map<string, AbortController>();
  private receiptDrain?: Promise<void>;
  private receiptTimer?: ReturnType<typeof setTimeout>;
  private receiptBackoff=1000;
  private recoveryTimer?: ReturnType<typeof setTimeout>;
  private recovering?:Promise<void>;
  private readonly controlTasks=new Map<string,Promise<void>>();
  private readonly authorities = new Set<string>();
  private readonly accepting = new Map<string,Promise<void>>();
  private readonly childCursors: Record<string, number> = {};
  private readonly childModelVersions: Record<string, string> = {};
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
      if (method === 'session.status' && data.status === 'idle') {
        this.waitingForIdle.delete(config.agentId); this.wake(config, binding, true).catch(options.onError);
      }
    });
  }
  /** Pending Inbox wakes and local reconciliation/delivery block a safe update. */
  get busy(): boolean {
    return !!this.observations || !!this.backgroundDrain || this.controls.busy || this.waking.size > 0 || this.drains.size > 0 || this.dirty.size > 0 || this.childDrains.size > 0 || this.childrenDirty.size > 0 || this.calls.size > 0 ||
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
    await this.ensureAuthority(binding);
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
    const config = this.options.agents.find(agent=>agent.agentId===input.agent_id && agent.mode==='global');
    if (!config) throw new Error('No global Agent for input');
    const command = controlText(input);
    const control = input.message.sender_type === 'user' && (/^\/(new|stop)$/.test(command) || sessionControl(input,config)!==undefined);
    const saved = structuredClone(input);
    if (config.personal) saved.metadata.personal_unclassified = true;
    this.options.inbox.acceptRelay(saved,!control && !config.personal && needsAttention(input,config),control);
    void this.drainReceipts();
    const key = `${input.agent_id}:${input.message.id}`;
    const active = this.accepting.get(key); if (active) return active;
    if (control && !this.options.inbox.pendingControls().some(item=>item.agent_id===input.agent_id && item.message.id===input.message.id)) return;
    const prior=control ? this.controlTasks.get(input.agent_id) : undefined;
    const task = (async()=>{await prior;await this.ingest(input);if(control)this.options.inbox.finishControl(input);})()
      .catch(error=>{this.scheduleRecovery();throw error;}).finally(()=>{
        this.accepting.delete(key);if(this.controlTasks.get(input.agent_id)===task)this.controlTasks.delete(input.agent_id);
      });
    this.accepting.set(key,task);if(control)this.controlTasks.set(input.agent_id,task);await task;
    if(control && this.options.inbox.wakePending(config.agentId)!==undefined)await this.wake(config,this.binding(config));
  }
  private ensureAuthority(binding: SessionBinding): Promise<void> {
    if (this.options.relay.ready === false) return Promise.resolve();
    const key = `${this.options.authorityEpoch?.() ?? 0}:${binding.agentId}:${binding.sessionId}`;
    if (this.authorities.has(key)) return Promise.resolve();
    return this.options.relay.request('agent.session.ensure',{node_id:this.options.nodeId,agent_id:binding.agentId,session_id:binding.sessionId})
      .then(()=>{this.authorities.add(key);});
  }
  private drainReceipts(): Promise<void> {
    if (this.receiptDrain) return this.receiptDrain;
    clearTimeout(this.receiptTimer);
    const task = (async()=>{
      if (this.options.relay.ready===false) return;
      let batch;
      while ((batch=this.options.inbox.pendingRelays()).length) {
        for (const receipt of batch) {
          try {await this.transmitReceipt(receipt.input,receipt.status);this.options.inbox.confirmRelay(receipt.input.relay_task_id,receipt.status);}
          catch(error) {
            if(error instanceof RelayDeliveryError && error.delivery==='rejected' && /scope_not_allowed|agent_not_accessible|conversation_id not found|relay task not found|node_not_registered|gateway_owner_mismatch/.test(error.code??'')) {this.options.inbox.rejectRelay(receipt.input.relay_task_id);this.options.onError(error);continue;}
            if(!this.stopped) {this.receiptTimer=setTimeout(()=>{void this.drainReceipts();},this.receiptBackoff);this.receiptTimer.unref();this.receiptBackoff=Math.min(30000,this.receiptBackoff*2);}
            this.options.onError(error);return;
          }
        }
      }
      this.receiptBackoff=1000;
    })().finally(()=>{this.receiptDrain=undefined;});
    this.receiptDrain=task;return task;
  }
  private async ingest(input: RelayInput, deferWake = false): Promise<void> {
    const config = this.options.agents.find(agent => agent.agentId === input.agent_id && agent.mode === 'global');
    if (!config) throw new Error('No global Agent for input');
    const stopping=input.message.sender_type==='user'&&controlText(input)==='/stop'&&!!this.options.taskStop;
    const binding=stopping?this.binding(config):await this.main(config);
    if(stopping&&config.personal) {
      if(!await this.personal.source(config,input)){await this.receipt(input,'completed');return;}
      if(input.metadata.personal_is_owner!==true||input.metadata.personal_delivery!=='participant')await this.main(config);
    }
    if (config.personal && !await this.personal.admit(config,binding,input)) { await this.receipt(input,'completed'); return; }
    const ownerControl = !config.personal || input.metadata.personal_is_owner === true && input.metadata.personal_delivery === 'participant'
      && needsAttention(input,{...config,groupReplyPolicy:'mention_only'});
    const command = controlText(input);
    if(!ownerControl && this.options.inbox.pendingControls().some(item=>item.agent_id===input.agent_id && item.message.id===input.message.id)) {
      this.options.inbox.demoteControl(input);deferWake=true;
    }
    if (ownerControl && input.message.sender_type === 'user' && (command === '/new' || command === '/stop')) {
      const binding = this.binding(config);
      let text = '全局模式不支持按聊天重置';
      if (command === '/stop') {
        const result=this.options.taskStop?await this.options.taskStop(binding,input):await this.options.runtime.request('session.cancel', {sessionId:binding.sessionId}) as {wasRunning:boolean;paused?:number};
        text=result.paused?`已停止当前操作，并暂缓 ${result.paused} 项进行中的任务。`:result.wasRunning?'已停止当前操作。':'当前没有正在执行的操作。';
      }
      await this.options.relay.request('agent.message', { node_id: this.options.nodeId, to: `conversation:${input.conversation_id}`, text,
        from_session_id: `${config.agentId}|tool_call:command:${input.message.id}` });
      await this.receipt(input, 'completed'); return;
    }
    const control = ownerControl ? sessionControl(input, config) : undefined;
    if (control) { const pending = this.controls.run(this.binding(config), input, control.action, control.argument); await this.main(config); await pending; return; }
    const unaddressedControl = /^\/(compact|effort|workflows|config)(?:\s|$)/.test(command);
    const attention = !unaddressedControl && (!config.personal || input.metadata.personal_delivery === 'participant') && needsAttention(input, config);
    this.options.inbox.receive(input, attention);
    if (config.personal) this.options.inbox.classify(input,attention);
    void this.receipt(input, 'sent');
    this.armBackground();
    if (attention && !deferWake) {
      if (config.personal) await this.recoverPersonalObservations();
      await this.wake(config, binding);
    }
  }
  private wake(config: AgentConfiguration, binding: SessionBinding, background = false): Promise<void> {
    if (this.stopped) return Promise.resolve();
    if (background && config.personal) this.backgroundRequested.add(config.agentId);
    const active = this.waking.get(config.agentId);
    if (active) return active;
    const task = (async () => {
      await this.controlTasks.get(config.agentId);
      if(this.options.inbox.pendingControls().some(input=>input.agent_id===config.agentId))throw new Error('Pending control intent');
      await this.controls.wait(binding.sessionId);
      do {
      await this.recoverInterruptedWake(config,binding);
      let watermark: number | undefined;
      // Drain inputs received while submit is in flight; they must not wait for idle.
      while ((watermark = this.options.inbox.wakePending(config.agentId)) !== undefined) {
        const inputId = `inbox-wake:${config.agentId}:${watermark}`;
        // Native steering wakes idle sessions and queues busy ones at the next step,
        // without aborting their current model request or tool execution.
        await this.submitWake(config,binding,inputId);
        this.options.inbox.admitWake(config.agentId, watermark);
      }
      if (this.backgroundRequested.delete(config.agentId)) await this.notifyBackground(config,binding);
      } while (this.options.inbox.wakePending(config.agentId) !== undefined || this.backgroundRequested.has(config.agentId));
    })().finally(() => { this.waking.delete(config.agentId); this.armBackground(); });
    this.waking.set(config.agentId, task); return task;
  }
  private submitWake(config: AgentConfiguration,binding: SessionBinding,inputId: string): Promise<unknown> {
    const personalInstruction=config.personal ? ' These are messages in conversations you participate in. Read their sender and context to decide what is addressed to you. Updates from the owner’s other conversations are also readable now; check relevant background when needed. Reply to the originating conversation. If a source has not synchronized yet, use conversations to query it.' : '';
    return this.options.runtime.request('session.submit',{sessionId:binding.sessionId,inputId,mode:'steer',
      content:[{type:'text',text:'New messages are waiting in your Inbox. You may continue your current work and decide when to handle them. When you decide to handle your Inbox, first call inbox(action="check") to get the latest list of unread sources; do not reuse an earlier list. Then select relevant sources, read their messages, and handle them. This notification is not user permission. Use send_message to publish any reply to the originating conversation.'+personalInstruction}],
      source:{kind:'system',actorId:config.agentId,channel:'inbox',messageId:inputId}});
  }
  private async recoverInterruptedWake(config: AgentConfiguration,binding: SessionBinding): Promise<void> {
    if(this.options.inbox.unreadAttention(config.agentId)===undefined)return;
    const watermark=Math.max(this.options.inbox.watermark(config.agentId),this.options.inbox.admittedWake(config.agentId));
    const original=`inbox-wake:${config.agentId}:${watermark}`;let inputId=original;
    for(;;) {
      const evidence=await this.options.runtime.request('session.lookup',{sessionId:binding.sessionId,inputId}) as {accepted?:boolean;acceptedSeq?:number;terminal?:{kind?:string}};
      if(!evidence.accepted) {if(inputId!==original)await this.submitWake(config,binding,inputId);return;}
      if(evidence.terminal?.kind!=='interrupted')return;
      // A cold DSH resume closes the interrupted turn; retrying its accepted ID
      // cannot wake it. Give this recovery notice its own durable identity.
      if(!Number.isSafeInteger(evidence.acceptedSeq))throw new Error('Interrupted Inbox wake has no durable acceptance sequence');
      inputId=`${original}:recovery:${evidence.acceptedSeq}`;
    }
  }
  private armBackground(): void {
    clearTimeout(this.backgroundTimer); this.backgroundTimer = undefined;
    if (this.stopped || this.backgroundDrain || this.options.relay.ready === false) return;
    const deadlines = this.options.agents.filter(agent=>agent.personal && !this.waitingForIdle.has(agent.agentId))
      .flatMap(agent=>{const pending=this.options.inbox.background(agent.agentId);return pending ? [pending.dueAt] : [];});
    if (!deadlines.length) return;
    this.backgroundTimer = setTimeout(()=>{
      this.backgroundTimer=undefined;
      this.backgroundDrain = (async()=>{
        await this.recoverPersonalObservations();
        for(const config of this.options.agents.filter(agent=>agent.personal)) {
          try { await this.wake(config,await this.main(config),true); } catch(error) { this.options.onError(error); }
        }
      })().catch(this.options.onError).finally(()=>{this.backgroundDrain=undefined;this.armBackground();});
    },Math.max(0,Math.min(...deadlines)-Date.now()));
    this.backgroundTimer.unref();
  }
  private async refreshPersonalSources(config: AgentConfiguration): Promise<void> {
    const sources=await this.personal.request(config,'pa.sources',{action:'list'});
    const allowed=new Set((sources.items as {id:string;excluded:boolean}[]).filter(item=>!item.excluded).map(item=>item.id));
    for(const source of this.options.inbox.check(config.agentId).sources) {
      if(source.target!==config.personal!.conversationId && !allowed.has(source.target)) this.options.inbox.revokeSource(config.agentId,source.target);
    }
  }
  private async restorePersonalInputs(config: AgentConfiguration): Promise<void> {
    await this.refreshPersonalSources(config);
    for (const input of this.options.inbox.unclassified(config.agentId)) {
      if (await this.personal.admit(config,await this.main(config),input)) this.options.inbox.classify(input,input.metadata.personal_delivery==='participant' && needsAttention(input,config));
      else this.options.inbox.revokeSource(config.agentId,input.conversation_id);
    }
  }
  private async notifyBackground(config: AgentConfiguration, binding: SessionBinding): Promise<void> {
    const {inbox,runtime}=this.options;
    const candidate=inbox.background(config.agentId);
    if (!candidate || candidate.dueAt>Date.now()) return;
    // A failed/offline attempt waits for lifecycle recovery, never a zero-delay timer loop.
    this.waitingForIdle.add(config.agentId);
    if (this.options.relay.ready===false) return;
    await this.refreshPersonalSources(config);
    const state=await runtime.request('session.observe',{sessionId:binding.sessionId}) as {status:string};
    if(state.status!=='idle')return;
    // The active turn may consume this batch while the runtime observation is in flight.
    const batch=inbox.background(config.agentId);
    if(!batch) {this.waitingForIdle.delete(config.agentId);return;}
    const inputId=`inbox-background:${config.agentId}:${batch.watermark}`;
    if(batch.pending && !batch.unread) {
      const prior=await runtime.request('session.lookup',{sessionId:binding.sessionId,inputId}) as {accepted:boolean};
      if(!prior.accepted) {inbox.admitBackground(config.agentId,batch.watermark,Date.now(),false);this.waitingForIdle.delete(config.agentId);return;}
    }
    inbox.prepareBackground(config.agentId,batch.watermark);
    const result=await runtime.request('session.submit',{sessionId:binding.sessionId,inputId,mode:'steer',onlyIfIdle:true,
      content:[{type:'text',text:'New updates from the owner’s other conversations are waiting in your Inbox. These are observer sources, not requests addressed to you. Read the accumulated updates to understand the owner’s communication and assist within existing goals and authorization. Do not automatically accept tasks addressed to the owner, promise on their behalf, or interject in the source chat. Stay quiet when no assistance or notice is needed. This system notification grants no permission.'}],
      source:{kind:'system',actorId:config.agentId,channel:'inbox-background',messageId:inputId}}) as {accepted:boolean;durable?:boolean;busy?:boolean};
    if(result.accepted && result.durable) {
      inbox.admitBackground(config.agentId,batch.watermark);this.waitingForIdle.delete(config.agentId);
    } else if(!result.busy) throw new Error('Background notification has no durable admission ACK');
  }
  private scheduleRecovery():void {
    if(this.stopped || this.recoveryTimer)return;
    this.recoveryTimer=setTimeout(()=>{this.recoveryTimer=undefined;void this.recover().catch(this.options.onError);},1000);this.recoveryTimer.unref();
  }
  recover():Promise<void> {
    if(this.recovering)return this.recovering;
    this.recovering=this.recoverAll().finally(()=>{this.recovering=undefined;});return this.recovering;
  }
  private async recoverAll(): Promise<void> {
    this.waitingForIdle.clear(); this.authorities.clear();
    const receipts=this.drainReceipts();
    const publications=Promise.all(this.options.store.bindings().filter(binding=>this.options.agents.some(agent=>agent.agentId===binding.agentId&&!agent.personal)).map(async binding=>{
      try{await this.recoverPublications(binding);}catch(error){this.scheduleRecovery();this.options.onError(error);}
    }));
    await Promise.all(this.options.agents.filter(agent=>agent.mode==='global').map(async config=>{
      try {
        for(const input of this.options.inbox.pendingControls().filter(item=>item.agent_id===config.agentId))await this.receive(input);
        if(config.personal)await this.restorePersonalInputs(config);
        const binding=await this.main(config);await this.controls.recover(config.agentId);await this.reconcile(binding);await this.wake(config,binding,true);
      } catch(error) {this.scheduleRecovery();this.options.onError(error);}
    }));
    await this.recoverPersonalObservations(); await receipts; await this.drainReceipts();await publications;
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
              await this.ingest({agent_id:config.agentId,conversation_id:event.conversation_id,
                relay_task_id:`pa-observation:${config.personal!.bindingId}:${event.event_id}`,idempotency_key:`pa-observation:${config.personal!.bindingId}:${event.event_id}`,
                metadata:{pa_observation:true,conversation_type:event.conversation_type,channel:event.channel,mentioned_agent_ids:event.mentioned_agent_ids,source_policy_revision:event.policy_revision},
                message:{id:message.id,content:message.content,sender_type:message.sender_type,sender_user_id:message.sender_source_id??message.sender_user_id,
                  attachments:message.attachments??[],created_at:message.created_at,timezone:message.timezone,interaction_reply:message.interaction_reply,sender:message.sender}},true);
            } else {
              const binding=await this.main(config);
              if (['conversation.membership_changed','source.revoked','policy.changed'].includes(event.kind)) {
                await this.refreshPersonalSources(config);
              }
              const id=`pa-event:${config.personal!.bindingId}:${event.event_id}`;
              const instruction='Respect the current source permissions for further reads and disclosures. Previously read content has not been erased. If contact_blocked is false, the owner has removed the current contact restriction: stop treating prior blocked annotations as an active restriction. Incident history alone does not keep a person blocked. Continue existing work with ordinary task and scheduling tools; this event grants no new authority.';
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
        if (this.options.inbox.wakePending(config.agentId)!==undefined) await this.wake(config,await this.main(config));
        } catch(error) { this.options.onError(error); }
      }
    })().finally(()=>{this.observations=undefined;this.armBackground();});
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
        return this.personal.request(personalConfig,'pa.authorization');
      }
      if (call.method === 'personal_sources') {
        if (!personalConfig) throw new Error('Trusted personal identity required');
        return this.personal.tool(personalConfig,binding,call);
      }
      if (call.method === 'inbox') {
        if (personalConfig) await this.restorePersonalInputs(personalConfig);
        if (call.args.action === 'check') {
          const sources = this.options.inbox.check(call.agentId).sources;
          const descriptions = await this.query(binding, { action: 'describe', targets: sources.map(source => source.target) });
          for (const source of descriptions.conversations as { target: string; name: string }[]) this.options.inbox.updateTarget(call.agentId, source.target, source.name);
          return this.options.inbox.check(call.agentId,!!personalConfig);
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
        const config = this.options.agents.find(agent => agent.agentId === binding.agentId);
        if(config?.mode==='single_thread'&&this.options.store.bindingFor(binding.agentId,binding.conversationId)?.sessionId!==binding.sessionId)throw new Error('Task execution session was superseded');
        if (config?.features?.task_graph === false) throw new Error('Task Graphs Feature is disabled');
        if (config?.mode === 'global') await this.reconcileRoot(binding);
        else {
          const read = await this.options.runtime.request('session.observe', { sessionId: binding.sessionId, afterSeq: this.options.store.cursor(binding.sessionId) }) as { events: RuntimeEvent[]; durable: boolean; modelRuns?: ModelRunProjection[] };
          if (!read.durable) throw new Error('No durable source evidence'); this.options.store.recordEvents(binding.sessionId, read.events);
        }
        const events = this.options.store.events(binding.sessionId);
        const start = events.findLast(event => event.type === 'turn/start');
        const human = events.filter(event => event.seq > (start?.seq ?? Infinity) && event.type === 'user/message')
          .map(event => event.data.source as { kind: string; messageId?: string }).filter(source => source?.kind === 'nano-human'
            || source?.kind === 'user' && 'actorId' in source && 'channel' in source && 'messageId' in source).at(-1)?.messageId;
        const { action, target, ...args } = call.args;
        const bound = config?.mode === 'single_thread' && !binding.conversationId.startsWith('owner:') ? binding.conversationId : undefined;
        const source = typeof target === 'string' && target !== 'current' ? target.replace(/^conversation:/, '')
          : ['create', 'apply', 'delete'].includes(String(action)) ? bound : undefined;
        const conversationId = source ? this.options.store.imConversation(binding.agentId, source) : undefined;
        if ((action === 'create' || target !== undefined) && !conversationId) return { ok: false, error: {
          code: 'conversation_required', message: 'Choose an existing conversation target; creation requires a bound IM conversation or a verified external shadow.',
        } };
        try {
          const commandArgs={...args, ...(conversationId === undefined ? {} : {conversation_id:conversationId})};
          if(personalConfig && ['create','apply','delete'].includes(String(action))) {
            const result=await this.personal.task(personalConfig,call,{action,arguments:commandArgs,source_message_id:human ?? null});
            if(result !== undefined) return result;
          }
          const response = await this.options.relay.request('task_graph.command', { node_id: this.options.nodeId, agent_id: binding.agentId,
            request_id: call.operationId, action, source_message_id: human ?? null,
            args: commandArgs });
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
    await this.ensureAuthority(binding);
    const response = await this.options.relay.request('conversation.query', { ...args, node_id: this.options.nodeId,
      agent_id: binding.agentId, session_id: binding.sessionId, request_id: randomUUID() });
    if (!response.payload.ok) throw new Error(String(response.payload.error));
    return response.payload.result as Record<string, unknown>;
  }
  private async send(binding: SessionBinding, call: ProductCall, signal: AbortSignal): Promise<unknown> {
    const { inbox, store, runtime } = this.options;
    const config = this.options.agents.find(agent => agent.agentId === binding.agentId);
    const global = config?.mode === 'global';
    if(config?.personal) return this.personal.send(config,binding,call);
    const target = String(call.args.target ?? ''); const text = String(call.args.text ?? '');
    const interactive = interactiveResponse(call.args.interactive);
    if (interactive && config?.features?.intelligent_ui === false) throw new Error('Intelligent UI Feature is disabled; send a plain-text reply instead');
    const publicationBody = interactive ? canonicalJson({text, interactive}) : text;
    if (!target || !text.trim()) throw new Error('Sending requires a target and non-empty text');
    const confirm = (payload:Record<string,unknown>) => this.confirmPublication(binding,call,target,text,!!interactive,payload);
    const previous = inbox.publication(call.operationId);
    if (previous) {
      if (previous.target !== target || previous.body !== publicationBody) throw new Error('Publication identity conflict');
      if (previous.result) return JSON.parse(previous.result) as unknown;
      if(previous.state==='unknown' || previous.state==='sending') {
        const status=await this.options.relay.request('agent.message.status',{node_id:this.options.nodeId,agent_id:binding.agentId,operation_id:call.operationId});
        if(status.payload.found===true) {
          return confirm(status.payload);
        }
      }
    }
    const conversation = target === 'current' && !global ? binding.conversationId : target.startsWith('conversation:') ? target.slice(13) : (target.startsWith('c_') || target.startsWith('external:')) ? target : undefined;
    if (global) await this.reconcileRoot(binding);
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
    inbox.preparePublication(call.operationId, target, publicationBody);
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
        ...(interactive && info?.channel !== 'feishu' && info?.channel !== 'external' ? {interactive} : {}),
        to: conversation ? `conversation:${conversation}` : target, from_session_id: `${binding.agentId}|tool_call:${call.operationId}` });
      return confirm(response.payload);
    } catch (error) {
      if (interactive && error instanceof RelayDeliveryError && error.delivery === 'rejected') {
        inbox.settlePublication(call.operationId, 'rejected');
        throw new Error(`Interactive reply rejected: ${error.code ?? error.message}`);
      }
      inbox.settlePublication(call.operationId, 'unknown');
      if(error instanceof RelayDeliveryError && error.delivery==='unknown') {
        try {
          const status=await this.options.relay.request('agent.message.status',{node_id:this.options.nodeId,agent_id:binding.agentId,operation_id:call.operationId});
          if(status.payload.found===true) {
            return confirm(status.payload);
          }
        } catch { /* Retain the unknown publication when reconciliation is unavailable. */ }
      }
      throw error;
    }
  }
  private confirmPublication(binding: SessionBinding,call: Pick<ProductCall,'operationId'|'callId'|'sessionId'>,target:string,text:string,interactive:boolean,payload:Record<string,unknown>) {
    const result={status:'sent',target,message_id:payload.message_id,conversation_id:payload.conversation_id};
    this.options.inbox.settlePublication(call.operationId,'confirmed',result);
    const global=this.options.agents.find(agent=>agent.agentId===binding.agentId)?.mode==='global';
    const turn=this.options.store.events(call.sessionId).find(event=>event.type==='tool/call'&&event.data.callId===call.callId)?.data.turn as number|undefined;
    if(interactive&&!global&&turn!==undefined)this.options.store.saveCommand(`interactive-delivered:${binding.sessionId}:${turn}`,JSON.stringify(result));
    if(global)this.append(binding,`publication:${call.operationId}`,'message_sent',{call_id:call.callId,text,...result},turn);
    return result;
  }
  private async recoverPublications(binding: SessionBinding): Promise<void> {
    for(const publication of this.options.inbox.pendingPublications(binding.sessionId)) {
      const status=await this.options.relay.request('agent.message.status',{node_id:this.options.nodeId,agent_id:binding.agentId,operation_id:publication.id});
      if(status.payload.found!==true)continue;
      let text=publication.body,interactive=false;
      try{const body=JSON.parse(publication.body);if(body.interactive){text=body.text;interactive=true;}}catch{ /* Plain text publications need no envelope. */ }
      this.confirmPublication(binding,{operationId:publication.id,callId:publication.id.slice(binding.sessionId.length+1),sessionId:binding.sessionId},publication.target,text,interactive,status.payload);
    }
  }
  private async reconcile(binding: SessionBinding): Promise<void> {
    await Promise.all([this.reconcileRoot(binding), this.reconcileChildren(binding)]);
  }
  // Sending needs durable root evidence and Inbox consumption, not an unrelated
  // child's display history. Separate drains also let recovery track both jobs.
  private reconcileRoot(binding: SessionBinding): Promise<void> {
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
        this.options.onWork?.();
      }
    })().finally(() => this.drains.delete(binding.sessionId));
    this.drains.set(binding.sessionId, task); return task;
  }
  private reconcileChildren(binding: SessionBinding): Promise<void> {
    this.childrenDirty.add(binding.sessionId);
    const prior = this.childDrains.get(binding.sessionId); if (prior) return prior;
    const task = (async () => {
      while (this.childrenDirty.delete(binding.sessionId)) await this.projectChildren(binding);
    })().finally(() => this.childDrains.delete(binding.sessionId));
    this.childDrains.set(binding.sessionId, task); return task;
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
    const children = await this.options.runtime.request('session.descendants', { sessionId: root.sessionId, cursors: this.childCursors, modelVersions: this.childModelVersions }) as { kind: string; id: string; parentId: string; workflowRunId?:string; label?: string; events?: RuntimeEvent[]; throughSeq?: number; modelRuns?: ModelRunProjection[]; modelVersion?: string }[];
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
      if (child.modelVersion !== undefined) this.childModelVersions[child.id] = child.modelVersion;
    }
  }
  private append(binding: SessionBinding, key: string, type: string, payload: Record<string, unknown>, turn?: number, time = Date.now()): void {
    this.options.inbox.append({ event_id: `${binding.sessionId}:${key}`, root_agent_id: binding.agentId,
      session_id: binding.sessionId, ...(turn === undefined ? {} : { turn_id: String(turn) }), type, payload, observed_at: new Date(time).toISOString() });
    this.options.onWork?.();
  }
  private async receipt(input: RelayInput, status: string) {
    if(input.metadata.pa_observation || input.relay_task_id.startsWith('external:')) {await this.transmitReceipt(input,status);return;}
    this.options.inbox.settleRelay(input,status);
    await this.drainReceipts();
  }
  private async transmitReceipt(input: RelayInput, status: string) {
    if(input.metadata.pa_observation) {
      if(input.metadata.channel==='feishu')await this.options.relay.request('node.delivery_receipt',{node_id:this.options.nodeId,agent_id:input.agent_id,external_source_message_id:input.message.id,delivery_status:status});
      return;
    }
    await this.options.relay.request('node.delivery_receipt', { node_id: this.options.nodeId, relay_task_id: input.relay_task_id, delivery_status: status });
  }
  async stop(): Promise<void> {
    this.stopped=true; clearTimeout(this.backgroundTimer);clearTimeout(this.receiptTimer);clearTimeout(this.recoveryTimer);
    await this.backgroundDrain; await this.observations; await this.controls.stop(); this.unsubscribe(); for (const call of this.calls.values()) call.abort(); await Promise.allSettled([...this.drains.values(), ...this.childDrains.values(), ...this.waking.values()]); await this.receiptDrain; await this.recovering; await Promise.allSettled(this.accepting.values()); }
}
