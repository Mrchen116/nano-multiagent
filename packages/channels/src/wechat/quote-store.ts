import { createHash } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';
import type { WeChatPartialText, WeChatRefMessage } from './ilink.js';

export interface PartialQuoteResult {
  resolved: string | null;
  fallback: boolean;
}

export interface WeChatQuoteRecord {
  svrId: string;
  direction: 'inbound' | 'outbound';
  text: string;
  mediaSummary?: string;
}

const MAX_QUOTE_ROWS = 500;
const MAX_STORED_TEXT_CHARS = 16_000;
const MAX_EXCERPT_CHARS = 1_000;

function nthIndexOf(text: string, value: string, occurrence: number, fromIndex = 0): number {
  if (!value || !Number.isInteger(occurrence) || occurrence < 0) return -1;
  let position = fromIndex;
  for (let current = 0; current <= occurrence; current++) {
    position = text.indexOf(value, position);
    if (position < 0) return -1;
    if (current < occurrence) position += value.length;
  }
  return position;
}

function hashQuote(text: string): string {
  return createHash('md5').update(text, 'utf8').digest('hex');
}

function sliceCandidate(
  fullText: string,
  partial: WeChatPartialText,
  endSearchMode: 'global' | 'relative',
): string | null {
  const start = nthIndexOf(fullText, partial.start, partial.startindex);
  if (start < 0) return null;
  const end = endSearchMode === 'global'
    ? nthIndexOf(fullText, partial.end, partial.endindex)
    : nthIndexOf(fullText, partial.end, partial.endindex, start + partial.start.length);
  if (end < start) return null;
  return fullText.slice(start, end + partial.end.length);
}

/** Resolves a WeChat partial-text selection quote using 0-based substring occurrence indices.
 *
 * Evaluates both observed iLink `endindex` semantics (`global` from start of message vs `relative`
 * after `start`), disambiguating with `quotemd5` when supplied.
 *
 * Args:
 *   fullText: Cached plaintext of the referenced message.
 *   partial: `partial_text` descriptor from `ref_msg`.
 * Returns:
 *   Exact selected substring or `{ resolved: null, fallback: true }` when unmatched.
 */
export function resolvePartialQuote(fullText: string, partial: WeChatPartialText): PartialQuoteResult {
  if (!fullText || !partial.start || !partial.end) {
    return { resolved: null, fallback: true };
  }
  const candidates = [
    sliceCandidate(fullText, partial, 'global'),
    sliceCandidate(fullText, partial, 'relative'),
  ].filter((value, index, all): value is string => Boolean(value) && all.indexOf(value) === index);

  if (!partial.quotemd5) {
    return candidates[0]
      ? { resolved: candidates[0], fallback: false }
      : { resolved: null, fallback: true };
  }
  const expected = partial.quotemd5.toLowerCase();
  const resolved = candidates.find(value => hashQuote(value) === expected) ?? null;
  return { resolved, fallback: resolved === null };
}

/** Bounded (`<= 500` rows) SQLite quote cache backed by the channel's `0600` local state file. */
export class WeChatQuoteStore {
  constructor(private readonly db: DatabaseSync) {}

  /** Ensures the `quotes` table exists on standalone SQLite handles used in unit tests. */
  ensureSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS quotes(
        svr_id TEXT PRIMARY KEY,
        direction TEXT NOT NULL,
        text TEXT NOT NULL,
        media_json TEXT,
        created_at INTEGER NOT NULL
      );
    `);
  }

  /** Stores a message summary under its lossless decimal `svr_id` without persisting keys or CDN URLs. */
  save(entry: WeChatQuoteRecord): void {
    const id = entry.svrId.trim();
    if (!id) return;
    const text = entry.text.slice(0, MAX_STORED_TEXT_CHARS);
    const mediaJson = entry.mediaSummary ? JSON.stringify({ summary: entry.mediaSummary.slice(0, 200) }) : null;
    try {
      this.db.prepare(
        'INSERT OR REPLACE INTO quotes(svr_id, direction, text, media_json, created_at) VALUES(?,?,?,?,?)',
      ).run(id, entry.direction, text, mediaJson, Date.now());
      this.db.exec(
        `DELETE FROM quotes WHERE svr_id NOT IN (SELECT svr_id FROM quotes ORDER BY created_at DESC LIMIT ${MAX_QUOTE_ROWS})`,
      );
    } catch {
      // Quote persistence is best-effort and must never interrupt message handling.
    }
  }

  /** Reads a cached message entry by its lossless `svr_id`. */
  get(svrId: string): WeChatQuoteRecord | undefined {
    const id = svrId.trim();
    if (!id) return undefined;
    try {
      const row = this.db.prepare(
        'SELECT svr_id, direction, text, media_json FROM quotes WHERE svr_id=?',
      ).get(id) as { svr_id: string; direction: 'inbound' | 'outbound'; text: string; media_json: string | null } | undefined;
      if (!row) return undefined;
      let mediaSummary: string | undefined;
      if (row.media_json) {
        try {
          mediaSummary = (JSON.parse(row.media_json) as { summary?: string }).summary;
        } catch { /* ignore */ }
      }
      return {
        svrId: row.svr_id,
        direction: row.direction,
        text: row.text,
        ...(mediaSummary ? { mediaSummary } : {}),
      };
    } catch {
      return undefined;
    }
  }

  /** Formats a quoted-message context block (`[引用历史消息摘录]`) for model and shadow chat clarity. */
  formatRefPrefix(ref: WeChatRefMessage): string | undefined {
    const lookupId = ref.svr_id?.trim() || ref.message_item?.msg_id?.trim() || '';
    const cached = lookupId ? this.get(lookupId) : undefined;
    const inlineText = ref.message_item?.text_item?.text?.trim()
      || ref.message_item?.voice_item?.text?.trim()
      || '';
    const fullText = cached?.text || inlineText;

    let excerpt = '';
    if (ref.partial_text && fullText) {
      const partial = resolvePartialQuote(fullText, ref.partial_text);
      excerpt = partial.resolved ?? fullText;
    } else if (fullText) {
      excerpt = fullText;
    } else if (cached?.mediaSummary) {
      excerpt = cached.mediaSummary;
    } else if (ref.title?.trim()) {
      excerpt = ref.title.trim();
    } else if (ref.message_item?.image_item) {
      excerpt = '[历史图片]';
    } else if (ref.message_item?.file_item?.file_name) {
      excerpt = `[历史文件: ${ref.message_item.file_item.file_name}]`;
    } else if (lookupId) {
      excerpt = '[历史消息]';
    }

    const normalized = excerpt.trim().slice(0, MAX_EXCERPT_CHARS);
    if (!normalized) return undefined;
    const quotedLines = normalized.split(/\r?\n/).map(line => `> ${line}`).join('\n');
    return `[引用历史消息摘录]\n${quotedLines}\n\n`;
  }
}
