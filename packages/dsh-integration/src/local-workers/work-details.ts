import type { RuntimeWorkerDetail, WorkUsage } from '@nano/product-contracts';

type Fact = RuntimeWorkerDetail['fact'];
type Emit = (id: string, detail: RuntimeWorkerDetail) => void;

function extractToolSummary(args: unknown): string | undefined {
  const fields = args as {
    description?: string;
    toolSummary?: string;
    command?: string;
    CommandLine?: string;
    file_path?: string;
    Path?: string;
    path?: string;
    questions?: { question?: string }[];
  } | null;
  const raw =
    fields?.description ??
    fields?.toolSummary ??
    fields?.command ??
    fields?.CommandLine ??
    fields?.file_path ??
    fields?.Path ??
    fields?.path ??
    fields?.questions?.[0]?.question;
  return typeof raw === 'string' && raw ? raw.split('\n', 1)[0]!.slice(0, 80) : undefined;
}

/** Collect only the current native turn's product facts and match tool results by call id. */
export class WorkerTurnDetails {
  private turnId?: string;
  model?: string;
  private readonly sent = new Set<string>();
  private readonly openTools = new Map<string, string>();
  private lastAssistant?: string;

  constructor(private readonly emit: Emit) {}

  begin(id: string, model?: string) {
    if (this.turnId === id) return;
    this.turnId = id;
    this.model = model;
    this.sent.clear();
    this.openTools.clear();
    this.lastAssistant = undefined;
    this.fact('', {
      type: 'turn_started',
      payload: { origin: 'background_task', trigger: { kind: 'background_task' }, model },
    });
  }

  private fact(item: string, fact: Fact) {
    if (!this.turnId) return;
    const id = JSON.stringify([fact.type, item]);
    if (this.sent.has(id)) return;
    this.sent.add(id);
    this.emit(item, { turnId: this.turnId, fact });
  }

  message(id: string, role: 'user' | 'assistant' | 'system', text: string) {
    if (!text) return;
    this.fact(id, { type: 'message', payload: { message_id: id, role, text } });
    if (role === 'assistant') this.lastAssistant = text;
  }

  finalMessage(id: string, text: string) {
    if (text !== this.lastAssistant) this.message(id, 'assistant', text);
  }

  toolStart(id: string, name: string, args: unknown) {
    this.openTools.set(id, name);
    const summary = extractToolSummary(args);
    this.fact(id, {
      type: 'tool_start',
      payload: {
        call_id: id,
        tool_name: name,
        arguments: args,
        presentation: summary ? { summary } : undefined,
      },
    });
  }

  toolEnd(
    id: string,
    name: string | undefined,
    output: unknown,
    failed: boolean,
    options: { duration?: number; reason?: string; args?: unknown } = {},
  ) {
    name = this.openTools.get(id) ?? name;
    if (!name) return;
    this.openTools.delete(id);
    const summary = extractToolSummary(options.args);
    this.fact(id, {
      type: 'tool_end',
      payload: {
        call_id: id,
        tool_name: name,
        is_error: failed,
        reason_code: options.reason,
        duration_ms: options.duration,
        arguments: options.args,
        presentation: { ...(summary && { summary }), detail: { content: output } },
      },
    });
  }

  end(state: string, total: number | WorkUsage | null, error?: string) {
    if (state !== 'completed') {
      for (const [id, name] of this.openTools) this.toolEnd(id, name, error, true, { reason: state });
    }
    let usage: WorkUsage | undefined;
    if (typeof total === 'number') {
      usage = { total_tokens: total };
    } else if (total && typeof total === 'object') {
      const entries = Object.entries(total).filter(
        ([, value]) => typeof value === 'number' && Number.isFinite(value) && value >= 0,
      );
      if (entries.length > 0) usage = Object.fromEntries(entries);
    }
    this.fact('', {
      type: 'turn_end',
      payload: {
        status: state,
        stop_reason: state,
        model: this.model,
        error: state === 'failed' && error ? {message:error} : undefined,
        usage,
      },
    });
    this.turnId = undefined;
  }
}

export interface CodexItem {
  id: string;
  type: string;
  text?: string;
  phase?: string;
  command?: string;
  cwd?: string;
  changes?: { path: string }[];
  tool?: string;
  arguments?: unknown;
  status?: string;
  server?: string;
  namespace?: string;
  result?: { content?: unknown; structuredContent?: unknown };
  error?: unknown;
  success?: boolean;
  durationMs?: number;
  aggregatedOutput?: string;
  exitCode?: number;
  contentItems?: unknown[];
  query?: string;
  action?: unknown;
  results?: unknown[];
  path?: string;
  name?: string;
  output?: unknown;
}

/** Read v2 item variants. A terminal snapshot may contain items already delivered live. */
export function codexItem(details: WorkerTurnDetails, item: CodexItem, completed: boolean) {
  const { id, type } = item;
  if (type === 'agentMessage' || type === 'plan') {
    if (completed && item.text) details.message(id, 'assistant', item.text);
    return;
  }
  let name: string, input: unknown, output: unknown;
  switch (type) {
    case 'commandExecution':
      name = type;
      input = { command: item.command, cwd: item.cwd };
      output = { output: item.aggregatedOutput, exitCode: item.exitCode };
      break;
    case 'fileChange':
      name = type;
      input = { changes: item.changes };
      output = { status: item.status };
      break;
    case 'mcpToolCall':
      name = `${item.server}.${item.tool}`;
      input = item.arguments;
      output =
        item.error ??
        (item.result && { content: item.result.content, structuredContent: item.result.structuredContent });
      break;
    case 'dynamicToolCall':
      name = [item.namespace, item.tool].filter(Boolean).join('.');
      input = item.arguments;
      output = item.contentItems;
      break;
    case 'webSearch':
      name = type;
      input = { query: item.query, action: item.action };
      output = item.results;
      break;
    case 'imageView':
      name = type;
      input = { path: item.path };
      output = { path: item.path };
      break;
    case 'functionCallOutput':
      if (completed) details.toolEnd(id, item.name, item.output, false);
      return;
    default:
      return;
  }
  details.toolStart(id, name, input);
  if (!completed || item.status === 'inProgress') return;
  const failed =
    item.status === 'failed' ||
    item.status === 'declined' ||
    item.success === false ||
    !!item.error ||
    (typeof item.exitCode === 'number' && item.exitCode !== 0);
  details.toolEnd(id, name, output, failed, {
    duration: item.durationMs ?? undefined,
    reason: item.status === 'declined' ? 'denied' : undefined,
    // File changes and the selected search action can be filled in during execution.
    args: type === 'fileChange' || type === 'webSearch' ? input : undefined,
  });
}
