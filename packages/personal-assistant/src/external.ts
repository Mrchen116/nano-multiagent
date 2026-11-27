import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { basename, isAbsolute } from 'node:path';
import type { FeishuConfiguration, FeishuMessage, ProtocolFrame, WeChatInboundMessage } from '@nano/channels';
import { RelayDeliveryError } from '@nano/channels';
import {
  decodeAgentPublication,
  decodeChatStream,
  formatLocalTime,
  type ChatAttachment,
  type ChatStreamFact,
  type RelayInput,
} from '@nano/product-contracts';
import {
  ExternalStore,
  type ExternalChat,
  type ExternalInbound,
  type ExternalOutput,
  type ExternalProvider,
  type ExternalStoredMessage,
} from './external-store.js';
import { NodeStore } from './store.js';

type CompletedMessage = Extract<ChatStreamFact, { kind: 'message_completed' }>;

interface Connection {
  supportsReactions?: boolean;
  supportsCards?: boolean;
  config: Pick<FeishuConfiguration, 'appId' | 'botOpenId' | 'ownerOpenId'>;
  send(
    chatId: string,
    text: string,
    operationId: string,
    card?: Record<string, unknown>,
    images?: { data: Buffer; mediaType: string }[],
  ): Promise<string>;
  setTyping?(chatId: string, active: boolean): Promise<void> | void;
  reaction(messageId: string, reactionId?: string, emoji?: string): Promise<string | undefined>;
  quotedSender?(chatId: string, messageId: string): Promise<string | undefined>;
  image(messageId: string, key: string): Promise<{ data: Buffer; mediaType: string }>;
  updateCard(messageId: string, card: Record<string, unknown>): Promise<void>;
}

export interface ExternalDelivery {
  provider: ExternalProvider;
  agentId: string;
  target: string;
  shadowId?: string;
  appId: string;
  sourceId: string;
  chatId: string;
  text: string;
  card?: Record<string, unknown>;
  attachments?: ChatAttachment[];
  operationId: string;
  incidentRef?: string;
  dispatch(text: string, card?: Record<string, unknown>): Promise<string>;
}

interface Options {
  nodeId: string;
  ownerId: string;
  store: NodeStore;
  runtimeFooter?: boolean | ((provider: ExternalProvider) => boolean);
  agentName?(agentId: string): string | undefined;
  personalAgent?(agentId: string): boolean;
  globalAgent?(agentId: string): boolean;
  personalDelivery?(delivery: ExternalDelivery): Promise<string | undefined>;
  ownerOnly?(agentId: string): boolean;
  attention?(input: RelayInput): boolean;
  relay: { readonly ready: boolean; request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> };
  im(path: string, options?: RequestInit): Promise<unknown>;
  receive(input: RelayInput): Promise<void>;
  permission(payload: Record<string, unknown>): Promise<void>;
  onError(error: unknown): void;
}

const PROVIDERS: readonly ExternalProvider[] = ['feishu', 'wechat'];

function chatProvider(chat: Pick<ExternalChat, 'provider' | 'sourceId'>): ExternalProvider {
  if (chat.provider === 'wechat' || chat.sourceId.startsWith('wechat:')) return 'wechat';
  return 'feishu';
}

function connKey(provider: ExternalProvider, agentId: string): string {
  return `${provider}:${agentId}`;
}

/** Platform execution continues offline; IM catches up from its own durable projection outbox. */
export class ExternalChannels {
  private readonly state: ExternalStore;
  private readonly connections = new Map<string, Connection>();
  private readonly restrictionEpoch = new Map<string, number>();
  private readonly admissions = new Map<string, Promise<void>>();
  private readonly recovering = new Map<string, Promise<void>>();
  private readonly retry = new Map<string, ReturnType<typeof setTimeout>>();
  private readonly retryDelay = new Map<string, number>();
  private stopping = false;
  private readonly dispatches = new Map<string, Promise<void>>();
  private flushing?: Promise<void>;
  private flushAgain = false;

  constructor(path: string, private readonly options: Options) {
    this.state = new ExternalStore(path);
    const relay = options.relay;
    const im = options.im;
    this.options = {
      ...options,
      relay: {
        get ready() { return relay.ready; },
        request: (type, payload) =>
          relay.request(type, type === 'node.delivery_receipt' ? payload : options.store.executionPayload(payload)),
      },
      im: (path, request) => {
        const identity = options.store.lifecycle.current();
        if (!identity) return im(path, request);
        const revision = options.store.lifecycle.assert(identity.agentId, identity.revision);
        const url = new URL(path, 'http://local');
        const headers = new Headers(request?.headers);
        headers.set('x-agent-lifecycle-revision', String(revision));
        let body = request?.body;
        if (typeof body === 'string' && headers.get('content-type') === 'application/json') {
          body = JSON.stringify({ ...JSON.parse(body), lifecycle_revision: revision });
        } else {
          url.searchParams.set('lifecycle_revision', String(revision));
        }
        return im(url.pathname + url.search, { ...request, headers, body });
      },
    };
  }

  historyConversation(agentId: string, source: string, chatId: string): string | undefined {
    if (source !== 'feishu' && source !== 'wechat') return;
    return this.state.chatForSource(agentId, chatId)?.id;
  }

  get ready() { return this.options.relay.ready; }

  add(agentId: string, connection: Connection, provider: ExternalProvider = 'feishu'): void {
    this.connections.set(connKey(provider, agentId), {
      supportsReactions: connection.supportsReactions,
      supportsCards: connection.supportsCards,
      config: connection.config,
      send: (...args) => { this.options.store.lifecycle.assert(agentId); return connection.send(...args); },
      setTyping: connection.setTyping
        ? (...args) => { this.options.store.lifecycle.assert(agentId); return connection.setTyping!(...args); }
        : undefined,
      reaction: (...args) => { this.options.store.lifecycle.assert(agentId); return connection.reaction(...args); },
      quotedSender: connection.quotedSender
        ? (...args) => { this.options.store.lifecycle.assert(agentId); return connection.quotedSender!(...args); }
        : undefined,
      image: (...args) => { this.options.store.lifecycle.assert(agentId); return connection.image(...args); },
      updateCard: (...args) => { this.options.store.lifecycle.assert(agentId); return connection.updateCard(...args); },
    });
  }

  remove(agentId: string, provider?: ExternalProvider): void {
    if (provider) {
      this.connections.delete(connKey(provider, agentId));
      return;
    }
    for (const p of PROVIDERS) this.connections.delete(connKey(p, agentId));
  }

  /** Cancel active external approvals and transient recovery timers when an Agent is disabled. */
  cancelAgent(agentId: string): void {
    clearTimeout(this.retry.get(agentId));
    this.retry.delete(agentId);
    this.retryDelay.delete(agentId);
    this.state.closeApprovalsForAgent(agentId);
    for (const chat of this.state.chats()) {
      if (chat.agentId === agentId) {
        void this.stopTyping(chat).catch(this.options.onError);
      }
    }
  }

  /** Purge local copies without contacting the external platform. */
  purgeAgent(agentId: string): void {
    this.cancelAgent(agentId);
    this.remove(agentId);
    this.state.purgeAgent(agentId);
  }

  available(agentId: string, provider?: ExternalProvider): boolean {
    if (provider) return this.connections.has(connKey(provider, agentId));
    return PROVIDERS.some(p => this.connections.has(connKey(p, agentId)));
  }

  /** A replacement App/Bot cannot resume a conversation owned by its predecessor. */
  canRecoverConversation(agentId: string, conversationId: string): boolean {
    const chat = this.state.chatById(conversationId);
    if (!chat || chat.agentId !== agentId) return false;
    const provider = chatProvider(chat);
    const connection = this.connections.get(connKey(provider, agentId));
    return !!connection && chat.appId === connection.config.appId;
  }

  receive(
    agentId: string,
    message: FeishuMessage | WeChatInboundMessage,
    provider: ExternalProvider = 'feishu',
  ): Promise<void> {
    const connection = this.connections.get(connKey(provider, agentId));
    const app = connection?.config.appId;
    if (!app) throw new Error('No channel for Agent');
    const eventKey = provider === 'feishu'
      ? `external:${agentId}:${app}:${message.messageId}`
      : `external:${agentId}:${provider}:${app}:${message.messageId}`;
    const previous = this.state.inbound(eventKey);
    if (previous) {
      this.options.store.lifecycle.assert(agentId, previous.input.lifecycle_revision ?? 1);
      return this.admitOnce(previous.id);
    }
    return this.receiveNew(agentId, message, provider, this.options.store.lifecycle.assert(agentId));
  }

