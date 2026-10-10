import type { RuntimeEvent, ModelRunProjection } from '@nano/product-contracts';

/** Preserve the runtime's disjoint input/cache accounting at the IM boundary. */
export function tokenUsage(events: RuntimeEvent[], turn: number): Record<string, number> | undefined {
  const answers = events.filter(event => event.type === 'assistant/message' && event.data.turn === turn);
  const usage = answers.map(event => {
    const usage = event.data.usage as Record<string, number> | undefined;
    const stream = event.data.stream as {chunk?: {type?: string; replayState?: {response?: {kind?: string}}}}[] | undefined;
    // The public pi-ai adapter omits zero cache counters; other providers may not report them.
    const pi = stream?.some(item => item.chunk?.type === 'finish' && item.chunk.replayState?.response?.kind === 'pi-ai');
    return usage && pi ? {cacheReadTokens: 0, cacheWriteTokens: 0, ...usage} : usage;
  }).filter((item): item is Record<string, number> => !!item);
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

type NativeToolView = {call?: Record<string, unknown>; result?: Record<string, unknown>; childSessionId?: string; delegationKind?: string};

/** Project durable tool events using their original names and stable call identity. */
export function toolPresentation(event: RuntimeEvent, events: RuntimeEvent[]) {
  const data = event.data;
  if (event.type === 'tool/call') return {
    id: data.callId, name: data.name, input: argumentsObject(data.arguments), status: 'running', output: toolSummary(data.name, argumentsObject(data.arguments), data.nanoToolView as NativeToolView | undefined), detail: {native_view: (data.nanoToolView as NativeToolView | undefined)?.call ?? {card: 'generic'}, native_call: (data.nanoToolView as NativeToolView | undefined)?.call}, ...workflowDetail(data.name,argumentsObject(data.arguments)),
  };
  if (event.type === 'tool/result') {
    const message = data.message as { toolCallId: string; isError?: boolean; content: { type: string; text?: string }[] };
    const call = events.find(item => item.type === 'tool/call' && item.data.callId === message.toolCallId);
    if (!call) return undefined;
    const output = message.content.filter(block => block.type === 'text').map(block => block.text ?? '').join('');
    const view = data.nanoToolView as NativeToolView | undefined;
    let detail: Record<string, unknown> | undefined;
    try { const parsed = JSON.parse(output); if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) detail = parsed; } catch { /* Plain native output remains displayable as text. */ }
    const error = data.error as {name?: string; code?: string} | undefined;
    const reason = error?.name === 'NanoApprovalDenied' ? 'denied' : ['ABORTED', 'ABORTED_BEFORE_DISPATCH'].includes(error?.code ?? '') ? 'interrupted' : undefined;
    if (view) detail = {content: output, ...detail, native_view: view.result ?? view.call, native_call: view.call, child_session_id: view.childSessionId, delegation_kind: view.delegationKind};
    else if (!detail) detail = {content: output, native_view: {card: 'generic', content: message.content}};
    return { id: message.toolCallId, name: call.data.name, input: argumentsObject(call.data.arguments),
      reason, status: message.isError ? 'failed' : 'completed', duration_ms: event.time - call.time,
      output: toolSummary(call.data.name, argumentsObject(call.data.arguments), view, output, message.isError), detail: {...detail, ...(error ? {error} : {})},
      ...workflowDetail(call.data.name,argumentsObject(call.data.arguments),message.content.filter(block=>block.type==='text').map(block=>block.text??'').join(''),message.isError),
    };
  }
  return undefined;
}
/** Preserve the original Bash card summary; command output belongs to its native detail. */
function bashSummary(name: unknown, input: Record<string, unknown>): string | undefined {
  if (name !== 'bash') return undefined;
  const summary = String(input.description ?? '').trim() || String(input.command ?? '').split('\n')[0]!;
  return summary.length > 80 ? summary.slice(0, 77) + '...' : summary;
}
/** Card headers describe the operation; complete results remain in native detail. */
function toolSummary(name: unknown, input: Record<string, unknown>, view?: NativeToolView, output?: string, failed = false): string {
  const bash = bashSummary(name, input); if (bash !== undefined) return bash;
  const result = view?.result, call = view?.call;
  const short = (value: unknown) => typeof value === 'string' ? value.trim() : '';
  let summary = short(result?.title) || short(call?.description) || short(input.description) || short(call?.title);
  if (!summary) summary = failed ? 'failed' : output ?? JSON.stringify(input);
  return summary.length > 80 ? summary.slice(0, 77) + '...' : summary;
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

/** Request headers are deltas, so an unchanged model carries across native turns. */
export function modelAt(events: RuntimeEvent[], seq: number): string | undefined {
  for (const event of events.filter(event => event.seq <= seq).reverse()) {
    const model = event.type === 'request/header' ? (event.data.header as {config?: {model?: unknown}} | undefined)?.config?.model : event.type === 'request/context' ? event.data.model : undefined;
    if (typeof model === 'string') return model;
  }
  return undefined;
}
