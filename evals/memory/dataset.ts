import { createHash } from 'node:crypto';
import type { EvaluationHistory, EvaluationQuestion } from '@nano/product-contracts';

export const QUESTION_TYPES = ['single-session-user', 'single-session-assistant', 'single-session-preference', 'temporal-reasoning', 'knowledge-update', 'multi-session'] as const;
export interface GoldRecord { questionId: string; type: string; question: string; answer: string; abstention: boolean; annotations?: { answerSessionIds: unknown; sessionIds: unknown[]; hasAnswer: unknown[][] } }
export interface EvaluationCase { history: EvaluationHistory; question: EvaluationQuestion; gold: GoldRecord }

/** Hash the exact public input without exposing benchmark labels in candidate identifiers. */
export function digest(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

/** Interpret unzoned benchmark dates as UTC, retaining original precision in HistoryInput.
 *
 * Args:
 *   value: LongMemEval date or ISO date/time.
 * Returns:
 *   Unix milliseconds independent of the machine timezone.
 */
export function parseHistoryDate(value: string): number {
  let normalized = value.replace(/\s+\([A-Za-z]+\)/, '').replaceAll('/', '-').trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) normalized += 'T00:00:00Z';
  else {
    normalized = normalized.replace(' ', 'T');
    if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized)) normalized += 'Z';
  }
  const timestamp = Date.parse(normalized);
  if (!Number.isFinite(timestamp) || timestamp < 0) throw new Error(`Invalid history date: ${value}`);
  return timestamp;
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Expected ${label} object`);
  return value as Record<string, unknown>;
}
function text(value: unknown, label: string): string {
  if (typeof value !== 'string') throw new Error(`Expected ${label} string`);
  return value;
}
function array(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`Expected ${label} array`);
  return value;
}

/** Split full histories, future queries and gold before invoking a candidate.
 *
 * Args:
 *   source: Parsed official LongMemEval JSON array.
 *   selectedIds: Exact optional question selection; missing or duplicate IDs reject.
 * Returns:
 *   Complete selected cases in selection order, with label-free candidate inputs.
 */
export function loadCases(source: unknown, selectedIds?: readonly string[]): EvaluationCase[] {
  const all = new Map<string, EvaluationCase>();
  const idsSeen = new Set<string>();
  const selected = selectedIds === undefined ? undefined : new Set(selectedIds);
  for (const row of array(source, 'dataset')) {
    const item = record(row, 'case');
    const id = text(item.question_id, 'question_id');
    if (idsSeen.has(id)) throw new Error(`Duplicate question_id: ${id}`);
    idsSeen.add(id);
    if (selected && !selected.has(id)) continue;
    const type = text(item.question_type, 'question_type');
    if (!QUESTION_TYPES.some(value => value === type)) throw new Error(`Unsupported question type: ${type}`);
    const question = text(item.question, 'question');
    const date = text(item.question_date, 'question_date');
    parseHistoryDate(date);
    const sessions = array(item.haystack_sessions, 'haystack_sessions');
    const ids = array(item.haystack_session_ids, 'haystack_session_ids');
    const dates = array(item.haystack_dates, 'haystack_dates');
    if (sessions.length !== ids.length || sessions.length !== dates.length) throw new Error(`History array length mismatch: ${id}`);
    const caseKey = `case-${digest(id).slice(0, 24)}`;
    const history: EvaluationHistory = { caseKey, sessions: sessions.map((session, index) => {
      const originalId = text(ids[index], 'session id');
      const originalDate = text(dates[index], 'session date');
      return {
        id: `source-${digest([caseKey, originalId, index]).slice(0, 24)}`,
        date: originalDate, timestamp: parseHistoryDate(originalDate),
        turns: array(session, 'session turns').map(raw => {
          const turn = record(raw, 'turn');
          if (turn.role !== 'user' && turn.role !== 'assistant') throw new Error(`Unsupported history role: ${String(turn.role)}`);
          // The whitelist intentionally excludes has_answer and all future dataset annotations.
          return { role: turn.role as 'user' | 'assistant', content: text(turn.content, 'turn content') };
        }),
      };
    }).sort((a, b) => a.timestamp - b.timestamp) };
    all.set(id, { history, question: { id: `query-${digest(id).slice(0, 24)}`, text: question, date },
      gold: { questionId: id, type, question, answer: text(item.answer, 'answer'), abstention: id.includes('_abs'), annotations: { answerSessionIds: item.answer_session_ids, sessionIds: ids,
        hasAnswer: sessions.map(session => array(session, 'session turns').map(turn => record(turn, 'turn').has_answer ?? null)) } } });
  }
  if (selectedIds === undefined) return [...all.values()];
  if (new Set(selectedIds).size !== selectedIds.length) throw new Error('Duplicate selected question ID');
  return selectedIds.map(id => { const item = all.get(id); if (!item) throw new Error(`Missing selected question: ${id}`); return item; });
}
