import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ContentBlock } from '@deepseek-ai/dsh-llm';
import { SessionId, type SessionEvent } from '@deepseek-ai/dsh-session';
import { SessionQueryError } from '@deepseek-ai/dsh-session-query';
import { stripContextItemId } from 'dsh-agent-context';
import type { WorkerRuntime } from '@nano/product-contracts';
import { extractToolSummary } from './work-details.js';
import type { StoredWorker } from './manager.js';

export const MAX_HISTORY_ENTRIES = 400;
export const MAX_STORED_ENTRY_CHARS = 16_000;
export const SUMMARY_ACTIVITY_LIMIT = 5;
export const SUMMARY_ACTIVITY_CHARS = 120;
export const SUMMARY_PREVIEW_CHARS = 600;
export const LIST_DEFAULT_LIMIT = 10;
export const READ_MAX_LIMIT = 30;
export const READ_MESSAGES_DEFAULT_LIMIT = 10;
export const READ_ACTIVITY_DEFAULT_LIMIT = 12;
export const READ_MESSAGES_BUDGET_CHARS = 12_000;
export const READ_ACTIVITY_BUDGET_CHARS = 10_000;
export const READ_MESSAGES_ITEM_CAP = 2_400;
export const READ_ACTIVITY_ITEM_CAP = 1_200;
export const READ_SLICE_CHARS = 4_000;

export interface WorkerUsageSnapshot {
  turnCount: number;
  totalTokens?: number;
  tokensPartial?: boolean;
}

export interface WorkerHistoryEntry {
  seq: number;
  dedupeKey: string;
  time: number;
  kind: 'message' | 'tool' | 'system';
  role?: 'parent' | 'worker';
  via?: 'report';
  toolName?: string;
  callId?: string;
  status?: 'running' | 'ok' | 'error';
  summary?: string;
  text: string;
  durationMs?: number;
  reasonCode?: string;
}

export interface WorkerHistoryRecord {
  rootId: string;
  nextSeq: number;
  truncatedBefore?: number;
  entries: WorkerHistoryEntry[];
}

interface TraceItem {
  item_id: string;
  seq: number;
  time?: string;
  kind: 'message' | 'tool' | 'system';
  role?: 'parent' | 'worker';
  via?: 'report';
  tool_name?: string;
  status?: 'running' | 'ok' | 'error';
  summary?: string;
  text: string;
  duration_ms?: number;
  reason_code?: string;
  is_error?: boolean;
}

export interface WorkerReadSource {
  listRecords(rootId: string): Promise<StoredWorker[]>;
  getRecord(rootId: string, workerId: string): Promise<StoredWorker | undefined>;
  getCliHistory(workerId: string): Promise<WorkerHistoryRecord | undefined>;
}

const EXCLUDED_DSH_USER_SOURCES = new Set([
  'agent-instructions',
  'agent-context',
  'runtime-context',
  'skill-catalog',
  'skill-invocation',
  'working-directory',
  'compact-checkpoint',
  'model-selection',
  'tool-registry',
  'action-cards',
  'ptc-mode',
  'plan-mode',
]);

const PEM_PRIVATE_KEY_RE =
  /-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----/g;
