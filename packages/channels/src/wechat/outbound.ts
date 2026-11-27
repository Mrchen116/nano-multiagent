import { createHash, randomBytes } from 'node:crypto';
import { aesEcbPaddedSize, encryptAesEcb } from './crypto.js';
import {
  WeChatUploadMediaType,
  assertWeChatAllowedUrl,
  getWeChatUploadUrl,
  resolveWeChatCdnBaseUrl,
} from './ilink.js';

export const WECHAT_MAX_TEXT_CODEPOINTS = 3_500;

const CJK_RE = /[\u2E80-\u9FFF\uAC00-\uD7AF\uF900-\uFAFF]/;
const DEEP_HEADING_RE = /^#{5,6}\s+/gm;
const STRIKE_RE = /~~([^~\n]+)~~/g;
const EMPHASIS_RE = /(\*{1,3}|_{1,3})([^*_\n]+)(\*{1,3}|_{1,3})/g;
const IMAGE_MD_RE = /!\[[^\]\n]*\]\([^)\n]*\)/g;

/** Strips Markdown constructs rendered poorly by WeChat while preserving `**bold**` and code.
 *
 * Args:
 *   markdown: Outbound assistant Markdown text.
 * Returns:
 *   Cleaned text ready for WeChat downstream delivery.
 */
export function filterWeChatMarkdown(markdown: string): string {
  const lines = markdown.split(/(\n)/);
  let inFence = false;
  let result = '';
  for (let i = 0; i < lines.length; i += 2) {
    const line = lines[i] ?? '';
    const newline = lines[i + 1] ?? '';
    if (line.trimStart().startsWith('```')) {
      inFence = !inFence;
      result += line + newline;
      continue;
    }
    if (inFence) {
      result += line + newline;
      continue;
    }
    result += filterInlineOutsideCode(line) + newline;
  }
  return result;
}

function filterInlineOutsideCode(line: string): string {
  let out = '';
  let rest = line;
  while (rest.length > 0) {
    const start = rest.indexOf('`');
    if (start < 0) {
      out += filterPlainSegment(rest);
      break;
    }
    out += filterPlainSegment(rest.slice(0, start));
    let end = start;
    while (end < rest.length && rest[end] === '`') end++;
    const marker = rest.slice(start, end);
    const closeIdx = rest.indexOf(marker, end);
    if (closeIdx < 0) {
      out += rest.slice(start);
      break;
    }
    const afterClose = closeIdx + marker.length;
    out += rest.slice(start, afterClose);
    rest = rest.slice(afterClose);
  }
  return out;
}

function filterPlainSegment(segment: string): string {
  return segment
    .replace(IMAGE_MD_RE, '')
    .replace(DEEP_HEADING_RE, '')
    .replace(STRIKE_RE, '$1')
    .replace(EMPHASIS_RE, (whole, open: string, inner: string, close: string) => {
      if (open !== close || !CJK_RE.test(inner) || open.length === 2) return whole;
      return inner;
    });
}

/** Splits WeChat text into `<= maxCodePoints` chunks without breaking fenced code blocks.
 *
 * When a split lands inside an open ```` ```lang ```` block, the current chunk closes with `\n\`\`\``
 * and the next chunk reopens with the exact opening fence header (`\`\`\`lang\n`).
 *
 * Args:
 *   text: Sanitized outbound text.
 *   maxCodePoints: Maximum Unicode code points per WeChat message (defaults to 3,500).
 * Returns:
 *   Ordered non-empty text chunks, each within `maxCodePoints`.
 */
