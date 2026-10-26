import type { FeishuConfiguration, FeishuMessage, ProtocolFrame } from '@nano/channels';
import { RelayDeliveryError } from '@nano/channels';
import type { RelayInput } from '@nano/product-contracts';
import { formatLocalTime } from '@nano/product-contracts';
import { NodeStore } from './store.js';
import { ExternalStore, type ExternalChat, type ExternalOutput } from './external-store.js';

interface Connection {
  config: Pick<FeishuConfiguration, 'appId' | 'botOpenId' | 'ownerOpenId'>;
  send(chatId: string, text: string, operationId: string, card?: Record<string, unknown>): Promise<string>;
  thinking(messageId: string, reactionId?: string): Promise<string | undefined>;
  image(messageId: string, key: string): Promise<{ data: Buffer; mediaType: string }>;
  updateCard(messageId: string, card: Record<string, unknown>): Promise<void>;
}
export interface ExternalDelivery {
  agentId:string; target:string; shadowId?:string; appId:string; sourceId:string; chatId:string;
  text:string; card?:Record<string,unknown>; operationId:string; incidentRef?:string;
  ownerDelivery?:Record<string,unknown>;
  dispatch(text:string,card?:Record<string,unknown>):Promise<string>;
}
interface Options {
  nodeId: string; ownerId: string; store: NodeStore;
  runtimeFooter?: boolean;
  personalAgent?(agentId:string):boolean;
  personalDelivery?(delivery:ExternalDelivery):Promise<string|undefined>;
  attention?(input: RelayInput): boolean;
  relay: { readonly ready: boolean; request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  im(path: string, options?: RequestInit): Promise<unknown>;
  receive(input: RelayInput): Promise<void>;
  permission(payload: Record<string, unknown>): Promise<void>;
  onError(error: unknown): void;
}

/** Platform execution continues offline; IM catches up from its own durable projection outbox. */
export class ExternalChannels {
  private readonly state: ExternalStore;
  private readonly connections = new Map<string, Connection>();
  private readonly admissions = new Map<string, Promise<void>>();
  private readonly dispatches = new Map<string, Promise<void>>();
  private flushing?: Promise<void>;
  private flushAgain = false;
  constructor(path: string, private readonly options: Options) {
    this.state = new ExternalStore(path);
    const relay=options.relay,im=options.im;
    this.options={...options,relay:{get ready(){return relay.ready;},request:(type,payload)=>relay.request(type,type==='node.delivery_receipt'?payload:options.store.executionPayload(payload))},
      im:(path,request)=>{
        const identity=options.store.lifecycle.current();
        if(!identity)return im(path,request);
        const revision=options.store.lifecycle.assert(identity.agentId,identity.revision);
        const url=new URL(path,'http://local');
        const headers=new Headers(request?.headers);headers.set('x-agent-lifecycle-revision',String(revision));
        let body=request?.body;
        if(typeof body==='string' && headers.get('content-type')==='application/json')body=JSON.stringify({...JSON.parse(body),lifecycle_revision:revision});
        else url.searchParams.set('lifecycle_revision',String(revision));
        return im(url.pathname+url.search,{...request,headers,body});
      }};
  }
  historyConversation(agentId: string, source: string, chatId: string): string | undefined {
    if (source !== 'feishu') return;
    return this.state.chats().find(chat => chat.agentId === agentId && chat.sourceId === chatId)?.id;
  }
  get ready() { return this.options.relay.ready; }
  add(agentId: string, connection: Connection): void {
    this.connections.set(agentId,{config:connection.config,
      send:(...args)=>{this.options.store.lifecycle.assert(agentId);return connection.send(...args);},
      thinking:(...args)=>{this.options.store.lifecycle.assert(agentId);return connection.thinking(...args);},
      image:(...args)=>{this.options.store.lifecycle.assert(agentId);return connection.image(...args);},
      updateCard:(...args)=>{this.options.store.lifecycle.assert(agentId);return connection.updateCard(...args);}});
  }
  remove(agentId: string): void { this.connections.delete(agentId); }
  available(agentId: string): boolean { return this.connections.has(agentId); }