  private async receiveNew(
    agentId: string,
    rawMessage: FeishuMessage | WeChatInboundMessage,
    provider: ExternalProvider,
    revision: number,
  ): Promise<void> {
    const connection = this.connections.get(connKey(provider, agentId));
    if (!connection) throw new Error('No channel for Agent');
    const appId = connection.config.appId;
    const sourceId = `${provider}:${appId}:${rawMessage.isGroup ? `group:${rawMessage.chatId}` : `dm:${rawMessage.senderId}`}`;
    const id = `external:${agentId}:${sourceId}`;
    const eventId = provider === 'feishu'
      ? `external:${agentId}:${appId}:${rawMessage.messageId}`
      : `external:${agentId}:${provider}:${appId}:${rawMessage.messageId}`;
    const active = this.admissions.get(eventId);
    if (active) return active;

    const previous = this.state.chat(id);
    this.state.saveChat({
      id,
      agentId,
      appId,
      chatId: rawMessage.chatId,
      sourceId,
      isGroup: rawMessage.isGroup,
      ...previous,
      provider,
      ...('chatName' in rawMessage && rawMessage.chatName ? { name: rawMessage.chatName } : {}),
    });

    // Persist inline binary parts (e.g. WeChat decrypted images/files) before stripping Buffer fields for SQLite JSON.
    for (const part of rawMessage.parts) {
      if (part.type === 'image' && 'data' in part && Buffer.isBuffer(part.data)) {
        const url = `${eventId}:${part.key}`;
        if (!this.state.image(url, agentId)) {
          this.state.saveImage(url, agentId, part.data, part.mediaType, 'fileName' in part ? part.fileName : undefined);
        }
      } else if (part.type === 'file' && 'data' in part && Buffer.isBuffer(part.data)) {
        const url = `${eventId}:${part.key}`;
        if (!this.state.image(url, agentId)) {
          this.state.saveImage(url, agentId, part.data, part.mediaType, part.fileName);
        }
      }
    }

    const storedMessage: ExternalStoredMessage = {
      messageId: rawMessage.messageId,
      chatId: rawMessage.chatId,
      senderId: rawMessage.senderId,
      isGroup: rawMessage.isGroup,
      mentioned: rawMessage.mentioned,
      time: rawMessage.time,
      ...('parentId' in rawMessage && rawMessage.parentId ? { parentId: rawMessage.parentId } : {}),
      ...('mentionIds' in rawMessage && rawMessage.mentionIds ? { mentionIds: rawMessage.mentionIds } : {}),
      ...('senderName' in rawMessage && rawMessage.senderName ? { senderName: rawMessage.senderName } : {}),
      ...('chatName' in rawMessage && rawMessage.chatName ? { chatName: rawMessage.chatName } : {}),
      ...('contextOnly' in rawMessage && rawMessage.contextOnly ? { contextOnly: rawMessage.contextOnly } : {}),
      parts: rawMessage.parts.map(part => {
        if (part.type === 'text') return { type: 'text', text: part.text };
        if (part.type === 'image') {
          return { type: 'image', key: part.key, ...('fileName' in part && part.fileName ? { fileName: part.fileName } : {}) };
        }
        return { type: 'file', key: part.key, fileName: part.fileName, mediaType: part.mediaType };
      }),
    };

    const text = storedMessage.parts
      .filter(part => part.type === 'text')
      .map(part => part.text)
      .join(provider === 'wechat' ? '\n\n' : '');
    const attachments = storedMessage.parts
      .filter((part): part is Extract<typeof part, { type: 'image' | 'file' }> => part.type === 'image' || part.type === 'file')
      .map(part => ({
        url: `${eventId}:${part.key}`,
        content_type: part.type === 'file' ? (part.mediaType ?? 'application/octet-stream') : 'image/png',
        file_name: part.type === 'file' ? part.fileName : (part.fileName ?? part.key),
      }));

    const ownerDirect = !storedMessage.isGroup && storedMessage.senderId === connection.config.ownerOpenId;
    const epoch = this.restrictionEpoch.get(agentId);
    const ownerOnlyAtArrival = this.options.ownerOnly?.(agentId) === true;

    let quoted: string | undefined;
    if (storedMessage.parentId && !storedMessage.contextOnly) {
      const parentKey = provider === 'feishu'
        ? `external:${agentId}:${appId}:${storedMessage.parentId}`
        : `external:${agentId}:${provider}:${appId}:${storedMessage.parentId}`;
      const original = this.state.inbound(parentKey);
      if (original?.chatId === id) quoted = original.message.senderId;
      else if (this.state.sentInChat(id, storedMessage.parentId)) quoted = connection.config.botOpenId;
      else {
        try { quoted = await connection.quotedSender?.(storedMessage.chatId, storedMessage.parentId); }
        catch (error) { this.options.onError(error); }
      }
    }
    const repliedToBot = !!quoted && quoted === connection.config.botOpenId;
    const addressedToOwner = !!connection.config.ownerOpenId
      && storedMessage.senderId !== connection.config.ownerOpenId
      && (storedMessage.mentionIds?.includes(connection.config.ownerOpenId) || quoted === connection.config.ownerOpenId);

    const instant = /^\d+$/.test(storedMessage.time) ? Number(storedMessage.time) : NaN;
    const time = Number.isSafeInteger(instant) && instant > 0 && instant <= 8.64e15 ? new Date(instant).toISOString() : null;

    let input: RelayInput = {
      lifecycle_revision: revision,
      relay_task_id: eventId,
      idempotency_key: eventId,
      agent_id: agentId,
      conversation_id: id,
      metadata: {
        conversation_type: storedMessage.isGroup ? 'group' : 'direct',
        mentioned_agent_ids: storedMessage.mentioned ? [agentId] : [],
        owner_direct: ownerDirect,
        addressed_to_agent: !storedMessage.isGroup || storedMessage.mentioned || repliedToBot,
        replied_to_owner: !!quoted && quoted === connection.config.ownerOpenId,
        addressed_to_owner: !!addressedToOwner,
        explicit_mentioned_agent_ids: storedMessage.mentioned ? [agentId] : [],
        ...(repliedToBot ? { reply_to_agent_id: agentId } : {}),
        provider_source_time: time,
        mentioned_owner: (storedMessage.mentionIds ?? []).includes(connection.config.ownerOpenId ?? ''),
        scope_skipped: !ownerDirect && (ownerOnlyAtArrival || this.restrictionEpoch.get(agentId) !== epoch || this.options.ownerOnly?.(agentId) === true),
        external_reply: eventId,
        source_timestamp: storedMessage.time,
        channel: provider,
        sender_display_name: storedMessage.senderName,
        ...(storedMessage.contextOnly ? { context_only: true } : {}),
        ...(storedMessage.senderId === connection.config.ownerOpenId ? { owner_user_id: this.options.ownerId } : {}),
        content_parts: storedMessage.parts.map(part =>
          part.type === 'text'
            ? part
            : { type: part.type === 'image' ? 'image' : 'attachment', url: `${eventId}:${part.key}` },
        ),
      },
      message: {
        id: eventId,
        content: text,
        sender_type: 'user',
        sender_user_id: storedMessage.senderId,
        attachments,
        created_at: time ?? new Date().toISOString(),
        ...(storedMessage.senderId === connection.config.ownerOpenId && this.options.store.ownerTimezone
          ? { timezone: this.options.store.ownerTimezone }
          : {}),
      },
    };

    if ((connection.supportsReactions !== false || ownerDirect) && this.options.globalAgent?.(agentId) && this.attention(input, storedMessage)) {
      input.metadata.agent_receipt = true;
    }

    const trimmedControl = text.trim();
    if (ownerDirect && (trimmedControl === '/stop' || trimmedControl === '/new')) {
      this.state.closeApprovalsForChat(id);
    }

    const isPlainSingleWeChat = provider === 'wechat'
      && ownerDirect
      && !this.options.personalAgent?.(agentId)
      && !this.options.globalAgent?.(agentId)
      && 'plainSingleText' in rawMessage
      && rawMessage.plainSingleText === true;
    const approvalCmd = isPlainSingleWeChat ? parseWeChatApprovalCommand(text) : undefined;
    const activeApproval = approvalCmd ? this.state.latestActiveApprovalForChat(id) : undefined;

    if (approvalCmd && activeApproval) {
      // Mirror the owner's reply to the IM shadow conversation without starting a model turn.
      input.metadata.scope_skipped = true;
      input = this.options.store.admitInput(input);
      this.state.saveInbound(eventId, id, storedMessage, input);
      await this.admitOnce(eventId);

      if (activeApproval.settled) {
        await connection.send(
          rawMessage.chatId,
          '该工具审批已处理，无需重复确认。',
          `approval-dup:${rawMessage.messageId}`,
        ).catch(this.options.onError);
        return;
      }

      const approvalOutput = this.state.output(activeApproval.outputId);
      this.state.settleApproval(activeApproval.requestId, 'wechat');
      await this.options.permission({
        request_id: activeApproval.requestId,
        decision: approvalCmd.decision,
        ...(approvalCmd.reason ? { reason: approvalCmd.reason } : {}),
        agent_id: agentId,
        lifecycle_revision: approvalOutput?.lifecycle_revision ?? revision,
      });
      await connection.send(
        rawMessage.chatId,
        approvalCmd.decision === 'allow_once' ? '已允许本次工具操作，继续执行中。' : '已拒绝本次工具操作。',
        `approval-ack:${activeApproval.requestId}`,
      ).catch(this.options.onError);
      return;
    }

    input = this.options.store.admitInput(input);
    this.state.saveInbound(eventId, id, storedMessage, input);
    return this.admitOnce(eventId);
  }

