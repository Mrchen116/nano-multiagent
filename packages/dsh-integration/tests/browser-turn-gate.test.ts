import { expect, it } from 'vitest';
import { evaluateTurnGate, PRESENCE_WINDOW_MS } from '../src/policy/turn.js';
import { event, humanMessage, systemMessage, turnSession } from './helpers/browser-fakes.js';

const NOW = 1_800_000_000_000;
const openTurn = (turn = 1) => event(1, NOW - 60_000, 'turn/start', { turn });

it('allows a launch when the latest human message is inside the 300s presence window', () => {
  const session = turnSession('s', [openTurn(), humanMessage(2, NOW - 60_000)]);
  expect(evaluateTurnGate(session, () => undefined, NOW)).toMatchObject({ allowed: true, sessionId: 's', deltaMs: 60_000 });
  expect(evaluateTurnGate(session, () => undefined, NOW - 60_000 + PRESENCE_WINDOW_MS)).toMatchObject({ allowed: true });
});

it('rejects a long turn whose latest human message is older than 300s', () => {
  const session = turnSession('s', [openTurn(), humanMessage(2, NOW - 600_000)]);
  expect(evaluateTurnGate(session, () => undefined, NOW)).toEqual({ allowed: false, reason: 'outside_presence_window' });
});

it('rejects a negative delta instead of treating a backwards clock as fresh', () => {
  const session = turnSession('s', [openTurn(), humanMessage(2, NOW + 1_000)]);
  expect(evaluateTurnGate(session, () => undefined, NOW)).toEqual({ allowed: false, reason: 'outside_presence_window' });
});

it('rejects when the last turn is closed, including an earlier still-open turn', () => {
  const closed = turnSession('s', [openTurn(), humanMessage(2, NOW - 10_000), event(3, NOW - 5_000, 'turn/end', { turn: 1, reason: 'completed' })]);
  expect(evaluateTurnGate(closed, () => undefined, NOW)).toEqual({ allowed: false, reason: 'no_open_turn' });
  const earlierOpen = turnSession('s', [
    event(1, NOW - 20_000, 'turn/start', { turn: 1 }), humanMessage(2, NOW - 19_000), event(3, NOW - 18_000, 'turn/end', { turn: 1, reason: 'completed' }),
    event(4, NOW - 10_000, 'turn/start', { turn: 2 }), event(5, NOW - 9_000, 'turn/end', { turn: 2, reason: 'completed' }),
  ]);
  expect(evaluateTurnGate(earlierOpen, () => undefined, NOW)).toEqual({ allowed: false, reason: 'no_open_turn' });
});

it('rejects heartbeat and task-execution turns because those turns have no human message', () => {
  for (const channel of ['heartbeat', 'task-execution', 'task-change']) {
    const session = turnSession('s', [openTurn(), systemMessage(2, NOW - 1_000, channel)]);
    expect(evaluateTurnGate(session, () => undefined, NOW)).toEqual({ allowed: false, reason: 'no_human_message' });
  }
});

it('lets a human message win over a nano-system task input in the same turn', () => {
  const session = turnSession('s', [openTurn(), systemMessage(2, NOW - 2_000, 'task-execution'), humanMessage(3, NOW - 1_000)]);
  expect(evaluateTurnGate(session, () => undefined, NOW)).toMatchObject({ allowed: true, deltaMs: 1_000 });
});

it('denies a subagent whose parent is no longer in the live registry', () => {
  const child = turnSession('child', [openTurn(), humanMessage(2, NOW - 1_000)], { origin: 'subagent', parentSession: 'gone' });
  expect(evaluateTurnGate(child, () => undefined, NOW)).toEqual({ allowed: false, reason: 'lineage_broken' });
});

it('detects self and mutual parent cycles without looping', () => {
  const self = turnSession('a', [openTurn(), humanMessage(2, NOW - 1_000)], { origin: 'subagent', parentSession: 'a' });
  expect(evaluateTurnGate(self, id => id === 'a' ? self : undefined, NOW)).toEqual({ allowed: false, reason: 'lineage_cycle' });
  const a = turnSession('a', [], { origin: 'subagent', parentSession: 'b' });
  const b = turnSession('b', [], { origin: 'subagent', parentSession: 'a' });
  const registry = new Map([['a', a], ['b', b]]);
  expect(evaluateTurnGate(a, id => registry.get(id), NOW)).toEqual({ allowed: false, reason: 'lineage_cycle' });
});

it('ignores the child seed source shape and uses the human ancestor turn', () => {
  const parent = turnSession('parent', [openTurn(), humanMessage(2, NOW - 30_000)]);
  const child = turnSession('child', [openTurn(), event(2, NOW - 1_000, 'user/message', { source: { kind: 'user' } as never })], { origin: 'subagent', parentSession: 'parent' });
  const registry = new Map([['parent', parent], ['child', child]]);
  expect(evaluateTurnGate(child, id => registry.get(id), NOW)).toMatchObject({ allowed: true, sessionId: 'parent', deltaMs: 30_000 });
});

it('uses the latest human message when the user speaks twice in one turn', () => {
  const refreshed = turnSession('s', [openTurn(), humanMessage(2, NOW - 900_000), humanMessage(3, NOW - 10_000)]);
  expect(evaluateTurnGate(refreshed, () => undefined, NOW)).toMatchObject({ allowed: true, deltaMs: 10_000 });
});
