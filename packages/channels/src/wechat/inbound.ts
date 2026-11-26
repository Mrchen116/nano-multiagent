import { basename, extname } from 'node:path';
import type { WeChatInboundMessage, WeChatInboundPart, WeChatInboundTransformContext } from './connection.js';
import { decryptAesEcb, parseWeChatAesKey, readBoundedResponseBytes } from './crypto.js';
import {
  WeChatItemType,
  assertWeChatAllowedUrl,
  resolveWeChatCdnBaseUrl,
  type WeChatCdnMedia,
  type WeChatMessageItem,
  type WeChatWireMessage,
} from './ilink.js';
import { WeChatQuoteStore } from './quote-store.js';
import { parseWeChatXmlPayload } from './xml.js';

export const MAX_WECHAT_IMAGE_BYTES = 16 * 1024 * 1024;
export const MAX_NORMALIZED_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_WECHAT_IMAGE_DIMENSION = 4096;
export const MAX_WECHAT_VOICE_BYTES = 8 * 1024 * 1024;
export const MAX_WECHAT_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_WECHAT_MESSAGE_MEDIA_BYTES = 40 * 1024 * 1024;

const MEDIA_DOWNLOAD_TIMEOUT_MS = 30_000;

const EXTENSION_MIME: Record<string, string> = {
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
  '.m4a': 'audio/mp4',
  '.amr': 'audio/amr',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
};