  private admitOnce(id: string): Promise<void> {
    const active = this.admissions.get(id);
    if (active) return active;
    const task = this.admit(id).finally(() => this.admissions.delete(id));
    this.admissions.set(id, task);
    return task;
  }

  private async admit(id: string) {
    const row = this.state.inbound(id)!;
    if (row.accepted) return;
    if (!this.options.store.lifecycle.allowed(row.input.agent_id, row.input.lifecycle_revision ?? 1)) return;
    return this.options.store.lifecycle.run(row.input.agent_id, row.input.lifecycle_revision ?? 1, () => this.admitInput(row));
  }

  private attention(input: RelayInput, message: ExternalStoredMessage): boolean {
    return !input.metadata.scope_skipped && !message.contextOnly && (this.options.attention?.(input) ?? (!message.isGroup || message.mentioned));
  }

  private async admitInput(row: ExternalInbound) {
    const id = row.id;
    const chat = this.state.chat(row.chatId)!;
    const provider = chatProvider(chat);
    const connection = this.connections.get(connKey(provider, chat.agentId));
    if (!connection) throw new Error('External connection is unavailable');

    if (connection.supportsReactions !== false && !row.reaction && !row.input.metadata.agent_receipt && this.attention(row.input, row.message)) {
      try {
        const reaction = await connection.reaction(row.message.messageId);
        if (reaction) this.state.reaction(id, reaction);
      } catch (error) {
        this.options.onError(error);
      }
    }
    if (connection.setTyping && !row.input.metadata.scope_skipped && !row.message.contextOnly) {
      void Promise.resolve(connection.setTyping(chat.chatId, true)).catch(this.options.onError);
    }

    // Persist actual image bytes before admitting the input so restart never changes its content.
    for (const part of row.message.parts) {
      if (part.type === 'image') {
        const url = `${id}:${part.key}`;
        if (!this.state.image(url, chat.agentId)) {
          const image = await connection.image(row.message.messageId, part.key);
          this.state.saveImage(url, chat.agentId, image.data, image.mediaType);
        }
      }
    }
    for (const attachment of row.input.message.attachments) {
      attachment.content_type = this.state.image(attachment.url, chat.agentId)!.mediaType;
    }
    this.options.store.lifecycle.assert(chat.agentId);
    if (this.state.inbound(id)?.input.metadata.scope_skipped) row.input.metadata.scope_skipped = true;
    this.state.updateInput(id, row.message, row.input);

    if (this.options.personalAgent?.(chat.agentId)) {
      if (!this.ready) throw new Error('Personal source authority requires the center');
      // The durable IM source event is the PA's sole ingress; output projection is independent.
      await this.mirrorInput(row);
    } else if (!row.input.metadata.scope_skipped) {
      await this.options.receive(row.input);
    }
    this.state.accept(id);
    void this.flush().catch(this.options.onError);
  }

  image(url: string, agentId: string): { data: Buffer; mediaType: string } {
    const image = this.state.image(url, agentId);
    if (!image) throw new Error('Image is outside the authenticated external input');
    return image;
  }

  attachment(url: string, agentId: string): { data: Buffer; mediaType: string; fileName?: string } {
    const item = this.state.image(url, agentId);
    if (!item) throw new Error('Image is outside the authenticated external input');
    return {
      data: item.data,
      mediaType: item.mediaType,
      ...(item.fileName ? { fileName: item.fileName } : {}),
    };
  }

  /** Stages a validated local raster image (`1B..10 MiB`, `<= 4096x4096`) in `ExternalStore` for offline-capable external delivery and later IM shadow upload. */
  async stageOutboundImage(input: {
    agentId: string;
    conversationId: string;
    operationId: string;
    index: number;
    path: string;
    lifecycleRevision: number;
    signal: AbortSignal;
  }): Promise<ChatAttachment> {
    if (!isAbsolute(input.path)) throw new Error('Use an absolute local image path');
    this.options.store.lifecycle.assert(input.agentId, input.lifecycleRevision);
    const url = `external:out:${input.operationId}:${input.index}`;
    const name = basename(input.path);
    const existing = this.state.image(url, input.agentId);
    if (existing) {
      return { url, content_type: existing.mediaType, file_name: existing.fileName ?? name };
    }

    const file = await open(input.path, constants.O_RDONLY | constants.O_NONBLOCK);
    let bytes: Buffer;
    try {
      const stat = await file.stat();
      if (!stat.isFile() || !stat.size || stat.size > 10 * 1024 * 1024) {
        throw new Error('Use a non-empty regular image file up to 10 MiB');
      }
      const scratch = Buffer.allocUnsafe(stat.size + 1);
      const { bytesRead } = await file.read(scratch, 0, scratch.length, 0);
      if (bytesRead !== stat.size) throw new Error('The image changed while reading it');
      bytes = scratch.subarray(0, bytesRead);
    } finally {
      await file.close();
    }

    const detected = inspectRasterImageBuffer(bytes);
    if (!detected) {
      throw new Error('Outbound external image must be a valid PNG, JPEG, GIF, or WebP file');
    }
    if (detected.width > 4096 || detected.height > 4096) {
      throw new Error('Outbound external image dimensions must not exceed 4096x4096');
    }

    this.state.saveImage(url, input.agentId, bytes, detected.mime, name);
    return { url, content_type: detected.mime, file_name: name };
  }

  restrictToOwner(agentId: string): void {
    this.restrictionEpoch.set(agentId, (this.restrictionEpoch.get(agentId) ?? 0) + 1);
    this.state.restrictToOwner(agentId);
  }

  async recover(agentId?: string): Promise<void> {
    if (this.stopping) return;
    const agents = agentId === undefined ? new Set(this.state.pendingAdmissions().map(row => row.agentId)) : [agentId];
    await Promise.all([...agents].map(id => this.recoverAgent(id)));
    if (!this.stopping) await this.flush();
  }

  private recoverAgent(agentId: string): Promise<void> {
    const active = this.recovering.get(agentId);
    if (active) return active;
    if (this.stopping || !this.available(agentId) || !this.options.store.lifecycle.allowed(agentId)) return Promise.resolve();
    const task = (async () => {
      for (const row of this.state.pendingAdmissions(agentId)) {
        if (this.stopping || !this.available(agentId)) return;
        const inbound = this.state.inbound(row.id);
        const chat = inbound ? this.state.chat(inbound.chatId) : undefined;
        if (chat && !this.available(agentId, chatProvider(chat))) continue;
        await this.admitOnce(row.id);
      }
      clearTimeout(this.retry.get(agentId));
      this.retry.delete(agentId);
      this.retryDelay.delete(agentId);
    })().catch(error => {
      this.options.onError(error);
      if (this.stopping || this.retry.has(agentId)) return;
      const delay = this.retryDelay.get(agentId) ?? 1000;
      this.retryDelay.set(agentId, Math.min(delay * 2, 30_000));
      const timer = setTimeout(() => {
        this.retry.delete(agentId);
        void this.recoverAgent(agentId).catch(this.options.onError);
      }, delay);
      timer.unref();
      this.retry.set(agentId, timer);
    }).finally(() => this.recovering.delete(agentId));
    this.recovering.set(agentId, task);
    return task;
  }

