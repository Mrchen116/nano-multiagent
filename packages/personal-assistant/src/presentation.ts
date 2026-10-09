import type { RuntimeEvent } from '@nano/product-contracts';

/** Preserve the runtime's disjoint input/cache accounting at the IM boundary. */
export function tokenUsage(events: RuntimeEvent[], turn: number): Record<string, number> | undefined {
  const answers = events.filter(event => event.type === 'assistant/message' && event.data.turn === turn);
  const usage = answers.map(event => event.data.usage as Record<string, number> | undefined).filter((item): item is Record<string, number> => !!item);
  const last = usage.at(-1);
  if (!last) return undefined;
  const prompt = last.inputTokens! + (last.cacheReadTokens ?? 0) + (last.cacheWriteTokens ?? 0);
  const result: Record<string, number> = { prompt, completion: usage.reduce((sum, item) => sum + item.outputTokens!, 0) };
  if (usage.every(item => item.totalTokens !== undefined)) result.total = usage.reduce((sum, item) => sum + item.totalTokens!, 0);
  if (last.cacheReadTokens !== undefined) { result.cache_read = last.cacheReadTokens; result.cache_total_input = prompt; }
  const context = events.filter(event => event.type === 'request/context' && event.seq <= answers.at(-1)!.seq).at(-1);
  if (typeof context?.data.contextWindow === 'number') result.context_window = context.data.contextWindow;
  return result;
}

/** Project durable tool events using their original names and stable call identity. */
export function toolPresentation(event: RuntimeEvent, events: RuntimeEvent[]) {
  const data = event.data;
  if (event.type === 'tool/call') return {
    id: data.callId, name: data.name, input: argumentsObject(data.arguments), status: 'running',
  };
  if (event.type === 'tool/result') {
    const message = data.message as { toolCallId: string; isError?: boolean; content: { type: string; text?: string }[] };
    const call = events.find(item => item.type === 'tool/call' && item.data.callId === message.toolCallId);
    if (!call) return undefined;
    return { id: message.toolCallId, name: call.data.name, input: argumentsObject(call.data.arguments),
      status: message.isError ? 'failed' : 'completed', duration_ms: event.time - call.time,
      output: message.content.filter(block => block.type === 'text').map(block => block.text ?? '').join(''),
    };
  }
  return undefined;
}
export function argumentsObject(raw: unknown): Record<string, unknown> {
  try { return JSON.parse(String(raw)) as Record<string, unknown>; }
  catch { return { raw }; }
}
