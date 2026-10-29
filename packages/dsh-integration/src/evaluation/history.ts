import { createHash } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { SESSION_FORMAT_VERSION, Session, SessionId, SessionSeq, snapshotSessionEvent, type SessionEvent } from '@deepseek-ai/dsh-session';
import { SessionAlreadyOwnedError } from '@deepseek-ai/dsh-session-persistence';
import { CompactionId, compactCheckpointSource } from '@deepseek-ai/dsh-compaction';
import type {} from '@deepseek-ai/dsh-token-meter';
import { ToolCallId, createAssistantMessage, createToolResultMessage, createUserMessage } from '@deepseek-ai/dsh-llm';
import type { EvaluationHistory } from '@nano/product-contracts';
import type {} from '../knowledge/runtime.js';

export const hash = (value: unknown): string => createHash('sha256').update(JSON.stringify(value)).digest('hex');

/** Register the single empty Global root before its memory activation baseline.
 *
 * Args:
 *   ctx: Isolated evaluation runtime with the ordinary Nano memory services.
 *   history: Label-free history; only its first timestamp is used here.
 *   workspace: Isolated source workspace.
 *   agentId: Trusted evaluation owner identity.
 *   rootSessionId: The only persistent Global session for this case.
 */
export async function initializeHistory(ctx: Context, history: EvaluationHistory, workspace: string, agentId: string, rootSessionId: string) {
  const handle = await ctx.sessionPersistence.create({ version: SESSION_FORMAT_VERSION, id: SessionId(rootSessionId),
    createdAt: history.sessions[0]?.timestamp ?? 0, cwd: workspace, isSeeded: false, agentPreset: `nano:${agentId}:1` });
  try { await handle.flush(); } finally { await handle.close(); }
  await ctx.nanoKnowledge.dreaming.status(agentId);
}

async function openWriter(ctx: Context, id: string) {
  // Native disposal closes persistence asynchronously; only this explicit owner handoff may wait.
  const deadline = Date.now() + 5000;
  for (;;) {
    try { return await ctx.sessionPersistence.open(SessionId(id), 'write'); }
    catch (error) {
      if (!(error instanceof SessionAlreadyOwnedError) || Date.now() >= deadline) throw error;
      await new Promise(resolve => setTimeout(resolve, 25));
    }
  }
}

/** Append one arrived dialogue as a native window of the same cold Global root.
 *
 * Args:
 *   ctx: Runtime whose live root handle has already been released.
 *   session: Original dialogue segment, appended once at its arrival time.
 *   rootSessionId: Persistent Global identity shared by all segments.
 *   target: The one owner conversation, independent of dataset segment IDs.
 *   windowIndex: Zero-based segment position; the first uses the initial window.
 * Returns:
 *   Window identity and original-turn mapping for audit, never extra memory.
 */
