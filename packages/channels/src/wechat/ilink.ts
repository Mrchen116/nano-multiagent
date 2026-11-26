import { randomBytes } from 'node:crypto';

export const DEFAULT_WECHAT_BASE_URL = 'https://ilinkai.weixin.qq.com';
export const DEFAULT_WECHAT_CDN_BASE_URL = 'https://novac2c.cdn.weixin.qq.com/c2c';
export const DEFAULT_ILINK_BOT_TYPE = '3';

const ILINK_APP_ID = 'bot';
// 3.0.0 encoded as 0x00MMNNPP to match official iLink Bot protocol expectations.
const ILINK_APP_CLIENT_VERSION = String((3 << 16) | 0);
const CHANNEL_VERSION = '3.0.0-beta-1';
const BOT_AGENT = 'Crewden/1.0';
const LOSSLESS_ID_FIELDS = new Set(['message_id', 'msg_id', 'svr_id']);
const WEIXIN_HOST_RE = /^[a-z0-9-]+(?:\.[a-z0-9-]+)*\.weixin\.qq\.com$/i;

export const WeChatMessageType = {
  NONE: 0,
  USER: 1,
  BOT: 2,
} as const;

export const WeChatItemType = {
  NONE: 0,
  TEXT: 1,
  IMAGE: 2,
  VOICE: 3,
  FILE: 4,
  VIDEO: 5,
} as const;

export const WeChatMessageState = {
  NEW: 0,
  GENERATING: 1,
  FINISH: 2,
} as const;

export const WeChatUploadMediaType = {
  IMAGE: 1,
  VIDEO: 2,
  FILE: 3,
  VOICE: 4,
} as const;

export interface WeChatCdnMedia {
  encrypt_query_param?: string;
  aes_key?: string;
  encrypt_type?: number;
  full_url?: string;
}

export interface WeChatPartialText {
  start: string;
  end: string;
  startindex: number;
  endindex: number;
  quotemd5?: string;
}

export interface WeChatRefMessage {
  message_item?: WeChatMessageItem;
  title?: string;
  svr_id?: string;
  partial_text?: WeChatPartialText;
}

export interface WeChatMessageItem {
  type?: number;
  create_time_ms?: number;
  msg_id?: string;
  ref_msg?: WeChatRefMessage;
  text_item?: { text?: string };
  image_item?: {
    media?: WeChatCdnMedia;
    thumb_media?: WeChatCdnMedia;
    aeskey?: string;
    mid_size?: number;
    hd_size?: number;
  };
  voice_item?: {
    media?: WeChatCdnMedia;
    encode_type?: number;
    bits_per_sample?: number;
    sample_rate?: number;
    playtime?: number;
    text?: string;
  };
  file_item?: {
    media?: WeChatCdnMedia;
    file_name?: string;
    md5?: string;
    len?: string;
  };
  video_item?: {
    media?: WeChatCdnMedia;
    video_size?: number;
    play_length?: number;
    video_md5?: string;
  };
}

export interface WeChatWireMessage {
  seq?: number;
  message_id?: string;
  svr_id?: string;
  from_user_id?: string;
  to_user_id?: string;
  client_id?: string;
  create_time_ms?: number;
  session_id?: string;
  message_type?: number;
  message_state?: number;
  item_list?: WeChatMessageItem[];
  context_token?: string;
}

export interface WeChatGetUpdatesResp {
  ret?: number;
  errcode?: number;
  errmsg?: string;
  msgs?: WeChatWireMessage[];
  get_updates_buf?: string;
  longpolling_timeout_ms?: number;
}

export interface WeChatQrCodeResp {
  qrcode: string;
  qrcode_img_content: string;
}

export type WeChatQrRawStatus =
  | 'wait'
  | 'scaned'
  | 'confirmed'
  | 'expired'
  | 'scaned_but_redirect'
  | 'need_verifycode'
  | 'confirmed_but_need_verifycode'
  | 'verify_code_blocked'
  | 'binded_redirect';

export interface WeChatQrStatusResp {
  status: WeChatQrRawStatus;
  bot_token?: string;
  ilink_bot_id?: string;
  ilink_user_id?: string;
  baseurl?: string;
  redirect_host?: string;
}

export interface WeChatUploadUrlReq {
  filekey: string;
  media_type: number;
  to_user_id: string;
  rawsize: number;
  rawfilemd5: string;
  filesize: number;
  no_need_thumb?: boolean;
  aeskey: string;
}

export interface WeChatUploadUrlResp {
  upload_param?: string;
  upload_full_url?: string;
}

