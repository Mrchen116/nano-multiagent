import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { createHistoryView } from 'dsh-agent-context';
import { isHumanSource } from '../input-source.js';

export interface HistoryLocator { session_id: string; window_id: string; item_id?: string }
export type HistoryLocators = Record<string, Record<number, HistoryLocator>>;
type RecordValue = Record<string, unknown>;

/** Resolve source references through the same public History view used for recovery. */
export function historyLocators(sessionId: string, events: readonly SessionEvent[]): Record<number, HistoryLocator> {
  const view = createHistoryView(sessionId, events);
  const messages = events.filter(event => event.type === 'assistant/message' || event.type === 'tool/result' ||
    event.type === 'user/message' && !['runtime-context', 'compact-checkpoint', 'agent-context'].includes(event.data.source.kind));
  const result: Record<number, HistoryLocator> = {};
  let cursor: string | undefined; let index = 0;
  do {
    const page = view.search({recent_first:false,limit:100,max_chars_per_item:1,cursor});
    for (const item of page.items) {
      const event = messages[index++]!;
      result[event.seq] = {session_id:sessionId,window_id:item.window_id,item_id:item.item_id};
    }
    cursor = page.next_cursor ?? undefined;
  } while (cursor);
  const calls = new Map<string, HistoryLocator>();
  const results = new Map<string, HistoryLocator>();
  for (const event of messages) {
    if (event.type === 'assistant/message') for (const block of event.data.message.content) {
      if (block.type === 'tool-call') calls.set(block.id, result[event.seq]!);
    }
    if (event.type === 'tool/result') results.set(event.data.message.toolCallId, result[event.seq]!);
  }
  for (const event of events) if (event.type === 'tool/call') {
    const assistant = calls.get(event.data.callId); const output = results.get(event.data.callId);
    if (assistant) result[event.seq] = assistant;
    else if (output) result[event.seq] = {session_id:sessionId,window_id:output.window_id};
  }
  return result;
}

function contentText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.map(block => typeof block === 'string' ? block : block?.type === 'text' ? block.text : JSON.stringify(block, null, 2)).join('\n');
  return content === undefined ? '' : JSON.stringify(content, null, 2);
}
function metadataText(record: RecordValue): string {
  return Object.entries(record).filter(([,value]) => value !== undefined).map(([key,value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`).join('\n');
}

/** Render qualified original payloads without turning tool outputs into user messages. */
export function renderMaterial(events: readonly unknown[]): string {
  return events.map(value => {
    const record = value as RecordValue;
    if (record.type === 'source_text_continuation') {
      return `${renderMaterial([record.source])}\nOriginal message ${record.messageId}; characters ${record.offset}–${record.end}/${record.total}; ${Number(record.end)<Number(record.total)?'same message continues':'message end'}\n${record.text}`;
    }
    const {seq: _seq,sessionId: _sessionId,history: locator,type,time,content,...metadata} = record;
    const history = locator as HistoryLocator | undefined;
    const heading = [type,typeof time === 'number' && Number.isFinite(time) ? new Date(time).toISOString() : typeof time === 'string' ? time : undefined,history?.item_id === undefined ? undefined : `item_id=${history.item_id}`].filter(Boolean).join(' · ');
    if (content && typeof content === 'object' && !Array.isArray(content) && Array.isArray((content as {messages?:unknown[]}).messages)) {
      const {messages,...envelope} = content as {messages:RecordValue[]};
      return [heading ? `### ${heading}` : '',metadataText(metadata),`Conversation: ${JSON.stringify(envelope)}`,renderMaterial(messages)].filter(Boolean).join('\n');
    }
    return [heading ? `### ${heading}` : '',metadataText(metadata),contentText(content)].filter(Boolean).join('\n');
  }).join('\n\n');
}

/** Preserve native roles, full tool payloads and provenance in the shared record format. */
export function nativeMaterial(event: SessionEvent, history?: HistoryLocator): RecordValue | undefined {
  const base = {seq:event.seq,time:event.time,type:event.type,history};
  if (event.type === 'user/message') return {...base,messageId:event.data.id,source:event.data.source,
    evidence:isHumanSource(event.data.source)?'host_attested_human':'agent_or_delegated_task_input_not_human_authorization',content:event.data.content};
  if (event.type === 'assistant/message') {
    const content=event.data.message.content.filter(block=>block.type==='text');
    return content.length ? {...base,evidence:'assistant_self_report',content} : undefined;
  }
  if (event.type === 'tool/call') return {...base,callId:event.data.callId,name:event.data.name,arguments:event.data.arguments};
  if (event.type === 'tool/result') {
    let content: unknown = event.data.message.content;
    try {
      const body = JSON.parse(event.data.message.content.filter(block => block.type === 'text').map(block => block.text).join('\n'));
      if (Array.isArray(body.messages)) content = body;
    } catch { /* Non-JSON output retains its original blocks. */ }
    return {...base,callId:event.data.message.toolCallId,isError:event.data.message.isError === true,content};
  }
  return undefined;
}

/** Group persisted units by source session, retaining unit/page order and complete page bodies. */
export function renderSessionMaterials(units: readonly {sessionId:string;events:readonly unknown[]}[]): Array<{sessionId:string;text:string}> {
  const sessions = new Map<string, unknown[]>();
  for (const unit of units) {
    const records = sessions.get(unit.sessionId) ?? [];
    records.push(...unit.events); sessions.set(unit.sessionId, records);
  }
  return [...sessions].map(([sessionId,records]) => {
    let windowId: string | undefined;
    const text = records.map(value => {
      const record = value as RecordValue;
      const source = record.type === 'source_text_continuation' ? record.source as RecordValue : record;
      const history = source.history as HistoryLocator | undefined;
      const heading = history && history.window_id !== windowId ? `## window_id=${history.window_id}\n\n` : '';
      if (history) windowId = history.window_id;
      return heading + renderMaterial([record]);
    }).join('\n\n');
    return {sessionId,text:`# session_id=${sessionId}\n\n${text}`};
  });
}