  async request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> {
    if (type === 'node.delivery_receipt') return this.requestAdmitted(type, payload);
    const output = this.state.output(String(payload.message_id));
    const agentId = output
      ? this.state.chat(output.chatId)!.agentId
      : typeof payload.agent_id === 'string'
        ? payload.agent_id
        : typeof payload.from_session_id === 'string'
          ? payload.from_session_id.split('|')[0]
          : this.options.store.lifecycle.current()?.agentId;
    if (!agentId) return this.requestAdmitted(type, payload);
    const revision = output?.lifecycle_revision ?? (typeof payload.lifecycle_revision === 'number' ? payload.lifecycle_revision : undefined);
    return this.options.store.lifecycle.run(agentId, revision, () => this.requestAdmitted(type, this.options.store.executionPayload(payload)));
  }

  private async requestAdmitted(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> {
    if (type === 'node.delivery_receipt' && typeof payload.external_source_message_id === 'string') {
      const status = String(payload.delivery_status);
      const source = typeof payload.agent_id === 'string' ? this.state.inboundByMirror(payload.external_source_message_id, payload.agent_id) : undefined;
      if (source && ['completed', 'failed'].includes(status)) {
        await this.removeReaction(source.id);
        const chat = this.state.chat(source.chatId);
        if (chat) await this.stopTyping(chat);
      }
      if (['sent', 'read'].includes(status)) {
        return this.options.relay.request(type, payload);
      }
      return ack(type);
    }
    if (type === 'node.delivery_receipt' && String(payload.relay_task_id).startsWith('external:')) {
      const id = String(payload.relay_task_id);
      const status = String(payload.delivery_status);
      const row = this.state.inbound(id);
      if (row?.input.metadata.agent_receipt) {
        if (['sent', 'read'].includes(status)) {
          await this.showReceipt(row, status === 'read' ? 'read' : 'received');
          if (row.input.metadata.owner_direct && row.input.metadata.conversation_type === 'direct') {
            this.state.recordImReceiptStage(id, status === 'read' ? 'read' : 'sent');
            void this.flush().catch(this.options.onError);
          }
        } else if (['completed', 'failed'].includes(status)) {
          const chat = this.state.chat(row.chatId);
          if (chat) await this.stopTyping(chat);
        }
      } else if (['completed', 'failed'].includes(status)) {
        await this.removeReaction(id);
        if (row) {
          const chat = this.state.chat(row.chatId);
          if (chat) await this.stopTyping(chat);
        }
      }
      return ack(type);
    }
    if (type === 'node.system_message') {
      const target = String(payload.conversation_id);
      const chat = target.startsWith('external:') ? this.state.chat(target) : undefined;
      if (chat) {
        const notice = payload.system_notice as { source_agent_id: string };
        if (notice.source_agent_id !== chat.agentId) throw new Error('Knowledge notice belongs to another Agent');
        const output = this.state.prepare(chat.id, String(payload.idempotency_key), 'explicit', Number(payload.lifecycle_revision ?? 1));
        await this.publish(output, String(payload.text));
        this.state.frame(output.id, { ...payload, kind: 'system_notice' });
        void this.flush().catch(this.options.onError);
        return ack(type, { message_id: this.state.output(output.id)!.platformId });
      }
    }
    if (['pa.source.admit', 'pa.incident.report'].includes(type) && String(payload.source_message_id).startsWith('external:')) {
      const source = typeof payload.source_message_id === 'string' ? this.state.inbound(payload.source_message_id) : undefined;
      const chat = source && source.input.agent_id === payload.agent_id ? this.state.chat(source.chatId) : undefined;
      if (!source?.mirror || !chat?.shadowId) throw new Error('Personal source is not yet synchronized');
      return this.options.relay.request(type, { ...payload, source_message_id: source.mirror, conversation_id: chat.shadowId });
    }
    if (type === 'task.execution.pause' && String(payload.control_message_id).startsWith('external:')) {
      const source = typeof payload.control_message_id === 'string' ? this.state.inbound(payload.control_message_id) : undefined;
      const chat = source && source.input.agent_id === payload.agent_id ? this.state.chat(source.chatId) : undefined;
      if (!source || !chat) {
        return {
          type: 'task.execution.pause.result',
          payload: {
            request_id: payload.request_id,
            ok: false,
            error: { code: 'invalid_human_control', message: 'Unknown external stop input' },
          },
        };
      }
      if (!this.ready) {
        if (!chat.shadowId && !this.options.globalAgent?.(chat.agentId) && !this.options.personalAgent?.(chat.agentId)) {
          return {
            type: 'task.execution.pause.result',
            payload: { request_id: payload.request_id, ok: true, result: { paused: 0, offline_unmirrored: true } },
          };
        }
        throw new Error('External stop requires center synchronization');
      }
      if (!source.mirror) await this.mirrorInput(source);
      const refreshedSource = this.state.inbound(source.id);
      const refreshedChat = this.state.chat(chat.id);
      if (!refreshedSource?.mirror || !refreshedChat?.shadowId) {
        throw new Error('External stop input has not been mirrored');
      }
      return this.options.relay.request(type, {
        ...payload,
        control_message_id: refreshedSource.mirror,
        ...(payload.conversation_id !== undefined || (!this.options.globalAgent?.(chat.agentId) && !this.options.personalAgent?.(chat.agentId))
          ? { conversation_id: payload.conversation_id ?? refreshedChat.shadowId }
          : {}),
      });
    }
    if (type === 'agent.message.status' && typeof payload.agent_id === 'string' && typeof payload.operation_id === 'string') {
      const existing = this.state.outputByOperation(`${payload.agent_id}|tool_call:${payload.operation_id}`);
      if (existing) {
        const chat = this.state.chat(existing.chatId);
        if (chat?.agentId === payload.agent_id) {
          if (existing.state === 'confirmed' && (existing.platformId || existing.imId)) {
            return ack(type, {
              found: true,
              message_id: existing.platformId ?? existing.imId,
              conversation_id: existing.reply ? chat.id : (chat.shadowId ?? chat.id),
            });
          }
          return ack(type, { found: false });
        }
      }
    }
    if (type === 'task_graph.command' && ['create', 'apply', 'delete'].includes(String(payload.action)) && String(payload.source_message_id).startsWith('external:')) {
      const source = typeof payload.source_message_id === 'string' ? this.state.inbound(payload.source_message_id) : undefined;
      if (!source?.mirror || source.input.agent_id !== payload.agent_id) {
        return {
          type: 'task_graph.result',
          payload: {
            request_id: payload.request_id,
            ok: false,
            error: { code: 'source_unavailable', message: 'The external source message has not been mirrored to IM.' },
          },
        };
      }
      return this.options.relay.request(type, { ...payload, source_message_id: source.mirror });
    }
    if (type === 'conversation.query') {
      const local = this.query(payload);
      if (local) return { type: 'conversation.query.result', payload: { request_id: payload.request_id, ok: true, result: local } };
      if (payload.target && (payload.action === 'search' || (payload.action === 'read' && (payload.message_id || payload.around_message_id)))) {
        const target = String(payload.target).replace(/^conversation:/, '');
        const chat = this.state.chatsForTargets(String(payload.agent_id), [target])[0];
        if (chat) {
          if (!chat.shadowId) return { type: 'conversation.query.result', payload: { request_id: payload.request_id, ok: false, error: 'External source is not synchronized to IM' } };
          return this.options.relay.request(type, { ...payload, target: chat.shadowId });
        }
      }
    }
    if (type === 'agent.message') {
      const publication = decodeAgentPublication(payload);
      const target = String(publication.to).replace(/^conversation:/, '');
      const chat = this.state.chat(target);
      if (chat) {
        if (publication.reply_to_message_id !== undefined) throw new Error('Quoted replies require a Nano IM destination');
        const agentId = String(publication.from_session_id).split('|')[0];
        if (chat.agentId !== agentId) throw new Error('External target belongs to another Agent');
        const replyMode = publication.internal_shadow_only ? undefined : 'explicit';
        const output = this.state.prepare(chat.id, String(publication.from_session_id), replyMode, Number(publication.lifecycle_revision ?? 1));
        this.state.frame(output.id, { lifecycle_revision: output.lifecycle_revision, kind: 'turn_start', conversation_id: chat.id, agent_id: agentId, idempotency_key: output.operationId });
        const complete: CompletedMessage = {
          lifecycle_revision: output.lifecycle_revision,
          kind: 'message_completed',
          message_id: output.id,
          final_content: publication.text,
          ...(publication.attachments?.length ? { attachments: publication.attachments } : {}),
          pa_incident_ref: publication.pa_incident_ref,
          delivery_status: 'completed',
        };
        await this.finish(output, complete);
        if (publication.internal_shadow_only) {
          await this.flush();
          const settled = this.state.output(output.id)!;
          if (settled.imId) this.state.settle(output.id, 'confirmed', settled.imId);
          return ack(type, { message_id: settled.imId ?? output.id, conversation_id: chat.shadowId ?? chat.id });
        }
        void this.flush().catch(this.options.onError);
        return ack(type, { message_id: output.platformId ?? this.state.output(output.id)!.platformId, conversation_id: chat.id });
      }
      return this.options.relay.request(type, { ...publication });
    }
    if (type !== 'node.streaming_delta') return this.options.relay.request(type, payload);
    const stream = decodeChatStream(payload);
    if (stream.kind === 'run_terminal_reconcile') return this.forwardStream(stream);
    if (stream.kind === 'turn_start') {
      const chat = this.state.chat(String(stream.conversation_id));
      if (!chat) return this.forwardStream(stream);
      const output = this.state.prepare(
        chat.id,
        String(stream.idempotency_key),
        typeof stream.external_reply === 'string' ? stream.external_reply : undefined,
        Number(stream.lifecycle_revision ?? 1),
      );
      this.state.frame(output.id, stream);
      void this.flush().catch(this.options.onError);
      return ack(type, { message_id: output.id, conversation_id: chat.id });
    }
    const output = this.state.output(String(stream.message_id));
    if (!output) return this.forwardStream(stream);
    if (stream.kind === 'message_completed') {
      const source = stream.external_reply;
      if (typeof source === 'string' && this.state.inbound(source)?.chatId !== output.chatId) {
        throw new Error('External reply source belongs to another conversation');
      }
      const final = source === undefined ? output : this.state.finalReply(output, source);
      this.state.closeApprovalsForOutput(output.id);
      if (final.id !== output.id) this.state.closeApprovalsForOutput(final.id);
      await this.finish(final, stream);
      if (final.reply) await this.removeReaction(final.reply);
      if (output.reply && output.reply !== final.reply) await this.removeReaction(output.reply);
    } else {
      this.state.frame(output.id, stream);
      if (stream.kind === 'message_discarded') {
        this.state.closeApprovalsForOutput(output.id);
        const chat = this.state.chat(output.chatId);
        if (chat) await this.stopTyping(chat);
      }
    }
    if (stream.kind === 'permission_request' && output.reply) await this.approval(output, stream);
    if (stream.kind === 'permission_resolved') await this.resolveApproval(String(stream.permission_request?.request_id ?? stream.request_id), String(stream.decision));
    void this.flush().catch(this.options.onError);
    return ack(type);
  }

  private forwardStream(payload: ChatStreamFact): Promise<ProtocolFrame> {
    return this.options.relay.request('node.streaming_delta', { ...payload });
  }

  private async stopTyping(chat: ExternalChat): Promise<void> {
    const provider = chatProvider(chat);
    const connection = this.connections.get(connKey(provider, chat.agentId));
    if (!connection?.setTyping) return;
    await Promise.resolve(connection.setTyping(chat.chatId, false)).catch(this.options.onError);
  }

  private footerEnabled(provider: ExternalProvider): boolean {
    if (typeof this.options.runtimeFooter === 'function') return this.options.runtimeFooter(provider);
    return Boolean(this.options.runtimeFooter);
  }

  private async finish(output: ExternalOutput, payload: CompletedMessage): Promise<void> {
    const chat = this.state.chat(output.chatId)!;
    const provider = chatProvider(chat);
    const enrichedPayload = this.extractInlineDataImages(output, chat.agentId, payload);
    try {
      if (output.reply && (String(enrichedPayload.final_content ?? '').trim() || enrichedPayload.attachments?.length)) {
        await this.publish(output, String(enrichedPayload.final_content ?? ''), enrichedPayload);
      }
      this.state.frame(output.id, enrichedPayload);
      await this.stopTyping(chat);
    } catch (error) {
      await this.stopTyping(chat);
      if (error instanceof RelayDeliveryError && error.delivery === 'unknown') {
        const providerLabel = provider === 'wechat' ? '微信' : '飞书';
        this.state.frame(output.id, {
          ...enrichedPayload,
          delivery_status: 'failed',
          external_delivery_status: 'unknown',
          final_content: `${enrichedPayload.final_content ?? ''}\n\n${providerLabel}发送结果未知，未自动重发。`,
        });
        if (output.reply) await this.removeReaction(output.reply);
        void this.flush().catch(this.options.onError);
      }
      throw error;
    }
  }

  private extractInlineDataImages(output: ExternalOutput, agentId: string, payload: CompletedMessage): CompletedMessage {
    const rawText = payload.final_content ?? '';
    if (!rawText.includes('data:image/')) return payload;
    const existing = payload.attachments ?? [];
    const inlineAttachments: ChatAttachment[] = [];
    const strippedSpans: [number, number][] = [];
    const dataUriRe = /!\[[^\]\n]*\]\((data:image\/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=\s]+))\)/gi;
    let match: RegExpExecArray | null;
    while ((match = dataUriRe.exec(rawText)) !== null) {
      if (existing.length + inlineAttachments.length >= 5) break;
      const b64 = match[3]!.replace(/\s+/g, '');
      const buf = Buffer.from(b64, 'base64');
      if (buf.length === 0 || buf.length > 10 * 1024 * 1024) continue;
      const detected = inspectRasterImageBuffer(buf);
      if (!detected || detected.width > 4096 || detected.height > 4096) continue;
      const idx = inlineAttachments.length;
      const ext = detected.mime === 'image/jpeg' ? '.jpg' : `.${detected.mime.slice(6)}`;
      const fileName = `inline-${idx + 1}${ext}`;
      const url = `external:out:${output.operationId}:inline:${idx}`;
      this.state.saveImage(url, agentId, buf, detected.mime, fileName);
      inlineAttachments.push({ url, content_type: detected.mime, file_name: fileName });
      strippedSpans.push([match.index, match.index + match[0].length]);
    }
    if (!inlineAttachments.length) return payload;
    let cleanedText = '';
    let cursor = 0;
    for (const [start, end] of strippedSpans) {
      cleanedText += rawText.slice(cursor, start);
      cursor = end;
    }
    cleanedText += rawText.slice(cursor);
    cleanedText = cleanedText.replace(/\n{3,}/g, '\n\n').trim();
    return {
      ...payload,
      final_content: cleanedText,
      attachments: [...existing, ...inlineAttachments],
    };
  }

  private async publish(output: ExternalOutput, text: string, metadata?: CompletedMessage): Promise<void> {
    const agentId = this.state.chat(output.chatId)!.agentId;
    return this.options.store.lifecycle.run(agentId, output.lifecycle_revision, () => this.publishAdmitted(output, text, metadata));
  }

  private async publishAdmitted(output: ExternalOutput, text: string, metadata?: CompletedMessage): Promise<void> {
    const active = this.dispatches.get(output.id);
    if (active) return active;
    const task = (async () => {
      const current = this.state.output(output.id)!;
      if (current.state === 'confirmed') return;
      if (current.state === 'unknown') {
        throw new RelayDeliveryError('External send outcome is unknown; it will not be automatically repeated', 'unknown');
      }
      const chat = this.state.chat(output.chatId)!;
      const provider = chatProvider(chat);
      const connection = this.connections.get(connKey(provider, chat.agentId));
      if (!connection || connection.config.appId !== chat.appId) throw new Error('External app is unavailable');

      const useFooter = this.footerEnabled(provider) && !!metadata;
      const card = useFooter && connection.supportsCards !== false && metadata ? runtimeCard(text, metadata) : undefined;
      const bodyWithFooter = useFooter && connection.supportsCards === false && metadata
        ? appendPlainRuntimeFooter(text, metadata)
        : text;

      const outboundImages: { data: Buffer; mediaType: string }[] = [];
      for (const att of metadata?.attachments ?? []) {
        const attUrl = att.url;
        if (attUrl?.startsWith('external:')) {
          const img = this.state.image(attUrl, chat.agentId);
          if (img) outboundImages.push({ data: img.data, mediaType: img.mediaType });
        }
      }

      const dispatch = async (body: string, frozenCard?: Record<string, unknown>) => {
        this.options.store.lifecycle.assert(chat.agentId, output.lifecycle_revision);
        this.state.settle(output.id, 'sending');
        try {
          const id = await connection.send(
            chat.chatId,
            body,
            output.operationId,
            frozenCard,
            outboundImages.length ? outboundImages : undefined,
          );
          this.state.settle(output.id, 'confirmed', id);
          return id;
        } catch {
          this.state.settle(output.id, 'unknown');
          throw new RelayDeliveryError('External send outcome is unknown; it will not be automatically repeated', 'unknown');
        }
      };

      if (this.options.personalAgent?.(chat.agentId)) {
        if (!this.options.personalDelivery) throw new Error('Personal delivery adapter unavailable');
        const id = await this.options.personalDelivery({
          provider,
          agentId: chat.agentId,
          target: chat.id,
          shadowId: chat.shadowId,
          appId: chat.appId,
          sourceId: chat.sourceId,
          chatId: chat.chatId,
          text: bodyWithFooter,
          card,
          ...(metadata?.attachments?.length ? { attachments: metadata.attachments } : {}),
          operationId: output.operationId,
          incidentRef: typeof metadata?.pa_incident_ref === 'string' ? metadata.pa_incident_ref : undefined,
          dispatch,
        });
        if (!id) throw new Error('Personal delivery has no provider receipt');
        this.state.settle(output.id, 'confirmed', id);
      } else {
        await dispatch(bodyWithFooter, card);
      }
    })().finally(() => this.dispatches.delete(output.id));
    this.dispatches.set(output.id, task);
    return task;
  }

  private async showReceipt(row: ExternalInbound, stage: 'received' | 'read'): Promise<void> {
    if (row.reactionStage === stage || row.reactionStage === 'read') return;
    const { agent_id: agentId, lifecycle_revision: revision } = row.input;
    if (!this.options.store.lifecycle.allowed(agentId, revision ?? 1)) return;
    const chat = this.state.chat(row.chatId);
    if (!chat) return;
    const provider = chatProvider(chat);
    const connection = this.connections.get(connKey(provider, agentId));
    if (connection?.supportsReactions === false) return;
    if (!connection || connection.config.appId !== chat.appId) {
      throw new RelayDeliveryError('External app is unavailable', 'not-sent');
    }
    await this.options.store.lifecycle.run(agentId, revision, async () => {
      if (row.reaction) {
        await connection.reaction(row.message.messageId, row.reaction);
        this.state.reaction(row.id, null);
      }
      const reaction = await connection.reaction(row.message.messageId, undefined, stage === 'read' ? 'Get' : 'CRY');
      if (!reaction) throw new Error('Feishu returned no reaction identity');
      this.state.reaction(row.id, reaction, stage);
    });
  }

  private async removeReaction(id: string): Promise<void> {
    const row = this.state.inbound(id);
    if (!row?.reaction || row.input.metadata.agent_receipt) return;
    const chat = this.state.chat(row.chatId);
    const provider = chat ? chatProvider(chat) : 'feishu';
    const connection = this.connections.get(connKey(provider, row.input.agent_id));
    if (!connection || connection.supportsReactions === false || !this.options.store.lifecycle.allowed(row.input.agent_id, row.input.lifecycle_revision ?? 1)) return;
    try {
      await connection.reaction(row.message.messageId, row.reaction);
      this.state.reaction(id, null);
    } catch (error) {
      this.options.onError(error);
    }
  }

  private query(payload: Record<string, unknown>): Record<string, unknown> | undefined {
    const describe = (chat: ExternalChat) => {
      const provider = chatProvider(chat);
      const connection = this.connections.get(connKey(provider, chat.agentId));
      const owner = connection?.config.appId === chat.appId ? connection.config.ownerOpenId : undefined;
      return {
        target: chat.id,
        id: chat.id,
        name: chatTitle(chat, this.options.agentName),
        type: chat.isGroup ? 'group' : 'direct',
        channel: provider,
        owner_recipient: !!owner && !chat.isGroup && chat.sourceId === `${provider}:${chat.appId}:dm:${owner}`,
      };
    };
    if (payload.action === 'describe' && Array.isArray(payload.targets) && payload.targets.every(target => typeof target === 'string')) {
      const chats = this.state.chatsForTargets(String(payload.agent_id), payload.targets);
      if (payload.targets.every(target => chats.some(chat => chat.id === target || chat.shadowId === target))) {
        return { conversations: chats.map(describe) };
      }
    }
    const chat = this.state.chat(String(payload.target).replace(/^conversation:/, ''), String(payload.target));
    if (!chat || chat.agentId !== payload.agent_id) return;
    const provider = chatProvider(chat);
    if (payload.action === 'info') return describe(chat);
    if (payload.action === 'read' && !payload.message_id && !payload.around_message_id) {
      return {
        ...describe(chat),
        history_scope: 'external_cache',
        messages: this.state.recentInbound(chat.id).map(row => ({
          ...row.input.message,
          ...(row.input.message.created_at ? { created_at: formatLocalTime(row.input.message.created_at, row.input.message.timezone) } : {}),
          sender: { name: row.message.senderName, kind: 'external', channel: provider, source_id: row.message.senderId },
          source: { target: chat.id, name: chatTitle(chat, this.options.agentName), ...(row.mirror ? { message_id: row.mirror } : {}) },
          partial: { status: 'unknown' },
        })),
      };
    }
  }

  private flush(): Promise<void> {
    if (!this.ready) return Promise.resolve();
    this.flushAgain = true;
    if (this.flushing) return this.flushing;
    const task = (async () => {
      while (this.flushAgain) {
        this.flushAgain = false;
        for (const row of this.state.pendingMirrors()) await this.mirrorInput(row);
        for (const row of this.state.pendingImReceipts()) {
          const stage = row.imReceiptStage;
          if (!stage || !row.mirror || !this.options.store.lifecycle.allowed(row.input.agent_id, row.input.lifecycle_revision ?? 1)) continue;
          try {
            await this.options.store.lifecycle.run(row.input.agent_id, row.input.lifecycle_revision ?? 1, async () => {
              await this.options.relay.request('node.delivery_receipt', {
                node_id: this.options.nodeId,
                agent_id: row.input.agent_id,
                external_source_message_id: row.mirror,
                delivery_status: stage,
              });
              this.state.confirmImReceipt(row.id, stage);
            });
          } catch (error) {
            if (error instanceof RelayDeliveryError && error.delivery === 'rejected'
              && /scope_not_allowed|agent_not_accessible|conversation_id not found|external source message not found|node_not_registered|gateway_owner_mismatch/.test(error.code ?? '')) {
              this.state.confirmImReceipt(row.id, stage);
            }
            this.options.onError(error);
          }
        }
        for (const frame of this.state.pendingFrames()) {
          const output = this.state.output(frame.outputId)!;
          const chat = this.state.chat(output.chatId)!;
          if (!chat.shadowId || !this.options.store.lifecycle.allowed(chat.agentId, output.lifecycle_revision)) continue;
          frame.body = { ...frame.body, agent_id: chat.agentId, lifecycle_revision: output.lifecycle_revision };
          try {
            await this.options.store.lifecycle.run(chat.agentId, output.lifecycle_revision, async () => {
              if (frame.body.kind === 'system_notice') {
                const { kind: _, ...payload } = frame.body;
                const response = await this.options.relay.request('node.system_message', { ...payload, node_id: this.options.nodeId, conversation_id: chat.shadowId });
                if (typeof response.payload.message_id !== 'string') throw new Error('Knowledge projection has no message identity');
                this.state.mirrorOutput(output.id, response.payload.message_id);
              } else if (frame.body.kind === 'turn_start') {
                const response = await this.forwardStream({ ...frame.body, node_id: this.options.nodeId, conversation_id: chat.shadowId });
                if (typeof response.payload.message_id !== 'string') throw new Error('IM mirror has no message identity');
                this.state.mirrorOutput(output.id, response.payload.message_id);
              } else {
                if (!output.imId) return;
                let streamBody = frame.body;
                if (streamBody.kind === 'message_completed' && streamBody.attachments?.length) {
                  const uploadedAttachments: ChatAttachment[] = [];
                  for (const att of streamBody.attachments) {
                    const attUrl = att.url;
                    if (!attUrl) continue;
                    if (!attUrl.startsWith('external:')) {
                      uploadedAttachments.push(att);
                      continue;
                    }
                    const blob = this.state.image(attUrl, chat.agentId);
                    if (!blob) continue;
                    if (blob.uploaded) {
                      uploadedAttachments.push(JSON.parse(blob.uploaded) as ChatAttachment);
                    } else {
                      const fileName = att.file_name || blob.fileName || 'image.png';
                      const uploaded = await this.options.im(
                        `/im/v1/conversations/${encodeURIComponent(chat.shadowId!)}/images?agent_id=${encodeURIComponent(chat.agentId)}&file_name=${encodeURIComponent(fileName)}&screenshot=1`,
                        {
                          method: 'POST',
                          headers: { 'Content-Type': blob.mediaType, 'Idempotency-Key': `shadow-out:${attUrl}` },
                          body: new Uint8Array(blob.data),
                        },
                      ) as ChatAttachment;
                      this.state.uploaded(attUrl, uploaded);
                      uploadedAttachments.push(uploaded);
                    }
                  }
                  streamBody = {
                    ...streamBody,
                    attachments: uploadedAttachments,
                  };
                }
                await this.forwardStream(
                  streamBody.kind === 'run_terminal_reconcile'
                    ? { ...streamBody, node_id: this.options.nodeId }
                    : { ...streamBody, node_id: this.options.nodeId, message_id: output.imId },
                );
              }
              this.state.confirmFrame(frame.id);
            });
          } catch (error) {
            this.options.onError(error);
          }
        }
      }
    })().finally(() => { this.flushing = undefined; });
    this.flushing = task;
    return task;
  }

  private async mirrorInput(row: ExternalInbound): Promise<void> {
    if (row.mirror || !this.options.store.lifecycle.allowed(row.input.agent_id, row.input.lifecycle_revision ?? 1)) return;
    return this.options.store.lifecycle.run(row.input.agent_id, row.input.lifecycle_revision ?? 1, () => this.mirrorAdmitted(row));
  }

  private async mirrorAdmitted(row: ExternalInbound): Promise<void> {
    if (row.mirror) return;
    const chat = this.state.chat(row.chatId)!;
    const provider = chatProvider(chat);
    if (!chat.shadowId) {
      const result = await this.options.im('/im/v1/conversations/external/find-or-create', json({
        external_source: provider,
        external_chat_id: chat.sourceId,
        agent_id: chat.agentId,
        title: chatTitle(chat, this.options.agentName),
        is_group: chat.isGroup,
        participant_ids: [`user:${this.options.ownerId}`, `agent:${chat.agentId}`],
      })) as { id: string };
      chat.shadowId = result.id;
      this.state.saveChat(chat);
      this.options.store.aliasConversation(chat.agentId, result.id, chat.id);
    }
    const attachments = [];
    for (const attachment of row.input.message.attachments) {
      const blob = this.state.image(attachment.url, chat.agentId)!;
      if (blob.uploaded) {
        attachments.push(JSON.parse(blob.uploaded));
      } else {
        const fileName = attachment.file_name || (blob.mediaType.startsWith('image/') ? 'image.png' : 'attachment.bin');
        const uploaded = await this.options.im(
          `/im/v1/uploads?conversation_id=${encodeURIComponent(chat.shadowId!)}&agent_id=${encodeURIComponent(chat.agentId)}&file_name=${encodeURIComponent(fileName)}${this.options.personalAgent?.(chat.agentId) ? '&external_incoming=1' : ''}`,
          { method: 'POST', headers: { 'Content-Type': blob.mediaType }, body: new Uint8Array(blob.data) },
        );
        this.state.uploaded(attachment.url, uploaded);
        attachments.push(uploaded);
      }
    }
    const content = provider === 'wechat'
      ? row.input.message.content
      : (row.message.parts.length > 1
        ? row.message.parts.map(part => part.type === 'text' ? part.text : '[图片]').join('')
        : row.input.message.content);
    const result = await this.options.im(
      `/im/v1/conversations/${chat.shadowId}/${this.options.personalAgent?.(chat.agentId) ? 'external-incoming' : 'messages'}?agent_id=${encodeURIComponent(chat.agentId)}`,
      json({
        sender_user_id: this.options.ownerId,
        sender_type: 'user',
        sender_source_id: row.message.senderId,
        sender_display_name: row.input.metadata.owner_user_id ? '你' : row.message.senderName,
        content,
        attachments,
        provider_facts: {
          source_time: row.input.metadata.provider_source_time ?? null,
          mentioned_bot: row.message.mentioned,
          mentioned_owner: row.input.metadata.mentioned_owner === true,
          replied_to_owner: row.input.metadata.replied_to_owner === true,
          replied_to_bot: row.input.metadata.reply_to_agent_id === chat.agentId,
          context_only: row.message.contextOnly === true,
          scope_skipped: this.state.inbound(row.id)?.input.metadata.scope_skipped === true,
        },
        created_at: row.input.message.created_at,
        timezone: row.input.message.timezone,
        suppress_relay: true,
      }, { 'Idempotency-Key': `shadow:${row.id}` }),
    ) as { id: string };
    this.state.mirrorInput(row.id, result.id);
  }

  private async approval(output: ExternalOutput, payload: Extract<ChatStreamFact, { kind: 'permission_request' }>): Promise<void> {
    const chat = this.state.chat(output.chatId)!;
    const provider = chatProvider(chat);
    const connection = this.connections.get(connKey(provider, chat.agentId));
    if (this.options.personalAgent?.(chat.agentId) || !connection?.config.ownerOpenId) return;
    const request = payload.permission_request ?? payload;
    const id = String(request.request_id);
    const prior = this.state.approvalForRequest(id);
    if (prior) return;
    this.state.approval(id, output.id, request);
    if (connection.supportsCards === false) {
      const prompt = wechatApprovalPrompt(request);
      const platformId = await connection.send(chat.chatId, prompt, `approval:${id}`);
      this.state.approval(id, output.id, request, platformId);
      return;
    }
    const card = approvalCard(id, request, chat.isGroup);
    const platformId = await connection.send(chat.chatId, '', `approval:${id}`, card);
    this.state.approval(id, output.id, request, platformId);
  }

  async card(agentId: string, value: unknown): Promise<unknown> {
    const event = value as { operator?: { open_id?: string }; context?: { open_message_id?: string }; action?: { value?: { request_id?: string; decision?: string } } };
    const requestId = event.action?.value?.request_id;
    const decision = event.action?.value?.decision;
    const pending = requestId ? this.state.approvalForRequest(requestId) : undefined;
    const connection = this.connections.get(connKey('feishu', agentId));
    if (pending?.settled) return { toast: { type: 'info', content: '审批已结束' }, card: { type: 'raw', data: approvalStatus('已处理') } };
    if (!pending || !connection?.config.ownerOpenId || event.operator?.open_id !== connection.config.ownerOpenId || pending.platformId !== event.context?.open_message_id) {
      return { toast: { type: 'error', content: '此审批不可用或无权操作' } };
    }
    const output = this.state.output(pending.outputId)!;
    if (this.state.chat(output.chatId)!.agentId !== agentId || !['allow_once', 'deny'].includes(decision ?? '')) {
      return { toast: { type: 'error', content: '无效审批' } };
    }
    this.options.store.lifecycle.assert(agentId, output.lifecycle_revision);
    await this.options.permission({ request_id: requestId, decision, agent_id: agentId, lifecycle_revision: output.lifecycle_revision });
    this.state.settleApproval(requestId!);
    return { toast: { type: 'success', content: '已提交审批决定' }, card: { type: 'raw', data: approvalStatus(decision!) } };
  }

  private async resolveApproval(requestId: string, decision: string): Promise<void> {
    const pending = requestId ? this.state.approvalForRequest(requestId) : undefined;
    if (!pending) return;
    const alreadySettled = pending.settled === 1;
    this.state.settleApproval(requestId, 'im');
    const output = this.state.output(pending.outputId)!;
    const chat = this.state.chat(output.chatId)!;
    const provider = chatProvider(chat);
    const connection = this.connections.get(connKey(provider, chat.agentId));
    if (!connection) return;
    if (connection.supportsCards === false) {
      if (!alreadySettled && provider === 'wechat') {
        const label = decision === 'allow_once' || decision === 'allow' ? '已允许' : '已拒绝';
        await connection.send(
          chat.chatId,
          `工具审批已在内部 IM 处理（${label}）。`,
          `approval-im:${requestId}`,
        ).catch(this.options.onError);
      }
      return;
    }
    if (!pending.platformId) return;
    await connection.updateCard(pending.platformId, approvalStatus(decision));
  }

  async stop(): Promise<void> {
    this.stopping = true;
    for (const timer of this.retry.values()) clearTimeout(timer);
    await Promise.allSettled([...this.recovering.values(), ...this.admissions.values(), ...this.dispatches.values(), this.flushing]);
    this.state.close();
  }
}

