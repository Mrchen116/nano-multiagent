import { randomUUID } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { SessionId } from '@deepseek-ai/dsh-session';
import { ToolCallId, type ContentBlock } from '@deepseek-ai/dsh-llm';
import type { ToolExecution, ToolRunContext } from '@deepseek-ai/dsh-tools';
import type { PromptContentPart } from '@deepseek-ai/dsh-attachment';
import type { AgentConfiguration, SessionBinding } from '../index.js';
import { isHumanSource, scopedChatEvents } from '../input-source.js';
import { computerScope, permitsWindow, scopeAllows } from './scope.js';
import { BrowserBackend } from './browser.js';
import { DesktopBackend } from './desktop.js';
import type { ComputerBackend, ComputerContent, PreparedAction } from './backend.js';

declare module '@deepseek-ai/cordis' {
  interface Context {
    nanoComputer: ComputerHost;
  }
}

type Surface = 'browser' | 'desktop';
type Call = { surface: Surface; action: string; input?: Record<string, unknown>; request_ref?: string };
type OwnerRequest = { id: string; text: string; ref: string; read?: string; ownerContext?: string };
type Seat = {
  root: Agent;
  controller: AbortController;
  request?: OwnerRequest;
  browser?: ComputerBackend;
  desktop?: ComputerBackend;
  busy?: string;
};
type Pending = { seat: Seat; action: PreparedAction; signal: AbortSignal; request?: OwnerRequest };
type WorkerCall = { seat: Seat; result?: ComputerContent[] };

const parameters = {
  type: 'object',
  properties: {
    surface: { enum: ['browser', 'desktop'] },
    action: { type: 'string' },
    input: { type: 'object', additionalProperties: true },
    request_ref: {
      type: 'string',
      description: 'Inbox message ID or direct IM message ID. Omit for the sole direct owner request.',
    },
  },
  required: ['surface', 'action'],
  additionalProperties: false,
} as const;

/** Recognize direct requests to use the current clipboard, without interpreting quotations or subordinate clauses. */
export function requestsClipboard(text: string): boolean {
  const zh =
    /^(?:请|帮我|请帮我)?(?:把我刚复制的(?:内容|文字|文本)(?:整理(?:一下)?|总结(?:一下)?|翻译(?:一下)?)|(?:读取|读一下|整理|总结|翻译)(?:一下)?(?:我刚复制的(?:内容|文字|文本)|(?:我的|系统)?剪贴板(?:里|中|上)?的?(?:内容|文字|文本)?))$/u;
  const en =
    /^(?:please )?(?:read|summarize|organize|translate) (?:my (?:current )?clipboard(?: contents)?|what i (?:just )?copied)$/i;
  const instruction = text
    .trim()
    .replace(/[。.!！]+$/u, '')
    .trim();
  return zh.test(instruction) || en.test(instruction);
}

/** A root turn and each explicitly delegated worker own distinct backend connections. */
export class ComputerHost {
  private roots = new Map<string, Seat>();
  private workers = new Map<string, Seat>();
  private calls = new Map<string, WorkerCall>();
  private prepared = new Map<ToolExecution['token'], Pending>();
  private grantEpoch = new Map<string, number>();
  private revokedAt = new Map<string, number>();
  private direct = new Map<string, Set<string>>();
  constructor(
    private ctx: Context,
    private bindings: Map<string, SessionBinding>,
    private config: (a: Agent) => AgentConfiguration | undefined,
  ) {
    ctx.provide('nanoComputer', this);
    ctx.on('session/event', (session, event) => {
      if (event.type === 'user/message' && isHumanSource(event.data.source) && event.data.source.computerOwnerRequest) {
        const live = this.direct.get(session.id) ?? new Set<string>();
        live.add(event.data.id);
        this.direct.set(session.id, live);
      }
      if (event.type === 'turn/end') {
        this.endRoot(session.id);
      }
    });
    ctx.on('agent/disposed', ({ agent }) => {
      this.revokedAt.delete(agent.id);
      this.endRoot(agent.id);
    });
    ctx.on('tools/result', (exec) => {
      this.release(exec);
    });
    ctx.effect(() => async () => {
      await Promise.all([...this.roots.values(), ...this.workers.values()].map((seat) => this.close(seat)));
      this.roots.clear();
      this.workers.clear();
    });
  }

