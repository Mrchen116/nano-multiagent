import { createHash } from 'node:crypto';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { isHumanSource } from '../input-source.js';
import type { SourceEligibility } from './memory-documents.js';

const excludedTools = new Set(['memory', 'memory_maintenance', 'skill', 'skill_manage', 'notes', 'history', 'source_history', 'new_context', 'get_context_remaining']);
/** Keep original event identity while removing maintenance and unauthorized mixed-source content. */
export function qualifiedEvents(events: readonly SessionEvent[], options: { sources?: SourceEligibility }): SessionEvent[] {
  const allowed = (id: string) => (!options.sources || options.sources.allowed.includes(id) && !options.sources.excluded.includes(id));
  const calls = new Map<string, boolean>();
  const messages = new Set<string>();
  return events.flatMap<SessionEvent>(original => {
    if (typeof original.surfaceOp === 'object' && original.surfaceOp.op === 'replace') return [];
    const event = structuredClone(original);
    if (event.type === 'user/message') {
      const source = event.data.source;
      if (!isHumanSource(source) && source.kind !== 'user' && source.kind !== 'agent-message' && source.kind !== 'subagent-settled') return [];
      if ('conversationId' in source && !allowed(String(source.conversationId))) return [];
      return [{...event,data:{...event.data,content:event.data.content.filter(block => block.type !== 'reasoning')}}];
    }
    if (event.type === 'assistant/message') {
      const content = event.data.message.content.filter(block => block.type === 'text' || block.type === 'tool-call' &&
        !excludedTools.has(block.name) && !/\.nanoassistant\/(?:memory|maintenance)/.test(block.arguments));
      return content.length ? [{...event,data:{...event.data,message:{...event.data.message,content}}}] : [];
    }
    if (event.type === 'tool/call') {
      const permitted = !excludedTools.has(event.data.name) && !/\.nanoassistant\/(?:memory|maintenance)/.test(event.data.arguments);
      calls.set(event.data.callId, permitted);
      return permitted ? [event] : [];
    }
    if (event.type === 'tool/result') {
      if (!calls.get(event.data.message.toolCallId)) return [];
      const call = events.find(item => item.type === 'tool/call' && item.data.callId === event.data.message.toolCallId);
      if (call?.type === 'tool/call' && ['inbox','conversations'].includes(call.data.name)) {
        try {
          const body = JSON.parse(event.data.message.content.filter(block => block.type === 'text').map(block => block.text).join('\n'));
          if (Array.isArray(body.messages)) body.messages = body.messages.filter((message: Record<string, unknown>) => {
            const conversation=String(message.conversation_id ?? message.target ?? body.conversation_id ?? body.target ?? body.source ?? '');
            if(!allowed(conversation))return false;
            const sender=message.sender as {id?:string;type?:string}|undefined;
            const identity=JSON.stringify([conversation,message.id??message.message_id,message.revision??createHash('sha256').update(JSON.stringify({content:message.content,sender:{id:sender?.id,type:sender?.type}})).digest('hex')]);
            if(messages.has(identity))return false;messages.add(identity);return true;
          });
          return [{...event,data:{...event.data,message:{...event.data.message,content:[{type:'text' as const,text:JSON.stringify(body)}]}}}];
        } catch { return []; }
      }
      return [event];
    }
    // Window markers preserve native history locators; they carry no business claims.
    if (event.type === 'compaction/start' || event.type === 'compaction/end') return [event];
    if (event.type === 'compaction/summary') return [{...event,data:{...event.data,summary:[]}}];
    return [];
  });
}

/** Last complete paired step at the time boundary, never a later result for an earlier call. */
export function safeBoundary(events: readonly SessionEvent[], cutoff = Infinity): {through:number;time:number} {
  let through = -1; let time = 0;
  const pending = new Set<string>();
  for (const event of events) {
    if (!Number.isFinite(event.time) || event.time > cutoff) break;
    if (event.type === 'tool/call') pending.add(event.data.callId);
    if (event.type === 'tool/result') {
      if (!pending.delete(event.data.message.toolCallId)) break;
    }
    if (event.type === 'step/end' && !pending.size) { through = event.seq; time = event.time; }
  }
  return {through,time};
}

/** Original conversation IDs from already-qualified material, never model-supplied scope. */
export function sourceConversations(events:readonly SessionEvent[]):string[]{
  return [...new Set(events.flatMap(event=>{
    if(event.type==='user/message' && 'conversationId' in event.data.source)return [String(event.data.source.conversationId)];
    if(event.type!=='tool/result')return [];
    try{
      const body=JSON.parse(event.data.message.content.filter(block=>block.type==='text').map(block=>block.text).join('\n'));
      return Array.isArray(body.messages)?body.messages.map((message:Record<string,unknown>)=>String(message.conversation_id??message.target??body.conversation_id??body.target??body.source??'')).filter(Boolean):[];
    }catch{return [];}
  }))];
}