function ack(type: string, payload: Record<string, unknown> = {}): ProtocolFrame {
  return { type: 'ack', payload: { message_type: type, ...payload } };
}

function json(body: unknown, headers: Record<string, string> = {}): RequestInit {
  return { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) };
}

function approvalCard(id: string, request: Record<string, unknown>, group: boolean): Record<string, unknown> {
  const elements: unknown[] = [{ tag: 'markdown', content: `**${request.tool_name}**\n${group ? '需要 owner 审批；请在内部 IM 查看完整输入' : request.reason ?? '需要审批'}` }];
  for (const [key, value] of Object.entries((request.tool_input ?? {}) as Record<string, unknown>)) {
    const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    const lines = text.split('\n').length;
    if (group) {
      elements.push({ tag: 'markdown', content: `**${key}**：请在内部 IM 查看完整输入` });
    } else if (text.length > 180 || lines > 2) {
      elements.push({
        tag: 'collapsible_panel',
        expanded: false,
        header: { title: { tag: 'plain_text', content: `${key} · ${lines} 行 · ${text.slice(0, 100)}` } },
        elements: [{ tag: 'div', text: { tag: 'plain_text', content: text.slice(0, 20000) } }],
      });
    } else {
      elements.push({
        tag: 'column_set',
        background_style: 'grey-50',
        columns: [{ tag: 'column', width: 'weighted', weight: 1, elements: [{ tag: 'div', text: { tag: 'plain_text', content: `${key} · ${lines} 行\n${text}` } }] }],
      });
    }
  }
  elements.push({
    tag: 'action',
    actions: [
      { tag: 'button', text: { tag: 'plain_text', content: '允许一次' }, type: 'primary', value: { request_id: id, decision: 'allow_once' } },
      { tag: 'button', text: { tag: 'plain_text', content: '拒绝' }, value: { request_id: id, decision: 'deny' } },
    ],
  });
  return { config: { wide_screen_mode: true, update_multi: true }, elements };
}

