import { createServer } from 'node:net';
import { appendFileSync, existsSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, isAbsolute } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import { SESSION_FORMAT_VERSION, Session, SessionId, SessionSeq, snapshotSessionEvent, type SessionEvent } from '@deepseek-ai/dsh-session';
import { SessionAlreadyOwnedError } from '@deepseek-ai/dsh-session-persistence';
import { CompactionId, compactCheckpointSource } from '@deepseek-ai/dsh-compaction';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type {} from '@deepseek-ai/dsh-subagent';
import type {} from '@deepseek-ai/dsh-system-prompt';
import type {} from '@deepseek-ai/dsh-token-meter';
import type { EvaluationLimits } from '@nano/product-contracts';
import { RpcPeer } from '../rpc.js';
import { contextTools } from '../agent-context.js';
import type {} from '../owned-sessions.js';
import type {} from '../knowledge/runtime.js';

export const name = 'nano-dolphinbench-evaluation';
export const inject = ['nanoKnowledge', 'nanoSessions', 'sessionPersistence', 'sessions', 'tools', 'llm', 'tokenMeter'];

export interface DolphinBenchRuntimeConfig {
  socket: string;
  workspace: string;
  agentId: string;
  ownerId: string;
  rootSessionId: string;
  conversationId: string;
  stage: 'ingestion' | 'test';
  allowConversationSearch: boolean;
  saveRawRequests: boolean;
  dreamMinIntervalDays?: number;
  audit: string;
  limits: EvaluationLimits;
  startTime: number;
  builtinSkillsRoot: string;
}

export interface AppServerSpec {
  command: string;
  args: string[];
  env: Record<string, string>;
}

async function openWriter(ctx: Context, id: string) {
  const deadline = Date.now() + 5000;
  for (;;) {
    try { return await ctx.sessionPersistence.open(SessionId(id), 'write'); }
    catch (error) {
      if (!(error instanceof SessionAlreadyOwnedError) || Date.now() >= deadline) throw error;
      await new Promise(resolveWait => setTimeout(resolveWait, 25));
    }
  }
}

function sanitizeJsonSchema(schema: unknown): Record<string, unknown> {
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) {
    return { type: 'object', properties: {} };
  }
  const copy = { ...(schema as Record<string, unknown>) };
  delete copy.$schema;
  if (!copy.type) copy.type = 'object';
  return copy;
}

function resolveExistingOrChildRealpath(targetAbs: string): string {
  const pendingSegments: string[] = [];
  let cursor = targetAbs;
  while (!existsSync(cursor)) {
    const parent = dirname(cursor);
    if (parent === cursor) break;
    pendingSegments.unshift(relative(parent, cursor));
    cursor = parent;
  }
  const realBase = realpathSync(cursor);
  return pendingSegments.length ? join(realBase, ...pendingSegments) : realBase;
}

/** Mount isolated DolphinBench controls: logical clock, window rollover, and per-turn MCP apps.
 *
 * Args:
 *   ctx: Isolated DSH Cordis context for one ingestion or cold-test runtime.
 *   config: Benchmark stage, sandbox roots, budget limits, and control socket path.
 */