export async function appendHistoryWindow(ctx: Context, session: EvaluationHistory['sessions'][number], rootSessionId: string,
  target: string, windowIndex: number) {
  const mapping: Array<{ session: string; turn: number; rootSessionId: string; windowId: string; firstSeq: number; lastSeq: number; contentHash: string }> = [];
  const handle = await openWriter(ctx, rootSessionId);
  try {
    const { events: prior } = await handle.read();
    // Detached restoration expects a terminal restore marker; persist it with the imported suffix.
    const restored = snapshotSessionEvent({ type: 'session/end-seed', seq: SessionSeq(prior.length), time: session.timestamp, data: {} });
    const native = Session.create(handle.id, [...prior, restored], handle.header);
    const events: SessionEvent[] = [restored];
    const record = <T extends SessionEvent>(event: T): T => {
      const imported = snapshotSessionEvent({ ...event, time: session.timestamp });
      events.push(imported); return imported;
    };
    let windowId = `${rootSessionId}:initial`;
    if (windowIndex > 0) {
      // Fixed dataset boundaries are structural imports, not model summaries or pressure-triggered rollovers.
      const compactionId = CompactionId(`import-window-${windowIndex}`);
      const lifecycle = { compactionId, turn: null };
      if (!native.surface.nodes.length) record(native.append('user/message', createUserMessage({
        content: [{ type: 'text', text: 'Imported empty history window.' }], source: { kind: 'agent-context', form: 'notice', summary: 'imported-history' },
      }), { surfaceOp: 'append' }));
      const startIndex = prior[native.surface.nodes[0] ?? -1]?.type === 'system/message' ? 1 : 0;
      const nodes = native.surface.nodes.slice(startIndex);
      const start = nodes[0]!, end = nodes.at(-1)!;
      const shadowedTokenCount = ctx.tokenMeter.measure(native).nodes.slice(startIndex).reduce((sum, node) => sum + node.heuristicTokens, 0);
      const opening = record(native.append('compaction/start', lifecycle));
      windowId = `${rootSessionId}:${opening.seq}`;
      const summary = [{ type: 'text' as const, text: 'Imported history window boundary. Earlier dialogue remains in History; no summary was generated.' }];
      const summarized = record(native.append('compaction/summary', { compactionId, summary,
        shadowedRange: { start, end }, shadowedSeqs: nodes, shadowedTokenCount,
        provider: 'imported-history', model: 'structural-window-mapping' }));
      record(native.append('user/message', createUserMessage({ content: summary, source: compactCheckpointSource(compactionId) }),
        { surfaceOp: { op: 'replace', startSeq: start, endSeq: end }, sourceEventSeqs: [opening.seq, summarized.seq, ...nodes] }));
      record(native.append('compaction/end', lifecycle));
    }
    let turn = prior.reduce((last, event) => event.type === 'turn/start' ? Math.max(last, event.data.turn) : last, 0);
    for (const [index, message] of session.turns.entries()) {
      turn++;
      const firstSeq = native.seq;
      record(native.append('turn/start', { turn })); record(native.append('step/start', { turn, step: 1 }));
      const callId = ToolCallId(`import-${turn}`);
      const name = message.role === 'user' ? 'inbox' : 'send_message';
      const args = message.role === 'user' ? { action: 'read', target } : { target, text: message.content };
      const provenance = { source: 'imported-history', session_id: session.id, session_date: session.date, original_turn: index, time_precision: 'session' };
      const fragments = Array.from(message.content);
      const parts: string[] = [];
      for (let offset = 0; offset < fragments.length; offset += 6000) parts.push(fragments.slice(offset, offset + 6000).join(''));
      if (!parts.length) parts.push('');
      const body = message.role === 'user' ? { target, provenance, messages: parts.map((text, index) => ({
        id: `${session.id}-${turn}`, sender: { id: 'evaluation-owner', type: 'user', name: 'Owner', is_owner: true },
        time: session.date, content: [{ type: 'text', text }],
        ...(parts.length > 1 ? { partial: true, part: index + 1, parts: parts.length } : {}),
      })) } : { status: 'sent', target, provenance, message_id: `${session.id}-${turn}` };
      record(native.append('assistant/message', { turn, step: 1, stream: [], message: createAssistantMessage({
        content: [{ type: 'tool-call', id: callId, name, arguments: JSON.stringify(args) }],
        source: { provider: 'imported-history', model: 'structural-mapping' },
      }) }, { surfaceOp: 'append' }));
      record(native.append('tool/call', { turn, step: 1, callId, name, arguments: JSON.stringify(args) }));
      record(native.append('tool/result', { turn, step: 1, message: createToolResultMessage({ callId,
        content: [{ type: 'text', text: JSON.stringify(body) }], isError: false }) }, { surfaceOp: 'append' }));
      record(native.append('step/end', { turn, step: 1 })); record(native.append('turn/end', { turn, reason: { kind: 'completed' } }));
      mapping.push({ session: session.id, turn: index, rootSessionId, windowId, firstSeq, lastSeq: native.seq - 1, contentHash: hash(message.content) });
    }
    await handle.append(events); await handle.flush();
    return { windowId, mapping };
  } finally { await handle.close(); }
}