  receive(agentId: string, message: FeishuMessage): Promise<void> {
    const connection = this.connections.get(agentId); if (!connection) throw new Error('No channel for Agent');
    const appId = connection.config.appId;
    const sourceId = `feishu:${appId}:${message.isGroup ? `group:${message.chatId}` : `dm:${message.senderId}`}`;
    const id = `external:${agentId}:${sourceId}`; const eventId = `external:${agentId}:${appId}:${message.messageId}`;
    const active = this.admissions.get(eventId); if (active) return active;
    const previous = this.state.chat(id);
    this.state.saveChat({ id, agentId, appId, chatId: message.chatId, sourceId, isGroup: message.isGroup, ...previous, ...(message.chatName ? { name: message.chatName } : {}) });
    const text = message.parts.filter(part => part.type === 'text').map(part => part.text).join('');
    const attachments = message.parts.filter(part => part.type === 'image').map(part => ({ url: `${eventId}:${part.key}`, content_type: 'image/png', file_name: part.key }));
    let input: RelayInput = { relay_task_id: eventId, idempotency_key: eventId, agent_id: agentId, conversation_id: id,
      metadata: { conversation_type: message.isGroup ? 'group' : 'direct', mentioned_agent_ids: message.mentioned ? [agentId] : [],
        external_reply: eventId, source_timestamp: message.time, channel: 'feishu',
        sender_display_name: message.senderName, ...(message.contextOnly ? { context_only: true } : {}),
        ...(message.senderId === connection.config.ownerOpenId ? { owner_user_id: this.options.ownerId } : {}),
        content_parts: message.parts.map(part => part.type === 'text' ? part : { type: 'image', url: `${eventId}:${part.key}` }),
      }, message: { id: eventId, content: text, sender_type: 'user', sender_user_id: message.senderId, attachments,
        created_at: new Date(Number.isFinite(Number(message.time)) && Number(message.time) > 0 ? Number(message.time) : Date.now()).toISOString(),
        ...(message.senderId === connection.config.ownerOpenId && this.options.store.ownerTimezone ? { timezone: this.options.store.ownerTimezone } : {}),
      } };
    input=this.options.store.admitInput(input);
    this.state.saveInbound(eventId, id, message, input);
    const task = this.admit(eventId).finally(() => this.admissions.delete(eventId)); this.admissions.set(eventId, task); return task;
  }
  private async admit(id: string) {
    const row = this.state.inbound().find(row => row.id === id)!;
    if (row.accepted) return;
    if(!this.options.store.lifecycle.allowed(row.input.agent_id,row.input.lifecycle_revision??1))return;
    return this.options.store.lifecycle.run(row.input.agent_id,row.input.lifecycle_revision??1,()=>this.admitInput(row));
  }
  private async admitInput(row:ReturnType<ExternalStore['inbound']>[number]) {
    const id=row.id;
    const chat = this.state.chat(row.chatId)!; const connection = this.connections.get(chat.agentId)!;
    if (!row.reaction && (this.options.attention?.(row.input) ?? (!row.message.isGroup || row.message.mentioned))) {
      try { const reaction = await connection.thinking(row.message.messageId); if (reaction) this.state.reaction(id, reaction); } catch (error) { this.options.onError(error); }
    }
    // Persist actual image bytes before admitting the input so restart never changes its content.
    for (const part of row.message.parts) if (part.type === 'image') {
      const url = `${id}:${part.key}`;
      if (!this.state.image(url, chat.agentId)) {
        const image = await connection.image(row.message.messageId, part.key);
        this.state.saveImage(url, chat.agentId, image.data, image.mediaType);
      }
    }
    for (const attachment of row.input.message.attachments) attachment.content_type = this.state.image(attachment.url, chat.agentId)!.mediaType;
    this.options.store.lifecycle.assert(chat.agentId);
    this.state.updateInput(id, row.message, row.input);
    if(this.options.personalAgent?.(chat.agentId)) {
      if(!this.ready)throw new Error('Personal source authority requires the center');
      // The durable IM source event is the PA's sole ingress; output projection is independent.
      await this.mirrorInput(row);
    } else await this.options.receive(row.input);
    this.state.accept(id);
    void this.flush().catch(this.options.onError);
  }
  image(url: string, agentId: string): { data: Buffer; mediaType: string } {
    const image = this.state.image(url, agentId); if (!image) throw new Error('Image is outside the authenticated external input'); return image;
  }
  async recover(): Promise<void> {
    for (const row of this.state.inbound()) if (!row.accepted && this.connections.has(row.input.agent_id)) await this.admit(row.id);
    await this.flush();
  }