function parseE2eOrigin(env: NodeJS.ProcessEnv = process.env): URL | undefined {
  const raw = env.NANO_WECHAT_E2E_BASE_URL?.trim();
  if (!raw) return undefined;
  const parsed = new URL(raw);
  if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || !parsed.port || parsed.username || parsed.password) {
    throw new Error('NANO_WECHAT_E2E_BASE_URL must be http://127.0.0.1:<port>');
  }
  return parsed;
}

/** Resolves the effective iLink API base URL, honoring isolated loopback E2E overrides.
 *
 * Args:
 *   configured: Saved channel `base_url`, if any.
 *   env: Process environment used to inspect `NANO_WECHAT_E2E_BASE_URL`.
 * Returns:
 *   Validated base URL string without trailing slash.
 */
export function resolveWeChatBaseUrl(configured?: string, env: NodeJS.ProcessEnv = process.env): string {
  const e2e = parseE2eOrigin(env);
  if (e2e) return e2e.origin;
  const target = configured?.trim() || DEFAULT_WECHAT_BASE_URL;
  return assertWeChatAllowedUrl(target, env).origin;
}

/** Resolves the effective WeChat C2C CDN base URL, honoring isolated loopback E2E overrides. */
export function resolveWeChatCdnBaseUrl(env: NodeJS.ProcessEnv = process.env): string {
  const e2e = parseE2eOrigin(env);
  if (e2e) return `${e2e.origin}/c2c`;
  return DEFAULT_WECHAT_CDN_BASE_URL;
}

/** Enforces the outbound SSRF allowlist (`https://*.weixin.qq.com` or explicit E2E loopback).
 *
 * Args:
 *   rawUrl: Candidate URL before issuing `fetch`.
 *   env: Process environment used to inspect `NANO_WECHAT_E2E_BASE_URL`.
 * Returns:
 *   Parsed `URL` guaranteed safe to contact with `redirect: 'error'`.
 * Raises:
 *   Error: If protocol, credentials, or host violate the WeChat boundary.
 */
export function assertWeChatAllowedUrl(rawUrl: string, env: NodeJS.ProcessEnv = process.env): URL {
  const url = new URL(rawUrl);
  if (url.username || url.password) {
    throw new Error('WeChat URL must not contain embedded credentials');
  }
  const e2e = parseE2eOrigin(env);
  if (e2e && url.origin === e2e.origin) {
    return url;
  }
  if (url.protocol !== 'https:' || !WEIXIN_HOST_RE.test(url.hostname)) {
    throw new Error(`Disallowed WeChat upstream host: ${url.origin}`);
  }
  return url;
}

/** Validates an IDC `redirect_host` returned by `scaned_but_redirect` before switching poll host. */
export function isValidWeChatRedirectHost(host: string, env: NodeJS.ProcessEnv = process.env): boolean {
  const trimmed = host.trim();
  if (!trimmed) return false;
  const e2e = parseE2eOrigin(env);
  if (e2e && trimmed === e2e.host) return true;
  return WEIXIN_HOST_RE.test(trimmed);
}

/** Quotes uint64 ID properties (`message_id`, `msg_id`, `svr_id`) before `JSON.parse` loses precision.
 *
 * Only actual object property values are rewritten; string literals containing the same text remain untouched.
 *
 * Args:
 *   rawText: Raw JSON response body from iLink CGI.
 * Returns:
 *   Parsed object with uint64 message identifiers preserved as exact decimal strings.
 */
export function parseWeChatApiJson<T>(rawText: string): T {
  if (!rawText.trim()) {
    throw new Error('WeChat iLink API returned an empty HTTP body');
  }
  let output = '';
  let index = 0;
  while (index < rawText.length) {
    if (rawText[index] !== '"') {
      output += rawText[index++];
      continue;
    }
    const stringStart = index++;
    let escaped = false;
    while (index < rawText.length) {
      const char = rawText[index++];
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') break;
    }
    const token = rawText.slice(stringStart, index);
    output += token;

    let cursor = index;
    while (/\s/.test(rawText[cursor] ?? '')) cursor++;
    if (rawText[cursor] !== ':') continue;

    let key: unknown;
    try {
      key = JSON.parse(token);
    } catch {
      continue;
    }
    if (typeof key !== 'string' || !LOSSLESS_ID_FIELDS.has(key)) continue;

    output += rawText.slice(index, cursor + 1);
    cursor++;
    while (/\s/.test(rawText[cursor] ?? '')) output += rawText[cursor++];

    const numberStart = cursor;
    if (rawText[cursor] === '-') cursor++;
    while (/\d/.test(rawText[cursor] ?? '')) cursor++;
    if (cursor > numberStart && !(cursor === numberStart + 1 && rawText[numberStart] === '-')) {
      output += `"${rawText.slice(numberStart, cursor)}"`;
      index = cursor;
    } else {
      index = numberStart;
    }
  }
  return JSON.parse(output) as T;
}