function summarizeApprovalInput(toolInput: unknown): string | undefined {
  if (!toolInput || typeof toolInput !== 'object' || Array.isArray(toolInput)) return undefined;
  const entries = Object.entries(toolInput as Record<string, unknown>);
  if (!entries.length) return undefined;
  const lines: string[] = [];
  for (const [key, value] of entries.slice(0, 6)) {
    const raw = typeof value === 'string' ? value : JSON.stringify(value);
    if (raw === undefined) continue;
    const compact = raw.replace(/\s+/g, ' ').trim();
    const chars = Array.from(compact);
    const clipped = chars.length > 120 ? `${chars.slice(0, 120).join('')}…` : compact;
    lines.push(`${key}: ${clipped}`);
  }
  if (entries.length > 6) lines.push(`…共 ${entries.length} 项参数`);
  if (!lines.length) return undefined;
  const joined = lines.join('\n');
  const totalChars = Array.from(joined);
  return totalChars.length > 300 ? `${totalChars.slice(0, 300).join('')}…` : joined;
}

function wechatApprovalPrompt(request: Record<string, unknown>): string {
  const toolName = String(request.tool_name ?? 'tool');
  const reason = typeof request.reason === 'string' && request.reason.trim() ? request.reason.trim() : '需要人工确认受控操作';
  const inputSummary = summarizeApprovalInput(request.tool_input);
  const summaryBlock = inputSummary ? `\n参数摘要：\n${inputSummary}` : '';
  return `【待确认操作】${toolName}\n原因：${reason}${summaryBlock}\n\n请直接回复「允许」（或 1）批准执行，或回复「拒绝 [原因]」（或 2）取消；也可在内部 IM 审批卡片中点击按钮。`;
}

