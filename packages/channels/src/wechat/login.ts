import { randomUUID } from 'node:crypto';
import QRCode from 'qrcode';
import type { NodeParams, NodeReply } from '@nano/product-contracts/node-rpc';
import {
  DEFAULT_ILINK_BOT_TYPE,
  fetchBotQrCode,
  isValidWeChatRedirectHost,
  pollQrCodeStatus,
  resolveWeChatBaseUrl,
} from './ilink.js';

export type WeChatSetupRequest = NodeParams<'node.wechat.setup.request'>;
export type WeChatSetupReply = NodeReply<'node.wechat.setup.request'>;

export interface ExistingWeChatCredentials {
  bot_token: string;
  bot_id: string;
  owner_user_id: string;
  base_url: string;
  revoked?: boolean;
}

interface ActiveLoginSession {
  setupId: string;
  agentId: string;
  editingChannelId?: string;
  qrcode: string;
  qrSvg: string;
  expiresAtMs: number;
  currentBaseUrl: string;
  state: WeChatSetupReply['state'];
  errorCode?: string;
  message?: string;
  binding?: NonNullable<WeChatSetupReply['binding']>;
  pendingVerifyCode?: string;
  verifyResolver?: () => void;
  stepWaiters: Array<() => void>;
  abort: AbortController;
  loopPromise?: Promise<void>;
}

const MAX_AUTO_QR_RENEWALS = 3;
const QR_TTL_MS = 5 * 60_000;

/** Coordinates background WeChat iLink QR login sessions on the Node without blocking WS RPCs. */
export class WeChatLoginCoordinator {
  private readonly sessions = new Map<string, ActiveLoginSession>();
  private readonly activeByAgent = new Map<string, string>();
  private readonly env: NodeJS.ProcessEnv;
  private readonly pollIntervalMs: number;
  private readonly pollTimeoutMs: number;

  constructor(private readonly options: {
    env?: NodeJS.ProcessEnv;
    pollIntervalMs?: number;
    pollTimeoutMs?: number;
    resolveLocalCredentials?: (channelId: string, agentId: string) => ExistingWeChatCredentials | undefined;
    listLocalTokens?: () => string[];
  } = {}) {
    this.env = options.env ?? process.env;
    this.pollIntervalMs = options.pollIntervalMs ?? 500;
    this.pollTimeoutMs = options.pollTimeoutMs ?? 35_000;
  }

  /** Reports whether any QR login session is actively waiting on user confirmation. */
  get busy(): boolean {
    for (const session of this.sessions.values()) {
      if (['waiting_scan', 'scanned', 'need_verify_code'].includes(session.state)) return true;
    }
    return false;
  }

  /** Handles `node.wechat.setup.request` commands (`start`, `status`, `verify_code`, `cancel`).
   *
   * Args:
   *   input: Validated setup command from IM Server.
   * Returns:
   *   Current setup state snapshot (including `binding` once `confirmed`).
   */
  async handle(input: WeChatSetupRequest): Promise<WeChatSetupReply> {
    if (input.action === 'start') {
      return this.startSession(input.agent_id, input.editing_channel_id);
    }
    const session = this.sessions.get(input.setup_id);
    if (!session || session.agentId !== input.agent_id) {
      return {
        setup_id: input.setup_id,
        state: 'failed',
        error_code: 'setup_not_found',
        message: '二维码会话已过期或不存在，请重新获取二维码。',
      };
    }
    if (input.action === 'cancel') {
      this.cancelSession(session);
      return this.snapshot(session);
    }
    if (input.action === 'verify_code') {
      if (session.state !== 'need_verify_code') {
        return this.snapshot(session);
      }
      session.pendingVerifyCode = input.code.trim();
      session.errorCode = undefined;
      session.message = undefined;
      const stepDone = new Promise<void>(resolve => {
        const timer = setTimeout(resolve, 4_000);
        timer.unref?.();
        session.stepWaiters.push(() => {
          clearTimeout(timer);
          resolve();
        });
      });
      session.verifyResolver?.();
      session.verifyResolver = undefined;
      await stepDone;
      return this.snapshot(session);
    }
    return this.snapshot(session);
  }

  /** Cancels all in-flight QR polling sessions when the Node shuts down. */
  async stop(): Promise<void> {
    const tasks: Promise<void>[] = [];
    for (const session of this.sessions.values()) {
      session.abort.abort();
      session.verifyResolver?.();
      if (session.loopPromise) tasks.push(session.loopPromise);
    }
    await Promise.allSettled(tasks);
    this.sessions.clear();
    this.activeByAgent.clear();
  }