function baseInfo() {
  return { channel_version: CHANNEL_VERSION, bot_agent: BOT_AGENT };
}

function randomWechatUin(): string {
  const uint32 = randomBytes(4).readUInt32BE(0);
  return Buffer.from(String(uint32), 'utf8').toString('base64');
}

function commonHeaders(): Record<string, string> {
  return {
    'iLink-App-Id': ILINK_APP_ID,
    'iLink-App-ClientVersion': ILINK_APP_CLIENT_VERSION,
  };
}

function postHeaders(token?: string): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    AuthorizationType: 'ilink_bot_token',
    'X-WECHAT-UIN': randomWechatUin(),
    ...commonHeaders(),
  };
  if (token?.trim()) {
    headers.Authorization = `Bearer ${token.trim()}`;
  }
  return headers;
}

function combineAbort(timeoutMs: number | undefined, external?: AbortSignal): { signal?: AbortSignal; cleanup: () => void } {
  const controller = timeoutMs && timeoutMs > 0 ? new AbortController() : undefined;
  const timer = controller && timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : undefined;
  timer?.unref?.();
  if (!external) {
    return { signal: controller?.signal, cleanup: () => { if (timer) clearTimeout(timer); } };
  }
  if (!controller) {
    return { signal: external, cleanup: () => {} };
  }
  if (external.aborted) {
    controller.abort();
    return { signal: controller.signal, cleanup: () => { if (timer) clearTimeout(timer); } };
  }
  const onAbort = () => controller.abort();
  external.addEventListener('abort', onAbort, { once: true });
  return {
    signal: controller.signal,
    cleanup: () => {
      if (timer) clearTimeout(timer);
      external.removeEventListener('abort', onAbort);
    },
  };
}

export async function wechatGet(params: {
  baseUrl: string;
  endpoint: string;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<string> {
  const base = params.baseUrl.endsWith('/') ? params.baseUrl : `${params.baseUrl}/`;
  const url = assertWeChatAllowedUrl(new URL(params.endpoint, base).toString(), params.env);
  const { signal, cleanup } = combineAbort(params.timeoutMs, params.abortSignal);
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: commonHeaders(),
      redirect: 'error',
      ...(signal ? { signal } : {}),
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`WeChat GET ${params.endpoint} failed (${res.status})`);
    return text;
  } finally {
    cleanup();
  }
}

export async function wechatPost(params: {
  baseUrl: string;
  endpoint: string;
  body: Record<string, unknown>;
  token?: string;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<string> {
  const base = params.baseUrl.endsWith('/') ? params.baseUrl : `${params.baseUrl}/`;
  const url = assertWeChatAllowedUrl(new URL(params.endpoint, base).toString(), params.env);
  const { signal, cleanup } = combineAbort(params.timeoutMs, params.abortSignal);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: postHeaders(params.token),
      body: JSON.stringify(params.body),
      redirect: 'error',
      ...(signal ? { signal } : {}),
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`WeChat POST ${params.endpoint} failed (${res.status})`);
    return text;
  } finally {
    cleanup();
  }
}

