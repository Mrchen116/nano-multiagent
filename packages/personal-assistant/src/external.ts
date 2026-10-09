import type { FeishuConfiguration, FeishuMessage, ProtocolFrame } from '@nano/channels';
import { RelayDeliveryError } from '@nano/channels';
import type { RelayInput } from '@nano/product-contracts';
import { NodeStore } from './store.js';
import { ExternalStore, type ExternalChat, type ExternalOutput } from './external-store.js';

interface Connection {
  config: Pick<FeishuConfiguration, 'appId' | 'botOpenId' | 'ownerOpenId'>;
  send(chatId: string, text: string, operationId: string, card?: Record<string, unknown>): Promise<string>;
  thinking(messageId: string, reactionId?: string): Promise<string | undefined>;
  image(messageId: string, key: string): Promise<{ data: Buffer; mediaType: string }>;
  updateCard(messageId: string, card: Record<string, unknown>): Promise<void>;
}
interface Options {
  nodeId: string; ownerId: string; store: NodeStore;
  runtimeFooter?: boolean;
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
  constructor(path: string, private readonly options: Options) { this.state = new ExternalStore(path); }
  get ready() { return this.options.relay.ready; }
  add(agentId: string, connection: Connection): void { this.connections.set(agentId, connection); }
  remove(agentId: string): void { this.connections.delete(agentId); }

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
    const input: RelayInput = { relay_task_id: eventId, idempotency_key: eventId, agent_id: agentId, conversation_id: id,
      metadata: { conversation_type: message.isGroup ? 'group' : 'direct', mentioned_agent_ids: message.mentioned ? [agentId] : [],
        external_reply: eventId, source_timestamp: message.time, channel: 'feishu',
        sender_display_name: message.senderName, ...(message.contextOnly ? { context_only: true } : {}),
        ...(message.senderId === connection.config.ownerOpenId ? { owner_user_id: this.options.ownerId } : {}),
        content_parts: message.parts.map(part => part.type === 'text' ? part : { type: 'image', url: `${eventId}:${part.key}` }),
      }, message: { id: eventId, content: text, sender_type: 'user', sender_user_id: message.senderId, attachments } };
    this.state.saveInbound(eventId, id, message, input);
    const task = this.admit(eventId).finally(() => this.admissions.delete(eventId)); this.admissions.set(eventId, task); return task;
  }
  private async admit(id: string) {
    const row = this.state.inbound().find(row => row.id === id)!;
    if (row.accepted) return;
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
    this.state.updateInput(id, row.message, row.input);
    await this.options.receive(row.input); this.state.accept(id);
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
    if (type === 'node.delivery_receipt' && String(payload.relay_task_id).startsWith('external:')) {
      if (['completed', 'failed'].includes(String(payload.delivery_status))) await this.removeReaction(String(payload.relay_task_id));
      return ack(type);
    }
    if (type === 'conversation.query') {
      const local = this.query(payload); if (local) return { type: 'conversation.query.result', payload: { request_id: payload.request_id, ok: true, result: local } };
    }
    if (type === 'agent.message') {
      const target = String(payload.to).replace(/^conversation:/, ''); const chat = this.state.chat(target);
      if (chat) {
        const agentId = String(payload.from_session_id).split('|')[0];
        if (chat.agentId !== agentId) throw new Error('External target belongs to another Agent');
        const output = this.state.prepare(chat.id, String(payload.from_session_id), 'explicit');
        this.state.frame(output.id, { kind: 'turn_start', conversation_id: chat.id, agent_id: agentId, idempotency_key: output.operationId });
        const complete = { kind: 'message_completed', message_id: output.id, final_content: payload.text, delivery_status: 'completed' };
        await this.finish(output, complete);
        void this.flush().catch(this.options.onError); return ack(type, { message_id: output.platformId ?? this.state.output(output.id)!.platformId, conversation_id: chat.id });
      }
    }
    if (type !== 'node.streaming_delta') return this.options.relay.request(type, payload);
    if (payload.kind === 'turn_start') {
      const chat = this.state.chat(String(payload.conversation_id));
      if (!chat) return this.options.relay.request(type, payload);
      const output = this.state.prepare(chat.id, String(payload.idempotency_key), typeof payload.external_reply === 'string' ? payload.external_reply : undefined);
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
    if (payload.kind === 'permission_resolved') await this.resolveApproval(String(payload.request_id), String(payload.decision));
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
    const active = this.dispatches.get(output.id); if (active) return active;
    const task = (async () => {
      const current = this.state.output(output.id)!;
      if (current.state === 'confirmed') return;
      if (current.state === 'unknown') throw new RelayDeliveryError('External send outcome is unknown; it will not be automatically repeated', 'unknown');
      const chat = this.state.chat(output.chatId)!; const connection = this.connections.get(chat.agentId);
      if (!connection || connection.config.appId !== chat.appId) throw new Error('External app is unavailable');
      this.state.settle(output.id, 'sending');
      try { const messageId = await connection.send(chat.chatId, text, output.operationId, this.options.runtimeFooter && metadata ? runtimeCard(text, metadata) : undefined); this.state.settle(output.id, 'confirmed', messageId); }
      catch { this.state.settle(output.id, 'unknown'); throw new RelayDeliveryError('External send outcome is unknown; it will not be automatically repeated', 'unknown'); }
    })().finally(() => this.dispatches.delete(output.id));
    this.dispatches.set(output.id, task); return task;
  }
  private async removeReaction(id: string): Promise<void> {
    const row = this.state.inbound().find(row => row.id === id); if (!row?.reaction) return;
    const connection = this.connections.get(row.input.agent_id); if (!connection) return;
    try { await connection.thinking(row.message.messageId, row.reaction); this.state.reaction(id, null); } catch (error) { this.options.onError(error); }
  }
  private query(payload: Record<string, unknown>): Record<string, unknown> | undefined {
    const chats = this.state.chats().filter(chat => chat.agentId === payload.agent_id);
    const describe = (chat: ExternalChat) => ({ target: chat.id, id: chat.id, name: chatTitle(chat), type: chat.isGroup ? 'group' : 'direct', channel: 'feishu' });
    if (payload.action === 'describe' && Array.isArray(payload.targets) && payload.targets.every(target => chats.some(chat => chat.id === target || chat.shadowId === target))) return { conversations: chats.filter(chat => (payload.targets as string[]).includes(chat.id) || (payload.targets as string[]).includes(chat.shadowId!)).map(describe) };
    const chat = chats.find(chat => chat.id === String(payload.target).replace(/^conversation:/, '') || chat.shadowId === payload.target);
    if (!chat) return;
    if (payload.action === 'info') return describe(chat);
    if (payload.action === 'read') return { ...describe(chat), messages: this.state.inbound().filter(row => row.chatId === chat.id).slice(-50).map(row => ({ ...row.input.message })) };
  }

  private flush(): Promise<void> {
    if (!this.ready) return Promise.resolve();
    this.flushAgain = true;
    if (this.flushing) return this.flushing;
    const task = (async () => {
      while (this.flushAgain) {
        this.flushAgain = false;
      for (const row of this.state.inbound()) {
        if (row.mirror) continue;
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
            const uploaded = await this.options.im(`/im/v1/uploads?conversation_id=${encodeURIComponent(chat.shadowId!)}&agent_id=${encodeURIComponent(chat.agentId)}&file_name=image.png`, { method: 'POST', headers: { 'Content-Type': image.mediaType }, body: new Uint8Array(image.data) });
            this.state.uploaded(attachment.url, uploaded); attachments.push(uploaded);
          }
        }
        const result = await this.options.im(`/im/v1/conversations/${chat.shadowId}/messages?agent_id=${encodeURIComponent(chat.agentId)}`, json({ sender_user_id: this.options.ownerId, sender_type: 'user', sender_source_id: row.message.senderId, sender_display_name: row.input.metadata.owner_user_id ? '你' : row.message.senderName,
          content: row.message.parts.length > 1 ? row.message.parts.map(part => part.type === 'text' ? part.text : '[图片]').join('') : row.input.message.content, attachments, suppress_relay: true }, { 'Idempotency-Key': `shadow:${row.id}` })) as { id: string };
        this.state.mirrorInput(row.id, result.id);
      }
      for (const frame of this.state.pendingFrames()) {
        const output = this.state.output(frame.outputId)!; const chat = this.state.chat(output.chatId)!;
        if (!chat.shadowId) continue;
        if (frame.body.kind === 'turn_start') {
          const response = await this.options.relay.request('node.streaming_delta', { ...frame.body, node_id: this.options.nodeId, conversation_id: chat.shadowId });
          if (typeof response.payload.message_id !== 'string') throw new Error('IM mirror has no message identity');
          this.state.mirrorOutput(output.id, response.payload.message_id);
        } else {
          if (!output.imId) continue;
          await this.options.relay.request('node.streaming_delta', { ...frame.body, node_id: this.options.nodeId, message_id: output.imId });
        }
        this.state.confirmFrame(frame.id);
      }
      }
    })().finally(() => { this.flushing = undefined; }); this.flushing = task; return task;
  }
  private async approval(output: ExternalOutput, payload: Record<string, unknown>): Promise<void> {
    const chat = this.state.chat(output.chatId)!; const connection = this.connections.get(chat.agentId)!;
    if (!connection.config.ownerOpenId) return;
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
    await this.options.permission({ request_id: requestId, decision });
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
  const usage = metadata.token_usage as { prompt?: number; context_window?: number } | undefined;
  const parts = [model.length > 512 ? `${model.slice(0, 512)}...` : model];
  if (usage?.prompt !== undefined && usage.context_window) parts.push(`ctx ${Math.round(100 * usage.prompt / usage.context_window)}%`);
  const footer = parts.filter(Boolean).join(' · '); if (!footer) return;
  return { config: { wide_screen_mode: true }, elements: [{ tag: 'markdown', content: text }, { tag: 'hr' }, { tag: 'note', elements: [{ tag: 'plain_text', content: footer }] }] };
}

function approvalStatus(decision: string): Record<string, unknown> { return { config: { update_multi: true }, elements: [{ tag: 'markdown', content: `审批已结束：${decision}` }] }; }
function chatTitle(chat: ExternalChat): string { return [chat.agentId, ...(chat.isGroup && chat.name ? [chat.name] : []), 'feishu'].join(' · '); }