  register(scope: Context) {
    scope.tools.register({
      name: 'computer_use',
      description:
        'Browse interactive or signed-in webpages in Chrome (background daily profile or clean isolated browser) and operate native desktop app windows when web_fetch/CLI are insufficient or user state lives in an app. Call describe or status first.',
      parameters,
      output: {
        schema: {
          type: 'object',
          properties: { content: { type: 'array', items: { type: 'object', additionalProperties: true } } },
          required: ['content'],
        },
        render: (_args, value) => (value as unknown as { content: ContentBlock[] }).content,
      },
      execute: async (_args, exec) => ({ content: await this.execute(exec) }),
    });
  }

  private enabled(root: Agent) {
    return !!this.bindings.get(root.id) && this.config(root)?.toolAllowlist?.includes('computer_use');
  }

  /** Release computer authority immediately when the owner deselects the tool. */
  revokeAgent(agentId: string) {
    this.grantEpoch.set(agentId, (this.grantEpoch.get(agentId) ?? 0) + 1);
    for (const [id, seat] of this.workers) {
      if (this.bindings.get(seat.root.id)?.agentId !== agentId) continue;
      this.workers.delete(id);
      void this.close(seat);
    }
    for (const [id, binding] of this.bindings)
      if (binding.agentId === agentId) {
        const seq = this.ctx.get('agents')?.get(SessionId(id))?.session.snapshotEvents().at(-1)?.seq;
        if (seq !== undefined) this.revokedAt.set(id, seq);
        this.endRoot(id);
      }
  }

  private endRoot(id: string) {
    this.direct.delete(id);
    const seat = this.roots.get(id);
    this.roots.delete(id);
    if (seat) void this.close(seat);
  }

  private async close(seat: Seat) {
    seat.controller.abort();
    await Promise.allSettled([seat.browser?.close(), seat.desktop?.close()]);
  }

  private async original(root: Agent, ref: string | undefined, signal: AbortSignal): Promise<OwnerRequest> {
    if (ref === 'current') ref = undefined;
    const owner = this.bindings.get(root.id)?.ownerId;
    const events = scopedChatEvents(root.session.snapshotEvents());
    const start = events.findLast((e) => e.type === 'turn/start' || e.type === 'turn/end');
    if (!owner || start?.type !== 'turn/start') throw new Error('No active owner request');
    const minRevoked = this.revokedAt.get(root.id);
    const afterReads =
      minRevoked !== undefined
        ? events
            .filter((ev) => ev.seq > minRevoked && ev.type === 'tool/result' && !ev.data.message.isError)
            .map((ev) => (ev as Extract<typeof ev, { type: 'tool/result' }>).data.message.toolCallId)
        : undefined;
    const matches = new Map<string, OwnerRequest>();
    const seenReads = new Set<string>();
    for (const e of events) {
      if (e.seq <= Math.max(start.seq, minRevoked ?? -1)) continue;
      if (e.type === 'user/message' && this.direct.get(root.id)?.has(e.data.id) && isHumanSource(e.data.source)) {
        const src = e.data.source;
        if (
          src.actorId === owner &&
          src.computerOwnerRequest &&
          src.directHumanText &&
          !src.pa_agent_id &&
          (!ref || ref === e.data.id || ref === src.messageId || ref === src.computerOwnerRequest)
        )
          matches.set(src.messageId, { id: src.messageId, ref: src.messageId, text: src.directHumanText });
      }
      if (
        e.type !== 'tool/result' ||
        e.data.message.isError ||
        !this.ctx.get('nanoApproval')!.sources.isLiveInbox(root.id, e.data.message.toolCallId)
      )
        continue;
      const block = e.data.message.content.find((part) => part.type === 'text');
      if (!block || !ref) continue;
      let page: { messages?: Array<{ id: string; partial?: boolean }> };
      try {
        page = JSON.parse(block.text);
      } catch {
        continue;
      }
      if (!page.messages?.some((m) => m.id === ref && !m.partial)) continue;
      const read = e.data.message.toolCallId;
      if (seenReads.has(read)) continue;
      seenReads.add(read);
      const source = (await this.ctx
        .get('nanoProduct')!
        .call(
          'computer.request',
          { ref, read, ...(afterReads ? { afterReads } : {}) },
          { agent: root, signal, callId: ToolCallId(randomUUID()) },
        )) as {
        id: string;
        text: string;
        ownerContext?: string;
      } | null;
      if (source) matches.set(source.id, { ...source, ref, read });
    }
    if (matches.size !== 1)
      throw new Error(
        'Identify one complete owner instruction addressed to this Agent. For Inbox tasks pass its message ID as request_ref.',
      );
    return matches.values().next().value!;
  }

