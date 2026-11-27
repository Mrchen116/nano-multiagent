import { randomUUID } from 'node:crypto';
import { constants, createWriteStream, existsSync, unlinkSync } from 'node:fs';
import { mkdir, open, rename } from 'node:fs/promises';
import { once } from 'node:events';
import { basename, extname, isAbsolute, join, resolve } from 'node:path';
import { chatAttachments, isRasterImageMime, type ChatAttachment } from '@nano/product-contracts';
import type { ImRequestOptions } from './im-http.js';

const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const MAX_FILE_BYTES = 25 * 1024 * 1024;
const TRANSFER_TIMEOUT_MS = 60_000;
const NATIVE_ATTACHMENT_URL_RE = /^\/im\/v1\/conversations\/([^/]+)\/(images|attachments)\/([\w-]+)$/;

type ImRequest = (path: string, options?: ImRequestOptions) => Promise<unknown>;

const EXTENSION_MIME_MAP: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.pdf': 'application/pdf',
  '.txt': 'text/plain',
  '.log': 'text/plain',
  '.md': 'text/markdown',
  '.markdown': 'text/markdown',
  '.json': 'application/json',
  '.csv': 'text/csv',
  '.tsv': 'text/tab-separated-values',
  '.yaml': 'text/yaml',
  '.yml': 'text/yaml',
  '.xml': 'application/xml',
  '.html': 'text/html',
  '.htm': 'text/html',
  '.zip': 'application/zip',
  '.gz': 'application/gzip',
  '.tgz': 'application/gzip',
  '.tar': 'application/x-tar',
  '.patch': 'text/plain',
  '.diff': 'text/plain',
  '.py': 'text/plain',
  '.ts': 'text/plain',
  '.tsx': 'text/plain',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.sh': 'text/plain',
  '.sql': 'text/plain',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
};

function inferMimeType(fileName: string): string {
  return EXTENSION_MIME_MAP[extname(fileName).toLowerCase()] ?? 'application/octet-stream';
}

function sanitizeDownloadFilename(rawName: string): string {
  const leaf = basename(rawName.replace(/\\/g, '/').trim())
    .replace(/[\x00-\x1F\x7F<>:"/\\|?*]+/g, '_')
    .replace(/^\.+/, '')
    .trim();
  if (!leaf) return 'attachment';
  const ext = extname(leaf).slice(0, 16);
  const stem = leaf.slice(0, leaf.length - ext.length).slice(0, 80) || 'attachment';
  return `${stem}${ext}`;
}

function filenameFromDisposition(header: string | null): string | undefined {
  if (!header) return undefined;
  const star = /filename\*=UTF-8''([^;\s]+)/i.exec(header);
  if (star?.[1]) {
    try { return decodeURIComponent(star[1]); } catch { /* Ignore malformed RFC 5987 encoding. */ }
  }
  const plain = /filename="([^"]+)"/i.exec(header);
  return plain?.[1] || undefined;
}

/** Upload one local file as an idempotent conversation-scoped IM attachment.
 *
 * Args:
 *   im: Authenticated node request helper for the IM media service.
 *   input: Publication identity, authorized absolute path, and upload ordinal.
 * Returns:
 *   The conversation-scoped attachment descriptor returned by IM.
 */