function footerSummary(metadata: CompletedMessage): string | undefined {
  const model = typeof metadata.resolved_model === 'string' ? metadata.resolved_model : '';
  const usage = metadata.token_usage as { context_used?: number; context_window?: number } | undefined;
  const parts = [model.length > 512 ? `${model.slice(0, 512)}...` : model];
  if (usage?.context_used !== undefined && usage.context_window) {
    parts.push(`ctx ${Math.round((100 * usage.context_used) / usage.context_window)}%`);
  }
  const footer = parts.filter(Boolean).join(' · ');
  return footer || undefined;
}

function runtimeCard(text: string, metadata: CompletedMessage): Record<string, unknown> | undefined {
  const footer = footerSummary(metadata);
  if (!footer) return;
  return {
    config: { wide_screen_mode: true },
    elements: [{ tag: 'markdown', content: text }, { tag: 'hr' }, { tag: 'note', elements: [{ tag: 'plain_text', content: footer }] }],
  };
}

function appendPlainRuntimeFooter(text: string, metadata: CompletedMessage): string {
  const footer = footerSummary(metadata);
  if (!footer) return text;
  return `${text}\n\n—\n${footer}`;
}

function approvalStatus(decision: string): Record<string, unknown> {
  return { config: { update_multi: true }, elements: [{ tag: 'markdown', content: `审批已结束：${decision}` }] };
}

