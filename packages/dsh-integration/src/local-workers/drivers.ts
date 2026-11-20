import { randomUUID } from 'node:crypto';
import { CliProcess, acknowledged } from './cli-process.js';

export type CliEndState = 'completed' | 'failed' | 'interrupted';
export interface CliWorkerOptions {
  runtime: 'codex' | 'claude';
  cwd: string;
  sessionId?: string;
  instructions: string;
  mcp: { command: string; args: string[]; env: Record<string, string> };
  onReport(id: string, message: string): Promise<void>;
  onTurnEnd(id: string, totalTokens: number | null): Promise<void>;
  onEnd(id: string, state: CliEndState, text: string): Promise<void>;
}

// Keep report order, including the terminal report after a refusal on the same stdout stream.
class TurnEvents {
  active?: string;
  private delivery = Promise.resolve();
  private terminal = Promise.withResolvers<void>();
  private lastTurn?: string;
  constructor(private readonly options: CliWorkerOptions) {}

  begin(id: string) {
    if (!this.active) this.terminal = Promise.withResolvers<void>();
    this.active = id;
  }

  report(id: string, text: string) {
    this.deliver(() => this.options.onReport(id, text));
  }

  recordTurn(id: string, totalTokens: number | null) {
    if (!this.active || id === this.lastTurn) return false;
    this.lastTurn = id;
    this.deliver(() => this.options.onTurnEnd(id, totalTokens));
    return true;
  }

  end(id: string, state: CliEndState, text: string) {
    if (!this.active) return;
    this.active = undefined;
    const terminal = this.terminal;
    this.deliver(() => this.options.onEnd(id, state, text));
    void this.delivery.then(terminal.resolve, terminal.resolve);
  }

  private deliver(action: () => Promise<void>) {
    this.delivery = this.delivery
      .then(action)
      .catch((error) => console.error('Local worker report delivery failed', error));
  }

  get finished() {
    return this.active ? this.terminal.promise : this.delivery;
  }
}

interface CodexItem {
  id: string;
  type: string;
  text?: string;
  phase?: string;
  changes?: { path: string }[];
}
interface CodexTurn {
  id: string;
  status: string;
  items?: CodexItem[];
  error?: { message: string };
}
const finalMessage = (item: CodexItem) =>
  item.type === 'agentMessage' && (!item.phase || item.phase === 'final_answer');

const tokenCount = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;

function claudeResultTokens(usage?: Record<string, unknown>): number | null {
  if (!usage) return null;
  // result.usage aggregates the requests for this prompt. Cache detail fields subdivide these counts.
  const counts = [
    usage.input_tokens,
    usage.output_tokens,
    usage.cache_read_input_tokens ?? 0,
    usage.cache_creation_input_tokens ?? 0,
  ];
  return counts.every(tokenCount) ? counts.reduce((total, count) => total + count, 0) : null;
}

function details(subject: string, fields: Record<string, unknown>) {
  return `${subject} ${JSON.stringify(Object.fromEntries(Object.entries(fields).filter(([, value]) => value != null)))}`;
}

// A denied edit or tool call may contain file contents or other payloads. Report its target only.
function actionTarget(input: Record<string, unknown> = {}) {
  const keys = [
    'type',
    'command',
    'program',
    'argv',
    'processId',
    'cwd',
    'files',
    'file_path',
    'path',
    'paths',
    'directory',
    'pattern',
    'url',
    'host',
    'protocol',
    'port',
    'permissions',
    'reason',
    'server',
    'toolName',
    'resource',
    'target',
  ];
  return Object.fromEntries(keys.filter((key) => input[key] !== undefined).map((key) => [key, input[key]]));
}

