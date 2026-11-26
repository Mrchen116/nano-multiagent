import { randomUUID } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { isDeepStrictEqual } from 'node:util';
import type { WorkerRuntime, RuntimeWorkerDetail, WorkUsage } from '@nano/product-contracts';
import { WorkerTurnDetails, codexItem, type CodexItem } from './work-details.js';
import { CliProcess, acknowledged } from './cli-process.js';
import {
  identifyHostedAcpTool,
  hostedWorkerMcp,
  WorkerPermissions,
  type WorkerMcpLaunch,
  type WorkerPermissionHandler,
} from './worker-permissions.js';

export type CliEndState = 'completed' | 'failed' | 'interrupted';
export interface CliWorkerOptions {
  runtime: Exclude<WorkerRuntime, 'dsh'>;
  cwd: string;
  sessionId?: string;
  instructions: string;
  mcp: WorkerMcpLaunch;
  onPermission?: WorkerPermissionHandler;
  onReport(id: string, message: string): Promise<void>;
  onDetail(id: string, detail: RuntimeWorkerDetail): Promise<void>;
  onEnd(id: string, state: CliEndState, text: string): Promise<void>;
}

// Keep report order, including the terminal report after a refusal on the same stdout stream.
class TurnEvents {
  active?: string;
  private delivery = Promise.resolve();
  private terminal = Promise.withResolvers<void>();
  readonly details: WorkerTurnDetails;
  readonly permissions: WorkerPermissions;
  constructor(private readonly options: CliWorkerOptions) {
    this.permissions = new WorkerPermissions(options.onPermission);
    this.details = new WorkerTurnDetails((id, detail) => this.deliver(() => options.onDetail(id, detail)));
  }

  begin(id: string, model?: string) {
    if (!this.active) this.terminal = Promise.withResolvers<void>();
    if (this.active !== id) this.permissions.begin();
    this.active = id;
    this.details.begin(id, model);
  }

  report(id: string, text: string) {
    this.details.message(id, 'system', text);
    this.deliver(() => this.options.onReport(id, text));
  }

  end(id: string, state: CliEndState, text: string, tokens: number | WorkUsage | null = null) {
    if (!this.active) return;
    this.permissions.stop();
    this.details.end(state, tokens, text);
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
    'CommandLine',
    'command_line',
    'commandLine',
    'program',
    'argv',
    'processId',
    'cwd',
    'Cwd',
    'WorkingDirectory',
    'files',
    'file_path',
    'path',
    'Path',
    'paths',
    'Paths',
    'directory',
    'pattern',
    'url',
    'host',
    'protocol',
    'port',
    'permissions',
    'reason',
    'server',
    'ServerName',
    'toolName',
    'ToolName',
    'toolSummary',
    'resource',
    'target',
  ];
  return Object.fromEntries(
    keys.flatMap((key): [string, unknown][] => {
      const value = input[key];
      if (
        typeof value === 'string' ||
        typeof value === 'number' ||
        (Array.isArray(value) && value.every((item) => typeof item === 'string'))
      )
        return [[key, value]];
      // Structured permissions use native Codex schemas; other nested tool inputs (including file bodies) stay private.
      if (key === 'permissions' && value && typeof value === 'object') {
        const { network, fileSystem } = value as Record<string, unknown>;
        return [[key, { network, fileSystem }]];
      }
      if (key === 'target' && value && typeof value === 'object') {
        const { host, protocol, port } = value as Record<string, unknown>;
        return [[key, { host, protocol, port }]];
      }
      return [];
    }),
  );
}