  private async startSession(agentId: string, editingChannelId?: string): Promise<WeChatSetupReply> {
    const previousId = this.activeByAgent.get(agentId);
    if (previousId) {
      const prev = this.sessions.get(previousId);
      if (prev) this.cancelSession(prev);
    }
    this.pruneFinished();

    const baseUrl = resolveWeChatBaseUrl(undefined, this.env);
    const localTokens = this.options.listLocalTokens?.().slice(0, 10) ?? [];
    const qr = await fetchBotQrCode({
      baseUrl,
      botType: DEFAULT_ILINK_BOT_TYPE,
      localTokenList: localTokens,
      env: this.env,
    });
    const qrSvg = await renderQrSvg(qr.qrcode_img_content);
    const setupId = randomUUID();
    const session: ActiveLoginSession = {
      setupId,
      agentId,
      editingChannelId,
      qrcode: qr.qrcode,
      qrSvg,
      expiresAtMs: Date.now() + QR_TTL_MS,
      currentBaseUrl: baseUrl,
      state: 'waiting_scan',
      stepWaiters: [],
      abort: new AbortController(),
    };
    this.sessions.set(setupId, session);
    this.activeByAgent.set(agentId, setupId);
    session.loopPromise = this.runLoop(session).catch(() => {});
    return this.snapshot(session);
  }

  private cancelSession(session: ActiveLoginSession): void {
    session.abort.abort();
    session.verifyResolver?.();
    if (!['confirmed', 'failed', 'expired'].includes(session.state)) {
      session.state = 'cancelled';
    }
    this.notifyStepWaiters(session);
    if (this.activeByAgent.get(session.agentId) === session.setupId) {
      this.activeByAgent.delete(session.agentId);
    }
  }

  private notifyStepWaiters(session: ActiveLoginSession): void {
    for (const waiter of session.stepWaiters.splice(0)) waiter();
  }

  private async runLoop(session: ActiveLoginSession): Promise<void> {
    let renewals = 0;
    while (!session.abort.signal.aborted) {
      if (Date.now() >= session.expiresAtMs) {
        session.state = 'expired';
        session.message = '二维码已过期，请刷新二维码重新扫描。';
        this.notifyStepWaiters(session);
        break;
      }

      if (session.state === 'need_verify_code' && !session.pendingVerifyCode) {
        await new Promise<void>(resolve => {
          const remaining = Math.max(50, session.expiresAtMs - Date.now());
          const timer = setTimeout(resolve, remaining);
          timer.unref?.();
          session.verifyResolver = () => {
            clearTimeout(timer);
            resolve();
          };
        });
        if (session.abort.signal.aborted) break;
        if (Date.now() >= session.expiresAtMs && !session.pendingVerifyCode) {
          session.state = 'expired';
          this.notifyStepWaiters(session);
          break;
        }
      }

      const submittedCode = session.pendingVerifyCode;
      session.pendingVerifyCode = undefined;

      let resp;
      try {
        resp = await pollQrCodeStatus({
          baseUrl: session.currentBaseUrl,
          qrcode: session.qrcode,
          verifyCode: submittedCode,
          timeoutMs: this.pollTimeoutMs,
          abortSignal: session.abort.signal,
          env: this.env,
        });
      } catch (err) {
        if (session.abort.signal.aborted) break;
        await sleepAbortable(this.pollIntervalMs, session.abort.signal);
        continue;
      }
      if (session.abort.signal.aborted) break;

      if (
        resp.status === 'need_verifycode' ||
        resp.status === 'confirmed_but_need_verifycode' ||
        (resp.status as string) === 'wrong_verify_code'
      ) {
        session.state = 'need_verify_code';
        if (submittedCode || (resp.status as string) === 'wrong_verify_code') {
          session.errorCode = 'wrong_verify_code';
          session.message = '验证码不正确，请核对手机微信界面显示的数字后重试。';
        }
        this.notifyStepWaiters(session);
        continue;
      }

      if (resp.status === 'verify_code_blocked') {
        session.state = 'failed';
        session.errorCode = 'verify_code_blocked';
        session.message = '验证码多次输入错误，本次二维码已失效，请重新获取二维码。';
        this.notifyStepWaiters(session);
        break;
      }

      if (resp.status === 'scaned_but_redirect') {
        const host = resp.redirect_host?.trim() ?? '';
        if (!isValidWeChatRedirectHost(host, this.env)) {
          session.state = 'failed';
          session.errorCode = 'invalid_redirect_host';
          session.message = '微信跨区跳转域名校验未通过，已中止连接。';
          this.notifyStepWaiters(session);
          break;
        }
        const e2eUrl = this.env.NANO_WECHAT_E2E_BASE_URL?.trim();
        session.currentBaseUrl = e2eUrl && new URL(e2eUrl).host === host ? `http://${host}` : `https://${host}`;
        session.state = 'scanned';
        this.notifyStepWaiters(session);
        continue;
      }

      if (resp.status === 'scaned') {
        session.state = 'scanned';
        session.errorCode = undefined;
        session.message = undefined;
        this.notifyStepWaiters(session);
        await sleepAbortable(this.pollIntervalMs, session.abort.signal);
        continue;
      }

      if (resp.status === 'wait') {
        if (session.state !== 'scanned') session.state = 'waiting_scan';
        this.notifyStepWaiters(session);
        await sleepAbortable(this.pollIntervalMs, session.abort.signal);
        continue;
      }

      if (resp.status === 'expired') {
        renewals++;
        if (renewals > MAX_AUTO_QR_RENEWALS) {
          session.state = 'expired';
          session.message = '连续超时未扫码，请点击刷新二维码继续绑定。';
          this.notifyStepWaiters(session);
          break;
        }
        try {
          const base = resolveWeChatBaseUrl(undefined, this.env);
          const nextQr = await fetchBotQrCode({
            baseUrl: base,
            botType: DEFAULT_ILINK_BOT_TYPE,
            localTokenList: this.options.listLocalTokens?.().slice(0, 10) ?? [],
            abortSignal: session.abort.signal,
            env: this.env,
          });
          session.qrcode = nextQr.qrcode;
          session.qrSvg = await renderQrSvg(nextQr.qrcode_img_content);
          session.currentBaseUrl = base;
          session.expiresAtMs = Date.now() + QR_TTL_MS;
          session.state = 'waiting_scan';
          session.errorCode = undefined;
          session.message = undefined;
          this.notifyStepWaiters(session);
          continue;
        } catch {
          session.state = 'expired';
          this.notifyStepWaiters(session);
          break;
        }
      }

      if (resp.status === 'binded_redirect') {
        const existing = session.editingChannelId
          ? this.options.resolveLocalCredentials?.(session.editingChannelId, session.agentId)
          : undefined;
        if (existing && !existing.revoked && existing.bot_token && existing.bot_id && existing.owner_user_id) {
          session.binding = {
            bot_token: existing.bot_token,
            bot_id: existing.bot_id,
            owner_user_id: existing.owner_user_id,
            base_url: resolveWeChatBaseUrl(existing.base_url, this.env),
          };
          session.state = 'confirmed';
          this.notifyStepWaiters(session);
          break;
        }
        // Existing token is unavailable or revoked; request a fresh QR with empty local_token_list.
        try {
          const base = resolveWeChatBaseUrl(undefined, this.env);
          const freshQr = await fetchBotQrCode({
            baseUrl: base,
            botType: DEFAULT_ILINK_BOT_TYPE,
            localTokenList: [],
            abortSignal: session.abort.signal,
            env: this.env,
          });
          session.qrcode = freshQr.qrcode;
          session.qrSvg = await renderQrSvg(freshQr.qrcode_img_content);
          session.currentBaseUrl = base;
          session.expiresAtMs = Date.now() + QR_TTL_MS;
          session.state = 'waiting_scan';
          this.notifyStepWaiters(session);
          continue;
        } catch {
          session.state = 'failed';
          session.errorCode = 'rebind_qr_failed';
          session.message = '无法重新获取新绑定二维码，请重试。';
          this.notifyStepWaiters(session);
          break;
        }
      }

      if (resp.status === 'confirmed') {
        if (!resp.bot_token?.trim() || !resp.ilink_bot_id?.trim() || !resp.ilink_user_id?.trim()) {
          session.state = 'failed';
          session.errorCode = 'incomplete_binding';
          session.message = '微信授权返回信息不完整，请重新扫码。';
          this.notifyStepWaiters(session);
          break;
        }
        let resolvedBase: string;
        try {
          resolvedBase = resolveWeChatBaseUrl(resp.baseurl || session.currentBaseUrl, this.env);
        } catch {
          resolvedBase = resolveWeChatBaseUrl(undefined, this.env);
        }
        session.binding = {
          bot_token: resp.bot_token.trim(),
          bot_id: resp.ilink_bot_id.trim(),
          owner_user_id: resp.ilink_user_id.trim(),
          base_url: resolvedBase,
        };
        session.state = 'confirmed';
        session.errorCode = undefined;
        session.message = undefined;
        this.notifyStepWaiters(session);
        break;
      }
    }
  }

