import { createServer } from 'node:net';
import { appendFileSync, writeFileSync, realpathSync } from 'node:fs';
import { join, relative, resolve, isAbsolute } from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { EvaluationHistory, EvaluationLimits, EvaluationUsage } from '@nano/product-contracts';
import { RpcPeer } from '../rpc.js';
import { initializeHistory, appendHistoryWindow } from './history.js';
import type {} from '../owned-sessions.js';
import type {} from '../knowledge/runtime.js';

export const name = 'nano-memory-evaluation';
export const inject = ['nanoKnowledge', 'nanoSessions', 'sessionPersistence', 'sessions', 'tools', 'llm', 'tokenMeter'];
interface Configuration { socket: string; workspace: string; agentId: string; rootSessionId: string; conversationId: string; stage: 'prepare' | 'answer'; audit: string; limits: EvaluationLimits; startTime: number }

/** Mount only in the evaluation profile; production exposes none of these controls. */
export function apply(ctx: Context, config: Configuration) {
  const started = Date.now();
  let logicalTime = config.startTime, importedSessions = 0, importedMessages = 0;
  const dreaming = ctx.nanoKnowledge.dreaming;
  if (config.stage === 'prepare') dreaming.useClock(() => logicalTime);
  const timeline = (event: Record<string, unknown>) => appendFileSync(join(config.audit, 'timeline.jsonl'),
    JSON.stringify({ logicalTime, importedSessions, ...event }) + '\n');
  const usage: EvaluationUsage = { modelCalls: 0, inputTokens: null, outputTokens: null, costUsd: null, elapsedMs: 0 };
  let deniedTools = 0, accountedCalls = 0, inputTokens = 0, outputTokens = 0, budgetExhausted = false;
  const requests = join(config.audit, 'requests.jsonl');
  const audit = () => ({ processId: process.pid, requests, deniedTools, importedSessions, importedMessages, usage: { ...usage, elapsedMs: Date.now() - started,
    inputTokens: accountedCalls === usage.modelCalls && accountedCalls > 0 ? inputTokens : null,
    outputTokens: accountedCalls === usage.modelCalls && accountedCalls > 0 ? outputTokens : null } });
  const persistAudit = () => writeFileSync(join(config.audit, 'usage.json'), JSON.stringify(audit()));
  persistAudit();
  ctx.on('agent/request', async (_payload, next) => {
    const request = await next();
    return { ...request, maxTokens: Math.min(request.maxTokens ?? config.limits.maxOutputTokens, config.limits.maxOutputTokens) };
  }, { prepend: true });
  ctx.on('llm/stream', async function* (options, next) {
    if (usage.modelCalls >= config.limits.maxModelCalls) { budgetExhausted = true; throw new Error('Evaluation model-call budget exhausted'); }
    usage.modelCalls++; persistAudit();
    if (options.maxTokens === undefined || options.maxTokens > config.limits.maxOutputTokens) throw new Error('Evaluation output budget was not applied');
    // Capture assembled inputs, not provider credentials or environment values.
    appendFileSync(requests, JSON.stringify({ ...(config.stage === 'prepare' ? { logicalTime, importedSessions } : {}), sessionId: options.sessionId, messages: options.messages,
      tools: options.tools, system: options.system, maxTokens: options.maxTokens }) + '\n');
    let observed = false;
    try {
      for await (const chunk of next()) {
        if (chunk.type === 'usage') { inputTokens += chunk.usage.inputTokens; outputTokens += chunk.usage.outputTokens; observed = true; }
        yield chunk;
      }
    } finally { if (observed) accountedCalls++; persistAudit(); }
  }, { prepend: true });
  if (config.stage === 'answer') {
    const root = realpathSync(join(config.workspace, '.nanoassistant/memory'));
    ctx.tools.guard(execution => {
      let reason: string | undefined;
      const args = execution.arguments as Record<string, unknown>;
      if (execution.name === 'inbox' || execution.name === 'send_message') return;
      if (!['read', 'glob', 'grep'].includes(execution.name)) reason = 'Evaluation answer allows only memory reads and local communication';
      else {
        const requested = args.file_path ?? args.path ?? root;
        try {
          if (typeof requested !== 'string') throw new Error('Invalid path');
          const path = realpathSync(resolve(config.workspace, requested));
          const rel = relative(root, path);
          if (rel.startsWith('..') || isAbsolute(rel)) throw new Error('Outside prepared memory');
          if (execution.name === 'glob' && typeof args.pattern === 'string' && (isAbsolute(args.pattern) || args.pattern.split('/').includes('..'))) throw new Error('Pattern escapes memory');
        } catch { reason = 'Evaluation isolation: only the prepared memory directory is readable'; }
      }
      if (reason) { deniedTools++; appendFileSync(join(config.audit, 'denied-tools.jsonl'), JSON.stringify({ name: execution.name, args, reason }) + '\n'); }
      return reason;
    });
  }
  const peers = new Set<RpcPeer>();
  const server = createServer(socket => {
    const peer = new RpcPeer(socket, socket); peers.add(peer); socket.once('close', () => peers.delete(peer));
    peer.handle('initializeHistory', async value => initializeHistory(ctx, value as EvaluationHistory, config.workspace, config.agentId, config.rootSessionId));
    peer.handle('prepare', async value => {
      const history = value as EvaluationHistory;
      const mapping: Awaited<ReturnType<typeof appendHistoryWindow>>['mapping'] = [];
      const attempt = async (at: number) => {
        logicalTime = at;
        const parent = await ctx.nanoSessions.resolve(config.rootSessionId);
        timeline({ event: 'automatic_start' });
        const run = await dreaming.tick(config.agentId) as { accepted: boolean; state?: string; reason?: string; error?: string; summary?: string } | undefined;
        await dreaming.whenIdle(config.agentId);
        await parent.whenIdle(); await ctx.sessions.flush(parent.session);
        await ctx.nanoSessions.disposeAgent(config.agentId);
        timeline({ event: 'automatic_end', result: run });
        if (run?.state === 'completed' || run?.reason === 'no_eligible_increment') return;
        return { status: budgetExhausted || run?.state === 'cancelled' ? 'incomplete' as const : 'failed' as const,
          reason: budgetExhausted ? 'Evaluation model-call budget exhausted' : run?.error ?? run?.reason ?? run?.summary ?? run?.state ?? 'Automatic maintenance was not admitted', details: run };
      };
      for (let index = 0; index < history.sessions.length;) {
        const arrival = history.sessions[index]!.timestamp;
        // Product scheduling chooses admission times; the adapter only advances between arrivals.
        let due = await dreaming.nextAutomaticAt(config.agentId);
        while (due !== undefined && due < arrival) {
          const failure = await attempt(Math.max(logicalTime, due));
          if (failure) return failure;
          due = await dreaming.nextAutomaticAt(config.agentId);
        }
        logicalTime = arrival;
        // A simultaneous arrival wins a tie with maintenance, including all same-time sessions.
        do {
          const session = history.sessions[index]!;
          const imported = await appendHistoryWindow(ctx, session, config.rootSessionId, config.conversationId, index++);
          mapping.push(...imported.mapping);
          importedSessions++; importedMessages += session.turns.length; persistAudit();
          timeline({ event: 'session_imported', sessionId: session.id, rootSessionId: config.rootSessionId, windowId: imported.windowId });
          writeFileSync(join(config.audit, 'source-map.json'), JSON.stringify(mapping, null, 2));
        } while (index < history.sessions.length && history.sessions[index]!.timestamp === arrival);
        dreaming.recordActivity(config.agentId);
        due = await dreaming.nextAutomaticAt(config.agentId);
        if (due !== undefined && due <= logicalTime) {
          const failure = await attempt(logicalTime);
          if (failure) return failure;
        }
      }
      await dreaming.whenIdle(config.agentId);
      const status = await dreaming.status(config.agentId);
      if (!status) throw new Error('Evaluation memory owner unavailable');
      timeline({ event: 'frozen', backlog: status.backlog, active: status.active });
      if (status.active || !['pending', 'no_eligible_increment'].includes(status.backlog.state)) {
        return { status: 'incomplete', reason: status.backlog.state, details: status };
      }
      return { status: 'ready', details: status };
    });
    peer.handle('idle', async () => {
      const agent = await ctx.nanoSessions.resolve(config.rootSessionId);
      await agent.whenIdle(); await ctx.sessions.flush(agent.session);
      return { status: agent.status };
    });
    peer.handle('audit', audit);
  });
  server.listen(config.socket);
  ctx.effect(() => () => { for (const peer of peers) peer.close(); server.close(); });
}