export function apply(ctx: Context, config: DolphinBenchRuntimeConfig) {
  const clockStatePath = join(config.audit, 'clock-state.json');
  let persistedConsolidationAt: number | undefined;
  if (config.stage === 'ingestion' && existsSync(clockStatePath)) {
    try {
      const parsed = JSON.parse(readFileSync(clockStatePath, 'utf8')) as { lastConsolidationAt?: number };
      if (typeof parsed.lastConsolidationAt === 'number') persistedConsolidationAt = parsed.lastConsolidationAt;
    } catch { /* Ignore corrupt state and fall back to startTime. */ }
  }
  let logicalTime = config.startTime;
  let lastConsolidationAt = persistedConsolidationAt ?? config.startTime;
  const saveClockState = () => {
    writeFileSync(clockStatePath, JSON.stringify({ lastConsolidationAt }, null, 2));
  };
  if (config.stage === 'ingestion' && persistedConsolidationAt === undefined) {
    saveClockState();
  }
  let inDreaming = false;
  const dreaming = ctx.nanoKnowledge.dreaming;
  if (config.stage === 'ingestion') dreaming.useClock(() => logicalTime);

  const timeline = (event: Record<string, unknown>) =>
    appendFileSync(join(config.audit, 'timeline.jsonl'), JSON.stringify({ logicalTime, ...event }) + '\n');

  let turnCalls = 0, turnInput = 0, turnOutput = 0, turnCached = 0, turnDenied = 0;
  let dreamCalls = 0, dreamInput = 0, dreamOutput = 0, dreamCached = 0;
  let turnCallLimit = config.limits.maxModelCalls;
  let budgetExhausted = false;

  const activeChildren = new Set<string>();
  let wakeIdleCheck: (() => void) | undefined;
  ctx.on('subagent/start', ({ runId }) => { activeChildren.add(runId); });
  ctx.on('subagent/end', ({ runId }) => { activeChildren.delete(runId); wakeIdleCheck?.(); });

  const activeMcpTools = new Set<string>();
  let closeApps: (() => Promise<void>) | undefined;

  const memoryRoot = () => realpathSync(join(config.workspace, '.nanoassistant/memory'));
  const guidanceRoot = realpathSync(config.builtinSkillsRoot);
  const communicationTools = new Set([
    'inbox', 'send_message', 'send_user_message', 'personal_sources', 'skill',
    ...(config.stage === 'ingestion' ? ['memory_maintenance'] : []),
    ...(config.allowConversationSearch ? ['conversations', 'read_messages', 'search_messages', 'threads'] : []),
  ]);
  const allowedForegroundTool = (toolName: string) =>
    activeMcpTools.has(toolName)
    || contextTools.has(toolName)
    || communicationTools.has(toolName)
    || toolName === 'read'
    || toolName === 'glob'
    || toolName === 'grep';

  ctx.on('agent/request', async (_payload, next) => {
    const request = await next();
    return {
      ...request,
      maxTokens: Math.min(request.maxTokens ?? config.limits.maxOutputTokens, config.limits.maxOutputTokens),
    };
  }, { prepend: true });

  ctx.on('system-prompt/assemble', async (_assembly, _context, next) => {
    const assembly = await next();
    if (inDreaming) return assembly;
    const sections = assembly.sections.filter(section =>
      !section.name.startsWith('tool:') || allowedForegroundTool(section.name.slice('tool:'.length)));
    sections.push({
      name: 'nano-dolphinbench-direct-tools',
      text: 'Benchmark environment note: local workspace coding worker delegation (delegate_worker, subagent) is disabled here. Handle requests directly using your connected application tools and memory.',
    });
    if (!config.allowConversationSearch) {
      sections.push({
        name: 'nano-dolphinbench-memory-only',
        text: 'Evaluation ablation (memory-only): historical chat search tools (conversations, read_messages, search_messages, threads) are unavailable in this session. Use .nanoassistant/memory and inbox(action="read") for the current turn.',
      });
    }
    return { ...assembly, sections };
  }, { prepend: true });

  ctx.on('llm/stream', async function* (options, next) {
    const isDream = inDreaming;
    if (!isDream && turnCalls >= turnCallLimit) {
      budgetExhausted = true;
      throw new Error(`Evaluation per-turn model-call budget exhausted (${turnCallLimit})`);
    }
    if (isDream) dreamCalls++; else turnCalls++;
    if (config.saveRawRequests) {
      appendFileSync(join(config.audit, 'requests.jsonl'), JSON.stringify({
        logicalTime, stage: isDream ? 'dreaming' : config.stage, sessionId: options.sessionId,
        toolCount: Array.isArray(options.tools) ? options.tools.length : 0, maxTokens: options.maxTokens,
        messages: options.messages,
      }) + '\n');
    }
    for await (const chunk of next()) {
      if (chunk.type === 'usage') {
        const u = chunk.usage as { inputTokens?: number; outputTokens?: number; cacheReadTokens?: number; cachedTokens?: number };
        const cached = u.cacheReadTokens ?? u.cachedTokens ?? 0;
        if (isDream) {
          dreamInput += u.inputTokens ?? 0;
          dreamOutput += u.outputTokens ?? 0;
          dreamCached += cached;
        } else {
          turnInput += u.inputTokens ?? 0;
          turnOutput += u.outputTokens ?? 0;
          turnCached += cached;
        }
      }
      yield chunk;
    }
  }, { prepend: true });

  ctx.tools.guard(execution => {
    if (inDreaming) return;
    let reason: string | undefined;
    const args = execution.arguments as Record<string, unknown>;
    if (activeMcpTools.has(execution.name) || contextTools.has(execution.name) || communicationTools.has(execution.name)) return;
    if (!['read', 'glob', 'grep'].includes(execution.name)) {
      reason = `DolphinBench evaluation disallows host tool: ${execution.name}`;
    } else {
      try {
        const root = memoryRoot();
        const workspaceRoot = realpathSync(config.workspace);
        const nanoRoot = realpathSync(join(config.workspace, '.nanoassistant'));
        const requested = args.file_path ?? args.path ?? root;
        if (typeof requested !== 'string') throw new Error('Invalid path');
        const resolved = resolveExistingOrChildRealpath(resolve(config.workspace, requested));
        const inside = (base: string) => { const rel = relative(base, resolved); return !rel.startsWith('..') && !isAbsolute(rel); };
        const listingWorkspaceForMemory = (execution.name === 'glob' || execution.name === 'grep')
          && (resolved === workspaceRoot || resolved === nanoRoot);
        if (!inside(root) && !inside(guidanceRoot) && !listingWorkspaceForMemory) {
          throw new Error('Outside memory and guidance');
        }
        if (execution.name === 'glob' && typeof args.pattern === 'string' && (isAbsolute(args.pattern) || args.pattern.split('/').includes('..'))) {
          throw new Error('Glob pattern escapes memory');
        }
      } catch {
        reason = 'Evaluation isolation: only .nanoassistant/memory and packaged skills are readable';
      }
    }
    if (reason) {
      turnDenied++;
      appendFileSync(join(config.audit, 'denied-tools.jsonl'), JSON.stringify({ logicalTime, name: execution.name, args, reason }) + '\n');
    }
    return reason;
  });

  const disposeLiveRoot = async () => {
    const live = ctx.sessions.get(SessionId(config.rootSessionId));
    if (live) {
      const parent = await ctx.nanoSessions.resolve(config.rootSessionId);
      await parent.whenIdle();
      await ctx.sessions.flush(parent.session);
    }
    await ctx.nanoSessions.disposeAgent(config.agentId);
  };

  const peers = new Set<RpcPeer>();
  const server = createServer(socket => {
    const peer = new RpcPeer(socket, socket);
    peers.add(peer);
    socket.once('close', () => peers.delete(peer));

    peer.handle('initRoot', async value => {
      const { timestamp } = value as { timestamp: number };
      logicalTime = Math.max(logicalTime, timestamp);
      const exists = await ctx.sessionPersistence.stat(SessionId(config.rootSessionId));
      if (!exists) {
        const handle = await ctx.sessionPersistence.create({
          version: SESSION_FORMAT_VERSION,
          id: SessionId(config.rootSessionId),
          createdAt: timestamp,
          cwd: config.workspace,
          isSeeded: false,
          agentPreset: `nano:${config.agentId}:1`,
        });
        try { await handle.flush(); } finally { await handle.close(); }
      }
      if (config.stage === 'ingestion') await dreaming.status(config.agentId);
      return { initialized: !exists };
    });

    peer.handle('advanceClock', async value => {
      const { toMs, force } = value as { toMs: number; force?: boolean };
      const runs: Array<{ at: number; state?: string; reason?: string; inputTokens: number; outputTokens: number; modelCalls: number }> = [];
      const minIntervalDays = Math.max(1, config.dreamMinIntervalDays ?? 1);
      const minIntervalMs = (minIntervalDays - 1) * 86_400_000 + 12 * 3_600_000;
      if (config.stage === 'ingestion') {
        const shouldRunNow = Boolean(force) || minIntervalDays <= 1 || (toMs - lastConsolidationAt) >= minIntervalMs;
        if (shouldRunNow) {
          let due = await dreaming.nextAutomaticAt(config.agentId);
          while (due !== undefined && due <= toMs) {
            // When coalescing multiple calendar days, jump to toMs's night boundary so Dreaming batches them once.
            const stepAt = minIntervalDays > 1 && !force
              ? Math.max(logicalTime, due, toMs - 60_000)
              : Math.max(logicalTime, due);
            logicalTime = stepAt;
            await disposeLiveRoot();
            const beforeCalls = dreamCalls, beforeIn = dreamInput, beforeOut = dreamOutput;
            inDreaming = true;
            let run: { accepted?: boolean; state?: string; reason?: string; error?: string } | undefined;
            try {
              timeline({ event: 'dreaming_start', due: stepAt });
              run = await dreaming.tick(config.agentId) as typeof run;
              await dreaming.whenIdle(config.agentId);
            } finally {
              inDreaming = false;
            }
            await disposeLiveRoot();
            if (run?.state === 'completed') {
              lastConsolidationAt = stepAt;
              saveClockState();
            }
            timeline({ event: 'dreaming_end', result: run, modelCalls: dreamCalls - beforeCalls });
            runs.push({
              at: stepAt, state: run?.state, reason: run?.reason,
              modelCalls: dreamCalls - beforeCalls, inputTokens: dreamInput - beforeIn, outputTokens: dreamOutput - beforeOut,
            });
            if (
              run
              && run.state !== 'completed'
              && run.reason !== 'no_eligible_increment'
              && run.reason !== 'deferred_below_min_volume'
            ) {
              throw new Error(`Dreaming failed at ${new Date(stepAt).toISOString()}: ${run.error ?? run.reason ?? run.state}`);
            }
            due = await dreaming.nextAutomaticAt(config.agentId);
          }
          if (force) {
            logicalTime = Math.max(logicalTime, toMs);
            const pendingStatus = await dreaming.status(config.agentId);
            if (pendingStatus?.backlog.state === 'pending') {
              await disposeLiveRoot();
              const parent = await ctx.nanoSessions.resolve(config.rootSessionId);
              const beforeCalls = dreamCalls, beforeIn = dreamInput, beforeOut = dreamOutput;
              inDreaming = true;
              let flushRun: { accepted?: boolean; state?: string; reason?: string; error?: string } | undefined;
              try {
                timeline({ event: 'dreaming_flush_start', at: logicalTime });
                flushRun = await dreaming.start(parent, false) as typeof flushRun;
                await dreaming.whenIdle(config.agentId);
              } finally {
                inDreaming = false;
              }
              await disposeLiveRoot();
              if (flushRun?.state === 'completed') {
                lastConsolidationAt = logicalTime;
                saveClockState();
              }
              timeline({ event: 'dreaming_flush_end', result: flushRun, modelCalls: dreamCalls - beforeCalls });
              runs.push({
                at: logicalTime, state: flushRun?.state, reason: flushRun?.reason,
                modelCalls: dreamCalls - beforeCalls, inputTokens: dreamInput - beforeIn, outputTokens: dreamOutput - beforeOut,
              });
              if (flushRun && flushRun.state !== 'completed' && flushRun.reason !== 'no_eligible_increment') {
                throw new Error(`Final Dreaming flush failed at ${new Date(logicalTime).toISOString()}: ${flushRun.error ?? flushRun.reason ?? flushRun.state}`);
              }
            }
          }
        }
      }
      logicalTime = Math.max(logicalTime, toMs);
      const status = config.stage === 'ingestion' ? await dreaming.status(config.agentId) : undefined;
      return { logicalTime, runs, backlog: status?.backlog };
    });

    peer.handle('rolloverWindow', async value => {
      const { windowIndex, timestamp } = value as { windowIndex: number; timestamp: number };
      logicalTime = Math.max(logicalTime, timestamp);
      await disposeLiveRoot();
      const handle = await openWriter(ctx, config.rootSessionId);
      try {
        const { events: prior } = await handle.read();
        if (!prior.length) return { rolledOver: false };
        const restored = snapshotSessionEvent({ type: 'session/end-seed', seq: SessionSeq(prior.length), time: timestamp, data: {} });
        const native = Session.create(handle.id, [...prior, restored], handle.header);
        const startIndex = prior[native.surface.nodes[0] ?? -1]?.type === 'system/message' ? 1 : 0;
        const nodes = native.surface.nodes.slice(startIndex);
        if (!nodes.length) return { rolledOver: false };
        // Skip if the only active node is already a compact-checkpoint boundary.
        if (nodes.length === 1) {
          const single = prior[nodes[0]!];
          if (single?.type === 'user/message' && single.data.source.kind === 'compact-checkpoint') {
            return { rolledOver: false };
          }
        }
        const events: SessionEvent[] = [restored];
        const record = <T extends SessionEvent>(event: T): T => {
          const stamped = snapshotSessionEvent({ ...event, time: timestamp });
          events.push(stamped);
          return stamped;
        };
        const start = nodes[0]!, end = nodes.at(-1)!;
        const shadowedTokenCount = ctx.tokenMeter.measure(native).nodes.slice(startIndex).reduce((sum, node) => sum + node.heuristicTokens, 0);
        const compactionId = CompactionId(`dolphinbench-window-${windowIndex}`);
        const lifecycle = { compactionId, turn: null };
        const opening = record(native.append('compaction/start', lifecycle));
        const summary = [{ type: 'text' as const, text: 'New conversation session. Earlier interactions remain in memory and conversation history.' }];
        const summarized = record(native.append('compaction/summary', {
          compactionId, summary, shadowedRange: { start, end }, shadowedSeqs: nodes,
          shadowedTokenCount, provider: 'dolphinbench-harness', model: 'fresh-session-boundary',
        }));
        record(native.append('user/message', createUserMessage({ content: summary, source: compactCheckpointSource(compactionId) }),
          { surfaceOp: { op: 'replace', startSeq: start, endSeq: end }, sourceEventSeqs: [opening.seq, summarized.seq, ...nodes] }));
        record(native.append('compaction/end', lifecycle));
        await handle.append(events);
        await handle.flush();
        timeline({ event: 'window_rollover', windowIndex, shadowedNodes: nodes.length });
        return { rolledOver: true, windowId: `${config.rootSessionId}:${opening.seq}` };
      } finally {
        await handle.close();
      }
    });

    peer.handle('mountApps', async value => {
      if (closeApps) { await closeApps(); closeApps = undefined; }
      const spec = value as AppServerSpec;
      const [{ Client }, { StdioClientTransport }] = await Promise.all([
        import('@modelcontextprotocol/client'),
        import('@modelcontextprotocol/client/stdio'),
      ]);
      const client = new Client({ name: 'nano-dolphinbench', version: '1.0.0' });
      const transport = new StdioClientTransport({
        command: spec.command,
        args: spec.args,
        env: { ...(process.env as Record<string, string>), ...spec.env },
        stderr: 'ignore',
      });
      await client.connect(transport);
      const listed = await client.listTools();
      const disposers: Array<() => void> = [];
      activeMcpTools.clear();
      for (const tool of listed.tools) {
        activeMcpTools.add(tool.name);
        const dispose = ctx.tools.register({
          name: tool.name,
          description: tool.description ?? `Simulated application tool ${tool.name}`,
          parameters: sanitizeJsonSchema(tool.inputSchema),
          output: {
            schema: {
              type: 'object',
              properties: { text: { type: 'string' } },
              required: ['text'],
              additionalProperties: false,
            },
            render: (_args, outputValue) => [{ type: 'text', text: (outputValue as { text: string }).text }],
          },
          timeoutMs: 120_000,
          execute: async (args, exec) => {
            const callRes = await client.callTool({ name: tool.name, arguments: (args ?? {}) as Record<string, unknown> }, { signal: exec.signal });
            const blocks = Array.isArray(callRes.content) ? callRes.content : [];
            const text = blocks.map(block => (block as { type?: string; text?: string }).type === 'text' ? String((block as { text?: string }).text ?? '') : JSON.stringify(block)).join('\n');
            if (callRes.isError) throw new Error(text || `MCP tool ${tool.name} returned an error`);
            return { text };
          },
        });
        disposers.push(dispose);
      }
      closeApps = async () => {
        for (const dispose of disposers.reverse()) { try { dispose(); } catch { /* ignore */ } }
        activeMcpTools.clear();
        try { await client.close(); } catch { /* ignore */ }
      };
      return { tools: [...activeMcpTools] };
    });

    peer.handle('unmountApps', async () => {
      if (closeApps) { await closeApps(); closeApps = undefined; }
      return { ok: true };
    });

    peer.handle('beginTurn', async value => {
      const { maxModelCalls, timestamp } = value as { maxModelCalls?: number; timestamp: number };
      logicalTime = Math.max(logicalTime, timestamp);
      turnCalls = 0; turnInput = 0; turnOutput = 0; turnCached = 0; turnDenied = 0;
      budgetExhausted = false;
      turnCallLimit = maxModelCalls ?? config.limits.maxModelCalls;
      return { ok: true };
    });

    peer.handle('idle', async () => {
      const agent = await ctx.nanoSessions.resolve(config.rootSessionId);
      for (;;) {
        await agent.whenIdle();
        if (!activeChildren.size) break;
        await new Promise<void>(resolveWait => { wakeIdleCheck = resolveWait; });
      }
      await ctx.sessions.flush(agent.session);
      if (config.stage === 'ingestion') dreaming.recordActivity(config.agentId, logicalTime);
      return {
        status: agent.status,
        budgetExhausted,
        turnUsage: {
          modelCalls: turnCalls,
          inputTokens: turnInput,
          outputTokens: turnOutput,
          cachedTokens: turnCached,
          deniedTools: turnDenied,
        },
        dreamUsage: {
          modelCalls: dreamCalls,
          inputTokens: dreamInput,
          outputTokens: dreamOutput,
          cachedTokens: dreamCached,
        },
      };
    });
  });

  server.listen(config.socket);
  ctx.effect(() => () => {
    if (closeApps) void closeApps();
    for (const peer of peers) peer.close();
    server.close();
  });
}