async function codex(options: CliWorkerOptions) {
  const proc = new CliProcess('codex', ['app-server', '--listen', 'stdio://'], options.cwd);
  const events = new TurnEvents(options);
  let threadId = options.sessionId;
  let nextId = 0;
  let finalText = '';
  let stopping = false;
  let previousTotal = options.sessionId ? undefined : 0;
  let usage: { turnId: string; baseline?: number } | undefined;
  const fileTargets = new Map<string, string[]>();
  const commands = new Map<string, string>();
  const request = <T>(method: string, params: unknown) => {
    const id = ++nextId;
    return proc.request<T>(id, { id, method, params }, method);
  };
  proc.onExit = (error) => {
    if (events.active) events.end(events.active, stopping ? 'interrupted' : 'failed', error.message);
  };
  proc.onMessage = ({ id, method, params, result, error }) => {
    if (!method) {
      proc.resolve(id, result, error?.message);
      return;
    }
    if (id !== undefined) {
      let reply: unknown;
      const p = params ?? {};
      if (method === 'item/commandExecution/requestApproval' || method === 'item/fileChange/requestApproval')
        reply = { decision: 'decline' };
      if (method === 'item/permissions/requestApproval') reply = { permissions: {}, scope: 'turn' };
      if (method === 'item/tool/requestUserInput') reply = { answers: {} };
      if (method === 'mcpServer/elicitation/request')
        reply = { action: 'decline', content: null, _meta: null };
      if (method === 'execCommandApproval' || method === 'applyPatchApproval') reply = { decision: 'abort' };
      const response = reply
        ? { id, result: reply }
        : { id, error: { code: -32601, message: 'Unsupported worker host request' } };
      void proc.write(response).catch(console.error);
      if (reply && threadId && (!p.threadId || p.threadId === threadId)) {
        events.report(
          `request:${p.turnId ?? ''}:${p.itemId ?? id}:${id}`,
          details(`Codex declined ${method}.`, {
            command: p.command ?? commands.get(p.itemId),
            cwd: p.cwd,
            reason: p.reason,
            target: p.grantRoot ?? p.networkApprovalContext,
            files: fileTargets.get(p.itemId) ?? (p.fileChanges && Object.keys(p.fileChanges)),
            permissions: p.permissions ?? p.additionalPermissions,
            questions: p.questions?.map((q: { question: string }) => q.question),
            server: p.serverName,
            message: p.message,
            url: p.url,
          }),
        );
      }
      return;
    }
    if (!threadId || params?.threadId !== threadId) return;
    if (method === 'thread/tokenUsage/updated') {
      const total = params.tokenUsage.total.totalTokens;
      if (!tokenCount(total)) return;
      if (usage?.turnId !== params.turnId) {
        // Resume replays the previous turn's thread total. Without a replay, last is one model request.
        const last = params.tokenUsage.last?.totalTokens;
        const baseline = previousTotal ?? (tokenCount(last) ? total - last : undefined);
        usage = { turnId: params.turnId, baseline };
      }
      previousTotal = total;
    }
    if (method === 'turn/started') events.begin(params.turn.id);
    if (method === 'item/started' && params.item.type === 'commandExecution')
      commands.set(params.item.id, params.item.command);
    if (method === 'item/started' && params.item.type === 'fileChange')
      fileTargets.set(params.item.id, (params.item as CodexItem).changes?.map((change) => change.path) ?? []);
    if (method === 'item/completed') {
      if (finalMessage(params.item)) finalText = params.item.text;
      fileTargets.delete(params.item.id);
      commands.delete(params.item.id);
    }
    if (
      method === 'item/autoApprovalReview/completed' &&
      ['denied', 'timedOut', 'aborted'].includes(params.review.status)
    ) {
      events.report(
        `review:${params.reviewId}`,
        details(`Codex Auto review ${params.review.status}.`, {
          action: actionTarget(params.action),
          reason: params.review.rationale,
        }),
      );
    }
    if (method === 'turn/completed') {
      const turn = params.turn as CodexTurn;
      const tokens =
        usage?.turnId === turn.id && usage.baseline !== undefined && previousTotal !== undefined
          ? previousTotal - usage.baseline
          : null;
      if (!events.recordTurn(turn.id, tokenCount(tokens) ? tokens : null)) return;
      const state = turn.status === 'completed' || turn.status === 'interrupted' ? turn.status : 'failed';
      events.end(
        turn.id,
        state,
        turn.error?.message ??
          (turn.items?.findLast(finalMessage)?.text || finalText || `Codex turn ${state}`),
      );
      finalText = '';
      fileTargets.clear();
      commands.clear();
    }
  };
  try {
    await request('initialize', {
      clientInfo: { name: 'nano_worker', title: 'Nano worker', version: '1' },
      capabilities: { experimentalApi: true },
    });
    await proc.write({ method: 'initialized' });
    const common = {
      cwd: options.cwd,
      developerInstructions: options.instructions,
      sandbox: 'workspace-write',
      approvalPolicy: 'on-request',
      approvalsReviewer: 'auto_review',
      config: { 'mcp_servers.nano-parent': { ...options.mcp, required: true } },
    };
    const response = await request<{ thread: { id: string } }>(
      threadId ? 'thread/resume' : 'thread/start',
      threadId ? { ...common, threadId } : common,
    );
    if (!response.thread.id || (threadId && threadId !== response.thread.id))
      throw new Error('Codex returned a different or empty thread id');
    threadId = response.thread.id;
  } catch (error) {
    await proc.close();
    throw error;
  }
  return {
    sessionId: threadId,
    async send(text: string) {
      const input = [{ type: 'text', text, text_elements: [] }];
      if (events.active) {
        await request('turn/steer', { threadId, expectedTurnId: events.active, input });
        return;
      }
      // The response and started/completed notifications can share a single stdout chunk.
      const provisional = randomUUID();
      events.begin(provisional);
      try {
        const { turn } = await request<{ turn: CodexTurn }>('turn/start', { threadId, input });
        if (events.active === provisional) events.begin(turn.id);
      } catch (error) {
        if (events.active) events.end(events.active, 'failed', String(error));
        throw error;
      }
    },
    async stop() {
      const turnId = events.active;
      const finished = events.finished;
      if (turnId) {
        stopping = true;
        try {
          await request('turn/interrupt', { threadId, turnId });
          await acknowledged(finished, 'Codex turn to stop');
        } finally {
          stopping = false;
        }
      } else await finished;
    },
    close: () => proc.close(),
  };
}