export async function uploadAttachment(im: ImRequest, input: {
  agentId: string; conversationId: string; operationId: string; index: number;
  path: string; lifecycleRevision: number; signal: AbortSignal;
}): Promise<ChatAttachment> {
  if (!isAbsolute(input.path)) throw new Error('Use an absolute local file path');
  const endpoint = `/im/v1/conversations/${encodeURIComponent(input.conversationId)}/attachments`;
  const query = new URLSearchParams({ agent_id: input.agentId, lifecycle_revision: String(input.lifecycleRevision) });
  const key = `${input.operationId}:file:${input.index}`;
  const recover = async () => {
    const result = await im(`${endpoint}?${query}&upload_key=${encodeURIComponent(key)}`, { signal: input.signal }) as { attachment: unknown };
    return result.attachment == null ? undefined : chatAttachments([result.attachment])[0];
  };
  const existing = await recover();
  if (existing) return existing;

  const name = basename(input.path);
  const mime = inferMimeType(name);
  const maxBytes = isRasterImageMime(mime) ? MAX_IMAGE_BYTES : MAX_FILE_BYTES;
  const file = await open(input.path, constants.O_RDONLY | constants.O_NONBLOCK);
  let bytes: Uint8Array<ArrayBuffer>;
  try {
    const stat = await file.stat();
    if (!stat.isFile() || !stat.size || stat.size > maxBytes) {
      throw new Error(`Use a non-empty regular file up to ${Math.round(maxBytes / (1024 * 1024))} MiB`);
    }
    bytes = new Uint8Array(stat.size + 1);
    const { bytesRead } = await file.read(bytes);
    if (bytesRead !== stat.size) throw new Error('The file changed while reading it');
    bytes = bytes.subarray(0, bytesRead);
  } finally {
    await file.close();
  }

  query.set('file_name', name);
  query.set('file', '1');
  try {
    const result = await im(`${endpoint}?${query}`, {
      method: 'POST',
      signal: input.signal,
      timeoutMs: TRANSFER_TIMEOUT_MS,
      body: bytes,
      headers: { 'Content-Type': mime, 'Idempotency-Key': key },
    });
    return chatAttachments([result])[0]!;
  } catch (error) {
    if (input.signal.aborted) throw error;
    const receipt = await recover().catch(() => undefined);
    if (receipt) return receipt;
    throw error;
  }
}

/** Stream-download one authorized native IM attachment into the Agent's managed download folder.
 *
 * Args:
 *   config: Authenticated IM base URL, token provider, and node home fallback.
 *   input: Short attachment reference, resolved canonical IM URL, and Agent workspace context.
 * Returns:
 *   Saved local path and verified transfer metadata.
 */
const MIME_EXTENSION_MAP: Record<string, string> = {
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/gif': '.gif',
  'image/webp': '.webp',
  'image/svg+xml': '.svg',
  'application/pdf': '.pdf',
  'text/plain': '.txt',
  'text/markdown': '.md',
  'application/json': '.json',
  'text/csv': '.csv',
  'text/tab-separated-values': '.tsv',
  'text/yaml': '.yaml',
  'application/yaml': '.yaml',
  'application/xml': '.xml',
  'text/xml': '.xml',
  'text/html': '.html',
  'application/zip': '.zip',
  'application/gzip': '.gz',
  'audio/mpeg': '.mp3',
  'audio/wav': '.wav',
  'video/mp4': '.mp4',
  'video/webm': '.webm',
};

function appendFallbackExtension(name: string, contentType: string): string {
  if (extname(name)) return name;
  const fallback = MIME_EXTENSION_MAP[contentType];
  return fallback ? `${name}${fallback}` : name;
}

