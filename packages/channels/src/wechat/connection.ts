import { createHash } from 'node:crypto';
import { chmod, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import {
  WeChatItemType,
  WeChatMessageType,
  getWeChatConfig,
  getWeChatUpdates,
  resolveWeChatBaseUrl,
  sendWeChatItem,
  sendWeChatTyping,
  type WeChatWireMessage,
} from './ilink.js';
import { transformWeChatInboundMessage } from './inbound.js';
import { chunkWeChatText, filterWeChatMarkdown, uploadWeChatOutboundImage } from './outbound.js';
import { WeChatQuoteStore } from './quote-store.js';

export type WeChatInboundPart =
  | { type: 'text'; text: string }
  | { type: 'image'; key: string; data: Buffer; mediaType: string; fileName?: string }
  | { type: 'file'; key: string; data: Buffer; mediaType: string; fileName: string };

export interface WeChatInboundMessage {
  messageId: string;
  svrId?: string;
  chatId: string;
  senderId: string;
  isGroup: false;
  mentioned: true;
  time: string;
  parts: WeChatInboundPart[];
  plainSingleText?: boolean;
  preprocessNotice?: string;
}

export interface WeChatConfiguration {
  channelId: string;
  botId: string;
  botToken: string;
  ownerUserId: string;
  baseUrl?: string;
  stateRoot: string;
  credentialRevision?: number;
  env?: NodeJS.ProcessEnv;
  longPollTimeoutMs?: number;
  typingIntervalMs?: number;
}

export type WeChatStatusReport =
  | 'ready'
  | 'reconnecting'
  | 'stopped'
  | 'failed'
  | { state: 'failed' | 'ready' | 'reconnecting' | 'stopped'; code?: string; message?: string };

export interface WeChatInboundTransformContext {
  db: DatabaseSync;
  baseUrl: string;
  ownerUserId: string;
  abortSignal: AbortSignal;
  env: NodeJS.ProcessEnv;
}

export type WeChatInboundTransformer = (
  wire: WeChatWireMessage,
  ctx: WeChatInboundTransformContext,
) => Promise<WeChatInboundMessage | undefined>;

const STRANGER_NOTICE_GAP_MS = 5 * 60_000;
const STALE_TOKEN_ERRCODE = -14;
const MAX_SEEN_MESSAGES = 500;
const MAX_TYPING_LEASE_MS = 90_000;

function safeStateStem(channelId: string): string {
  const sanitized = channelId.replace(/[^a-zA-Z0-9_.-]/g, '_');
  return sanitized.length > 0 && sanitized.length <= 96
    ? sanitized
    : createHash('sha256').update(channelId).digest('hex').slice(0, 32);
}

/** Deletes the `0600` local SQLite state (including WAL/SHM) for a removed WeChat channel.
 *
 * Args:
 *   stateRoot: Directory holding per-channel WeChat SQLite files.
 *   channelId: Managed channel ID (`ch_...`).
 */
export async function purgeWeChatChannelState(stateRoot: string, channelId: string): Promise<void> {
  const base = join(stateRoot, `${safeStateStem(channelId)}.sqlite3`);
  await Promise.all([
    rm(base, { force: true }),
    rm(`${base}-wal`, { force: true }),
    rm(`${base}-shm`, { force: true }),
  ]);
}

/** Reads whether a channel's local SQLite state has recorded an upstream `-14` token revocation. */
export function isWeChatChannelRevokedOnDisk(
  stateRoot: string,
  channelId: string,
  credentialRevision?: number,
): boolean {
  const path = join(stateRoot, `${safeStateStem(channelId)}.sqlite3`);
  let db: DatabaseSync | undefined;
  try {
    db = new DatabaseSync(path, { open: true });
    const revRow = db.prepare("SELECT value FROM kv WHERE key='credential_revision'").get() as { value: string } | undefined;
    if (credentialRevision !== undefined && revRow && Number(revRow.value) !== credentialRevision) {
      return false;
    }
    const revoked = db.prepare("SELECT value FROM kv WHERE key='revoked'").get() as { value: string } | undefined;
    return revoked?.value === '1';
  } catch {
    return false;
  } finally {
    try { db?.close(); } catch { /* ignore */ }
  }
}

/** Single-poller official iLink Bot connection with strict owner-only gating and `0600` local state. */
export class WeChatConnection {
  readonly supportsReactions = false;
  readonly supportsCards = false;
  readonly config: {
    appId: string;
    botOpenId: string;
    ownerOpenId: string;
    baseUrl: string;
  };

  private readonly env: NodeJS.ProcessEnv;
  private readonly strangerRepliedAt = new Map<string, number>();
  private readonly mediaBufferCache = new Map<string, { data: Buffer; mediaType: string }>();
  private db?: DatabaseSync;
  private abortController?: AbortController;
  private loopPromise?: Promise<void>;
  private typingTimer?: ReturnType<typeof setInterval>;
  private typingStartedAt = 0;
  private typingTicket?: string;
  private stopping = false;

  constructor(
    private readonly wechatConfig: WeChatConfiguration,
    private readonly options: {
      receive(message: WeChatInboundMessage): Promise<void>;
      status?(report: WeChatStatusReport): void;
      onError(error: Error): void;
      transformInbound?: WeChatInboundTransformer;
    },
  ) {
    this.env = wechatConfig.env ?? process.env;
    const resolvedBaseUrl = resolveWeChatBaseUrl(wechatConfig.baseUrl, this.env);
    this.config = {
      appId: wechatConfig.botId,
      botOpenId: wechatConfig.botId,
      ownerOpenId: wechatConfig.ownerUserId,
      baseUrl: resolvedBaseUrl,
    };
  }

  /** Opens `0600` local state and launches the single long-poll loop. */
  async start(): Promise<void> {
    if (this.loopPromise) return;
    this.stopping = false;
    await mkdir(this.wechatConfig.stateRoot, { recursive: true, mode: 0o700 });
    const dbPath = join(this.wechatConfig.stateRoot, `${safeStateStem(this.wechatConfig.channelId)}.sqlite3`);
    this.db = new DatabaseSync(dbPath);
    await chmod(dbPath, 0o600).catch(() => {});
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA synchronous=NORMAL;
      CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS seen_msgs(msg_id TEXT PRIMARY KEY, seen_at INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS quotes(
        svr_id TEXT PRIMARY KEY,
        direction TEXT NOT NULL,
        text TEXT NOT NULL,
        media_json TEXT,
        created_at INTEGER NOT NULL
      );
    `);

    const desiredRevision = String(this.wechatConfig.credentialRevision ?? 1);
    const savedRevision = this.getKv('credential_revision');
    if (savedRevision !== desiredRevision) {
      // A newly bound token starts clean without stale revocation flags or another session's quote cache.
      this.db.exec("DELETE FROM kv; DELETE FROM seen_msgs; DELETE FROM quotes;");
      this.setKv('credential_revision', desiredRevision);
    }

    if (this.getKv('revoked') === '1') {
      this.options.status?.({
        state: 'failed',
        code: 'wechat_token_revoked',
        message: '微信登录已失效，请点击「重新扫码」恢复绑定',
      });
      return;
    }

    const abort = new AbortController();
    this.abortController = abort;
    this.loopPromise = this.pollLoop(abort.signal).finally(() => {
      if (this.abortController === abort) {
        this.abortController = undefined;
        this.loopPromise = undefined;
      }
    });
  }

  /** Aborts any in-flight `getupdates` call and waits until the poller completely exits. */
  async stop(): Promise<void> {
    this.stopping = true;
    await this.setTyping(this.wechatConfig.ownerUserId, false).catch(() => {});
    this.abortController?.abort();
    if (this.loopPromise) {
      await this.loopPromise.catch(() => {});
    }
    this.mediaBufferCache.clear();
    if (this.db) {
      try { this.db.close(); } catch { /* ignore */ }
      this.db = undefined;
    }
    this.options.status?.('stopped');
  }

  /** Sends sanitized, fence-safe chunked text (and optional pre-staged images) to the bound WeChat owner. */
  async send(
    chatId: string,
    text: string,
    operationId: string,
    _card?: Record<string, unknown>,
    images?: { data: Buffer; mediaType: string }[],
  ): Promise<string> {
    const contextToken = this.getKv('context_token');
    if (!contextToken) {
      throw new Error('WeChat context_token unavailable: owner must send a message first');
    }
    const targetUser = chatId || this.wechatConfig.ownerUserId;
    const filtered = filterWeChatMarkdown(text);
    const chunks = chunkWeChatText(filtered);
    let lastMessageId = '';

    for (const [index, chunk] of chunks.entries()) {
      const clientId = this.deterministicClientId(operationId, 'text', index);
      const resp = await sendWeChatItem({
        baseUrl: this.config.baseUrl,
        token: this.wechatConfig.botToken,
        toUserId: targetUser,
        contextToken,
        clientId,
        item: { type: WeChatItemType.TEXT, text_item: { text: chunk } },
        abortSignal: this.abortController?.signal,
        env: this.env,
      });
      lastMessageId = resp.message_id || clientId;
      if (resp.message_id) {
        this.rememberOutboundQuote(resp.message_id, chunk);
      }
    }

    for (const [index, img] of (images ?? []).entries()) {
      const uploaded = await uploadWeChatOutboundImage({
        data: img.data,
        toUserId: targetUser,
        baseUrl: this.config.baseUrl,
        token: this.wechatConfig.botToken,
        abortSignal: this.abortController?.signal,
        env: this.env,
      });
      const clientId = this.deterministicClientId(operationId, 'image', index);
      const resp = await sendWeChatItem({
        baseUrl: this.config.baseUrl,
        token: this.wechatConfig.botToken,
        toUserId: targetUser,
        contextToken,
        clientId,
        item: {
          type: WeChatItemType.IMAGE,
          image_item: {
            media: {
              encrypt_query_param: uploaded.encryptQueryParam,
              aes_key: uploaded.aesKeyBase64,
              encrypt_type: 1,
            },
            mid_size: uploaded.ciphertextSize,
          },
        },
        abortSignal: this.abortController?.signal,
        env: this.env,
      });
      lastMessageId = resp.message_id || clientId;
      if (resp.message_id) {
        this.rememberOutboundQuote(resp.message_id, '[图片]');
      }
    }

    return lastMessageId || this.deterministicClientId(operationId, 'empty', 0);
  }

  /** Toggles WeChat's "对方正在输入…" indicator with automatic 4-second renewal and guaranteed teardown. */
  async setTyping(_chatId: string, active: boolean): Promise<void> {
    const contextToken = this.getKv('context_token');
    if (!active) {
      if (this.typingTimer) {
        clearInterval(this.typingTimer);
        this.typingTimer = undefined;
      }
      const ticket = this.typingTicket ?? this.getKv('typing_ticket');
      this.typingStartedAt = 0;
      if (ticket && contextToken) {
        await sendWeChatTyping({
          baseUrl: this.config.baseUrl,
          token: this.wechatConfig.botToken,
          ilinkUserId: this.wechatConfig.ownerUserId,
          typingTicket: ticket,
          status: 2,
          timeoutMs: 4_000,
          env: this.env,
        }).catch(() => {});
      }
      return;
    }

    if (!contextToken || this.stopping) return;
    let ticket = this.typingTicket ?? this.getKv('typing_ticket');
    if (!ticket) {
      const cfg = await getWeChatConfig({
        baseUrl: this.config.baseUrl,
        token: this.wechatConfig.botToken,
        ilinkUserId: this.wechatConfig.ownerUserId,
        contextToken,
        abortSignal: this.abortController?.signal,
        env: this.env,
      }).catch(() => undefined);
      ticket = cfg?.typing_ticket?.trim();
      if (ticket) {
        this.typingTicket = ticket;
        this.setKv('typing_ticket', ticket);
      }
    }
    if (!ticket) return;

    await sendWeChatTyping({
      baseUrl: this.config.baseUrl,
      token: this.wechatConfig.botToken,
      ilinkUserId: this.wechatConfig.ownerUserId,
      typingTicket: ticket,
      status: 1,
      abortSignal: this.abortController?.signal,
      env: this.env,
    }).catch(() => {});

    this.typingStartedAt = Date.now();
    if (!this.typingTimer) {
      const intervalMs = this.wechatConfig.typingIntervalMs ?? 4_000;
      this.typingTimer = setInterval(() => {
        if (this.stopping || !this.typingTicket || Date.now() - this.typingStartedAt > MAX_TYPING_LEASE_MS) {
          void this.setTyping(this.wechatConfig.ownerUserId, false);
          return;
        }
        void sendWeChatTyping({
          baseUrl: this.config.baseUrl,
          token: this.wechatConfig.botToken,
          ilinkUserId: this.wechatConfig.ownerUserId,
          typingTicket: this.typingTicket,
          status: 1,
          abortSignal: this.abortController?.signal,
          env: this.env,
        }).catch(() => {});
      }, intervalMs);
      this.typingTimer.unref?.();
    }
  }

  async reaction(): Promise<string | undefined> {
    return undefined;
  }

  async image(_messageId: string, key: string): Promise<{ data: Buffer; mediaType: string }> {
    const cached = this.mediaBufferCache.get(key);
    if (!cached) throw new Error('WeChat inbound image buffer is unavailable');
    this.mediaBufferCache.delete(key);
    return cached;
  }

  async updateCard(): Promise<void> {
    // WeChat does not support interactive card patching; SingleThread text approvals report via message.
  }

  private async pollLoop(signal: AbortSignal): Promise<void> {
    let nextTimeoutMs = this.wechatConfig.longPollTimeoutMs ?? 35_000;
    let consecutiveFailures = 0;
    let markedReady = false;

    while (!signal.aborted) {
      try {
        if (!markedReady && consecutiveFailures === 0) {
          markedReady = true;
          this.options.status?.('ready');
        }
        const cursor = this.getKv('cursor') ?? '';
        const resp = await getWeChatUpdates({
          baseUrl: this.config.baseUrl,
          token: this.wechatConfig.botToken,
          cursor,
          timeoutMs: nextTimeoutMs,
          abortSignal: signal,
          env: this.env,
        });
        if (signal.aborted) break;

        if (resp.longpolling_timeout_ms && resp.longpolling_timeout_ms > 0) {
          nextTimeoutMs = resp.longpolling_timeout_ms;
        }

        const isError = (resp.ret !== undefined && resp.ret !== 0) || (resp.errcode !== undefined && resp.errcode !== 0);
        if (isError) {
          if (resp.errcode === STALE_TOKEN_ERRCODE || resp.ret === STALE_TOKEN_ERRCODE) {
            this.handleTokenRevoked();
            break;
          }
          consecutiveFailures++;
          markedReady = false;
          this.options.status?.('reconnecting');
          await sleepAbortable(consecutiveFailures >= 3 ? 30_000 : 2_000, signal);
          continue;
        }

        consecutiveFailures = 0;
        if (!markedReady) {
          markedReady = true;
          this.options.status?.('ready');
        }

        for (const wire of resp.msgs ?? []) {
          if (signal.aborted) break;
          await this.handleInboundWire(wire, signal);
        }

        if (typeof resp.get_updates_buf === 'string' && resp.get_updates_buf !== cursor) {
          this.setKv('cursor', resp.get_updates_buf);
        }
      } catch (err) {
        if (signal.aborted) break;
        consecutiveFailures++;
        markedReady = false;
        this.options.status?.('reconnecting');
        this.options.onError(err instanceof Error ? err : new Error(String(err)));
        await sleepAbortable(consecutiveFailures >= 3 ? 30_000 : 2_000, signal);
      }
    }
  }

  private handleTokenRevoked(): void {
    if (this.db) {
      this.db.exec("DELETE FROM seen_msgs; DELETE FROM quotes; DELETE FROM kv WHERE key IN ('cursor','context_token','typing_ticket');");
      this.setKv('revoked', '1');
    }
    this.options.status?.({
      state: 'failed',
      code: 'wechat_token_revoked',
      message: '微信登录已失效，请点击「重新扫码」恢复绑定',
    });
  }

  private async handleInboundWire(wire: WeChatWireMessage, signal: AbortSignal): Promise<void> {
    if (wire.message_type === WeChatMessageType.BOT) return;
    const senderId = wire.from_user_id?.trim();
    if (!senderId) return;
    const msgId = String(wire.message_id ?? wire.svr_id ?? wire.seq ?? '');
    if (!msgId || this.hasSeenMessage(msgId)) return;
    this.markSeenMessage(msgId);

    if (senderId !== this.wechatConfig.ownerUserId) {
      await this.replyStrangerRateLimited(senderId, wire.context_token, signal);
      return;
    }

    if (wire.context_token?.trim()) {
      this.setKv('context_token', wire.context_token.trim());
    }

    const transformer = this.options.transformInbound ?? transformWeChatInboundMessage;
    const parsed = await transformer(wire, {
      db: this.db!,
      baseUrl: this.config.baseUrl,
      ownerUserId: this.wechatConfig.ownerUserId,
      abortSignal: signal,
      env: this.env,
    });
    if (!parsed) return;

    for (const part of parsed.parts) {
      if (part.type === 'image') {
        this.mediaBufferCache.set(part.key, { data: part.data, mediaType: part.mediaType });
      }
    }

    if (parsed.preprocessNotice && wire.context_token?.trim()) {
      await sendWeChatItem({
        baseUrl: this.config.baseUrl,
        token: this.wechatConfig.botToken,
        toUserId: senderId,
        contextToken: wire.context_token.trim(),
        clientId: this.deterministicClientId(`notice:${msgId}`, 'text', 0),
        item: { type: WeChatItemType.TEXT, text_item: { text: parsed.preprocessNotice } },
        abortSignal: signal,
        env: this.env,
      }).catch(err => this.options.onError(err instanceof Error ? err : new Error(String(err))));
    }

    await this.options.receive(parsed);
  }

  private async replyStrangerRateLimited(strangerId: string, contextToken: string | undefined, signal: AbortSignal): Promise<void> {
    if (!contextToken?.trim()) return;
    const now = Date.now();
    const last = this.strangerRepliedAt.get(strangerId);
    if (last !== undefined && now - last < STRANGER_NOTICE_GAP_MS) return;
    this.strangerRepliedAt.set(strangerId, now);
    for (const [peer, ts] of this.strangerRepliedAt) {
      if (now - ts >= STRANGER_NOTICE_GAP_MS) this.strangerRepliedAt.delete(peer);
    }
    await sendWeChatItem({
      baseUrl: this.config.baseUrl,
      token: this.wechatConfig.botToken,
      toUserId: strangerId,
      contextToken: contextToken.trim(),
      clientId: this.deterministicClientId(`stranger:${strangerId}:${now}`, 'text', 0),
      item: {
        type: WeChatItemType.TEXT,
        text_item: { text: '该个人微信助手仅限扫码绑定者本人私聊使用。' },
      },
      abortSignal: signal,
      env: this.env,
    }).catch(() => {});
  }

  private deterministicClientId(operationId: string, kind: string, index: number): string {
    const digest = createHash('sha256')
      .update(`${this.wechatConfig.channelId}:${operationId}:${kind}:${index}`)
      .digest('hex')
      .slice(0, 24);
    return `nano-wx-${digest}`;
  }

  private rememberOutboundQuote(svrId: string, text: string): void {
    if (!this.db || !svrId || !text) return;
    new WeChatQuoteStore(this.db).save({
      svrId,
      direction: 'outbound',
      text,
      ...(text === '[图片]' ? { mediaSummary: '[图片]' } : {}),
    });
  }

  private getKv(key: string): string | undefined {
    if (!this.db) return undefined;
    const row = this.db.prepare('SELECT value FROM kv WHERE key=?').get(key) as { value: string } | undefined;
    return row?.value;
  }

  private setKv(key: string, value: string): void {
    this.db?.prepare('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run(key, value);
  }

  private hasSeenMessage(msgId: string): boolean {
    if (!this.db) return false;
    return !!this.db.prepare('SELECT 1 FROM seen_msgs WHERE msg_id=?').get(msgId);
  }

  private markSeenMessage(msgId: string): void {
    if (!this.db) return;
    this.db.prepare('INSERT OR IGNORE INTO seen_msgs(msg_id, seen_at) VALUES(?,?)').run(msgId, Date.now());
    this.db.exec(`DELETE FROM seen_msgs WHERE msg_id NOT IN (SELECT msg_id FROM seen_msgs ORDER BY seen_at DESC LIMIT ${MAX_SEEN_MESSAGES})`);
  }
}

function sleepAbortable(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.resolve();
  return new Promise(resolve => {
    const onAbort = () => {
      clearTimeout(timer);
      resolve();
    };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    timer.unref?.();
    signal.addEventListener('abort', onAbort, { once: true });
  });
}
