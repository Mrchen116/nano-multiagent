import type { RuntimeEvent, ModelRunProjection } from '@nano/product-contracts';

/** Preserve the runtime's disjoint input/cache accounting at the IM boundary. */
export function tokenUsage(events: RuntimeEvent[], turn: number): Record<string, number> | undefined {
  const answers = events.filter(event => event.type === 'assistant/message' && event.data.turn === turn);
  const usage = answers.map(event => event.data.usage as Record<string, number> | undefined).filter((item): item is Record<string, number> => !!item);
  const last = usage.at(-1);
  if (!last) return undefined;
  const prompt = last.inputTokens! + (last.cacheReadTokens ?? 0) + (last.cacheWriteTokens ?? 0);
  const result: Record<string, number> = { context_used: prompt, output: usage.reduce((sum, item) => sum + item.outputTokens!, 0) };
  if (usage.every(item => item.totalTokens !== undefined)) result.total = usage.reduce((sum, item) => sum + item.totalTokens!, 0);
  if (usage.every(item => item.cacheReadTokens !== undefined)) {
    result.cache_read_tokens = usage.reduce((sum, item) => sum + item.cacheReadTokens!, 0);
    result.cache_total_input_tokens = usage.reduce((sum, item) => sum + item.inputTokens! + item.cacheReadTokens! + (item.cacheWriteTokens ?? 0), 0);
  }
  const context = events.filter(event => event.type === 'request/context' && event.seq <= answers.at(-1)!.seq).at(-1);
  if (typeof context?.data.contextWindow === 'number') result.context_window = context.data.contextWindow;
  return result;
}

/** Project durable tool events using their original names and stable call identity. */
export function toolPresentation(event: RuntimeEvent, events: RuntimeEvent[]) {
  const data = event.data;
  if (event.type === 'tool/call') return {
    id: data.callId, name: data.name, input: argumentsObject(data.arguments), status: 'running', ...workflowDetail(data.name,argumentsObject(data.arguments)),
  };
  if (event.type === 'tool/result') {
    const message = data.message as { toolCallId: string; isError?: boolean; content: { type: string; text?: string }[] };
    const call = events.find(item => item.type === 'tool/call' && item.data.callId === message.toolCallId);
    if (!call) return undefined;
    const output = message.content.filter(block => block.type === 'text').map(block => block.text ?? '').join('');
    const view = data.nanoToolView as {call?: unknown; result?: unknown; childSessionId?: string} | undefined;
    let detail: Record<string, unknown> | undefined;
    try { const parsed = JSON.parse(output); if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) detail = parsed; } catch { /* Plain native output remains displayable as text. */ }
    if (view) detail = {content: output, ...detail, native_view: view.result ?? view.call, native_call: view.call, child_session_id: view.childSessionId};
    return { id: message.toolCallId, name: call.data.name, input: argumentsObject(call.data.arguments),
      status: message.isError ? 'failed' : 'completed', duration_ms: event.time - call.time,
      output, ...(detail ? {detail} : {}),
      ...workflowDetail(call.data.name,argumentsObject(call.data.arguments),message.content.filter(block=>block.type==='text').map(block=>block.text??'').join(''),message.isError),
    };
  }
  return undefined;
}
function workflowDetail(name:unknown,input:Record<string,unknown>,output?:string,error?:boolean) {
  if(name!=='workflow')return {};
  const description=String((input.meta as {description?:string}|undefined)?.description??input.name??input.action??'Workflow');
  let result:Record<string,unknown>={};if(output)try{result=JSON.parse(output);}catch{result={error:output};}
  return {output:description,detail:{...result,description,script_preview:input.script??'',source:input.scriptPath??input.name??'inline',...(error?{error:output}:{} )}};
}
export function argumentsObject(raw: unknown): Record<string, unknown> {
  try { return JSON.parse(String(raw)) as Record<string, unknown>; }
  catch { return { raw }; }
}

/** Intermediate failed native turns remain facts but cannot close the product reply. */
export function logicalEvents(events: RuntimeEvent[], runs: ModelRunProjection[]): RuntimeEvent[] {
  return events.flatMap(event => {
    const run = runs.find(run => run.attempts.some(attempt => attempt.turn === event.data.turn));
    if (!run) return [event];
    if (event.type === 'turn/start' && event.data.turn !== run.turn) return [];
    if (event.type === 'turn/end' && (run.state !== 'completed' || event.data.turn !== run.attempts.at(-1)?.turn)) return [];
    return [{ ...event, data: { ...event.data, turn: run.turn, ...(event.type === 'turn/end' ? { reason: run.terminal } : {}) } }];
  });
}