  private snapshot(session: ActiveLoginSession): WeChatSetupReply {
    const reply: WeChatSetupReply = {
      setup_id: session.setupId,
      state: session.state,
      ...(session.state === 'waiting_scan' || session.state === 'scanned' || session.state === 'expired'
        ? { qr_svg: session.qrSvg, expires_at: new Date(session.expiresAtMs).toISOString() }
        : {}),
      ...(session.errorCode ? { error_code: session.errorCode } : {}),
      ...(session.message ? { message: session.message } : {}),
      ...(session.state === 'confirmed' && session.binding ? { binding: { ...session.binding } } : {}),
    };
    if (session.state === 'confirmed' && session.binding) {
      // Wipe in-memory token after handing off to IM Server for envelope sealing.
      session.binding = undefined;
      this.sessions.delete(session.setupId);
      if (this.activeByAgent.get(session.agentId) === session.setupId) {
        this.activeByAgent.delete(session.agentId);
      }
    }
    return reply;
  }

  private pruneFinished(): void {
    const now = Date.now();
    for (const [id, session] of this.sessions) {
      if (['cancelled', 'failed', 'expired'].includes(session.state) || now > session.expiresAtMs + 60_000) {
        session.abort.abort();
        this.sessions.delete(id);
      }
    }
  }
}

async function renderQrSvg(content: string): Promise<string> {
  return QRCode.toString(content, {
    type: 'svg',
    margin: 1,
    width: 168,
    color: { dark: '#0f172a', light: '#ffffff' },
  });
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
