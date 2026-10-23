/** Synthetic, non-production comparison of fallback input attribution algorithms. */
import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import { inputEvidence, inputIdsForTurn } from '../../packages/dsh-integration/src/input-evidence.js';
import type { SessionEvent } from '@deepseek-ai/dsh-session';

type Row = { type: string; data: unknown };
function history(inputs: number): SessionEvent[] {
  const rows: Row[] = [];
  for (let turn = 0; turn <= inputs; turn++) {
    const message = { id: `input-${turn}`, role: 'user', content: [{ type: 'text', text: 'Synthetic request' }], source: { kind: 'user' } };
    rows.push(
      { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, inserted: [message] } },
      { type: 'turn/start', data: { turn } },
      { type: 'agent/inbox/spliced', data: { target: 'next-turn', start: 0, removedCount: 1, inserted: [] } },
      { type: 'user/message', data: message },
      { type: 'turn/end', data: { turn, reason: { kind: 'completed' } } },
    );
  }
  return rows.map((row, seq) => ({ ...row, seq, time: seq })) as SessionEvent[];
}
function previous(events: readonly SessionEvent[], turn: number): string[] {
  const ids = events.flatMap(event => event.type === 'agent/inbox/spliced' ? event.data.inserted.map(message => message.id) : []);
  return [...new Set(ids.filter(id => inputEvidence(events, id).turn === turn))];
}
function medianMs(fn: () => unknown): number {
  fn();
  const times = Array.from({ length: 7 }, () => {
    const start = performance.now(); fn(); return performance.now() - start;
  });
  return times.sort((a, b) => a - b)[3]!;
}
function visits(fn: (events: readonly SessionEvent[], turn: number) => string[], events: SessionEvent[], turn: number): number {
  let count = 0;
  const measured = new Proxy(events, { get(target, property, receiver) {
    if (typeof property === 'string' && /^\d+$/.test(property)) count++;
    return Reflect.get(target, property, receiver);
  } });
  assert.deepEqual(fn(measured, turn), [`input-${turn}`]);
  return count;
}
for (const inputs of [500, 1000, 2000]) {
  const events = history(inputs);
  assert.deepEqual(inputIdsForTurn(events, inputs), previous(events, inputs));
  const oldMs = medianMs(() => previous(events, inputs));
  const newMs = medianMs(() => inputIdsForTurn(events, inputs));
  const oldVisits = visits(previous, events, inputs);
  const newVisits = visits(inputIdsForTurn, events, inputs);
  assert.ok(newVisits <= oldVisits * 0.05);
  console.log(JSON.stringify({ historicalInputs: inputs, events: events.length, currentInputs: 1, oldVisits, newVisits, oldMedianMs: oldMs, newMedianMs: newMs, speedup: oldMs / newMs, transientIdEntries: 2 * (inputs + 1), peakQueuedIds: 1, persistentIndexEntries: 0, node: process.version }));
}
