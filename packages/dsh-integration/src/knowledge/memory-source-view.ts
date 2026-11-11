import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { isHumanSource } from '../input-source.js';

/** Keep original event identity while selecting model-visible messages and paired tool records. */
export function qualifiedEvents(events: readonly SessionEvent[]): SessionEvent[] {
  const calls = new Set<string>();
  return events.flatMap<SessionEvent>(original => {
    if (typeof original.surfaceOp === 'object' && original.surfaceOp.op === 'replace') return [];
    const event = structuredClone(original);
    if (event.type === 'user/message') {
      const source = event.data.source;
      if (!isHumanSource(source) && source.kind !== 'user' && source.kind !== 'agent-message' && source.kind !== 'subagent-settled') return [];
      return [{...event,data:{...event.data,content:event.data.content.filter(block => block.type !== 'reasoning')}}];
    }
    if (event.type === 'assistant/message') {
      const content = event.data.message.content.filter(block => block.type === 'text' || block.type === 'tool-call');
      return content.length ? [{...event,data:{...event.data,message:{...event.data.message,content}}}] : [];
    }
    if (event.type === 'tool/call') {
      calls.add(event.data.callId);
      return [event];
    }
    if (event.type === 'tool/result') {
      if (!calls.has(event.data.message.toolCallId)) return [];
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
    // Native replacements revise an already completed result; they do not settle another call.
    if (event.type === 'tool/result' && typeof event.surfaceOp === 'object' && event.surfaceOp.op === 'replace') continue;
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