  private sessionOwnerContext(root: Agent, request: OwnerRequest): string {
    if (request.ownerContext) return request.ownerContext;
    const owner = this.bindings.get(root.id)?.ownerId;
    if (!owner) return request.text;
    const minSeq = this.revokedAt.get(root.id) ?? -1;
    const history: string[] = [];
    for (const e of scopedChatEvents(root.session.snapshotEvents())) {
      if (e.seq <= minSeq) continue;
      if (
        e.type === 'user/message' &&
        isHumanSource(e.data.source) &&
        e.data.source.actorId === owner &&
        !e.data.source.pa_agent_id &&
        e.data.source.directHumanText
      ) {
        history.push(e.data.source.directHumanText);
      }
    }
    if (!history.includes(request.text)) history.push(request.text);
    return history.join('\n');
  }

  async bindWorker(root: Agent, id: string, ref: string, signal: AbortSignal): Promise<() => void> {
    if (!this.enabled(root) || this.workers.has(id)) throw new Error('Computer delegation is unavailable');
    const agentId = this.bindings.get(root.id)!.agentId;
    const epoch = this.grantEpoch.get(agentId);
    const request = await this.original(root, ref, signal);
    if (!this.enabled(root) || epoch !== this.grantEpoch.get(agentId))
      throw new Error('Computer assignment was revoked');
    signal.throwIfAborted();
    if ([...this.workers.values()].some((s) => s.root === root && s.request?.id === request.id))
      throw new Error('This computer task is already assigned');
    const seat: Seat = { root, request, controller: new AbortController() };
    this.workers.set(id, seat);
    return () => {
      if (this.workers.get(id) === seat) {
        this.workers.delete(id);
        void this.close(seat);
      }
    };
  }

  async callWorker(root: Agent, id: string, args: unknown, signal: AbortSignal): Promise<ComputerContent[]> {
    const seat = this.workers.get(id);
    if (!seat || seat.root !== root || !this.enabled(root)) throw new Error('Computer assignment has ended');
    const boundSignal = AbortSignal.any([signal, seat.controller.signal]);
    const modelSelection = root.model.current() ?? { provider: root.options.provider!, model: root.options.model! };
    const toolSet = await root.ctx.tools.resolve({ agent: root, modelSelection, signal: boundSignal });
    const callId = ToolCallId(randomUUID());
    const origin: WorkerCall = { seat };
    this.calls.set(callId, origin);
    try {
      const batch = await root.ctx.tools.execute({
        agent: root,
        toolSet,
        signal: boundSignal,
        calls: [{ id: callId, type: 'tool-call', name: 'computer_use', arguments: JSON.stringify(args) }],
      });
      const result = batch.results[0]?.result;
      if (!result || result.isError || !origin.result)
        throw new Error(
          result?.content
            .filter((x) => x.type === 'text')
            .map((x) => x.text)
            .join('\n') || 'Computer operation denied',
        );
      return origin.result;
    } finally {
      this.calls.delete(callId);
      toolSet.dispose();
    }
  }