export function chunkWeChatText(text: string, maxCodePoints = WECHAT_MAX_TEXT_CODEPOINTS): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const limit = Math.max(64, maxCodePoints);
  const codepoints = Array.from(trimmed);
  if (codepoints.length <= limit) return [trimmed];

  const chunks: string[] = [];
  let offset = 0;
  let activeFenceHeader: string | null = null;

  while (offset < codepoints.length) {
    const prefix = activeFenceHeader ? `${activeFenceHeader}\n` : '';
    const prefixLen = Array.from(prefix).length;
    // Reserve 4 code points for a potential closing "\n```" suffix.
    const budget = Math.max(16, limit - prefixLen - 4);
    let end = Math.min(offset + budget, codepoints.length);

    if (end < codepoints.length) {
      // Never split inside a run of backticks.
      while (end > offset && (codepoints[end - 1] === '`' || codepoints[end] === '`')) {
        end--;
      }
      if (end <= offset) end = Math.min(offset + budget, codepoints.length);

      const floor = offset + Math.floor(budget * 0.55);
      // Prefer double-newline paragraph break, then single newline, then whitespace.
      let splitAt = -1;
      for (let i = end; i > floor; i--) {
        if (codepoints[i - 1] === '\n' && codepoints[i - 2] === '\n') {
          splitAt = i;
          break;
        }
      }
      if (splitAt < 0) {
        for (let i = end; i > floor; i--) {
          if (codepoints[i - 1] === '\n') {
            splitAt = i;
            break;
          }
        }
      }
      if (splitAt < 0) {
        for (let i = end; i > floor; i--) {
          if (/\s/.test(codepoints[i - 1] ?? '')) {
            splitAt = i;
            break;
          }
        }
      }
      if (splitAt > offset) end = splitAt;
    }

    const slice = codepoints.slice(offset, end).join('');
    activeFenceHeader = scanFenceState(slice, activeFenceHeader);
    const suffix = activeFenceHeader && end < codepoints.length ? '\n```' : '';
    chunks.push(`${prefix}${slice}${suffix}`);
    offset = end;
  }

  return chunks;
}

function scanFenceState(chunk: string, initialHeader: string | null): string | null {
  let active = initialHeader;
  for (const line of chunk.split('\n')) {
    const trimmed = line.trim();
    if (trimmed.startsWith('```')) {
      if (active) {
        active = null;
      } else {
        const lang = trimmed.slice(3).trim().split(/\s+/)[0] ?? '';
        active = lang && lang.length <= 24 ? `\`\`\`${lang}` : '```';
      }
    }
  }
  return active;
}

export interface UploadedWeChatMedia {
  filekey: string;
  encryptQueryParam: string;
  aesKeyBase64: string;
  plaintextSize: number;
  ciphertextSize: number;
}

/** Encrypts and uploads an outbound image buffer to WeChat's C2C CDN.
 *
 * Args:
 *   params: Image bytes, target owner WeChat user ID, and iLink credentials.
 * Returns:
 *   CDN parameters ready for `sendWeChatItem` (`image_item`).
 */
export async function uploadWeChatOutboundImage(params: {
  data: Buffer;
  toUserId: string;
  baseUrl: string;
  token: string;
  abortSignal?: AbortSignal;
  env?: NodeJS.ProcessEnv;
}): Promise<UploadedWeChatMedia> {
  if (params.data.length === 0 || params.data.length > 10 * 1024 * 1024) {
    throw new Error('WeChat outbound image must be between 1 B and 10 MiB');
  }
  const aesKey = randomBytes(16);
  const filekey = randomBytes(16).toString('hex');
  const rawsize = params.data.length;
  const rawfilemd5 = createHash('md5').update(params.data).digest('hex');
  const filesize = aesEcbPaddedSize(rawsize);

  const uploadMeta = await getWeChatUploadUrl({
    baseUrl: params.baseUrl,
    token: params.token,
    filekey,
    media_type: WeChatUploadMediaType.IMAGE,
    to_user_id: params.toUserId,
    rawsize,
    rawfilemd5,
    filesize,
    no_need_thumb: true,
    aeskey: aesKey.toString('hex'),
    abortSignal: params.abortSignal,
    env: params.env,
  });

  const cdnBase = resolveWeChatCdnBaseUrl(params.env);
  const rawUploadUrl = uploadMeta.upload_full_url?.trim()
    || (uploadMeta.upload_param
      ? `${cdnBase}/upload?encrypted_query_param=${encodeURIComponent(uploadMeta.upload_param)}&filekey=${encodeURIComponent(filekey)}`
      : '');
  if (!rawUploadUrl) {
    throw new Error('WeChat getuploadurl returned no upload URL');
  }
  const uploadUrl = assertWeChatAllowedUrl(rawUploadUrl, params.env);
  const ciphertext = encryptAesEcb(params.data, aesKey);

  const response = await fetch(uploadUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream' },
    body: new Uint8Array(ciphertext),
    redirect: 'error',
    ...(params.abortSignal ? { signal: params.abortSignal } : {}),
  });
  if (!response.ok) {
    throw new Error(`WeChat CDN upload failed (${response.status})`);
  }
  const encryptQueryParam = response.headers.get('x-encrypted-param')?.trim();
  if (!encryptQueryParam) {
    throw new Error('WeChat CDN upload response missing x-encrypted-param');
  }

  return {
    filekey,
    encryptQueryParam,
    aesKeyBase64: Buffer.from(aesKey.toString('hex'), 'utf8').toString('base64'),
    plaintextSize: rawsize,
    ciphertextSize: filesize,
  };
}