export async function downloadAttachment(config: {
  baseUrl: string;
  token: () => string;
  nodeHome: string;
  resolveExternalAttachment?: (url: string, agentId: string) => { data: Buffer; mediaType: string; fileName?: string };
}, input: {
  agentId: string;
  attachmentId: string;
  url: string;
  fileName?: string;
  workspace?: string;
  signal: AbortSignal;
}): Promise<{
  attachment_id: string;
  local_path: string;
  file_name: string;
  content_type: string;
  byte_size: number;
}> {
  if (input.url.startsWith('external:')) {
    if (!config.resolveExternalAttachment) {
      throw new Error('Only native Nano IM attachments can be downloaded with download_attachment');
    }
    const local = config.resolveExternalAttachment(input.url, input.agentId);
    if (local.data.byteLength > MAX_FILE_BYTES) {
      throw new Error('Attachment exceeds maximum downloadable size (25 MiB)');
    }
    const contentType = (local.mediaType || 'application/octet-stream').split(';')[0]!.trim().toLowerCase() || 'application/octet-stream';
    const safeName = appendFallbackExtension(sanitizeDownloadFilename(local.fileName ?? input.fileName ?? 'attachment'), contentType);
    const safeId = input.attachmentId.replace(/[^a-zA-Z0-9_-]/g, '');
    if (!safeId) throw new Error('Invalid attachment_id');

    const destDir = resolve(input.workspace ? join(input.workspace, '.nano-downloads') : join(config.nodeHome, 'downloads', input.agentId));
    await mkdir(destDir, { recursive: true });
    const destination = resolve(destDir, `${safeId}-${safeName}`);
    if (!destination.startsWith(`${destDir}/`) && !destination.startsWith(`${destDir}\\`)) {
      throw new Error('Attachment download path escapes managed download directory');
    }
    const temporary = join(destDir, `.${safeId}-${randomUUID()}.tmp`);
    const handle = await open(temporary, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY, 0o600);
    let committed = false;
    try {
      await handle.writeFile(local.data);
      await handle.close();
      await rename(temporary, destination);
      committed = true;
      return {
        attachment_id: input.attachmentId,
        local_path: destination,
        file_name: safeName,
        content_type: contentType,
        byte_size: local.data.byteLength,
      };
    } finally {
      if (!committed) {
        await handle.close().catch(() => {});
        if (existsSync(temporary)) {
          try { unlinkSync(temporary); } catch { /* Best-effort temp cleanup. */ }
        }
      }
    }
  }

  if (!NATIVE_ATTACHMENT_URL_RE.test(input.url)) {
    throw new Error('Only native Nano IM attachments can be downloaded with download_attachment');
  }
  const base = new URL(config.baseUrl);
  base.protocol = base.protocol === 'wss:' ? 'https:' : base.protocol === 'ws:' ? 'http:' : base.protocol;
  const target = new URL(input.url, base);
  if (target.origin !== base.origin || !NATIVE_ATTACHMENT_URL_RE.test(target.pathname)) {
    throw new Error('Attachment must come from the authenticated IM media service');
  }
  target.searchParams.set('agent_id', input.agentId);

  const signal = AbortSignal.any([AbortSignal.timeout(TRANSFER_TIMEOUT_MS), input.signal]);
  const response = await fetch(target, {
    signal,
    headers: { Authorization: `Bearer ${config.token()}` },
  });
  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => undefined) as { detail?: unknown; message?: unknown } | undefined;
    const detail = error?.detail ?? error?.message;
    throw new Error(`Attachment download failed (${response.status})${typeof detail === 'string' ? `: ${detail}` : ''}`);
  }

  const contentType = (response.headers.get('content-type') ?? 'application/octet-stream').split(';')[0]!.trim().toLowerCase() || 'application/octet-stream';
  const rawName = filenameFromDisposition(response.headers.get('content-disposition')) ?? input.fileName ?? basename(target.pathname);
  const safeName = appendFallbackExtension(sanitizeDownloadFilename(rawName), contentType);
  const safeId = input.attachmentId.replace(/[^a-zA-Z0-9_-]/g, '');
  if (!safeId) throw new Error('Invalid attachment_id');

  const destDir = resolve(input.workspace ? join(input.workspace, '.nano-downloads') : join(config.nodeHome, 'downloads', input.agentId));
  await mkdir(destDir, { recursive: true });
  const destination = resolve(destDir, `${safeId}-${safeName}`);
  if (!destination.startsWith(`${destDir}/`) && !destination.startsWith(`${destDir}\\`)) {
    throw new Error('Attachment download path escapes managed download directory');
  }
  const temporary = join(destDir, `.${safeId}-${randomUUID()}.tmp`);
  const output = createWriteStream(temporary, { flags: 'wx', mode: 0o600 });
  let size = 0;
  let committed = false;
  try {
    const reader = response.body.getReader();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const bytes = Buffer.from(value.buffer, value.byteOffset, value.byteLength);
        size += bytes.length;
        if (size > MAX_FILE_BYTES) {
          await reader.cancel().catch(() => {});
          throw new Error('Attachment exceeds maximum downloadable size (25 MiB)');
        }
        if (!output.write(bytes)) await once(output, 'drain');
      }
    } finally {
      reader.releaseLock();
    }
    output.end();
    await once(output, 'finish');
    await rename(temporary, destination);
    committed = true;
    return {
      attachment_id: input.attachmentId,
      local_path: destination,
      file_name: safeName,
      content_type: contentType,
      byte_size: size,
    };
  } finally {
    if (!committed) {
      if (!output.closed) {
        const closed = once(output, 'close');
        output.destroy();
        await closed.catch(() => {});
      }
      if (existsSync(temporary)) {
        try { unlinkSync(temporary); } catch { /* Best-effort temp cleanup. */ }
      }
    }
  }
}
