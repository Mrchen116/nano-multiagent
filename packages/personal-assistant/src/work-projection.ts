import type { RuntimeEvent } from '@nano/product-contracts';
import { tokenUsage, toolPresentation } from './presentation.js';

/** The same native facts render main and child execution without treating drafts as public replies. */
export function projectWorkEvent(sessionId: string, event: RuntimeEvent, events: RuntimeEvent[], child = false): { type: string; payload: Record<string, unknown>; turn?: number } | undefined {
  const turn = typeof event.data.turn === 'number' ? event.data.turn : undefined;
  if (event.type === 'turn/start') {
    const nextEnd = events.find(candidate => candidate.seq > event.seq && candidate.type === 'turn/end')?.seq ?? Infinity;
    const source = events.find(candidate => candidate.seq > event.seq && candidate.seq < nextEnd && candidate.type === 'user/message')?.data.source as { kind: string; channel?: string } | undefined;
    if (!source) return;
    return { type: 'turn_started', turn, payload: { run_id: `${sessionId}:${turn}`, origin: child ? 'background_task' : 'system', trigger: { kind: child ? 'agent' : source.kind === 'schedule' ? 'cron' : source.channel ?? 'inbox' } } };
  }
  const model = event.type === 'request/header'
    ? (event.data.header as { config?: { model?: unknown } } | undefined)?.config?.model
    : event.type === 'request/context' ? event.data.model : undefined;
  if (typeof model === 'string') {
    const start = events.findLast(candidate => candidate.seq < event.seq && candidate.type === 'turn/start');
    if (start) return { type: 'model_selected', turn: start.data.turn as number, payload: { model } };
  }
  const tool = toolPresentation(event, events);
  if (tool) return { type: event.type === 'tool/call' ? 'tool_start' : 'tool_end', turn, payload: { call_id: tool.id, tool_name: tool.name, arguments: tool.input, is_error: tool.status === 'failed', duration_ms: "duration_ms" in tool ? tool.duration_ms : undefined, presentation: { summary: tool.output ?? '', detail:tool.detail } } };
  if (event.type === 'assistant/message') {
    const message = event.data.message as { id: string; content: { type: string; text?: string }[] };
    return { type: 'message', turn, payload: { message_id: message.id, role: 'assistant', text: message.content.filter(part => part.type === 'text').map(part => part.text ?? '').join('') } };
  }
  if (event.type === 'turn/end') {
    const reason = event.data.reason as { kind: string }; const usage = tokenUsage(events, turn!);
    return { type: 'turn_end', turn, payload: { status: reason.kind === 'completed' ? 'completed' : ['cancelled', 'aborted'].includes(reason.kind) ? 'interrupted' : 'failed', stop_reason: reason.kind,
      usage: usage ? { prompt_tokens: usage.context_used, completion_tokens: usage.output, total_tokens: usage.total, context_used: usage.context_used, output: usage.output, context_window: usage.context_window, cache_read_input_tokens: usage.cache_read_tokens } : undefined,
    } };
  }
}
