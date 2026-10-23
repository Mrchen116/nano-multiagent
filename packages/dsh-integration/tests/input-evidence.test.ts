import { describe, expect, it } from 'vitest';
import { SessionSeq, type SessionEvent } from '@deepseek-ai/dsh-session';
import { MessageId, freezeMessage } from '@deepseek-ai/dsh-llm';
import { inputEvidence, inputIdsForTurn } from '../src/input-evidence.js';

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

describe('turn input attribution', () => {
  const message = (id: string) => freezeMessage({ id: MessageId(id), role: 'user' as const, content: [{ type: 'text' as const, text: id }], source: { kind: 'user' as const } });
  const rows: { type: string; data: unknown }[] = [
    { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, inserted: [message('a'), message('b')] } },
    { type: 'turn/start', data: { turn: 1 } },
    { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [] } },
    { type: 'agent/inbox/spliced', data: { target: 'next-step', start: 0, inserted: [message('c'), message('d')] } },
    { type: 'agent/inbox/spliced', data: { target: 'next-step', start: -1, removedCount: 1, inserted: [message('e')], outcome: 'canceled' } },
    { type: 'agent/inbox/spliced', data: { target: 'next-step', start: 0, removedCount: 2, inserted: [] } },
    { type: 'user/message', data: message('c') },
    { type: 'user/message', data: message('transcript-only') },
    { type: 'turn/end', data: { turn: 1, reason: { kind: 'error', error: { code: 'AUTH', message: 'failed' } } } },
    { type: 'turn/start', data: { turn: 2 } },
    { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, inserted: [message('a'), message('a'), message('nano-fallback:r:1')] } },
    { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 3, inserted: [] } },
    { type: 'user/message', data: message('a') },
    { type: 'turn/end', data: { turn: 2, reason: { kind: 'completed' } } },
    { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, inserted: [message('c')] } },
    { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [], outcome: 'canceled' } },
    { type: 'user/message', data: message('a') },
    { type: 'turn/start', data: { turn: 3 } },
    { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [] } },
    { type: 'turn/end', data: { turn: 3, reason: { kind: 'interrupted' } } },
  ];
  const history = rows.map((row, seq) => ({ ...row, seq: SessionSeq(seq), time: seq })) as SessionEvent[];
  it('preserves inputEvidence final ownership and first insertion order at every recovery prefix', () => {
    for (let end = 0; end <= history.length; end++) {
      const prefix = history.slice(0, end);
      const ids = [...new Set(prefix.flatMap(event => event.type === 'agent/inbox/spliced' ? event.data.inserted.map(message => message.id) : []))];
      for (const turn of [1, 2, 3]) {
        expect(inputIdsForTurn(prefix, turn), `prefix=${end}, turn=${turn}`).toEqual(ids.filter(id => inputEvidence(prefix, id).turn === turn));
      }
    }
    expect(inputIdsForTurn(history, 1)).toEqual(['c', 'e']);
    expect(inputIdsForTurn(history, 2)).toEqual(['nano-fallback:r:1']);
    expect(inputIdsForTurn(history, 3)).toEqual(['b']);
  });

  it('visits long history once rather than once per historical input', () => {
    const events = Array.from({ length: 1000 }, (_, turn) => [
      { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, inserted: [message(`input-${turn}`)] } },
      { type: 'turn/start', data: { turn } },
      { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [] } },
      { type: 'user/message', data: message(`input-${turn}`) },
      { type: 'turn/end', data: { turn, reason: { kind: 'completed' } } },
    ]).flat().map((row, seq) => ({ ...row, seq: SessionSeq(seq), time: seq })) as SessionEvent[];
    let visits = 0;
    const measured = new Proxy(events, { get(target, property, receiver) {
      if (typeof property === 'string' && /^\d+$/.test(property)) visits++;
      return Reflect.get(target, property, receiver);
    } });
    expect(inputIdsForTurn(measured, 999)).toEqual(['input-999']);
    expect(visits).toBeLessThanOrEqual(events.length * 2);
  });
});