const AUTH_HEADER_RE = /\b(Authorization\s*[:=]\s*(?:Bearer|Basic)\s+)([^\s'",;}{]+)/gi;
const BEARER_STANDALONE_RE = /\b(Bearer\s+)([A-Za-z0-9._~+/=-]{16,})/g;
const PROVIDER_TOKEN_RE =
  /\b(?:sk-ant-[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|glpat-[A-Za-z0-9_-]{20,})\b/g;
const KV_SECRET_RE =
  /(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|auth[_-]?token|secret[_-]?key|private[_-]?key|password|passwd|secret|token)\b(?:\\?["'])?\s*[:=]\s*(?:\\?["'])?)([^\s'",;}{`\\]{8,})/gi;
const URL_USERINFO_RE = /(https?:\/\/[^/\s:@]+:)([^/\s@]+)(@)/gi;
const URL_SENSITIVE_PARAM_RE =
  /([?&](?:api[_-]?key|access[_-]?token|token|secret|signature|sig|auth|key)=)([^&\s'"#]+)/gi;

/** Redact common credentials, tokens, private keys, and sensitive URL parameters. */
export function redactSecrets(input: string): { text: string; redacted: boolean } {
  if (!input) return { text: '', redacted: false };
  let redacted = false;
  const replace = (source: string, pattern: RegExp, replacement: string | ((...args: string[]) => string)): string =>
    source.replace(pattern, (...args) => {
      redacted = true;
      return typeof replacement === 'function'
        ? replacement(...(args as string[]))
        : replacement.replace(/\$(\d)/g, (_, index) => String(args[Number(index)] ?? ''));
    });

  let text = input;
  text = replace(text, PEM_PRIVATE_KEY_RE, '[REDACTED PRIVATE KEY]');
  text = replace(text, AUTH_HEADER_RE, '$1[REDACTED]');
  text = replace(text, BEARER_STANDALONE_RE, '$1[REDACTED]');
  text = replace(text, PROVIDER_TOKEN_RE, '[REDACTED]');
  text = replace(text, URL_USERINFO_RE, '$1[REDACTED]$3');
  text = replace(text, URL_SENSITIVE_PARAM_RE, '$1[REDACTED]');
  text = text.replace(KV_SECRET_RE, (match, prefix: string, value: string) => {
    if (value === '[REDACTED]' || value.startsWith('[REDACTED')) return match;
    redacted = true;
    return `${prefix}[REDACTED]`;
  });
  return { text, redacted };
}

/** Format a compact, uniform usage trailer shared by DSH and external CLI terminal wakes. */
export function formatWorkerUsage(usage: WorkerUsageSnapshot): string {
  const parts = [`turns=${usage.turnCount}`];
  if (usage.totalTokens !== undefined) {
    parts.push(`tokens=${usage.totalTokens}${usage.tokensPartial ? ', partial' : ''}`);
  } else if (usage.tokensPartial) {
    parts.push('tokens=unavailable');
  }
  return `[Worker usage: ${parts.join(', ')}]`;
}

function isoTime(ms: number | undefined): string | undefined {
  return typeof ms === 'number' && Number.isFinite(ms) && ms > 0 ? new Date(ms).toISOString() : undefined;
}

function stripImagesDeep(value: unknown): unknown {
  if (typeof value === 'string') {
    return /^data:image\//i.test(value) ? '[image omitted]' : value;
  }
  if (Array.isArray(value)) return value.map(stripImagesDeep);
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (record.type === 'image') {
      const name = typeof record.name === 'string' && record.name ? `: ${record.name}` : '';
      return `[image omitted${name}]`;
    }
    return Object.fromEntries(
      Object.entries(record).map(([key, item]) => [
        key,
        key === 'data' && typeof record.mimeType === 'string' && record.mimeType.startsWith('image/')
          ? '[image omitted]'
          : stripImagesDeep(item),
      ]),
    );
  }
  return value;
}

/** Convert an arbitrary tool payload into bounded, image-free text for storage or projection. */
export function sanitizeWorkerValue(value: unknown, maxChars = MAX_STORED_ENTRY_CHARS): string {
  if (value === undefined || value === null) return '';
  const cleaned = stripImagesDeep(value);
  let text: string;
  if (typeof cleaned === 'string') {
    text = cleaned;
  } else {
    try {
      text = JSON.stringify(cleaned);
    } catch {
      text = String(cleaned);
    }
  }
  return text.length > maxChars ? `${text.slice(0, maxChars)}…` : text;
}

function renderBlocks(blocks: readonly ContentBlock[]): string {
  const parts: string[] = [];
  for (const block of stripContextItemId(blocks)) {
    if (block.type === 'text' && block.text) {
      parts.push(block.text);
    } else if (block.type === 'image') {
      parts.push('[image omitted]');
    }
  }
  return parts.join('\n').trim();
}

function parseArgs(raw: unknown): unknown {
  if (typeof raw !== 'string') return raw;
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function singleLine(text: string, maxChars = SUMMARY_ACTIVITY_CHARS): string {
  const compact = text.replace(/\s+/g, ' ').trim();
  return compact.length > maxChars ? `${compact.slice(0, maxChars - 1)}…` : compact;
}

function previewText(
  raw: string,
  maxChars = SUMMARY_PREVIEW_CHARS,
): { text: string; truncated: boolean; totalChars: number; redacted: boolean } {
  const { text: safe, redacted } = redactSecrets(raw.trim());
  const totalChars = safe.length;
  if (totalChars <= maxChars) return { text: safe, truncated: false, totalChars, redacted };
  return { text: `${safe.slice(0, maxChars)}…`, truncated: true, totalChars, redacted };
}

function encodeCursor(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

function decodeCursor<T>(cursor: string): T {
  try {
    return JSON.parse(Buffer.from(cursor, 'base64url').toString('utf8')) as T;
  } catch {
    throw new Error('Invalid pagination cursor');
  }
}

/** Synchronously compute settled turn count and accumulated token usage from DSH own events. */
export function computeDshUsage(
  events: readonly SessionEvent[],
  inheritedEventCount: number,
): WorkerUsageSnapshot {
  const turnTokens = new Map<number, { sum: number; missing: boolean; seen: boolean }>();
  let turnCount = 0;
  let totalTokens: number | undefined;
  let tokensPartial = false;

  for (const event of events) {
    if (event.seq < inheritedEventCount) continue;
    if (typeof event.surfaceOp === 'object' && event.surfaceOp?.op === 'replace') continue;
    if (event.type === 'assistant/message') {
      const turn = event.data.turn;
      const bucket = turnTokens.get(turn) ?? { sum: 0, missing: false, seen: false };
      const tokens = event.data.usage?.totalTokens;
      if (typeof tokens === 'number' && Number.isFinite(tokens) && tokens >= 0) {
        bucket.sum += tokens;
        bucket.seen = true;
      } else {
        bucket.missing = true;
      }
      turnTokens.set(turn, bucket);
    } else if (event.type === 'turn/end') {
      turnCount++;
      const bucket = turnTokens.get(event.data.turn);
      if (bucket?.seen) {
        totalTokens = (totalTokens ?? 0) + bucket.sum;
        if (bucket.missing) tokensPartial = true;
      } else {
        tokensPartial = true;
      }
    }
  }

  return {
    turnCount,
    ...(totalTokens !== undefined ? { totalTokens } : {}),
    ...(tokensPartial ? { tokensPartial: true } : {}),
  };
}

function projectDshSession(
  rootId: string,
  events: readonly SessionEvent[],
  inheritedEventCount: number,
): { items: TraceItem[]; usage: WorkerUsageSnapshot; updatedAt?: number } {
  const items: TraceItem[] = [];
  const toolByCallId = new Map<string, TraceItem>();
  const parentReportCallIds = new Set<string>();
  let updatedAt: number | undefined;

  for (const event of events) {
    if (event.seq < inheritedEventCount) continue;
    if (typeof event.surfaceOp === 'object' && event.surfaceOp?.op === 'replace') continue;
    if (typeof event.time === 'number' && Number.isFinite(event.time) && event.time > 0) {
      updatedAt = updatedAt === undefined ? event.time : Math.max(updatedAt, event.time);
    }

    if (event.type === 'user/message') {
      const source = event.data.source;
      if (EXCLUDED_DSH_USER_SOURCES.has(source.kind)) continue;
      const text = renderBlocks(event.data.content);
      if (!text) continue;
      const isParent =
        source.kind === 'user' ||
        (source.kind === 'agent-message' && source.senderSessionId === rootId);
      items.push({
        item_id: `dsh:${event.seq}`,
        seq: event.seq,
        time: isoTime(event.time),
        kind: isParent ? 'message' : 'system',
        ...(isParent ? { role: 'parent' as const } : {}),
        text,
      });
    } else if (event.type === 'tool/call') {
      const parsed = parseArgs(event.data.arguments);
      const record = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : undefined;
      const target = record?.agent_id ?? record?.agent;
      if (
        event.data.name === 'send_message' &&
        (target === rootId || target === 'lead') &&
        typeof record?.message === 'string' &&
        record.message.trim()
      ) {
        parentReportCallIds.add(event.data.callId);
        items.push({
          item_id: `dsh:${event.seq}`,
          seq: event.seq,
          time: isoTime(event.time),
          kind: 'message',
          role: 'worker',
          via: 'report',
          text: record.message.trim(),
        });
        continue;
      }
      const summary = extractToolSummary(parsed);
      const item: TraceItem = {
        item_id: `dsh:${event.seq}`,
        seq: event.seq,
        time: isoTime(event.time),
        kind: 'tool',
        tool_name: event.data.name,
        status: 'running',
        summary: summary ?? event.data.name,
        text: '',
      };
      toolByCallId.set(event.data.callId, item);
      items.push(item);
    } else if (event.type === 'tool/result') {
      const callId = event.data.message.toolCallId;
      if (parentReportCallIds.has(callId)) continue;
      const existing = toolByCallId.get(callId);
      const text = renderBlocks(event.data.message.content);
      if (existing) {
        existing.status = event.data.message.isError ? 'error' : 'ok';
        existing.text = text;
      }
    } else if (event.type === 'assistant/message') {
      const text = renderBlocks(event.data.message.content);
      if (!text) continue;
      const prev = items.at(-1);
      if (prev?.kind === 'message' && prev.role === 'worker' && prev.text.trim() === text.trim()) {
        continue;
      }
      items.push({
        item_id: `dsh:${event.seq}`,
        seq: event.seq,
        time: isoTime(event.time),
        kind: 'message',
        role: 'worker',
        text,
      });
    } else if (event.type === 'turn/end' && event.data.reason.kind !== 'completed') {
      const reason = event.data.reason;
      const message =
        'error' in reason && reason.error
          ? String(reason.error)
          : `Turn ended with reason: ${reason.kind}`;
      items.push({
        item_id: `dsh:${event.seq}`,
        seq: event.seq,
        time: isoTime(event.time),
        kind: 'system',
        is_error: true,
        text: message,
      });
    }
  }

  return { items, usage: computeDshUsage(events, inheritedEventCount), updatedAt };
}

function projectCliHistory(record: WorkerHistoryRecord | undefined): {
  items: TraceItem[];
  historyTruncated: boolean;
} {
  if (!record) return { items: [], historyTruncated: false };
  const items: TraceItem[] = record.entries.map((entry) => ({
    item_id: `cli:${entry.seq}`,
    seq: entry.seq,
    time: isoTime(entry.time),
    kind: entry.kind,
    ...(entry.role ? { role: entry.role } : {}),
    ...(entry.via ? { via: entry.via } : {}),
    ...(entry.toolName ? { tool_name: entry.toolName } : {}),
    ...(entry.status ? { status: entry.status } : {}),
    ...(entry.summary ? { summary: entry.summary } : {}),
    text: entry.text,
    ...(entry.durationMs !== undefined ? { duration_ms: entry.durationMs } : {}),
    ...(entry.reasonCode ? { reason_code: entry.reasonCode } : {}),
    ...(entry.kind === 'system' &&
    (entry.status === 'error' ||
      Boolean(entry.reasonCode) ||
      /\b(error|failed|interrupted|denied|declined|aborted)\b/i.test(entry.text))
      ? { is_error: true }
      : {}),
  }));
  return { items, historyTruncated: Boolean(record.truncatedBefore && record.truncatedBefore > 0) };
}

/** Read-only cross-runtime inspector enforcing ownership, budgets, pagination, and redaction. */
export class WorkerInspector {
  constructor(
    private readonly ctx: Context,
    private readonly workers: WorkerReadSource,
    private readonly bound: (rootId: string) => boolean,
  ) {}

  private assertRoot(root: Agent | undefined): Agent {
    if (!root || root.session.header.origin === 'subagent') {
      throw new Error('Only the Global root can read workers');
    }
    if (!this.bound(root.id)) {
      throw new Error('Worker inspection requires the bound Global root');
    }
    return root;
  }

  private async loadOwned(root: Agent, workerId: string): Promise<StoredWorker> {
    const id = workerId.trim();
    if (!id) throw new Error('worker_id is required');
    const row = await this.workers.getRecord(root.id, id);
    if (!row || row.rootId !== root.id) {
      throw new Error('Worker not found or does not belong to this Global session');
    }
    return row;
  }

  private async loadTrace(
    root: Agent,
    row: StoredWorker,
  ): Promise<{
    items: TraceItem[];
    usage?: WorkerUsageSnapshot;
    updatedAt?: number;
    historyTruncated: boolean;
  }> {
    if (row.runtime === 'dsh') {
      const sessionId = SessionId(row.workerId);
      const live = this.ctx.sessions.get(sessionId);
      if (live) {
        const projected = projectDshSession(root.id, live.snapshotEvents(), live.inheritedEventCount);
        return { ...projected, historyTruncated: false };
      }
      try {
        using observation = await this.ctx.sessionQuery.observeSession(sessionId, { projectionMode: 'none' });
        const projected = projectDshSession(root.id, observation.events, observation.inheritedEventCount);
        return { ...projected, historyTruncated: false };
      } catch (error) {
        if (error instanceof SessionQueryError && error.code === 'SESSION_QUERY_SESSION_NOT_FOUND') {
          return { items: [], historyTruncated: false };
        }
        throw error;
      }
    }
    const cli = projectCliHistory(await this.workers.getCliHistory(row.workerId));
    return { items: cli.items, historyTruncated: cli.historyTruncated };
  }

  /** List all first-level workers owned by this Global / PA root across all runtimes. */
  async list(
    root: Agent | undefined,
    args: { status?: 'all' | 'active' | 'terminal'; cursor?: string; limit?: number } = {},
  ) {
    const owner = this.assertRoot(root);
    const status = args.status ?? 'all';
    const limit = Math.min(Math.max(args.limit ?? LIST_DEFAULT_LIMIT, 1), READ_MAX_LIMIT);
    const all = await this.workers.listRecords(owner.id);

    const matchesStatus = (state: StoredWorker['state']) => {
      if (status === 'active') return state === 'starting' || state === 'running';
      if (status === 'terminal') return state === 'completed' || state === 'failed' || state === 'interrupted';
      return true;
    };

    const sorted = all
      .filter((row) => matchesStatus(row.state))
      .sort((a, b) => {
        const uDiff = (b.updatedAt ?? 0) - (a.updatedAt ?? 0);
        if (uDiff !== 0) return uDiff;
        const cDiff = (b.createdAt ?? 0) - (a.createdAt ?? 0);
        if (cDiff !== 0) return cDiff;
        return a.workerId.localeCompare(b.workerId);
      });

    let startIndex = 0;
    if (args.cursor) {
      const parsed = decodeCursor<{ updatedAt: number; createdAt: number; workerId: string }>(args.cursor);
      if (
        typeof parsed?.updatedAt !== 'number' ||
        typeof parsed?.createdAt !== 'number' ||
        typeof parsed?.workerId !== 'string'
      ) {
        throw new Error('Invalid list cursor');
      }
      startIndex = sorted.findIndex((row) => {
        const u = row.updatedAt ?? 0;
        const c = row.createdAt ?? 0;
        if (u !== parsed.updatedAt) return u < parsed.updatedAt;
        if (c !== parsed.createdAt) return c < parsed.createdAt;
        return row.workerId.localeCompare(parsed.workerId) > 0;
      });
      if (startIndex === -1) startIndex = sorted.length;
    }

    const slice = sorted.slice(startIndex, startIndex + limit);
    const hasMore = startIndex + limit < sorted.length;
    const last = slice.at(-1);

    const workers = slice.map((row) => ({
      worker_id: row.workerId,
      label: redactSecrets(row.label).text,
      runtime: row.runtime as WorkerRuntime,
      state: row.state,
      turn_count: row.turnCount ?? 0,
      ...(row.totalTokens !== undefined ? { total_tokens: row.totalTokens } : {}),
      ...(row.tokensPartial ? { tokens_partial: true } : {}),
      ...(isoTime(row.createdAt) ? { created_at: isoTime(row.createdAt) } : {}),
      ...(isoTime(row.updatedAt) ? { updated_at: isoTime(row.updatedAt) } : {}),
    }));

    return {
      workers,
      ...(hasMore && last
        ? {
            next_cursor: encodeCursor({
              updatedAt: last.updatedAt ?? 0,
              createdAt: last.createdAt ?? 0,
              workerId: last.workerId,
            }),
          }
        : {}),
    };
  }

  /** Return a compact <= ~2 KB status overview without waking or interrupting the worker. */
  async summary(root: Agent | undefined, workerId: string) {
    const owner = this.assertRoot(root);
    const row = await this.loadOwned(owner, workerId);
    const trace = await this.loadTrace(owner, row);

    const turnCount = trace.usage ? Math.max(trace.usage.turnCount, row.turnCount ?? 0) : (row.turnCount ?? 0);
    const totalTokens = trace.usage?.totalTokens ?? row.totalTokens;
    const tokensPartial = trace.usage ? trace.usage.tokensPartial : row.tokensPartial;
    const updatedAt = Math.max(row.updatedAt ?? 0, trace.updatedAt ?? 0) || undefined;

    const activityItems = trace.items.filter(
      (item) => item.kind === 'tool' || (item.kind === 'system' && item.is_error),
    );
    const recentActivity = activityItems.slice(-SUMMARY_ACTIVITY_LIMIT).map((item) => {
      const rawSummary = item.kind === 'tool' ? (item.summary || item.tool_name || 'tool') : item.text;
      const safe = redactSecrets(rawSummary).text;
      return {
        ...(item.time ? { time: item.time } : {}),
        tool_name: item.kind === 'tool' ? (item.tool_name ?? 'tool') : 'system',
        status: item.kind === 'tool' ? (item.status ?? 'ok') : 'error',
        summary: singleLine(safe, SUMMARY_ACTIVITY_CHARS),
      };
    });

    const latestReportItem =
      trace.items.findLast((item) => item.kind === 'message' && item.role === 'worker' && item.via === 'report') ??
      trace.items.findLast((item) => item.kind === 'message' && item.role === 'worker');
    const latestErrorItem =
      trace.items.findLast((item) => item.kind === 'system' && item.is_error) ??
      trace.items.findLast((item) => item.kind === 'tool' && item.status === 'error');

    const reportText = latestReportItem?.text || row.latestReport;
    const errorText =
      row.state === 'failed' || row.state === 'interrupted'
        ? (row.latestError || latestErrorItem?.text)
        : (row.latestError || (latestErrorItem?.kind === 'tool' ? undefined : latestErrorItem?.text));

    const reportPreview = reportText ? previewText(reportText, SUMMARY_PREVIEW_CHARS) : undefined;
    const errorPreview = errorText ? previewText(errorText, SUMMARY_PREVIEW_CHARS) : undefined;

    return {
      worker_id: row.workerId,
      label: redactSecrets(row.label).text,
      runtime: row.runtime as WorkerRuntime,
      state: row.state,
      turn_count: turnCount,
      ...(totalTokens !== undefined ? { total_tokens: totalTokens } : {}),
      ...(tokensPartial ? { tokens_partial: true } : {}),
      ...(isoTime(row.createdAt) ? { created_at: isoTime(row.createdAt) } : {}),
      ...(isoTime(updatedAt) ? { updated_at: isoTime(updatedAt) } : {}),
      recent_activity: recentActivity,
      ...(reportPreview
        ? {
            latest_report: reportPreview.text,
            ...(reportPreview.truncated
              ? {
                  latest_report_truncated: true,
                  latest_report_total_chars: reportPreview.totalChars,
                  ...(latestReportItem ? { latest_report_item_id: latestReportItem.item_id } : {}),
                }
              : {}),
          }
        : {}),
      ...(errorPreview
        ? {
            latest_error: errorPreview.text,
            ...(errorPreview.truncated
              ? {
                  latest_error_truncated: true,
                  latest_error_total_chars: errorPreview.totalChars,
                  ...(latestErrorItem ? { latest_error_item_id: latestErrorItem.item_id } : {}),
                }
              : {}),
          }
        : {}),
    };
  }

  /** Read bounded messages/activity pages or continue one truncated item by item_id + text_offset. */
  async read(
    root: Agent | undefined,
    args: {
      workerId: string;
      view?: 'messages' | 'activity';
      itemId?: string;
      textOffset?: number;
      cursor?: string;
      limit?: number;
    },
  ) {
    const owner = this.assertRoot(root);
    const row = await this.loadOwned(owner, args.workerId);
    const trace = await this.loadTrace(owner, row);

    if (args.itemId !== undefined) {
      if (args.cursor !== undefined || args.limit !== undefined) {
        throw new Error('item_id cannot be combined with cursor or limit');
      }
      const target = trace.items.find((item) => item.item_id === args.itemId);
      if (!target) {
        throw new Error(`Item ${args.itemId} was not found in worker history`);
      }
      const offset = args.textOffset ?? 0;
      if (!Number.isInteger(offset) || offset < 0) {
        throw new Error('text_offset must be a non-negative integer');
      }
      const { text: safe, redacted } = redactSecrets(target.text);
      const totalChars = safe.length;
      const slice = safe.slice(offset, offset + READ_SLICE_CHARS);
      const nextOffset = offset + slice.length < totalChars ? offset + slice.length : undefined;

      return {
        worker_id: row.workerId,
        item_id: target.item_id,
        kind: target.kind,
        ...(target.role ? { role: target.role } : {}),
        ...(target.via ? { via: target.via } : {}),
        ...(target.tool_name ? { tool_name: target.tool_name } : {}),
        ...(target.status ? { status: target.status } : {}),
        ...(target.time ? { time: target.time } : {}),
        text: slice,
        text_offset: offset,
        ...(nextOffset !== undefined ? { next_text_offset: nextOffset } : {}),
        total_chars: totalChars,
        ...(redacted ? { redacted: true } : {}),
      };
    }

    if (args.textOffset !== undefined) {
      throw new Error('text_offset requires item_id');
    }

    const view = args.view ?? 'messages';
    const limit = Math.min(
      Math.max(
        args.limit ?? (view === 'activity' ? READ_ACTIVITY_DEFAULT_LIMIT : READ_MESSAGES_DEFAULT_LIMIT),
        1,
      ),
      READ_MAX_LIMIT,
    );
    const budget = view === 'activity' ? READ_ACTIVITY_BUDGET_CHARS : READ_MESSAGES_BUDGET_CHARS;
    const itemCap = view === 'activity' ? READ_ACTIVITY_ITEM_CAP : READ_MESSAGES_ITEM_CAP;

    let beforeSeq = Number.POSITIVE_INFINITY;
    if (args.cursor) {
      const parsed = decodeCursor<{ before_seq: number; view: string }>(args.cursor);
      if (typeof parsed?.before_seq !== 'number' || parsed?.view !== view) {
        throw new Error('Invalid cursor for this view');
      }
      beforeSeq = parsed.before_seq;
    }

    const eligible = trace.items.filter(
      (item) =>
        item.seq < beforeSeq &&
        (view === 'activity' || item.kind === 'message' || item.kind === 'system'),
    );

    const selectedReversed: Record<string, unknown>[] = [];
    let usedChars = 0;
    let oldestSelectedSeq: number | undefined;

    for (let i = eligible.length - 1; i >= 0 && selectedReversed.length < limit; i--) {
      const raw = eligible[i]!;
      const { text: safeText, redacted: textRedacted } = redactSecrets(raw.text);
      const safeSummary = raw.summary ? redactSecrets(raw.summary) : undefined;
      const redacted = textRedacted || Boolean(safeSummary?.redacted);
      const totalChars = safeText.length;
      const truncated = totalChars > itemCap;
      const shownText = truncated ? safeText.slice(0, itemCap) : safeText;
      const itemCost = shownText.length + (safeSummary?.text.length ?? 0) + 120;

      if (selectedReversed.length > 0 && usedChars + itemCost > budget) break;
      usedChars += itemCost;
      oldestSelectedSeq = raw.seq;

      selectedReversed.push({
        item_id: raw.item_id,
        seq: raw.seq,
        ...(raw.time ? { time: raw.time } : {}),
        kind: raw.kind,
        ...(raw.role ? { role: raw.role } : {}),
        ...(raw.via ? { via: raw.via } : {}),
        ...(raw.tool_name ? { tool_name: raw.tool_name } : {}),
        ...(raw.status ? { status: raw.status } : {}),
        ...(safeSummary ? { summary: singleLine(safeSummary.text, SUMMARY_ACTIVITY_CHARS) } : {}),
        text: shownText,
        ...(raw.duration_ms !== undefined ? { duration_ms: raw.duration_ms } : {}),
        ...(raw.reason_code ? { reason_code: raw.reason_code } : {}),
        ...(truncated ? { truncated: true, next_text_offset: itemCap, total_chars: totalChars } : {}),
        ...(redacted ? { redacted: true } : {}),
      });
    }

    const items = selectedReversed.reverse();
    const hasOlder = oldestSelectedSeq !== undefined && eligible.some((item) => item.seq < oldestSelectedSeq!);

    return {
      worker_id: row.workerId,
      label: redactSecrets(row.label).text,
      runtime: row.runtime as WorkerRuntime,
      state: row.state,
      view,
      items,
      ...(hasOlder && oldestSelectedSeq !== undefined
        ? { next_cursor: encodeCursor({ before_seq: oldestSelectedSeq, view }) }
        : {}),
      ...(trace.historyTruncated ? { history_truncated: true } : {}),
    };
  }
}