async function codex(options: CliWorkerOptions) {
  const proc = new CliProcess('codex', ['app-server', '--listen', 'stdio://'], options.cwd);
  const events = new TurnEvents(options);
  let threadId = options.sessionId;
  let nextId = 0;
  let errorCount = 0;
  let model: string | undefined;
  // LocalWorkers serializes sends. A full turn can finish within the stdout chunk containing its RPC reply.
  let inputRequest: { rpcId: number; messageId: string; text: string; turnId?: string } | undefined;
  function acceptInput(turnId: string) {
    if (!inputRequest || (inputRequest.turnId && inputRequest.turnId !== events.active)) return;
    events.begin(turnId, model);
    events.details.message(inputRequest.messageId, 'user', inputRequest.text);
    inputRequest = undefined;
  }
  let finalText = '';
  let stopping = false;
  let previousTotal = options.sessionId ? undefined : 0;
  let usage: { turnId: string; baseline?: number } | undefined;
  const items = new Map<string, CodexItem>();
  const deniedItems = new Set<string>();
  const request = <T>(method: string, params: unknown) => {
    const id = ++nextId;
    return proc.request<T>(id, { id, method, params }, method);
  };
  proc.onExit = (error) => {
    if (events.active) events.end(events.active, stopping ? 'interrupted' : 'failed', error.message);
  };
  proc.onMessage = ({ id, method, params, result, error }) => {
    if (!method) {
      if (inputRequest?.rpcId === id && !error) acceptInput(result.turn?.id ?? result.turnId);
      proc.resolve(id, result, error?.message);
      return;
    }
    if (id !== undefined) {
      const p = params ?? {};
      const legacy = method === 'execCommandApproval' || method === 'applyPatchApproval';
      const call = legacy ? p.callId : p.itemId;
      const bound =
        threadId &&
        (legacy ? p.conversationId : p.threadId) === threadId &&
        events.active &&
        (legacy ? p.turnId === undefined || p.turnId === events.active : p.turnId === events.active);
      const reply = (result: unknown) => {
        if (!proc.ended) void proc.write({ id, result }).catch(console.error);
      };
      const report = (text: string) =>
        events.report(`request:${events.active ?? ''}:${call ?? id}:${id}`, text);
      const commandRequest =
        method === 'item/commandExecution/requestApproval' || method === 'execCommandApproval';
      const fileRequest = method === 'item/fileChange/requestApproval' || method === 'applyPatchApproval';
      if (commandRequest || fileRequest) {
        const item = bound ? items.get(call) : undefined;
        const command =
          p.command ?? (!p.approvalId && item?.type === 'commandExecution' ? item.command : undefined);
        const changes = item?.type === 'fileChange' ? item.changes : undefined;
        const files = legacy
          ? Object.keys(p.fileChanges ?? {}).flatMap((path) =>
              [path, p.fileChanges[path]?.move_path].filter(Boolean),
            )
          : changes?.flatMap((change) =>
              [change.path, (change as { kind?: { move_path?: string } }).kind?.move_path].filter(Boolean),
            );
        const summary = actionTarget({
          command,
          cwd: p.cwd ?? item?.cwd,
          files,
          reason: p.reason,
          target: p.networkApprovalContext ?? p.grantRoot,
          permissions: p.additionalPermissions,
        });
        const eligible =
          bound &&
          typeof call === 'string' &&
          call &&
          !deniedItems.has(call) &&
          !p.grantRoot &&
          (p.availableDecisions == null ||
            (Array.isArray(p.availableDecisions) && p.availableDecisions.includes('accept'))) &&
          (commandRequest
            ? (!p.kind || p.kind === 'command' || p.kind === 'humanCommand') &&
              (typeof command === 'string'
                ? !!command.trim()
                : legacy &&
                  Array.isArray(command) &&
                  command.length > 0 &&
                  command.every((arg) => typeof arg === 'string'))
            : files?.length);
        const decline = legacy ? 'abort' : 'decline';
        if (eligible) {
          events.permissions.request(
            id,
            call,
            { name: method, input: { ...p, command, changes }, summary },
            (decision) => {
              reply({ decision: decision.allow ? (legacy ? 'approved' : 'accept') : decline });
              if (!decision.allow || decision.report)
                report(
                  details(`Codex ${decision.allow ? 'allowed' : 'declined'} ${method}.`, {
                    ...summary,
                    decision: decision.reason,
                  }),
                );
            },
          );
        } else {
          reply({ decision: decline });
          if (bound) report(details(`Codex declined ${method}; no identifiable single-use action.`, summary));
        }
      } else if (method === 'item/permissions/requestApproval') {
        reply({ permissions: {}, scope: 'turn' });
        if (bound)
          report(
            details('Codex declined a broader grant. Request a specific command or file change.', {
              permissions: p.permissions,
              reason: p.reason,
            }),
          );
      } else if (method === 'item/tool/requestUserInput') {
        reply({ answers: {} });
        if (bound) report(details('Codex requested user input.', { questions: p.questions }));
      } else if (method === 'mcpServer/elicitation/request') {
        reply({ action: 'decline', content: null, _meta: null });
        if (threadId && p.threadId === threadId && events.active && (!p.turnId || p.turnId === events.active))
          report(
            details('Codex requested user input.', {
              server: p.serverName,
              message: p.message,
              url: p.url,
              schema: p.requestedSchema,
            }),
          );
      } else {
        void proc
          .write({ id, error: { code: -32601, message: 'Unsupported worker host request' } })
          .catch(console.error);
      }
      return;
    }
    if (!threadId || params?.threadId !== threadId) return;
    if (method === 'serverRequest/resolved') events.permissions.cancel(params.requestId);
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
    if (method === 'turn/started' && !inputRequest?.turnId) acceptInput(params.turn.id);
    if (
      method === 'item/started' &&
      params.item.type === 'userMessage' &&
      inputRequest &&
      params.item.clientId === inputRequest.messageId
    )
      acceptInput(params.turnId);
    if (params.turnId && params.turnId === events.active) {
      if (method === 'item/started' || method === 'item/completed')
        codexItem(events.details, params.item, method === 'item/completed');
      if (method === 'error' && params.error?.message)
        events.details.message(`error:${++errorCount}`, 'system', params.error.message);
    }
    if (params.turnId && params.turnId === events.active) {
      if (method === 'item/started' && ['commandExecution', 'fileChange'].includes(params.item.type))
        items.set(params.item.id, params.item);
      if (method === 'item/fileChange/patchUpdated') {
        events.permissions.cancelCall(params.itemId);
        items.set(params.itemId, { id: params.itemId, type: 'fileChange', changes: params.changes });
      }
      if (method === 'item/completed') {
        if (finalMessage(params.item)) finalText = params.item.text;
        events.permissions.cancelCall(params.item.id);
        items.delete(params.item.id);
      }
    }
    if (
      method === 'item/autoApprovalReview/completed' &&
      params.turnId === events.active &&
      ['denied', 'timedOut', 'aborted'].includes(params.review.status)
    ) {
      if (params.targetItemId) {
        deniedItems.add(params.targetItemId);
        events.permissions.cancelCall(params.targetItemId);
      }
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
      if (turn.id !== events.active) return;
      for (const item of turn.items ?? []) codexItem(events.details, item, true);
      const state = turn.status === 'completed' || turn.status === 'interrupted' ? turn.status : 'failed';
      events.end(
        turn.id,
        state,
        turn.error?.message ??
          (turn.items?.findLast(finalMessage)?.text || finalText || `Codex turn ${state}`),
        tokenCount(tokens) ? tokens : null,
      );
      finalText = '';
      items.clear();
      deniedItems.clear();
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
      config: Object.fromEntries(
        hostedWorkerMcp(options.mcp).map(({ server, launch, tools }) => [
          `mcp_servers.${server}`,
          {
            ...launch,
            required: true,
            tools: Object.fromEntries(tools.map((tool) => [tool, { approval_mode: 'approve' }])),
          },
        ]),
      ),
    };
    const response = await request<{ thread: { id: string }; model?: string }>(
      threadId ? 'thread/resume' : 'thread/start',
      threadId ? { ...common, threadId } : common,
    );
    if (!response.thread.id || (threadId && threadId !== response.thread.id))
      throw new Error('Codex returned a different or empty thread id');
    threadId = response.thread.id;
    model = response.model;
  } catch (error) {
    await proc.close();
    throw error;
  }
  return {
    sessionId: threadId,
    async send(text: string) {
      const input = [{ type: 'text', text, text_elements: [] }];
      const messageId = randomUUID();
      const turnId = events.active;
      inputRequest = { rpcId: nextId + 1, messageId, text, turnId };
      try {
        if (turnId)
          await request('turn/steer', {
            threadId,
            expectedTurnId: turnId,
            clientUserMessageId: messageId,
            input,
          });
        else await request('turn/start', { threadId, clientUserMessageId: messageId, input });
      } catch (error) {
        if (!turnId && inputRequest) acceptInput(messageId);
        inputRequest = undefined;
        if (events.active) events.end(events.active, 'failed', String(error));
        throw error;
      }
    },
    async stop() {
      events.permissions.stop();
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
    async close() {
      events.permissions.stop();
      await proc.close();
      if (events.active) events.end(events.active, 'interrupted', 'Worker session closed');
      await events.finished;
    },
  };
}

async function claude(options: CliWorkerOptions) {
  const sessionId = options.sessionId ?? randomUUID();
  const hosted = hostedWorkerMcp(options.mcp);
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
    ...hosted.flatMap(({ server, tools }) => tools.map((tool) => `mcp__${server}__${tool}`)),
    '--mcp-config',
    JSON.stringify({ mcpServers: Object.fromEntries(hosted.map(({ server, launch }) => [server, launch])) }),
    options.sessionId ? '--resume' : '--session-id',
    sessionId,
  ];
  const proc = new CliProcess('claude', args, options.cwd);
  const events = new TurnEvents(options);
  const unconsumed = new Map<string, string>();
  let model: string | undefined;
  let lastResultId: string | undefined;
  const consume = (id: string) => {
    const text = unconsumed.get(id);
    if (text !== undefined) events.details.message(id, 'user', text);
    unconsumed.delete(id);
  };
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
    if (message.type === 'control_cancel_request') {
      if (!message.session_id || message.session_id === sessionId)
        events.permissions.cancel(message.request_id);
      return;
    }
    if (message.type === 'control_request') {
      const request = message.request;
      const id = message.request_id;
      const reply = (response: unknown) => {
        if (!proc.ended)
          void proc
            .write({ type: 'control_response', response: { request_id: id, subtype: 'success', response } })
            .catch(console.error);
      };
      const bound = events.active && (!message.session_id || message.session_id === sessionId);
      const report = (text: string) => events.report(`request:${request.tool_use_id ?? id}`, text);
      if (request.subtype === 'can_use_tool') {
        const deny = (message: string) => reply({ behavior: 'deny', message });
        if (!bound || !events.permissions.open) {
          deny('No matching live worker turn.');
        } else if (request.tool_name === 'AskUserQuestion') {
          deny('Question forwarded to the parent.');
          reportedDenials.add(request.tool_use_id);
          report(details('Claude requested user input.', { questions: request.input?.questions }));
        } else {
          const input = request.input;
          const target = actionTarget(input ?? {});
          const summary = {
            ...target,
            ...(request.blocked_path ? { target: request.blocked_path } : {}),
            ...(request.decision_reason || request.description
              ? { reason: request.decision_reason ?? request.description }
              : {}),
          };
          const hasTarget =
            request.blocked_path ||
            Object.keys(target).some((key) => !['reason', 'type', 'toolSummary'].includes(key));
          if (
            !id ||
            !request.tool_use_id ||
            !request.tool_name ||
            !input ||
            !hasTarget ||
            typeof input !== 'object' ||
            Array.isArray(input)
          ) {
            deny('Incomplete worker tool request.');
            report(details('Claude declined an incomplete tool request.', summary));
          } else {
            events.permissions.request(
              id,
              request.tool_use_id,
              { name: request.tool_name, input, summary },
              (decision) => {
                if (decision.allow) reply({ behavior: 'allow', updatedInput: input });
                else {
                  reportedDenials.add(request.tool_use_id);
                  deny(decision.reason);
                }
                if (!decision.allow || decision.report)
                  report(
                    details(`Claude ${decision.allow ? 'allowed' : 'declined'} ${request.tool_name}.`, {
                      ...summary,
                      decision: decision.reason,
                    }),
                  );
              },
            );
          }
        }
      } else if (request.subtype === 'elicitation') {
        reply({ action: 'decline' });
        if (bound)
          report(
            details('Claude requested user input.', {
              server: request.mcp_server_name,
              message: request.message,
              url: request.url,
              schema: request.requested_schema,
            }),
          );
      } else {
        void proc
          .write({
            type: 'control_response',
            response: { request_id: id, subtype: 'error', error: 'Unsupported worker host request' },
          })
          .catch(console.error);
      }
      return;
    }
    if (message.session_id && message.session_id !== sessionId)
      throw new Error('Claude returned a different session id');
    if (message.type === 'system' && message.subtype === 'init') {
      model = message.model;
      events.details.model = model;
    }
    if (!events.active || message.parent_tool_use_id) return;
    if (message.type === 'user' && message.isReplay) consume(message.uuid);
    if (message.type === 'assistant' || message.type === 'user') {
      for (const [i, block] of (Array.isArray(message.message?.content)
        ? message.message.content
        : []
      ).entries()) {
        if (message.type === 'assistant' && block.type === 'text')
          events.details.message(`${message.uuid ?? message.message.id}:${i}`, 'assistant', block.text);
        if (message.type === 'assistant' && block.type === 'tool_use')
          events.details.toolStart(block.id, block.name, block.input);
        if (message.type === 'user' && block.type === 'tool_result') {
          events.permissions.cancelCall(block.tool_use_id);
          events.details.toolEnd(block.tool_use_id, undefined, block.content, !!block.is_error);
        }
      }
    }
    if (message.type !== 'result' || (message.uuid && lastResultId === message.uuid)) return;
    lastResultId = message.uuid;
    events.permissions.stop();
    const tokens = claudeResultTokens(message.usage);
    const state = message.subtype === 'success' && !message.is_error ? 'completed' : 'failed';
    const text = (message.errors ?? []).join('\n') || message.result || `Claude turn ${message.subtype}`;
    if (state === 'completed' && message.result)
      events.details.finalMessage(`result:${message.uuid ?? events.active}`, message.result);
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
      events.details.end(state, tokens);
      events.report(message.uuid, text);
      const [next, correction] = unconsumed.entries().next().value!;
      events.begin(next, model);
      events.details.message(next, 'user', correction);
      return;
    }
    events.end(
      message.uuid ?? events.active,
      stopping ? 'interrupted' : state,
      stopping ? 'Claude turn interrupted' : text,
      tokens,
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
      if (proc.ended) throw new Error('Worker process is closing');
      if (!events.active) {
        events.begin(uuid, model);
        events.details.message(uuid, 'user', text);
      }
      unconsumed.set(uuid, text);
      await proc.write({
        type: 'user',
        uuid,
        session_id: sessionId,
        parent_tool_use_id: null,
        message: { role: 'user', content: text },
      });
    },
    async stop() {
      events.permissions.stop();
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
    async close() {
      events.permissions.stop();
      await proc.close();
      if (events.active) events.end(events.active, 'interrupted', 'Worker session closed');
      await events.finished;
    },
  };
}

