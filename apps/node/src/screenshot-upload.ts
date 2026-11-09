import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { basename, isAbsolute } from 'node:path';
import { chatAttachments, type ChatAttachment } from '@nano/product-contracts';

const MAX_BYTES = 10 * 1024 * 1024;
type ImRequest = (path: string, options?: RequestInit) => Promise<unknown>;

/** Recover an existing screenshot receipt before reading or uploading its original file.
 *
 * Args:
 *   im: Authenticated node request to the IM media service.
 *   input: Trusted publication identity, authorized local path, and upload ordinal.
 * Returns:
 *   The conversation-scoped attachment returned by IM.
 */
export async function uploadScreenshot(im: ImRequest, input: {
  agentId: string; conversationId: string; operationId: string; index: number;
  path: string; lifecycleRevision: number; signal: AbortSignal;
}): Promise<ChatAttachment> {
  if (!isAbsolute(input.path)) throw new Error('Use an absolute local image path');
  const endpoint = `/im/v1/conversations/${encodeURIComponent(input.conversationId)}/images`;
  const query = new URLSearchParams({agent_id:input.agentId, lifecycle_revision:String(input.lifecycleRevision)});
  const key = `${input.operationId}:${input.index}`;
  const recover = async () => {
    const result = await im(`${endpoint}?${query}&upload_key=${encodeURIComponent(key)}`, {signal:input.signal}) as {attachment: unknown};
    return result.attachment == null ? undefined : chatAttachments([result.attachment])[0];
  };
  const existing = await recover();
  if (existing) return existing;

  const file = await open(input.path, constants.O_RDONLY | constants.O_NONBLOCK);
  let bytes: Uint8Array<ArrayBuffer>;
  try {
    const stat = await file.stat();
    if (!stat.isFile() || !stat.size || stat.size > MAX_BYTES) throw new Error('Use a non-empty regular image file up to 10 MiB');
    bytes = new Uint8Array(stat.size + 1);
    const {bytesRead} = await file.read(bytes);
    if (bytesRead !== stat.size) throw new Error('The screenshot changed while reading it');
    bytes = bytes.subarray(0, bytesRead);
  } finally {
    await file.close();
  }

  const name = basename(input.path);
  const mime = /\.jpe?g$/i.test(name) ? 'image/jpeg' : /\.webp$/i.test(name) ? 'image/webp' : 'image/png';
  query.set('file_name', name);
  query.set('screenshot', '1');
  try {
    const result = await im(`${endpoint}?${query}`, {method:'POST', signal:input.signal, body:bytes,
      headers:{'Content-Type':mime, 'Idempotency-Key':key}});
    return chatAttachments([result])[0]!;
  } catch (error) {
    if (input.signal.aborted) throw error;
    const receipt = await recover().catch(() => undefined);
    if (receipt) return receipt;
    throw error;
  }
}