function chatTitle(chat: ExternalChat, agentName?: (agentId: string) => string | undefined): string {
  const label = agentName?.(chat.agentId)?.trim() || chat.agentId;
  return [label, ...(chat.isGroup && chat.name ? [chat.name] : []), chatProvider(chat)].join(' · ');
}

function parseWeChatApprovalCommand(text: string): { decision: 'allow_once' | 'deny'; reason?: string } | undefined {
  const trimmed = text.trim();
  if (!trimmed) return undefined;
  if (/^(?:允许|同意|批准|allow|yes|1)$/i.test(trimmed)) {
    return { decision: 'allow_once' };
  }
  const denyMatch = /^(?:拒绝|不同意|deny|no|2)(?:\s+([\s\S]+))?$/i.exec(trimmed);
  if (denyMatch) {
    const reason = denyMatch[1]?.trim();
    return { decision: 'deny', ...(reason ? { reason } : {}) };
  }
  return undefined;
}

function inspectRasterImageBuffer(bytes: Buffer): { mime: string; width: number; height: number } | undefined {
  if (bytes.length >= 24 && bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    return { mime: 'image/png', width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
  }
  if (bytes.length >= 10 && (bytes.subarray(0, 6).toString('ascii') === 'GIF87a' || bytes.subarray(0, 6).toString('ascii') === 'GIF89a')) {
    return { mime: 'image/gif', width: bytes.readUInt16LE(6), height: bytes.readUInt16LE(8) };
  }
  if (bytes.length >= 30 && bytes.subarray(0, 4).toString('ascii') === 'RIFF' && bytes.subarray(8, 12).toString('ascii') === 'WEBP') {
    const chunk = bytes.subarray(12, 16).toString('ascii');
    if (chunk === 'VP8X') {
      const width = 1 + bytes.readUIntLE(24, 3);
      const height = 1 + bytes.readUIntLE(27, 3);
      return { mime: 'image/webp', width, height };
    }
    return { mime: 'image/webp', width: 1, height: 1 };
  }
  if (bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    let offset = 2;
    while (offset + 8 < bytes.length) {
      if (bytes[offset] !== 0xff) { offset++; continue; }
      const marker = bytes[offset + 1]!;
      if (marker === 0xff) { offset++; continue; }
      if (marker === 0xd8 || marker === 0xd9) { offset += 2; continue; }
      const segLen = bytes.readUInt16BE(offset + 2);
      if (segLen < 2 || offset + 2 + segLen > bytes.length) break;
      if ((marker >= 0xc0 && marker <= 0xc3) || (marker >= 0xc5 && marker <= 0xc7) || (marker >= 0xc9 && marker <= 0xcb) || (marker >= 0xcd && marker <= 0xcf)) {
        const height = bytes.readUInt16BE(offset + 5);
        const width = bytes.readUInt16BE(offset + 7);
        return { mime: 'image/jpeg', width, height };
      }
      offset += 2 + segLen;
    }
    return { mime: 'image/jpeg', width: 1, height: 1 };
  }
  return undefined;
}