  async request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> {
    if(type==='node.delivery_receipt')return this.requestAdmitted(type,payload);
    const output=this.state.output(String(payload.message_id));
    const agentId=output?this.state.chat(output.chatId)!.agentId:typeof payload.agent_id==='string'?payload.agent_id:typeof payload.from_session_id==='string'?payload.from_session_id.split('|')[0]:this.options.store.lifecycle.current()?.agentId;
    if(!agentId)return this.requestAdmitted(type,payload);
    const revision=output?.lifecycle_revision??(typeof payload.lifecycle_revision==='number'?payload.lifecycle_revision:undefined);
    return this.options.store.lifecycle.run(agentId,revision,()=>this.requestAdmitted(type,this.options.store.executionPayload(payload)));
  }
  private async requestAdmitted(type:string,payload:Record<string,unknown>):Promise<ProtocolFrame> {
    if(type==='node.delivery_receipt' && typeof payload.external_source_message_id==='string') {
      const source=this.state.inbound().find(row=>row.mirror===payload.external_source_message_id && row.input.agent_id===payload.agent_id);
      if(source && ['completed','failed'].includes(String(payload.delivery_status)))await this.removeReaction(source.id);
      return ack(type);
    }
    if (type === 'node.delivery_receipt' && String(payload.relay_task_id).startsWith('external:')) {
      if (['completed', 'failed'].includes(String(payload.delivery_status))) await this.removeReaction(String(payload.relay_task_id));
      return ack(type);
    }
    if (type === 'node.system_message') {
      const target = String(payload.conversation_id);
      const chat = target.startsWith('external:') ? this.state.chat(target) : undefined;
      if (chat) {
        const notice = payload.system_notice as { source_agent_id: string };
        if (notice.source_agent_id !== chat.agentId) throw new Error('Knowledge notice belongs to another Agent');
        const output = this.state.prepare(chat.id, String(payload.idempotency_key), 'explicit',Number(payload.lifecycle_revision??1));
        await this.publish(output, String(payload.text));
        this.state.frame(output.id, { ...payload, kind: 'system_notice' });
        void this.flush().catch(this.options.onError);
        return ack(type, { message_id: this.state.output(output.id)!.platformId });
      }
    }
    if(['pa.source.admit','pa.incident.report'].includes(type) && String(payload.source_message_id).startsWith('external:')) {
      const source=this.state.inbound().find(row=>row.id===payload.source_message_id&&row.input.agent_id===payload.agent_id);
      const chat=source?this.state.chat(source.chatId):undefined;
      if(!source?.mirror||!chat?.shadowId)throw new Error('Personal source is not yet synchronized');
      return this.options.relay.request(type,{...payload,source_message_id:source.mirror,conversation_id:chat.shadowId});
    }
    if (type === 'task_graph.command' && ['create', 'apply', 'delete'].includes(String(payload.action)) && String(payload.source_message_id).startsWith('external:')) {
      const source = this.state.inbound().find(row => row.id === payload.source_message_id && row.input.agent_id === payload.agent_id);
      if (!source?.mirror) return { type: 'task_graph.result', payload: { request_id: payload.request_id, ok: false,
        error: { code: 'source_unavailable', message: 'The external source message has not been mirrored to IM.' } } };
      return this.options.relay.request(type, { ...payload, source_message_id: source.mirror });
    }
    if (type === 'conversation.query') {
      const local = this.query(payload); if (local) return { type: 'conversation.query.result', payload: { request_id: payload.request_id, ok: true, result: local } };
    }
    if (type === 'agent.message') {
      const target = String(payload.to).replace(/^conversation:/, ''); const chat = this.state.chat(target);
      if (chat) {
        const agentId = String(payload.from_session_id).split('|')[0];
        if (chat.agentId !== agentId) throw new Error('External target belongs to another Agent');
        const output = this.state.prepare(chat.id, String(payload.from_session_id), 'explicit',Number(payload.lifecycle_revision??1));
        this.state.frame(output.id, { lifecycle_revision:output.lifecycle_revision,kind: 'turn_start', conversation_id: chat.id, agent_id: agentId, idempotency_key: output.operationId });
        const complete = { lifecycle_revision:output.lifecycle_revision,kind: 'message_completed', message_id: output.id, final_content: payload.text, pa_incident_ref:payload.pa_incident_ref, personal_owner_delivery:payload.personal_owner_delivery, delivery_status: 'completed' };
        await this.finish(output, complete);
        void this.flush().catch(this.options.onError); return ack(type, { message_id: output.platformId ?? this.state.output(output.id)!.platformId, conversation_id: chat.id });
      }
    }
    if (type !== 'node.streaming_delta') return this.options.relay.request(type, payload);
    if (payload.kind === 'turn_start') {
      const chat = this.state.chat(String(payload.conversation_id));
      if (!chat) return this.options.relay.request(type, payload);
      const output = this.state.prepare(chat.id, String(payload.idempotency_key), typeof payload.external_reply === 'string' ? payload.external_reply : undefined,Number(payload.lifecycle_revision??1));
      this.state.frame(output.id, payload);
      void this.flush().catch(this.options.onError); return ack(type, { message_id: output.id, conversation_id: chat.id });
    }
    const output = this.state.output(String(payload.message_id));
    if (!output) return this.options.relay.request(type, payload);
    if (payload.kind === 'message_completed') {
      await this.finish(output, payload);
      if (output.reply) await this.removeReaction(output.reply);
    } else this.state.frame(output.id, payload);
    if (payload.kind === 'permission_request' && output.reply) await this.approval(output, payload);
    if (payload.kind === 'permission_resolved') await this.resolveApproval(String((payload.permission_request as Record<string,unknown>|undefined)?.request_id ?? payload.request_id), String(payload.decision));
    void this.flush().catch(this.options.onError); return ack(type);
  }
  private async finish(output: ExternalOutput, payload: Record<string, unknown>): Promise<void> {
    try {
      if (output.reply && String(payload.final_content ?? '').trim()) await this.publish(output, String(payload.final_content), payload);
      this.state.frame(output.id, payload);
    } catch (error) {
      if (error instanceof RelayDeliveryError && error.delivery === 'unknown') {
        this.state.frame(output.id, { ...payload, delivery_status: 'failed', external_delivery_status: 'unknown', final_content: `${payload.final_content ?? ''}\n\n飞书发送结果未知，未自动重发。` });
        if (output.reply) await this.removeReaction(output.reply);
        void this.flush().catch(this.options.onError);
      }
      throw error;
    }
  }
  private async publish(output: ExternalOutput, text: string, metadata?: Record<string, unknown>): Promise<void> {
    const agentId=this.state.chat(output.chatId)!.agentId;
    return this.options.store.lifecycle.run(agentId,output.lifecycle_revision,()=>this.publishAdmitted(output,text,metadata));
  }
  private async publishAdmitted(output: ExternalOutput, text:string, metadata?:Record<string,unknown>):Promise<void> {
    const active = this.dispatches.get(output.id); if (active) return active;
    const task = (async () => {
      const current = this.state.output(output.id)!;
      if (current.state === 'confirmed') return;
      if (current.state === 'unknown') throw new RelayDeliveryError('External send outcome is unknown; it will not be automatically repeated', 'unknown');
      const chat = this.state.chat(output.chatId)!; const connection = this.connections.get(chat.agentId);
      if (!connection || connection.config.appId !== chat.appId) throw new Error('External app is unavailable');
      const card = this.options.runtimeFooter && metadata ? runtimeCard(text, metadata) : undefined;
      const dispatch=async(body:string,frozenCard?:Record<string,unknown>)=>{
        this.options.store.lifecycle.assert(chat.agentId,output.lifecycle_revision);
        this.state.settle(output.id,'sending');
        try { const id=await connection.send(chat.chatId,body,output.operationId,frozenCard);this.state.settle(output.id,'confirmed',id);return id; }
        catch {this.state.settle(output.id,'unknown');throw new RelayDeliveryError('External send outcome is unknown; it will not be automatically repeated','unknown');}
      };
      if(this.options.personalAgent?.(chat.agentId)) {
        if(!this.options.personalDelivery)throw new Error('Personal delivery adapter unavailable');
        const id=await this.options.personalDelivery({agentId:chat.agentId,target:chat.id,shadowId:chat.shadowId,appId:chat.appId,sourceId:chat.sourceId,chatId:chat.chatId,
          text,card,operationId:output.operationId,incidentRef:typeof metadata?.pa_incident_ref==='string'?metadata.pa_incident_ref:undefined,ownerDelivery:metadata?.personal_owner_delivery as Record<string,unknown>|undefined,dispatch});
        if(!id)throw new Error('Personal delivery has no provider receipt');
        this.state.settle(output.id,'confirmed',id);
      } else await dispatch(text,card);
    })().finally(() => this.dispatches.delete(output.id));
    this.dispatches.set(output.id, task); return task;
  }
  private async removeReaction(id: string): Promise<void> {
    const row = this.state.inbound().find(row => row.id === id); if (!row?.reaction) return;
    const connection = this.connections.get(row.input.agent_id); if (!connection || !this.options.store.lifecycle.allowed(row.input.agent_id,row.input.lifecycle_revision??1)) return;
    try { await connection.thinking(row.message.messageId, row.reaction); this.state.reaction(id, null); } catch (error) { this.options.onError(error); }
  }
  private query(payload: Record<string, unknown>): Record<string, unknown> | undefined {
    const chats = this.state.chats().filter(chat => chat.agentId === payload.agent_id);
    const describe = (chat: ExternalChat) => {
      const connection = this.connections.get(chat.agentId);
      const owner = connection?.config.appId === chat.appId ? connection.config.ownerOpenId : undefined;
      return { target: chat.id, id: chat.id, name: chatTitle(chat), type: chat.isGroup ? 'group' : 'direct', channel: 'feishu',
        owner_recipient: !!owner && !chat.isGroup && chat.sourceId === `feishu:${chat.appId}:dm:${owner}` };
    };
    if (payload.action === 'describe' && Array.isArray(payload.targets) && payload.targets.every(target => chats.some(chat => chat.id === target || chat.shadowId === target))) return { conversations: chats.filter(chat => (payload.targets as string[]).includes(chat.id) || (payload.targets as string[]).includes(chat.shadowId!)).map(describe) };
    const chat = chats.find(chat => chat.id === String(payload.target).replace(/^conversation:/, '') || chat.shadowId === payload.target);
    if (!chat) return;
    if (payload.action === 'info') return describe(chat);
    if (payload.action === 'read') return { ...describe(chat), messages: this.state.inbound().filter(row => row.chatId === chat.id).slice(-50).map(row => ({
      ...row.input.message, ...(row.input.message.created_at ? { created_at: formatLocalTime(row.input.message.created_at, row.input.message.timezone) } : {}),
    })) };
  }