const ANTIGRAVITY_MAX_INPUT_BYTES = 185_000;
const ANTIGRAVITY_MAX_TOOL_TEXT = 16_000;

function normalizeAcpToolName(title?: string, kind?: string) {
  const trimmed = title?.trim();
  if (trimmed) {
    return trimmed
      .replace(/^Run(?:ning)?\s+/i, '')
      .replace(/\?$/, '')
      .trim() || trimmed;
  }
  return typeof kind === 'string' && kind.trim() ? kind.trim() : undefined;
}

function sanitizeAcpToolOutput(value: unknown): unknown {
  if (typeof value === 'string') {
    if (/^data:image\//i.test(value)) return '[image omitted]';
    return value.length > ANTIGRAVITY_MAX_TOOL_TEXT
      ? `${value.slice(0, ANTIGRAVITY_MAX_TOOL_TEXT)}…`
      : value;
  }
  if (Array.isArray(value)) return value.map(sanitizeAcpToolOutput);
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (record.type === 'content' && record.content !== undefined) {
      return sanitizeAcpToolOutput(record.content);
    }
    if (record.type === 'image') return { type: 'image', omitted: true };
    return Object.fromEntries(
      Object.entries(record).map(([key, item]) => [
        key,
        key === 'data' && typeof record.mimeType === 'string' && record.mimeType.startsWith('image/')
          ? '[image omitted]'
          : sanitizeAcpToolOutput(item),
      ]),
    );
  }
  return value;
}