function sanitizeWeChatFileName(rawName: string | undefined, fallback: string): string {
  const cleaned = basename((rawName ?? '').replace(/\\/g, '/').trim())
    .replace(/[\x00-\x1f\x7f<>:"/\\|?*]+/g, '_')
    .replace(/^\.+/, '')
    .trim();
  if (!cleaned) return fallback;
  const ext = extname(cleaned).slice(0, 16);
  const stem = cleaned.slice(0, cleaned.length - ext.length).slice(0, 80) || 'attachment';
  return `${stem}${ext}`;
}

function inferWeChatMimeType(fileName: string, fallback = 'application/octet-stream'): string {
  return EXTENSION_MIME[extname(fileName).toLowerCase()] ?? fallback;
}

/** Wraps raw little-endian PCM samples in a standard 44-byte RIFF/WAVE header.
 *
 * Args:
 *   pcmBytes: Signed 16-bit PCM sample buffer (`pcm_s16le`).
 *   sampleRate: Audio sample rate in Hz (defaults to `24_000`).
 *   bitsPerSample: Bits per sample (defaults to `16`).
 *   channels: Audio channel count (defaults to `1` mono).
 * Returns:
 *   Complete `.wav` file buffer.
 */
export function wrapPcm16MonoWav(
  pcmBytes: Buffer,
  sampleRate = 24_000,
  bitsPerSample = 16,
  channels = 1,
): Buffer {
  const byteRate = sampleRate * channels * (bitsPerSample / 8);
  const blockAlign = channels * (bitsPerSample / 8);
  const header = Buffer.alloc(44);
  header.write('RIFF', 0, 'ascii');
  header.writeUInt32LE(36 + pcmBytes.length, 4);
  header.write('WAVE', 8, 'ascii');
  header.write('fmt ', 12, 'ascii');
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20); // PCM format = 1
  header.writeUInt16LE(channels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE(blockAlign, 32);
  header.writeUInt16LE(bitsPerSample, 34);
  header.write('data', 36, 'ascii');
  header.writeUInt32LE(pcmBytes.length, 40);
  return Buffer.concat([header, pcmBytes]);
}

async function downloadAndDecryptMedia(params: {
  media?: WeChatCdnMedia;
  fallbackHexKey?: string;
  maxPlaintextBytes: number;
  label: string;
  abortSignal: AbortSignal;
  env: NodeJS.ProcessEnv;
}): Promise<Buffer> {
  const media = params.media;
  const queryParam = media?.encrypt_query_param?.trim();
  const rawFullUrl = media?.full_url?.trim();
  if (!queryParam && !rawFullUrl) {
    throw new Error(`${params.label}: missing CDN download coordinates`);
  }
  const rawKey = params.fallbackHexKey?.trim() || media?.aes_key?.trim();
  if (!rawKey) {
    throw new Error(`${params.label}: missing AES-128 key`);
  }
  const key = parseWeChatAesKey(rawKey, params.label);

  const cdnBase = resolveWeChatCdnBaseUrl(params.env);
  const candidateUrl = rawFullUrl || `${cdnBase}/download?encrypted_query_param=${encodeURIComponent(queryParam!)}`;
  const safeUrl = assertWeChatAllowedUrl(candidateUrl, params.env);

  const signal = AbortSignal.any([params.abortSignal, AbortSignal.timeout(MEDIA_DOWNLOAD_TIMEOUT_MS)]);
  const response = await fetch(safeUrl, {
    method: 'GET',
    redirect: 'error',
    signal,
  });
  if (!response.ok) {
    throw new Error(`${params.label}: CDN download failed (${response.status})`);
  }
  // Allow up to 16 bytes of PKCS#7 block padding on top of maxPlaintextBytes.
  const ciphertext = await readBoundedResponseBytes(response, params.maxPlaintextBytes + 16, signal);
  const plaintext = decryptAesEcb(ciphertext, key);
  if (plaintext.length === 0 || plaintext.length > params.maxPlaintextBytes) {
    throw new Error(`${params.label}: decrypted payload exceeds ${Math.round(params.maxPlaintextBytes / (1024 * 1024))} MiB`);
  }
  return plaintext;
}

async function normalizeWeChatImage(rawBytes: Buffer): Promise<{ data: Buffer; mediaType: string; ext: string }> {
  const sharp = (await import('sharp')).default;
  const meta = await sharp(rawBytes, { failOn: 'none' }).metadata();
  const hasExifOrientation = meta.orientation !== undefined && meta.orientation !== 1;
  const exceedsDimensions = (meta.width ?? 0) > MAX_WECHAT_IMAGE_DIMENSION || (meta.height ?? 0) > MAX_WECHAT_IMAGE_DIMENSION;
  const supportedDirectFormat = meta.format === 'jpeg' || meta.format === 'png' || meta.format === 'webp' || meta.format === 'gif';

  if (!hasExifOrientation && !exceedsDimensions && supportedDirectFormat && rawBytes.length <= MAX_NORMALIZED_IMAGE_BYTES) {
    const ext = meta.format === 'jpeg' ? '.jpg' : `.${meta.format}`;
    const mediaType = meta.format === 'jpeg' ? 'image/jpeg' : `image/${meta.format}`;
    return { data: rawBytes, mediaType, ext };
  }

  let pipeline = sharp(rawBytes, { failOn: 'none' }).rotate();
  if (exceedsDimensions) {
    pipeline = pipeline.resize({
      width: MAX_WECHAT_IMAGE_DIMENSION,
      height: MAX_WECHAT_IMAGE_DIMENSION,
      fit: 'inside',
      withoutEnlargement: true,
    });
  }

  if (meta.format === 'png' && !exceedsDimensions && rawBytes.length <= MAX_NORMALIZED_IMAGE_BYTES) {
    const pngOut = await pipeline.png().toBuffer();
    if (pngOut.length <= MAX_NORMALIZED_IMAGE_BYTES) {
      return { data: pngOut, mediaType: 'image/png', ext: '.png' };
    }
  }

  for (const quality of [86, 72, 58]) {
    const jpegOut = await pipeline.jpeg({ quality, mozjpeg: true }).toBuffer();
    if (jpegOut.length <= MAX_NORMALIZED_IMAGE_BYTES) {
      return { data: jpegOut, mediaType: 'image/jpeg', ext: '.jpg' };
    }
  }

  const fallbackOut = await pipeline
    .resize({ width: 2048, height: 2048, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 60 })
    .toBuffer();
  if (fallbackOut.length > MAX_NORMALIZED_IMAGE_BYTES) {
    throw new Error('Image still exceeds 10 MiB after normalization');
  }
  return { data: fallbackOut, mediaType: 'image/jpeg', ext: '.jpg' };
}

async function decodeWeChatVoice(
  rawBytes: Buffer,
  voiceItem: NonNullable<WeChatMessageItem['voice_item']>,
): Promise<{ data: Buffer; mediaType: string; fileName: string }> {
  if (rawBytes.subarray(0, 4).toString('ascii') === 'RIFF' && rawBytes.subarray(8, 12).toString('ascii') === 'WAVE') {
    return { data: rawBytes, mediaType: 'audio/wav', fileName: 'voice.wav' };
  }
  if (voiceItem.encode_type === 1) {
    const rate = voiceItem.sample_rate && voiceItem.sample_rate > 0 ? voiceItem.sample_rate : 24_000;
    const bits = voiceItem.bits_per_sample && voiceItem.bits_per_sample > 0 ? voiceItem.bits_per_sample : 16;
    return {
      data: wrapPcm16MonoWav(rawBytes, rate, bits, 1),
      mediaType: 'audio/wav',
      fileName: 'voice.wav',
    };
  }

  const { decode, isSilk } = await import('silk-wasm');
  if (voiceItem.encode_type === 6 || isSilk(rawBytes)) {
    const decoded = await decode(rawBytes, 24_000);
    const wav = wrapPcm16MonoWav(Buffer.from(decoded.data), 24_000, 16, 1);
    return { data: wav, mediaType: 'audio/wav', fileName: 'voice.wav' };
  }

  if (voiceItem.encode_type === 7 || rawBytes.subarray(0, 3).toString('ascii') === 'ID3' || (rawBytes[0] === 0xff && (rawBytes[1]! & 0xe0) === 0xe0)) {
    return { data: rawBytes, mediaType: 'audio/mpeg', fileName: 'voice.mp3' };
  }

  throw new Error(`Unsupported voice encoding (${voiceItem.encode_type ?? 'unknown'})`);
}

/** Transforms a raw iLink `WeChatWireMessage` into a normalized `WeChatInboundMessage`.
 *
 * Handles plain text, `<appmsg>` share/article cards, recursive `<recordinfo>` merged-forwards,
 * `partial_text` / `svr_id` quote resolution, dual-layer voice (`text` transcript + `PCM`/`SILK` -> `24kHz WAV`),
 * `16 MiB` EXIF-oriented images (without `[图片]` placeholder text), bounded `FILE`/`VIDEO` downloads,
 * and explicit non-silent fallback notices for unsupported items.
 */
export async function transformWeChatInboundMessage(
  wire: WeChatWireMessage,
  ctx: WeChatInboundTransformContext,
): Promise<WeChatInboundMessage | undefined> {
  const senderId = wire.from_user_id?.trim();
  const msgId = String(wire.message_id ?? wire.svr_id ?? wire.seq ?? '');
  if (!senderId || !msgId) return undefined;

  const quoteStore = new WeChatQuoteStore(ctx.db);
  quoteStore.ensureSchema();

  const items = wire.item_list ?? [];
  const parts: WeChatInboundPart[] = [];
  const notices: string[] = [];
  const mediaSummaries: string[] = [];
  let cumulativeMediaBytes = 0;
  let sawXmlOrRef = false;
  let refPrefix: string | undefined;

  for (const [index, item] of items.entries()) {
    if (!refPrefix && item.ref_msg) {
      sawXmlOrRef = true;
      refPrefix = quoteStore.formatRefPrefix(item.ref_msg);
    }

    if (item.type === WeChatItemType.TEXT) {
      const rawText = item.text_item?.text ?? '';
      const parsedXml = parseWeChatXmlPayload(rawText);
      if (parsedXml.kind === 'plain_text') {
        if (parsedXml.text) {
          parts.push({ type: 'text', text: parsedXml.text });
        }
      } else if (parsedXml.kind === 'share_card' || parsedXml.kind === 'merged_forward' || parsedXml.kind === 'xml_quote') {
        sawXmlOrRef = true;
        parts.push({ type: 'text', text: parsedXml.formatted });
      } else {
        sawXmlOrRef = true;
        notices.push('暂不支持直接解析该类型的微信消息（如动画表情或特殊卡片），请发送文字、图片、语音、链接或文件。');
        parts.push({ type: 'text', text: '[收到暂不支持直接解析的微信特殊消息类型]' });
      }
      continue;
    }

    if (item.type === WeChatItemType.IMAGE && item.image_item) {
      const declaredSize = Number(item.image_item.hd_size ?? item.image_item.mid_size ?? 0);
      if (declaredSize > MAX_WECHAT_IMAGE_BYTES + 16) {
        notices.push('收到微信原图超过 16 MiB 上限，无法下载解析，请压缩或截图后重发。');
        parts.push({ type: 'text', text: '[收到超过 16 MiB 上限的微信图片，未能下载]' });
        continue;
      }
      if (cumulativeMediaBytes >= MAX_WECHAT_MESSAGE_MEDIA_BYTES) {
        notices.push('单条微信消息媒体总大小超过 40 MiB 上限，部分媒体已跳过。');
        parts.push({ type: 'text', text: '[部分微信图片因超出单消息 40 MiB 媒体上限未下载]' });
        continue;
      }
      try {
        const media = item.image_item.media?.encrypt_query_param || item.image_item.media?.full_url
          ? item.image_item.media
          : item.image_item.thumb_media;
        const decrypted = await downloadAndDecryptMedia({
          media,
          fallbackHexKey: item.image_item.aeskey,
          maxPlaintextBytes: MAX_WECHAT_IMAGE_BYTES,
          label: 'wechat_image',
          abortSignal: ctx.abortSignal,
          env: ctx.env,
        });
        if (cumulativeMediaBytes + decrypted.length > MAX_WECHAT_MESSAGE_MEDIA_BYTES) {
          notices.push('单条微信消息媒体总大小超过 40 MiB 上限，部分图片已跳过。');
          parts.push({ type: 'text', text: '[微信图片超出单消息 40 MiB 媒体总预算]' });
          continue;
        }
        cumulativeMediaBytes += decrypted.length;
        const normalized = await normalizeWeChatImage(decrypted);
        parts.push({
          type: 'image',
          key: `img_${index}`,
          data: normalized.data,
          mediaType: normalized.mediaType,
          fileName: `wechat-image-${index + 1}${normalized.ext}`,
        });
        mediaSummaries.push('[图片]');
      } catch (err) {
        const detail = err instanceof Error && err.message.includes('limit')
          ? '超过 16 MiB 上限'
          : '媒体下载或解密失败';
        notices.push(`微信图片处理失败（${detail}），请重发或改发截图。`);
        parts.push({ type: 'text', text: `[收到微信图片，但${detail}]` });
      }
      continue;
    }

    if (item.type === WeChatItemType.VOICE && item.voice_item) {
      const transcript = item.voice_item.text?.trim();
      if (transcript) {
        parts.push({ type: 'text', text: `[语音转写] ${transcript}` });
        mediaSummaries.push(`[语音] ${transcript.slice(0, 80)}`);
        continue;
      }
      try {
        const decrypted = await downloadAndDecryptMedia({
          media: item.voice_item.media,
          maxPlaintextBytes: MAX_WECHAT_VOICE_BYTES,
          label: 'wechat_voice',
          abortSignal: ctx.abortSignal,
          env: ctx.env,
        });
        if (cumulativeMediaBytes + decrypted.length > MAX_WECHAT_MESSAGE_MEDIA_BYTES) {
          notices.push('单条微信消息媒体总大小超过 40 MiB 上限，语音已跳过。');
          parts.push({ type: 'text', text: '[微信语音超出单消息 40 MiB 媒体上限]' });
          continue;
        }
        cumulativeMediaBytes += decrypted.length;
        const audio = await decodeWeChatVoice(decrypted, item.voice_item);
        parts.push({
          type: 'text',
          text: `[收到微信语音（无自带转写），已解密转换为音频附件 ${audio.fileName}]`,
        });
        parts.push({
          type: 'file',
          key: `voice_${index}`,
          data: audio.data,
          mediaType: audio.mediaType,
          fileName: audio.fileName,
        });
        mediaSummaries.push(`[语音附件: ${audio.fileName}]`);
      } catch (err) {
        const detail = err instanceof Error && err.message.includes('limit')
          ? '超过 8 MiB 语音上限'
          : '未附带文字转写且音频转码失败';
        notices.push(`未能解析该条微信语音（${detail}），请改发文字或在微信开启语音转文字后重试。`);
        parts.push({ type: 'text', text: `[收到微信语音，但${detail}]` });
      }
      continue;
    }

    if (item.type === WeChatItemType.FILE && item.file_item) {
      const fileName = sanitizeWeChatFileName(item.file_item.file_name, `wechat-file-${index + 1}.bin`);
      const declaredLen = Number.parseInt(item.file_item.len ?? '0', 10);
      if (Number.isFinite(declaredLen) && declaredLen > MAX_WECHAT_FILE_BYTES) {
        notices.push(`文件「${fileName}」超过 25 MiB 单文件上限，未能下载处理。`);
        parts.push({ type: 'text', text: `[收到微信文件「${fileName}」，但超过 25 MiB 上限未下载]` });
        continue;
      }
      try {
        const decrypted = await downloadAndDecryptMedia({
          media: item.file_item.media,
          maxPlaintextBytes: MAX_WECHAT_FILE_BYTES,
          label: 'wechat_file',
          abortSignal: ctx.abortSignal,
          env: ctx.env,
        });
        if (cumulativeMediaBytes + decrypted.length > MAX_WECHAT_MESSAGE_MEDIA_BYTES) {
          notices.push(`文件「${fileName}」超出单条消息 40 MiB 媒体总预算，未能接收。`);
          parts.push({ type: 'text', text: `[微信文件「${fileName}」超出单消息 40 MiB 媒体总预算]` });
          continue;
        }
        cumulativeMediaBytes += decrypted.length;
        parts.push({
          type: 'file',
          key: `file_${index}`,
          data: decrypted,
          mediaType: inferWeChatMimeType(fileName),
          fileName,
        });
        mediaSummaries.push(`[文件: ${fileName}]`);
      } catch (err) {
        const detail = err instanceof Error && err.message.includes('limit')
          ? '超过 25 MiB 单文件上限'
          : '文件下载或解密失败';
        notices.push(`文件「${fileName}」处理失败（${detail}）。`);
        parts.push({ type: 'text', text: `[收到微信文件「${fileName}」，但${detail}]` });
      }
      continue;
    }

    if (item.type === WeChatItemType.VIDEO && item.video_item) {
      const fileName = `wechat-video-${index + 1}.mp4`;
      const declaredSize = Number(item.video_item.video_size ?? 0);
      if (declaredSize > MAX_WECHAT_FILE_BYTES + 16) {
        notices.push('微信视频超过 25 MiB 上限，未能下载处理。');
        parts.push({ type: 'text', text: '[收到超过 25 MiB 上限的微信视频，未下载]' });
        continue;
      }
      try {
        const decrypted = await downloadAndDecryptMedia({
          media: item.video_item.media,
          maxPlaintextBytes: MAX_WECHAT_FILE_BYTES,
          label: 'wechat_video',
          abortSignal: ctx.abortSignal,
          env: ctx.env,
        });
        if (cumulativeMediaBytes + decrypted.length > MAX_WECHAT_MESSAGE_MEDIA_BYTES) {
          notices.push('微信视频超出单条消息 40 MiB 媒体总预算，未能接收。');
          parts.push({ type: 'text', text: '[微信视频超出单消息 40 MiB 媒体总预算]' });
          continue;
        }
        cumulativeMediaBytes += decrypted.length;
        parts.push({
          type: 'file',
          key: `video_${index}`,
          data: decrypted,
          mediaType: 'video/mp4',
          fileName,
        });
        mediaSummaries.push(`[视频: ${fileName}]`);
      } catch (err) {
        const detail = err instanceof Error && err.message.includes('limit')
          ? '超过 25 MiB 上限'
          : '视频下载或解密失败';
        notices.push(`微信视频处理失败（${detail}）。`);
        parts.push({ type: 'text', text: `[收到微信视频，但${detail}]` });
      }
      continue;
    }

    sawXmlOrRef = true;
    notices.push('暂不支持直接解析该类型的微信消息（如动画表情、位置或特殊名片），请发送文字、图片、语音、链接或文件。');
    parts.push({ type: 'text', text: '[收到暂不支持直接解析的微信特殊消息类型]' });
  }

  if (parts.length === 0) {
    notices.push('暂不支持直接解析该类型的微信消息，请发送文字、图片、语音、链接或文件。');
    parts.push({ type: 'text', text: '[收到空负载或暂不支持解析的微信消息]' });
  }

  if (refPrefix) {
    const firstTextIdx = parts.findIndex(p => p.type === 'text');
    if (firstTextIdx >= 0 && parts[firstTextIdx]?.type === 'text') {
      parts[firstTextIdx] = { type: 'text', text: `${refPrefix}${(parts[firstTextIdx] as { type: 'text'; text: string }).text}` };
    } else {
      parts.unshift({ type: 'text', text: refPrefix.trimEnd() });
    }
  }

  const combinedText = parts
    .filter((p): p is Extract<WeChatInboundPart, { type: 'text' }> => p.type === 'text')
    .map(p => p.text)
    .join('\n')
    .trim();
  const svrId = String(wire.svr_id ?? wire.message_id ?? '');
  if (svrId) {
    quoteStore.save({
      svrId,
      direction: 'inbound',
      text: combinedText,
      ...(mediaSummaries.length > 0 ? { mediaSummary: mediaSummaries.join(' ') } : {}),
    });
  }

  const plainSingleText = items.length === 1
    && items[0]?.type === WeChatItemType.TEXT
    && !sawXmlOrRef
    && notices.length === 0
    && parts.length === 1
    && parts[0]?.type === 'text';

  const uniqueNotices = Array.from(new Set(notices));
  return {
    messageId: msgId,
    svrId: svrId || undefined,
    chatId: senderId,
    senderId,
    isGroup: false,
    mentioned: true,
    time: String(wire.create_time_ms ?? Date.now()),
    parts,
    plainSingleText,
    ...(uniqueNotices.length > 0 ? { preprocessNotice: uniqueNotices.join('\n') } : {}),
  };
}