export async function fetchBotQrCode(params: {
  baseUrl?: string;
  botType?: string;
  localTokenList?: string[];
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<WeChatQrCodeResp> {
  const baseUrl = resolveWeChatBaseUrl(params.baseUrl, params.env);
  const botType = params.botType ?? DEFAULT_ILINK_BOT_TYPE;
  const raw = await wechatPost({
    baseUrl,
    endpoint: `ilink/bot/get_bot_qrcode?bot_type=${encodeURIComponent(botType)}`,
    body: { local_token_list: params.localTokenList ?? [] },
    timeoutMs: params.timeoutMs ?? 15_000,
    abortSignal: params.abortSignal,
    env: params.env,
  });
  return parseWeChatApiJson<WeChatQrCodeResp>(raw);
}

export async function pollQrCodeStatus(params: {
  baseUrl: string;
  qrcode: string;
  verifyCode?: string;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<WeChatQrStatusResp> {
  let endpoint = `ilink/bot/get_qrcode_status?qrcode=${encodeURIComponent(params.qrcode)}`;
  if (params.verifyCode) {
    endpoint += `&verify_code=${encodeURIComponent(params.verifyCode)}`;
  }
  try {
    const raw = await wechatGet({
      baseUrl: params.baseUrl,
      endpoint,
      timeoutMs: params.timeoutMs ?? 35_000,
      abortSignal: params.abortSignal,
      env: params.env,
    });
    return parseWeChatApiJson<WeChatQrStatusResp>(raw);
  } catch (err) {
    if (params.abortSignal?.aborted) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      return { status: 'wait' };
    }
    throw err;
  }
}

export async function getWeChatUpdates(params: {
  baseUrl: string;
  token: string;
  cursor: string;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<WeChatGetUpdatesResp> {
  try {
    const raw = await wechatPost({
      baseUrl: params.baseUrl,
      endpoint: 'ilink/bot/getupdates',
      body: {
        get_updates_buf: params.cursor,
        base_info: baseInfo(),
      },
      token: params.token,
      timeoutMs: params.timeoutMs ?? 35_000,
      abortSignal: params.abortSignal,
      env: params.env,
    });
    return parseWeChatApiJson<WeChatGetUpdatesResp>(raw);
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      return { ret: 0, msgs: [], get_updates_buf: params.cursor };
    }
    throw err;
  }
}

export async function sendWeChatItem(params: {
  baseUrl: string;
  token: string;
  toUserId: string;
  contextToken: string;
  clientId: string;
  item: WeChatMessageItem;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<{ message_id?: string }> {
  const raw = await wechatPost({
    baseUrl: params.baseUrl,
    endpoint: 'ilink/bot/sendmessage',
    body: {
      msg: {
        from_user_id: '',
        to_user_id: params.toUserId,
        client_id: params.clientId,
        message_type: WeChatMessageType.BOT,
        message_state: WeChatMessageState.FINISH,
        item_list: [params.item],
        context_token: params.contextToken,
      },
      base_info: baseInfo(),
    },
    token: params.token,
    timeoutMs: params.timeoutMs ?? 15_000,
    abortSignal: params.abortSignal,
    env: params.env,
  });
  const resp = parseWeChatApiJson<{ message_id?: string; ret?: number; errcode?: number; errmsg?: string }>(raw);
  if ((resp.ret !== undefined && resp.ret !== 0) || (resp.errcode !== undefined && resp.errcode !== 0)) {
    throw new Error(`WeChat sendmessage rejected (ret=${resp.ret ?? 0}, errcode=${resp.errcode ?? 0})`);
  }
  return resp;
}

export async function getWeChatConfig(params: {
  baseUrl: string;
  token: string;
  ilinkUserId: string;
  contextToken?: string;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<{ ret?: number; typing_ticket?: string }> {
  const raw = await wechatPost({
    baseUrl: params.baseUrl,
    endpoint: 'ilink/bot/getconfig',
    body: {
      ilink_user_id: params.ilinkUserId,
      context_token: params.contextToken,
      base_info: baseInfo(),
    },
    token: params.token,
    timeoutMs: params.timeoutMs ?? 10_000,
    abortSignal: params.abortSignal,
    env: params.env,
  });
  return parseWeChatApiJson<{ ret?: number; typing_ticket?: string }>(raw);
}

export async function sendWeChatTyping(params: {
  baseUrl: string;
  token: string;
  ilinkUserId: string;
  typingTicket: string;
  status: 1 | 2;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<void> {
  await wechatPost({
    baseUrl: params.baseUrl,
    endpoint: 'ilink/bot/sendtyping',
    body: {
      ilink_user_id: params.ilinkUserId,
      typing_ticket: params.typingTicket,
      status: params.status,
      base_info: baseInfo(),
    },
    token: params.token,
    timeoutMs: params.timeoutMs ?? 10_000,
    abortSignal: params.abortSignal,
    env: params.env,
  });
}

export async function getWeChatUploadUrl(params: WeChatUploadUrlReq & {
  baseUrl: string;
  token: string;
  timeoutMs?: number;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<WeChatUploadUrlResp> {
  const raw = await wechatPost({
    baseUrl: params.baseUrl,
    endpoint: 'ilink/bot/getuploadurl',
    body: {
      filekey: params.filekey,
      media_type: params.media_type,
      to_user_id: params.to_user_id,
      rawsize: params.rawsize,
      rawfilemd5: params.rawfilemd5,
      filesize: params.filesize,
      no_need_thumb: params.no_need_thumb ?? true,
      aeskey: params.aeskey,
      base_info: baseInfo(),
    },
    token: params.token,
    timeoutMs: params.timeoutMs ?? 15_000,
    abortSignal: params.abortSignal,
    env: params.env,
  });
  return parseWeChatApiJson<WeChatUploadUrlResp>(raw);
}