  /** Bind the exact prepared operation to DSH's opaque execution identity until dispatch. */
  async prepare(exec: ToolExecution) {
    const root = exec.agent;
    if (!root || !this.enabled(root)) throw new Error('Computer use is disabled for this caller');
    const args = exec.arguments as Call;
    const worker = this.calls.get(exec.callId);
    let seat = worker?.seat ?? this.roots.get(root.id);
    if (!seat) {
      seat = { root, controller: new AbortController() };
      this.roots.set(root.id, seat);
    }
    if (seat.busy) throw new Error('This computer task already has a pending operation');
    seat.busy = exec.callId;
    const signal = AbortSignal.any([exec.signal, seat.controller.signal]);
    try {
      const observation = ['status', 'describe'].includes(args.action);
      let request = worker?.seat.request;
      if (!observation && !request) request = await this.original(root, args.request_ref, signal);
      if (!worker && request && seat.request && seat.request.id !== request.id)
        throw new Error('This seat belongs to another owner request in the current turn');
      if (request && !observation) {
        const scope = computerScope(request.text, requestsClipboard(request.text));
        if (!scopeAllows(request.text, scope, args.surface, args.action, args.input ?? {}))
          throw new Error(
            args.action === 'read_clipboard'
              ? 'Reading the system clipboard requires a direct owner request.'
              : scope.isolatedOnly
                ? 'The owner requested an isolated browser profile; set mode="isolated".'
                : 'This computer operation is not permitted for a clipboard-only request.',
          );
        seat.request = request;
      }
      const backend =
        args.surface === 'browser'
          ? (seat.browser ??= new BrowserBackend(root.session.header.cwd!))
          : (seat.desktop ??= new DesktopBackend(root.session.header.cwd));
      const action = await backend.prepare(args.action, args.input ?? {}, signal);
      const ownerContext = request ? this.sessionOwnerContext(root, request) : '';
      if (action.window && (!request || !permitsWindow(ownerContext, action.window)))
        throw new Error('Name the intended window title in the owner request.');
      if (action.access === 'system_clipboard' && (!request || !requestsClipboard(request.text)))
        throw new Error(
          'Reading the system clipboard requires a direct owner request such as “把我刚复制的内容整理一下”.',
        );
      signal.throwIfAborted();
      this.prepared.set(exec.token, { seat, action, signal, request });
      return {
        access: action.access,
        target: action.evidence,
        ownerRequest: request?.text,
        ...(ownerContext && ownerContext !== request?.text ? { ownerContext } : {}),
        source: request?.id,
      };
    } catch (error) {
      delete seat.busy;
      throw error;
    }
  }

  private release(exec: ToolExecution) {
    const pending = this.prepared.get(exec.token);
    if (pending) {
      this.prepared.delete(exec.token);
      delete pending.seat.busy;
    }
  }

  private async execute(exec: ToolRunContext) {
    const op = this.prepared.get(exec.token);
    if (!op || !exec.agent || !this.enabled(exec.agent)) throw new Error('No approved computer operation remains');
    const { action, request, signal, seat } = op;
    signal.throwIfAborted();
    if (request?.read) {
      const current = (await this.ctx
        .get('nanoProduct')!
        .call('computer.request', { ref: request.ref, read: request.read }, exec)) as {
        id?: string;
        text?: string;
      } | null;
      if (current?.id !== request.id || current?.text !== request.text) throw new Error('Owner instruction withdrawn');
    } else if (
      request &&
      !scopedChatEvents(seat.root.session.snapshotEvents()).some(
        (event) =>
          event.type === 'user/message' &&
          isHumanSource(event.data.source) &&
          event.data.source.messageId === request.id &&
          event.data.source.computerOwnerRequest &&
          event.data.source.directHumanText === request.text,
      )
    )
      throw new Error('Owner instruction withdrawn');
    if (
      action.access === 'system_clipboard' &&
      !(await this.ctx.get('nanoProduct')!.call('computer.claim', { id: request!.id }, exec))
    )
      throw new Error('This instruction already consumed its clipboard read');
    signal.throwIfAborted();
    const blocks = await action.run(signal);
    const worker = this.calls.get(exec.callId);
    if (worker) worker.result = blocks;
    const content: PromptContentPart[] = blocks.map((block) =>
      block.type === 'text' ? block : { type: 'image', mediaType: block.mimeType as 'image/png', data: block.data },
    );
    return this.ctx.get('attachments')!.admitPromptContent(content);
  }
}