async function claude(options: CliWorkerOptions) {
  const sessionId = options.sessionId ?? randomUUID();
  const args = [
    '--print',
    '--verbose',
    '--input-format',
    'stream-json',
    '--output-format',
    'stream-json',
    '--replay-user-messages',
    '--permission-mode',
    'auto',
    '--permission-prompt-tool',
    'stdio',
    '--append-system-prompt',
    options.instructions,
    '--allowedTools',
    'mcp__nano-parent__send_message',
    '--mcp-config',
    JSON.stringify({ mcpServers: { 'nano-parent': options.mcp } }),
    options.sessionId ? '--resume' : '--session-id',
    sessionId,
  ];
  const proc = new CliProcess('claude', args, options.cwd);
  const events = new TurnEvents(options);
  const unconsumed = new Set<string>();
  const reportedDenials = new Set<string>();
  let stopping = false;
  const control = (subtype: string, params: Record<string, unknown> = {}) => {
    const id = randomUUID();
    return proc.request(
      id,
      { type: 'control_request', request_id: id, request: { subtype, ...params } },
      `Claude ${subtype}`,
    );
  };
  proc.onExit = (error) => {
    if (events.active) events.end(events.active, stopping ? 'interrupted' : 'failed', error.message);
  };
  proc.onMessage = (message) => {
    if (message.type === 'control_response') {
      const response = message.response;
      proc.resolve(
        response.request_id,
        response.response,
        response.subtype === 'error' ? String(response.error) : undefined,
      );
      return;
    }
    if (message.type === 'control_request') {
      const request = message.request;
      const id = message.request_id;
      let response: unknown;
      let report: string | undefined;
      if (request.subtype === 'can_use_tool') {
        response = {
          behavior: 'deny',
          message: 'This action has no approval. Contact the parent for clarification.',
        };
        reportedDenials.add(request.tool_use_id);
        report = details(`Claude declined ${request.tool_name}.`, {
          input: actionTarget(request.input),
          target: request.blocked_path,
          reason: request.decision_reason ?? request.description,
        });
      } else if (request.subtype === 'elicitation') {
        response = { action: 'decline' };
        report = details('Claude declined a request for input.', {
          server: request.mcp_server_name,
          message: request.message,
          url: request.url,
        });
      }
      const reply = response
        ? { subtype: 'success', response }
        : { subtype: 'error', error: 'Unsupported worker host request' };
      void proc
        .write({ type: 'control_response', response: { request_id: id, ...reply } })
        .catch(console.error);
      if (report) events.report(`request:${request.tool_use_id ?? id}`, report);
      return;
    }
    if (message.session_id && message.session_id !== sessionId)
      throw new Error('Claude returned a different session id');
    if (message.type === 'user' && message.isReplay) unconsumed.delete(message.uuid);
    if (message.type !== 'result' || !events.active) return;
    if (!events.recordTurn(message.uuid ?? events.active, claudeResultTokens(message.usage))) return;
    const state = message.subtype === 'success' && !message.is_error ? 'completed' : 'failed';
    const text = (message.errors ?? []).join('\n') || message.result || `Claude turn ${message.subtype}`;
    for (const denial of message.permission_denials ?? []) {
      if (reportedDenials.has(denial.tool_use_id)) continue;
      reportedDenials.add(denial.tool_use_id);
      events.report(
        `request:${denial.tool_use_id}`,
        details(`Claude denied ${denial.tool_name}.`, {
          input: actionTarget(denial.tool_input),
          reason: denial.decision_reason,
        }),
      );
    }
    // The CLI may queue steering behind the active turn. Retain the process until it consumes the correction.
    if (!stopping && state === 'completed' && unconsumed.size && !unconsumed.has(events.active)) {
      events.report(message.uuid, text);
      events.begin([...unconsumed][0]!);
      return;
    }
    events.end(
      message.uuid ?? events.active,
      stopping ? 'interrupted' : state,
      stopping ? 'Claude turn interrupted' : text,
    );
    unconsumed.clear();
  };
  try {
    await control('initialize');
    await control('set_permission_mode', { mode: 'auto' });
  } catch (error) {
    await proc.close();
    throw error;
  }
  return {
    sessionId,
    async send(text: string) {
      const uuid = randomUUID();
      if (!events.active) events.begin(uuid);
      unconsumed.add(uuid);
      await proc.write({
        type: 'user',
        uuid,
        session_id: sessionId,
        parent_tool_use_id: null,
        message: { role: 'user', content: text },
      });
    },
    async stop() {
      if (!events.active) {
        await events.finished;
        return;
      }
      stopping = true;
      try {
        await control('interrupt');
        // interrupt acknowledges the active generation. Exit also fences any queued user messages.
        await proc.close();
        if (events.active) events.end(events.active, 'interrupted', 'Claude session interrupted');
        await events.finished;
      } finally {
        stopping = false;
      }
    },
    close: () => proc.close(),
  };
}

/** Open the native CLI session in the assigned workspace and use its installed model and identity. */
export async function openCliWorker(options: CliWorkerOptions) {
  return options.runtime === 'codex' ? codex(options) : claude(options);
}
