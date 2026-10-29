import { createHash } from 'node:crypto';
import type { Context } from '@deepseek-ai/cordis';
import { SESSION_FORMAT_VERSION, SessionId, SessionSeq, snapshotSessionEvent, type SessionEvent } from '@deepseek-ai/dsh-session';
import { ToolCallId, createAssistantMessage, createToolResultMessage } from '@deepseek-ai/dsh-llm';
import type { EvaluationHistory } from '@nano/product-contracts';
import type {} from '../knowledge/runtime.js';

export const hash = (value: unknown): string => createHash('sha256').update(JSON.stringify(value)).digest('hex');

/** Materialize original conversations through the public persistence API.
 *
 * Args:
 *   ctx: Evaluation runtime with the ordinary Nano memory services.
 *   history: Label-free, complete history supplied by the runner.
 *   workspace: Isolated source workspace.
 *   agentId: Trusted evaluation owner identity.
 * Returns:
 *   Source mapping for audit, never exposed as additional memory.
 */
export async function importHistory(ctx: Context, history: EvaluationHistory, workspace: string, agentId: string) {
  for (const session of history.sessions) {
    const handle = await ctx.sessionPersistence.create({ version: SESSION_FORMAT_VERSION, id: SessionId(session.id),
      createdAt: session.timestamp, cwd: workspace, isSeeded: false, agentPreset: `nano:${agentId}:1` });
    await handle.flush(); await handle.close();
  }
  // The product's activation baseline must precede the imported experience.
  await ctx.nanoKnowledge.dreaming.status(agentId);
  const mapping: Array<{ session: string; turn: number; firstSeq: number; lastSeq: number; contentHash: string }> = [];
  for (const session of history.sessions) {
    const handle = await ctx.sessionPersistence.open(SessionId(session.id), 'write');
    let seq = 0;
    try {
      for (const [index, message] of session.turns.entries()) {
        const turn = index + 1;
        const events: SessionEvent[] = [];
        const add = (type: string, data: unknown, surface = false) => events.push(snapshotSessionEvent({
          type, seq: SessionSeq(seq++), time: session.timestamp, data, ...(surface ? { surfaceOp: 'append' } : {}),
        } as SessionEvent));
        const firstSeq = seq;
        add('turn/start', { turn }); add('step/start', { turn, step: 1 });
        const callId = ToolCallId(`import-${turn}`);
        const target = session.id;
        const name = message.role === 'user' ? 'inbox' : 'send_message';
        const args = message.role === 'user' ? { action: 'read', target } : { target, text: message.content };
        const provenance = { source: 'imported-history', session_date: session.date, original_turn: index, time_precision: 'session' };
        const fragments = Array.from(message.content);
        const parts: string[] = [];
        for (let offset = 0; offset < fragments.length; offset += 6000) parts.push(fragments.slice(offset, offset + 6000).join(''));
        if (!parts.length) parts.push('');
        const body = message.role === 'user' ? { target, provenance, messages: parts.map((text, index) => ({
          id: `${session.id}-${turn}`, sender: { id: 'evaluation-owner', type: 'user', name: 'Owner', is_owner: true },
          time: session.date, content: [{ type: 'text', text }],
          ...(parts.length > 1 ? { partial: true, part: index + 1, parts: parts.length } : {}),
        })) } : { status: 'sent', target, provenance, message_id: `${session.id}-${turn}` };
        add('assistant/message', { turn, step: 1, stream: [], message: createAssistantMessage({
          content: [{ type: 'tool-call', id: callId, name, arguments: JSON.stringify(args) }],
          source: { provider: 'imported-history', model: 'structural-mapping' },
        }) }, true);
        add('tool/call', { turn, step: 1, callId, name, arguments: JSON.stringify(args) });
        add('tool/result', { turn, step: 1, message: createToolResultMessage({ callId,
          content: [{ type: 'text', text: JSON.stringify(body) }], isError: false }) }, true);
        add('step/end', { turn, step: 1 }); add('turn/end', { turn, reason: { kind: 'completed' } });
        await handle.append(events);
        mapping.push({ session: session.id, turn: index, firstSeq, lastSeq: seq - 1, contentHash: hash(message.content) });
      }
      await handle.flush();
    } finally { await handle.close(); }
  }
  return mapping;
}