function normalizeAntigravityAuthError(error: unknown): Error {
  const code = (error as { code?: unknown } | null)?.code;
  const message = error instanceof Error ? error.message : String(error);
  if (code === -32000 || /No browser is available here|not logged in|not signed in|sign in/i.test(message)) {
    return new Error(`Antigravity CLI is not signed in on this machine: ${message}`);
  }
  return error instanceof Error ? error : new Error(message);
}

interface AcpPromptResult {
  stopReason?: string;
  usage?: {
    inputTokens?: unknown;
    outputTokens?: unknown;
    cachedReadTokens?: unknown;
  };
}

interface TrackedAcpTool {
  name: string;
  explicitName?: string;
  title?: string;
  kind?: string;
  rawInput?: Record<string, unknown>;
  locations?: { path?: string }[];
}

async function antigravity(options: CliWorkerOptions) {
  const runtimeTmp = await mkdtemp(join(tmpdir(), 'nano-agy-tmp-'));
  const proc = new CliProcess('agy', ['acp', '--process-per-session'], options.cwd, {
    env: {
      SSH_CLIENT: undefined,
      SSH_CONNECTION: undefined,
      SSH_TTY: undefined,
      BROWSER: undefined,
      AGY_CLI_DISABLE_AUTO_UPDATE: 'true',
      NO_COLOR: '1',
      PYTHONUNBUFFERED: '1',
      ...(process.platform === 'win32' ? { TEMP: runtimeTmp, TMP: runtimeTmp } : { TMPDIR: runtimeTmp }),
    },
    onStdoutLine: (line) =>
      line.startsWith('Open the following link to authenticate')
        ? new Error('Antigravity CLI is not signed in on this machine. Run agy login first.')
        : undefined,
    onCleanup: () => rm(runtimeTmp, { recursive: true, force: true }),
  });
  const events = new TurnEvents(options);
  let sessionId = options.sessionId ?? '';
  let nextId = 0;
  let msgSeq = 0;
  let model: string | undefined;
  let supportsAppend = false;
  let sentInitialInstructions = Boolean(options.sessionId);
  let stopping = false;
  let inFlightPrompts = 0;
  let assistantDraft = '';
  let lastAssistantText = '';
  const hosted = hostedWorkerMcp(options.mcp);
  const trackedTools = new Map<string, TrackedAcpTool>();
  const settledToolIds = new Set<string>();

  const freshStats = () => ({
    contextUsed: undefined as number | undefined,
    contextWindow: undefined as number | undefined,
    totalInput: 0,
    totalOutput: 0,
    totalCacheRead: 0,
    settledPrompts: 0,
    allPromptsReportedTokens: true,
    allPromptsReportedCache: true,
    highestSettledId: 0,
    outcome: undefined as { state: CliEndState; stopReason?: string; error?: string } | undefined,
  });
  let stats = freshStats();

  const flushAssistant = () => {
    if (!assistantDraft) return;
    lastAssistantText = assistantDraft;
    events.details.message(`assistant:${++msgSeq}`, 'assistant', assistantDraft);
    assistantDraft = '';
  };

  const settleOpenTools = (state: CliEndState) => {
    for (const [callId, entry] of trackedTools) {
      settledToolIds.add(callId);
      if (state === 'completed') {
        events.details.toolEnd(callId, entry.name, lastAssistantText || 'Awaiting parent response', false, {
          args: entry.rawInput,
        });
      }
    }
    trackedTools.clear();
  };

  const buildTurnUsage = (): WorkUsage | null => {
    const out: WorkUsage = {};
    if (stats.contextUsed !== undefined) out.context_used = stats.contextUsed;
    if (stats.contextWindow !== undefined) out.context_window = stats.contextWindow;
    if (inFlightPrompts === 0 && stats.settledPrompts > 0 && stats.allPromptsReportedTokens) {
      out.output = stats.totalOutput;
      out.total_tokens = stats.totalInput + stats.totalOutput;
      if (stats.allPromptsReportedCache) {
        out.cache_read_tokens = stats.totalCacheRead;
        out.cache_total_input_tokens = stats.totalInput;
      }
    }
    return Object.keys(out).length > 0 ? out : null;
  };

  const finishIfDrained = (turnId: string) => {
    if (inFlightPrompts > 0 || events.active !== turnId) return;
    flushAssistant();
    const outcome = stats.outcome;
    const state: CliEndState = stopping ? 'interrupted' : (outcome?.state ?? 'completed');
    const replyText =
      state === 'interrupted'
        ? 'Antigravity turn interrupted'
        : outcome?.error
          ? outcome.error
          : lastAssistantText || `Antigravity turn ${outcome?.stopReason ?? state}`;
    settleOpenTools(state);
    events.end(turnId, state, replyText, buildTurnUsage());
  };

  const request = async <T>(method: string, params: unknown) => {
    const id = ++nextId;
    try {
      return await proc.request<T>(id, { jsonrpc: '2.0', id, method, params }, `Antigravity ${method}`);
    } catch (error) {
      throw normalizeAntigravityAuthError(error);
    }
  };

  proc.onExit = (error) => {
    flushAssistant();
    if (events.active) {
      if (inFlightPrompts > 0) {
        stats.allPromptsReportedTokens = false;
        stats.allPromptsReportedCache = false;
      }
      inFlightPrompts = 0;
      const endState: CliEndState = stopping ? 'interrupted' : 'failed';
      settleOpenTools(endState);
      events.end(
        events.active,
        endState,
        normalizeAntigravityAuthError(error).message,
        buildTurnUsage(),
      );
    }
  };

  proc.onMessage = ({ id, method, params, result, error }) => {
    if (!method) {
      proc.resolve(id, result, error);
      return;
    }
    if (id !== undefined) {
      if (method === 'session/request_permission') {
        const rawCall = (params?.toolCall ?? {}) as {
          toolCallId?: string;
          name?: string;
          toolName?: string;
          title?: string;
          kind?: string;
          rawInput?: unknown;
          locations?: { path?: string }[];
        };
        const opts = (Array.isArray(params?.options) ? params.options : []) as {
          optionId?: string;
          kind?: string;
          name?: string;
        }[];
        const optionId = (kind: string) => {
          const id = opts.find((option) => option.kind === kind)?.optionId;
          return id && opts.filter((option) => option.optionId === id).length === 1 ? id : undefined;
        };
        const allow = optionId('allow_once');
        const reject = optionId('reject_once');
        const reply = (optionId?: string) => {
          const outcome = optionId ? { outcome: 'selected', optionId } : { outcome: 'cancelled' };
          if (!proc.ended) void proc.write({ jsonrpc: '2.0', id, result: { outcome } }).catch(console.error);
        };
        const call = rawCall.toolCallId;
        if (
          !sessionId ||
          params?.sessionId !== sessionId ||
          !events.active ||
          !events.permissions.open ||
          !call ||
          settledToolIds.has(call)
        ) {
          reply(reject);
          return;
        }
        const cached = trackedTools.get(call);
        const title = rawCall.title ?? cached?.title;
        if (call.startsWith('interaction_')) {
          reply();
          events.report(
            `question:${call}:${id}`,
            details('Antigravity requested user input.', {
              question: title || 'Choose an option',
              options: opts.map((o) => o.name || o.optionId),
            }),
          );
          return;
        }
        const kind = rawCall.kind ?? cached?.kind;
        const names = [rawCall.name, rawCall.toolName, cached?.explicitName].filter((v): v is string => !!v);
        const name = names[0] ?? normalizeAcpToolName(title, kind);
        const fromRequest = rawCall.rawInput;
        const rawInput = {
          ...cached?.rawInput,
          ...(fromRequest && typeof fromRequest === 'object' && !Array.isArray(fromRequest)
            ? fromRequest
            : {}),
        };
        const locations = (rawCall.locations ?? cached?.locations ?? [])
          .map((loc) => loc.path)
          .filter(Boolean);
        const target = actionTarget(rawInput);
        const path = target.Path ?? target.path ?? target.file_path;
        const summary = {
          kind,
          input: target,
          ...(locations.length && !(locations.length === 1 && locations[0] === path) ? { locations } : {}),
        };
        const report = (allowed: boolean, reason: string) =>
          events.report(
            `request:${call}:${id}`,
            details(`Antigravity ${allowed ? 'allowed' : 'declined'} ${name ?? 'action'}.`, {
              ...summary,
              decision: reason,
            }),
          );
        const titles = [rawCall.title, cached?.title]
          .filter((v): v is string => !!v)
          .map((t) => t.replace(/\?$/, ''));
        const conflicting =
          names.some((n) => n !== name) ||
          (rawCall.kind && cached?.kind && rawCall.kind !== cached.kind) ||
          (fromRequest != null && (typeof fromRequest !== 'object' || Array.isArray(fromRequest))) ||
          (cached?.rawInput &&
            fromRequest &&
            Object.entries(fromRequest).some(
              ([key, value]) => key in cached.rawInput! && !isDeepStrictEqual(cached.rawInput![key], value),
            ));
        if (!allow || !name || conflicting) {
          reply(reject);
          report(false, 'Missing single-use decision or unambiguous tool identity.');
          return;
        }
        const hostedTool = identifyHostedAcpTool(hosted, names, titles, kind, rawInput);
        if (hostedTool !== 'ordinary') {
          reply(hostedTool === 'bound' ? allow : reject);
          if (hostedTool === 'conflict') report(false, 'Conflicting host tool identity.');
          return;
        }
        const hasTarget =
          locations.length ||
          Object.keys(target).some((key) => !['reason', 'type', 'toolSummary'].includes(key));
        if (!Object.keys(rawInput).length || !hasTarget) {
          reply(reject);
          report(false, 'Missing target or tool arguments.');
          return;
        }
        events.permissions.request(
          id,
          call,
          {
            name,
            input: { ...rawCall, title, kind, rawInput, locations },
            summary,
          },
          (decision) => {
            reply(decision.allow ? allow : reject);
            if (!decision.allow || decision.report) report(decision.allow, decision.reason);
          },
        );
        return;
      }
      void proc
        .write({ jsonrpc: '2.0', id, error: { code: -32601, message: 'Unsupported worker host request' } })
        .catch(console.error);
      return;
    }
    if (method === '$/cancelRequest' && (!params?.sessionId || params.sessionId === sessionId))
      events.permissions.cancel(params.id);
    if (method !== 'session/update' || !sessionId || params?.sessionId !== sessionId) return;
    const upd = params?.update;
    if (!upd || typeof upd !== 'object') return;
    if (upd.sessionUpdate === 'config_option_update') {
      const updatedModel =
        upd.id === 'model' && typeof upd.currentValue === 'string'
          ? upd.currentValue
          : Array.isArray(upd.configOptions)
            ? upd.configOptions.find((entry: { id?: string; currentValue?: unknown }) => entry?.id === 'model')
                ?.currentValue
            : undefined;
      if (typeof updatedModel === 'string' && updatedModel) {
        model = updatedModel;
        events.details.model = model;
      }
    }
    if (!events.active) return;
    switch (upd.sessionUpdate) {
      case 'agent_message_chunk': {
        const chunk = upd.content?.text;
        if (typeof chunk === 'string' && chunk.length > 0) assistantDraft += chunk;
        break;
      }
      case 'tool_call':
      case 'tool_call_update': {
        const callId = typeof upd.toolCallId === 'string' ? upd.toolCallId : undefined;
        if (!callId || settledToolIds.has(callId)) break;
        flushAssistant();
        const prev = trackedTools.get(callId);
        const name =
          prev?.name ??
          (typeof upd.name === 'string' && upd.name ? upd.name : undefined) ??
          (typeof upd.toolName === 'string' && upd.toolName ? upd.toolName : undefined) ??
          normalizeAcpToolName(upd.title, upd.kind) ??
          'tool';
        const rawInput =
          upd.rawInput !== undefined && typeof upd.rawInput === 'object' && upd.rawInput !== null
            ? { ...prev?.rawInput, ...upd.rawInput }
            : prev?.rawInput;
        const entry: TrackedAcpTool = {
          name,
          explicitName: upd.name ?? upd.toolName ?? prev?.explicitName,
          title: typeof upd.title === 'string' ? upd.title : prev?.title,
          kind: typeof upd.kind === 'string' ? upd.kind : prev?.kind,
          rawInput,
          locations: Array.isArray(upd.locations) ? upd.locations : prev?.locations,
        };
        if (
          (upd.rawInput && !isDeepStrictEqual(prev?.rawInput, rawInput)) ||
          ((upd.name || upd.toolName) && (upd.name ?? upd.toolName) !== prev?.explicitName) ||
          (upd.kind && upd.kind !== prev?.kind) ||
          (upd.title && upd.title !== prev?.title) ||
          (upd.locations && !isDeepStrictEqual(prev?.locations, upd.locations))
        )
          events.permissions.cancelCall(callId);
        trackedTools.set(callId, entry);
        if (!prev) events.details.toolStart(callId, name, rawInput);
        if (upd.status === 'completed' || upd.status === 'failed' || upd.status === 'cancelled') {
          const rawOut = upd.content !== undefined ? upd.content : upd.rawOutput;
          events.details.toolEnd(callId, name, sanitizeAcpToolOutput(rawOut), upd.status !== 'completed', {
            reason: upd.status === 'cancelled' ? 'interrupted' : undefined,
            args: rawInput,
          });
          events.permissions.cancelCall(callId);
          trackedTools.delete(callId);
          settledToolIds.add(callId);
        }
        break;
      }
      case 'usage_update': {
        if (tokenCount(upd.used)) stats.contextUsed = upd.used;
        if (tokenCount(upd.size) && upd.size > 0) stats.contextWindow = upd.size;
        break;
      }
    }
  };

  try {
    const initialized = await request<{
      agentCapabilities?: {
        sessionCapabilities?: { resume?: unknown };
        _meta?: { antigravity?: { systemPrompt?: { append?: boolean } } };
      };
    }>('initialize', {
      protocolVersion: 1,
      clientInfo: { name: 'nano_worker', title: 'Nano worker', version: '1' },
      clientCapabilities: {
        fs: { readTextFile: false, writeTextFile: false },
        terminal: false,
      },
    });
    supportsAppend = initialized?.agentCapabilities?._meta?.antigravity?.systemPrompt?.append === true;
    const mcpServers = hosted.map(({ server: name, launch }) => ({
      name,
      command: launch.command,
      args: launch.args,
      env: Object.entries(launch.env).map(([name, value]) => ({ name, value })),
    }));
    const meta = supportsAppend
      ? { _meta: { antigravity: { systemPrompt: { append: options.instructions } } } }
      : {};
    type SessionSetup = {
      sessionId?: string;
      modes?: { currentModeId?: string; availableModes?: { id?: string }[] };
      configOptions?: { id?: string; currentValue?: unknown }[];
    };
    let setup: SessionSetup;
    if (options.sessionId) {
      if (!initialized?.agentCapabilities?.sessionCapabilities?.resume) {
        throw new Error('Antigravity CLI does not support session/resume');
      }
      setup = await request<SessionSetup>('session/resume', {
        sessionId: options.sessionId,
        cwd: options.cwd,
        mcpServers,
        ...meta,
      });
      if (setup?.sessionId !== options.sessionId) {
        throw new Error('Antigravity returned a different or empty session id');
      }
    } else {
      setup = await request<SessionSetup>('session/new', {
        cwd: options.cwd,
        mcpServers,
        ...meta,
      });
      if (!setup?.sessionId) throw new Error('Antigravity returned an empty session id');
    }
    sessionId = setup.sessionId;
    if (!setup.modes?.availableModes?.some((entry) => entry?.id === 'auto')) {
      throw new Error('Antigravity CLI does not offer auto permission mode');
    }
    await request('session/set_mode', { sessionId, modeId: 'auto' });
    const selectedModel = setup.configOptions?.find((entry) => entry?.id === 'model')?.currentValue;
    if (typeof selectedModel === 'string' && selectedModel) {
      model = selectedModel;
      events.details.model = model;
    }
  } catch (error) {
    await proc.close();
    throw error;
  }

  return {
    sessionId,
    async send(text: string) {
      if (Buffer.byteLength(text, 'utf8') > ANTIGRAVITY_MAX_INPUT_BYTES) {
        throw new Error(`Antigravity input exceeds ${ANTIGRAVITY_MAX_INPUT_BYTES}-byte limit`);
      }
      if (proc.ended) throw new Error('Worker process is closing');
      const messageId = randomUUID();
      const wireText =
        !supportsAppend && !sentInitialInstructions
          ? ((sentInitialInstructions = true), `${options.instructions}\n\n---\n\n${text}`)
          : text;
      if (!events.active) {
        stats = freshStats();
        inFlightPrompts = 0;
        assistantDraft = '';
        lastAssistantText = '';
        trackedTools.clear();
        events.begin(messageId, model);
      }
      const turnId = events.active!;
      events.details.message(messageId, 'user', text);
      const rpcId = ++nextId;
      inFlightPrompts++;
      try {
        const { response } = await proc.sendRequest<AcpPromptResult>(rpcId, {
          jsonrpc: '2.0',
          id: rpcId,
          method: 'session/prompt',
          params: { sessionId, prompt: [{ type: 'text', text: wireText }] },
        });
        void response.then(
          (res) => {
            inFlightPrompts = Math.max(0, inFlightPrompts - 1);
            if (events.active !== turnId) return;
            stats.settledPrompts++;
            const u = res?.usage;
            if (u && tokenCount(u.inputTokens) && tokenCount(u.outputTokens)) {
              const cacheRead = tokenCount(u.cachedReadTokens) ? u.cachedReadTokens : undefined;
              stats.totalInput += u.inputTokens + (cacheRead ?? 0);
              stats.totalOutput += u.outputTokens;
              if (cacheRead !== undefined) stats.totalCacheRead += cacheRead;
              else stats.allPromptsReportedCache = false;
            } else {
              stats.allPromptsReportedTokens = false;
              stats.allPromptsReportedCache = false;
            }
            if (rpcId >= stats.highestSettledId) {
              stats.highestSettledId = rpcId;
              const stopReason = res?.stopReason;
              const state: CliEndState =
                stopping || stopReason === 'cancelled'
                  ? 'interrupted'
                  : stopReason === 'refusal' || stopReason === 'error'
                    ? 'failed'
                    : 'completed';
              stats.outcome = { state, stopReason };
            }
            finishIfDrained(turnId);
          },
          (error) => {
            inFlightPrompts = Math.max(0, inFlightPrompts - 1);
            if (events.active !== turnId) return;
            stats.settledPrompts++;
            stats.allPromptsReportedTokens = false;
            stats.allPromptsReportedCache = false;
            if (rpcId >= stats.highestSettledId) {
              stats.highestSettledId = rpcId;
              stats.outcome = {
                state: stopping ? 'interrupted' : 'failed',
                error: stopping ? undefined : normalizeAntigravityAuthError(error).message,
              };
            }
            finishIfDrained(turnId);
          },
        );
      } catch (error) {
        inFlightPrompts = Math.max(0, inFlightPrompts - 1);
        if (events.active === turnId) {
          stats.settledPrompts++;
          stats.allPromptsReportedTokens = false;
          stats.allPromptsReportedCache = false;
          if (rpcId >= stats.highestSettledId) {
            stats.highestSettledId = rpcId;
            stats.outcome = { state: 'failed', error: normalizeAntigravityAuthError(error).message };
          }
          finishIfDrained(turnId);
        }
        throw error;
      }
    },
    async stop() {
      events.permissions.stop();
      if (!events.active) {
        await events.finished;
        return;
      }
      const finished = events.finished;
      stopping = true;
      try {
        await proc.write({ jsonrpc: '2.0', method: 'session/cancel', params: { sessionId } });
        await acknowledged(finished, 'Antigravity turn to stop');
      } finally {
        stopping = false;
      }
    },
    async close() {
      events.permissions.stop();
      await proc.close();
      if (events.active) {
        if (inFlightPrompts > 0) {
          stats.allPromptsReportedTokens = false;
          stats.allPromptsReportedCache = false;
        }
        inFlightPrompts = 0;
        settleOpenTools('interrupted');
        events.end(events.active, 'interrupted', 'Worker session closed', buildTurnUsage());
      }
      await events.finished;
    },
  };
}

const cliDrivers = { codex, claude, antigravity };

/** Open the native CLI session in the assigned workspace and use its installed model and identity. */
export async function openCliWorker(options: CliWorkerOptions) {
  return cliDrivers[options.runtime](options);
}
