import type { Agent } from '@deepseek-ai/dsh-agent';
import type { ContentBlock, Message } from '@deepseek-ai/dsh-llm';
import { isHumanSource } from '../input-source.js';
import { tokenCost } from './codex-context.js';

type Row = Record<string, unknown>;
export interface RetainedInstructions { units: Row[]; incomplete: boolean }
const body = (content: readonly ContentBlock[]) => content.filter(block => block.type === 'text').map(block => block.text).join('\n');
const record = (value: unknown): Row | undefined => value && typeof value === 'object' && !Array.isArray(value) ? value as Row : undefined;

/** Recover original human units from durable events, never from generated summaries.
 *
 * Args:
 *   agent: Parent whose original events remain available after compaction.
 *   inherited: Host-projected original delegation evidence.
 *   ownerId: PA owner; limits retained human sources to that owner when present.
 * Returns:
 *   Original messages with their immediate interpretation context and provenance.
 */
export function retainInstructions(agent: Agent, inherited: Row[] = [], ownerId?: string): RetainedInstructions {
  const units: Row[] = [];
  let incomplete=false;
  const events = agent.session.snapshotEvents();
  let previous: Row | undefined;
  const calls = new Map<string, string>();
  const messages = new Map<string, Row>();
  const eligible = (sender: Row | undefined) => !ownerId || sender?.is_owner === true || sender?.id === ownerId || sender?.user_id === ownerId;
  const addPage = (page: Row, observation: string) => {
    if (!Array.isArray(page.messages)) return;
    let preceding: Row | undefined;
    for (const value of page.messages) {
      const message = record(value); if (!message) continue;
      const sender = record(message.sender);
      const id = String(message.id ?? '');
      if (id) messages.set(id, message);
      const immediate=preceding;preceding=message;
      if ((sender?.type ?? sender?.kind) !== 'user' || !eligible(sender) || message.partial) continue;
      const replyId = message.reply_to ?? message.reply_to_message_id;
      const reply = replyId ? messages.get(String(replyId)) : undefined;
      units.push({id: `${String(page.conversation_id ?? page.target ?? '')}:${id}`, original_message: message,
        context: {conversation_id: page.conversation_id, conversation_type: page.conversation_type, delivery: page.delivery, observation},
        ...(replyId ? {reply_target: reply ?? {id: replyId, unavailable: true}} : immediate ? {preceding_message:immediate} : {})});
    }
  };
  for (const row of inherited) {
    if(record(row.retained_instruction)){units.push(row.retained_instruction as Row);continue;}
    const origin = record(row.origin);
    if(origin?.kind==='compact-checkpoint'&&!units.length)incomplete=true;
    if (origin?.kind === 'human' && (!ownerId || origin.actorId === ownerId || eligible(record(origin.sender)))) units.push({id: origin.messageId ?? row.id, original_message: row, inherited: true});
    for (const name of ['inbox_result','conversations_result']) { const page = record(row[name]); if (page) addPage(page, 'restored'); }
  }
  for (const event of events) {
    if(event.type==='compaction/start'&&!units.length)incomplete=true;
    if (event.type === 'assistant/message') {
      const message = event.data.message;
      if (body(message.content)) previous = {assistant: body(message.content), id: message.id, visibility: ownerId ? 'private' : 'context'};
      for (const block of message.content) if (block.type === 'tool-call') calls.set(block.id, block.name);
    } else if (event.type === 'user/message') {
      const message = event.data;
      if(message.source.kind==='compact-checkpoint'&&!units.length)incomplete=true;
      if (!isHumanSource(message.source) || ownerId && message.source.actorId !== ownerId) { previous=undefined;continue; }
      units.push({id: message.source.messageId, session_id: agent.id, original_message: {id: message.id, user: body(message.content), source: message.source}, ...(previous ? {preceding_assistant: previous} : {})});
      previous = undefined;
    } else if (event.type === 'tool/result' && !event.data.message.isError) {
      const message = event.data.message;
      if (!['inbox','conversations'].includes(calls.get(message.toolCallId) ?? '')) continue;
      try { const page = record(JSON.parse(body(message.content))); if (page) addPage(page, 'restored'); } catch { /* Non-structured results cannot attest human origin. */ }
    } else if (event.type === 'tool/ptc-dispatch' && !event.data.isError && ['inbox','conversations'].includes(event.data.name)) {
      try { const page = record(JSON.parse(body(event.data.content))); if (page) addPage(page, 'restored'); } catch { /* Same provenance rule for PTC. */ }
    }
  }
  const unique = [...new Map(units.map(unit => [JSON.stringify(unit), unit])).values()];
  return {units: unique, incomplete};
}

/** Select complete recent units and resend those absent from the actual reviewer surface. */
export function retainedEnvelope(retained: RetainedInstructions, history: readonly Message[], budget: number): string {
  const selected: string[] = [];
  const warning='<instructions_incomplete>Original instruction evidence is incomplete. Remaining permissions are not the complete authorization; omitted restrictions or withdrawals may exist.</instructions_incomplete>';
  const render=(units:string[],incomplete:boolean)=>`<original_instructions>\n${units.join('\n')}\n${incomplete?warning:''}\n</original_instructions>\n`;
  let omitted = retained.incomplete;
  for (const unit of [...retained.units].reverse()) {
    const serialized = JSON.stringify(unit);
    if (tokenCost(render([serialized,...selected],true)) > budget) { omitted = true; break; }
    selected.unshift(serialized);
  }
  const visible = history.flatMap(message => message.content.filter(block => block.type === 'text').map(block => block.text));
  const missing = selected.filter(unit => !visible.some(text => text.includes(unit)));
  if (!missing.length && !omitted) return '';
  return render(missing,omitted);
}