  private flush(): Promise<void> {
    if (!this.ready) return Promise.resolve();
    this.flushAgain = true;
    if (this.flushing) return this.flushing;
    const task = (async () => {
      while (this.flushAgain) {
        this.flushAgain = false;
      for (const row of this.state.inbound()) await this.mirrorInput(row);
      for (const frame of this.state.pendingFrames()) {
        const output = this.state.output(frame.outputId)!; const chat = this.state.chat(output.chatId)!;
        if (!chat.shadowId || !this.options.store.lifecycle.allowed(chat.agentId,output.lifecycle_revision)) continue;
        frame.body={...frame.body,agent_id:chat.agentId,lifecycle_revision:output.lifecycle_revision};
        try {
        await this.options.store.lifecycle.run(chat.agentId,output.lifecycle_revision,async()=>{
        if (frame.body.kind === 'system_notice') {
          const { kind: _, ...payload } = frame.body;
          const response = await this.options.relay.request('node.system_message', { ...payload, node_id: this.options.nodeId, conversation_id: chat.shadowId });
          if (typeof response.payload.message_id !== 'string') throw new Error('Knowledge projection has no message identity');
          this.state.mirrorOutput(output.id, response.payload.message_id);
        } else if (frame.body.kind === 'turn_start') {
          const response = await this.options.relay.request('node.streaming_delta', { ...frame.body, node_id: this.options.nodeId, conversation_id: chat.shadowId });
          if (typeof response.payload.message_id !== 'string') throw new Error('IM mirror has no message identity');
          this.state.mirrorOutput(output.id, response.payload.message_id);
        } else {
          if (!output.imId) return;
          await this.options.relay.request('node.streaming_delta', { ...frame.body, node_id: this.options.nodeId, message_id: output.imId });
        }
        this.state.confirmFrame(frame.id);
        });
        } catch(error) { this.options.onError(error); }
      }
      }
    })().finally(() => { this.flushing = undefined; }); this.flushing = task; return task;
  }
  private async mirrorInput(row: ReturnType<ExternalStore['inbound']>[number]): Promise<void> {
    if(row.mirror || !this.options.store.lifecycle.allowed(row.input.agent_id,row.input.lifecycle_revision??1))return;
    return this.options.store.lifecycle.run(row.input.agent_id,row.input.lifecycle_revision??1,()=>this.mirrorAdmitted(row));
  }
  private async mirrorAdmitted(row:ReturnType<ExternalStore['inbound']>[number]):Promise<void> {
        if (row.mirror) return;
        const chat = this.state.chat(row.chatId)!;
        if (!chat.shadowId) {
          const result = await this.options.im('/im/v1/conversations/external/find-or-create', json({ external_source: 'feishu', external_chat_id: chat.sourceId, agent_id: chat.agentId,
            title: chatTitle(chat), is_group: chat.isGroup, participant_ids: [`user:${this.options.ownerId}`, `agent:${chat.agentId}`] })) as { id: string };
          chat.shadowId = result.id; this.state.saveChat(chat); this.options.store.aliasConversation(chat.agentId, result.id, chat.id);
        }
        const attachments = [];
        for (const attachment of row.input.message.attachments) {
          const image = this.state.image(attachment.url, chat.agentId)!;
          if (image.uploaded) attachments.push(JSON.parse(image.uploaded));
          else {
            const uploaded = await this.options.im(`/im/v1/uploads?conversation_id=${encodeURIComponent(chat.shadowId!)}&agent_id=${encodeURIComponent(chat.agentId)}&file_name=image.png${this.options.personalAgent?.(chat.agentId)?'&external_incoming=1':''}`, { method: 'POST', headers: { 'Content-Type': image.mediaType }, body: new Uint8Array(image.data) });
            this.state.uploaded(attachment.url, uploaded); attachments.push(uploaded);
          }
        }
        const result = await this.options.im(`/im/v1/conversations/${chat.shadowId}/${this.options.personalAgent?.(chat.agentId)?'external-incoming':'messages'}?agent_id=${encodeURIComponent(chat.agentId)}`, json({ sender_user_id: this.options.ownerId, sender_type: 'user', sender_source_id: row.message.senderId, sender_display_name: row.input.metadata.owner_user_id ? '你' : row.message.senderName,
          content: row.message.parts.length > 1 ? row.message.parts.map(part => part.type === 'text' ? part.text : '[图片]').join('') : row.input.message.content, attachments, created_at: row.input.message.created_at, timezone: row.input.message.timezone, suppress_relay: true }, { 'Idempotency-Key': `shadow:${row.id}` })) as { id: string };
        this.state.mirrorInput(row.id, result.id);
  }
  private async approval(output: ExternalOutput, payload: Record<string, unknown>): Promise<void> {
    const chat = this.state.chat(output.chatId)!; const connection = this.connections.get(chat.agentId)!;
    if (this.options.personalAgent?.(chat.agentId) || !connection.config.ownerOpenId) return;
    const request = payload.permission_request as Record<string, unknown>; const id = String(request.request_id);
    const prior = this.state.approvals().find(row => row.requestId === id); if (prior) return;
    this.state.approval(id, output.id, request);
    const card = approvalCard(id, request, chat.isGroup);
    const platformId = await connection.send(chat.chatId, '', `approval:${id}`, card);
    this.state.approval(id, output.id, request, platformId);
  }
  async card(agentId: string, value: unknown): Promise<unknown> {
    const event = value as { operator?: { open_id?: string }; context?: { open_message_id?: string }; action?: { value?: { request_id?: string; decision?: string } } };
    const requestId = event.action?.value?.request_id; const decision = event.action?.value?.decision;
    const pending = this.state.approvals().find(row => row.requestId === requestId);
    const connection = this.connections.get(agentId);
    if (pending?.settled) return { toast: { type: 'info', content: '审批已结束' }, card: { type: 'raw', data: approvalStatus('已处理') } };
    if (!pending || !connection?.config.ownerOpenId || event.operator?.open_id !== connection.config.ownerOpenId || pending.platformId !== event.context?.open_message_id) return { toast: { type: 'error', content: '此审批不可用或无权操作' } };
    const output = this.state.output(pending.outputId)!; if (this.state.chat(output.chatId)!.agentId !== agentId || !['allow_once', 'deny'].includes(decision ?? '')) return { toast: { type: 'error', content: '无效审批' } };
    this.options.store.lifecycle.assert(agentId,output.lifecycle_revision);
    await this.options.permission({ request_id: requestId, decision,agent_id:agentId,lifecycle_revision:output.lifecycle_revision });
    this.state.settleApproval(requestId!); return { toast: { type: 'success', content: '已提交审批决定' }, card: { type: 'raw', data: approvalStatus(decision!) } };
  }
  private async resolveApproval(requestId: string, decision: string): Promise<void> {
    const pending = this.state.approvals().find(row => row.requestId === requestId); if (!pending) return;
    this.state.settleApproval(requestId);
    if (!pending.platformId) return;
    const output = this.state.output(pending.outputId)!; const chat = this.state.chat(output.chatId)!;
    await this.connections.get(chat.agentId)!.updateCard(pending.platformId, approvalStatus(decision));
  }
  async stop(): Promise<void> { await Promise.allSettled([...this.admissions.values(), ...this.dispatches.values(), this.flushing]); this.state.close(); }
}
function ack(type: string, payload: Record<string, unknown> = {}): ProtocolFrame { return { type: 'ack', payload: { message_type: type, ...payload } }; }
function json(body: unknown, headers: Record<string, string> = {}): RequestInit { return { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) }; }
function approvalCard(id: string, request: Record<string, unknown>, group: boolean): Record<string, unknown> {
  const elements: unknown[] = [{ tag: 'markdown', content: `**${request.tool_name}**\n${group ? '需要 owner 审批；请在内部 IM 查看完整输入' : request.reason ?? '需要审批'}` }];
  for (const [key, value] of Object.entries((request.tool_input ?? {}) as Record<string, unknown>)) {
    const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2); const lines = text.split('\n').length;
    if (group) elements.push({ tag: 'markdown', content: `**${key}**：请在内部 IM 查看完整输入` });
    else if (text.length > 180 || lines > 2) elements.push({ tag: 'collapsible_panel', expanded: false,
      header: { title: { tag: 'plain_text', content: `${key} · ${lines} 行 · ${text.slice(0, 100)}` } }, elements: [{ tag: 'div', text: { tag: 'plain_text', content: text.slice(0, 20000) } }] });
    else elements.push({ tag: 'column_set', background_style: 'grey-50', columns: [{ tag: 'column', width: 'weighted', weight: 1, elements: [{ tag: 'div', text: { tag: 'plain_text', content: `${key} · ${lines} 行\n${text}` } }] }] });
  }
  elements.push({ tag: 'action', actions: [{ tag: 'button', text: { tag: 'plain_text', content: '允许一次' }, type: 'primary', value: { request_id: id, decision: 'allow_once' } }, { tag: 'button', text: { tag: 'plain_text', content: '拒绝' }, value: { request_id: id, decision: 'deny' } }] });
  return { config: { wide_screen_mode: true, update_multi: true }, elements };
}

function runtimeCard(text: string, metadata: Record<string, unknown>): Record<string, unknown> | undefined {
  const model = typeof metadata.resolved_model === 'string' ? metadata.resolved_model : '';
  const usage = metadata.token_usage as { context_used?: number; context_window?: number } | undefined;
  const parts = [model.length > 512 ? `${model.slice(0, 512)}...` : model];
  if (usage?.context_used !== undefined && usage.context_window) parts.push(`ctx ${Math.round(100 * usage.context_used / usage.context_window)}%`);
  const footer = parts.filter(Boolean).join(' · '); if (!footer) return;
  return { config: { wide_screen_mode: true }, elements: [{ tag: 'markdown', content: text }, { tag: 'hr' }, { tag: 'note', elements: [{ tag: 'plain_text', content: footer }] }] };
}

function approvalStatus(decision: string): Record<string, unknown> { return { config: { update_multi: true }, elements: [{ tag: 'markdown', content: `审批已结束：${decision}` }] }; }
function chatTitle(chat: ExternalChat): string { return [chat.agentId, ...(chat.isGroup && chat.name ? [chat.name] : []), 'feishu'].join(' · '); }
