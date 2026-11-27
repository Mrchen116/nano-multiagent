import { createCipheriv, createDecipheriv } from 'node:crypto';

/** Encrypts plaintext bytes with AES-128-ECB and PKCS#7 padding for WeChat CDN transfers.
 *
 * Args:
 *   plaintext: Unencrypted media payload.
 *   key: Raw 16-byte AES-128 key.
 * Returns:
 *   PKCS#7-padded AES-128-ECB ciphertext.
 */
export function encryptAesEcb(plaintext: Buffer, key: Buffer): Buffer {
  const cipher = createCipheriv('aes-128-ecb', key, null);
  return Buffer.concat([cipher.update(plaintext), cipher.final()]);
}

/** Decrypts PKCS#7-padded AES-128-ECB ciphertext downloaded from WeChat CDN.
 *
 * Args:
 *   ciphertext: Encrypted CDN payload.
 *   key: Raw 16-byte AES-128 key.
 * Returns:
 *   Decrypted plaintext bytes.
 */
export function decryptAesEcb(ciphertext: Buffer, key: Buffer): Buffer {
  const decipher = createDecipheriv('aes-128-ecb', key, null);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

/** Computes the exact PKCS#7-padded ciphertext byte length for `getuploadurl`.
 *
 * Args:
 *   plaintextSize: Unencrypted payload byte size.
 * Returns:
 *   Ciphertext byte count aligned to the 16-byte AES block boundary.
 */
export function aesEcbPaddedSize(plaintextSize: number): number {
  return Math.ceil((plaintextSize + 1) / 16) * 16;
}

/** Decodes any of the three AES-128 key encodings observed across iLink item types.
 *
 * Image items may supply a 32-char hex string (`image_item.aeskey`) or `base64(16 raw bytes)`
 * (`media.aes_key`), whereas voice/file/video items frequently supply `base64(32-char ASCII hex)`.
 *
 * Args:
 *   rawKey: Hex or Base64 key string from an iLink media item.
 *   label: Diagnostic context for error reporting (never includes secret bytes).
 * Returns:
 *   16-byte AES-128 key buffer.
 * Raises:
 *   Error: If `rawKey` does not decode to a valid 16-byte AES key.
 */
export function parseWeChatAesKey(rawKey: string, label = 'wechat_media'): Buffer {
  const trimmed = rawKey.trim();
  if (/^[0-9a-fA-F]{32}$/.test(trimmed)) {
    return Buffer.from(trimmed, 'hex');
  }
  const decoded = Buffer.from(trimmed, 'base64');
  if (decoded.length === 16) {
    return decoded;
  }
  if (decoded.length === 32) {
    const ascii = decoded.toString('ascii');
    if (/^[0-9a-fA-F]{32}$/.test(ascii)) {
      return Buffer.from(ascii, 'hex');
    }
  }
  throw new Error(`${label}: invalid AES-128 key encoding (decoded length ${decoded.length})`);
}

/** Reads an HTTP response stream while enforcing a strict byte ceiling before buffering finishes.
 *
 * Args:
 *   response: Fetch response whose body will be consumed.
 *   maxBytes: Maximum allowed byte length.
 *   signal: Optional abort signal cancelling the transfer.
 * Returns:
 *   Buffered response bytes within `maxBytes`.
 * Raises:
 *   Error: When `Content-Length` or streamed bytes exceed `maxBytes`.
 */
export async function readBoundedResponseBytes(
  response: Response,
  maxBytes: number,
  signal?: AbortSignal,
): Promise<Buffer> {
  const declared = Number(response.headers.get('content-length'));
  if (Number.isFinite(declared) && declared > maxBytes) {
    void response.body?.cancel().catch(() => {});
    throw new Error(`Media exceeds limit (${declared} > ${maxBytes} bytes)`);
  }
  if (!response.body) {
    const buf = Buffer.from(await response.arrayBuffer());
    if (buf.length > maxBytes) throw new Error(`Media exceeds limit (${buf.length} > ${maxBytes} bytes)`);
    return buf;
  }
  const reader = response.body.getReader();
  const chunks: Buffer[] = [];
  let total = 0;
  try {
    while (true) {
      signal?.throwIfAborted();
      const { done, value } = await reader.read();
      if (done) break;
      if (!value?.byteLength) continue;
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel().catch(() => {});
        throw new Error(`Media exceeds limit (> ${maxBytes} bytes)`);
      }
      chunks.push(Buffer.from(value));
    }
  } finally {
    reader.releaseLock();
  }
  return Buffer.concat(chunks, total);
}
