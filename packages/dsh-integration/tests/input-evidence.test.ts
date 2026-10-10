import { describe, expect, it } from 'vitest';
import { SessionSeq, type SessionEvent } from '@deepseek-ai/dsh-session';
import { MessageId, freezeMessage } from '@deepseek-ai/dsh-llm';
import { inputEvidence } from '../src/input-evidence.js';

describe('durable input evidence', () => {
  const message = freezeMessage({ id: MessageId('inbound-1'), role: 'user' as const, content: [{ type: 'text' as const, text: 'hello' }], source: { kind: 'user' as const } });
  function events(rows: { type: string; data: unknown }[]): SessionEvent[] {
    return rows.map((row, seq) => ({ ...row, seq: SessionSeq(seq), time: seq })) as SessionEvent[];
  }
  const accepted = { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, inserted: [message] } };
  it('retains acceptance when a crash occurs between claim and transcript commit', () => {
    expect(inputEvidence(events([
      accepted,
      { type: 'turn/start', data: { turn: 1 } },
      { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [] } },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'interrupted' } } },
    ]), message.id)).toMatchObject({ accepted: true, pending: false, consumedSeq: undefined, terminal: { kind: 'interrupted' } });
  });
  it('does not assign another input completion to the queued input', () => {
    expect(inputEvidence(events([
      accepted,
      { type: 'turn/start', data: { turn: 1 } },
      { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } },
    ]), message.id)).toMatchObject({ accepted: true, pending: true, terminal: undefined });
  });
  it('distinguishes cancelled queued input from a completed turn', () => {
    expect(inputEvidence(events([
      accepted,
      { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [], outcome: 'canceled' } },
    ]), message.id)).toMatchObject({ accepted: true, pending: false, terminal: { kind: 'cancelled-before-consumption' } });
  });
});
