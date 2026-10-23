import type { Context } from '@deepseek-ai/cordis';
import type { SessionEvent } from '@deepseek-ai/dsh-session';
import { expect, it } from 'vitest';
import { readUsage } from '../src/usage.js';

function turn(number: number) {
  return [
    {type: 'turn/start', data: {turn: number}},
    {type: 'step/start', data: {turn: number, step: 1}},
    {type: 'assistant/message', data: {turn: number, step: 1,
      usage: {inputTokens: 12, outputTokens: 3, totalTokens: 15},
      message: {source: {provider: 'fixture', model: 'fixed'}}}},
    {type: 'step/end', data: {turn: number, step: 1}},
    {type: 'turn/end', data: {turn: number}},
  ];
}

function fixture(children = 0) {
  const records = new Map<string, {events: SessionEvent[]; persisted: SessionEvent[]; inherited: number; live: boolean; parent?: string}>();
  const listeners: ((session: any, event: SessionEvent) => void)[] = [];
  let observations = 0, lists = 0, observedEvents = 0;
  let flush: (() => Promise<boolean>) | undefined;
  let observed: (() => void) | undefined;
  function add(id: string, source = turn(1), inherited = 0, parent?: string) {
    const events = source.map((event, seq) => ({...event, seq, time: 1000 + seq})) as SessionEvent[];
    records.set(id, {events, persisted: [...events], inherited, live: false, parent});
  }
  function session(id: string): any {
    const row = records.get(id)!;
    return {id, header: {parentSession: row.parent}, get seq() {return row.events.length;},
      inheritedEventCount: row.inherited, isOwnSeq: (seq: number) => seq >= row.inherited};
  }
  const live = new Map<string, any>();
  function activate(id: string) {records.get(id)!.live = true; live.set(id, session(id));}
  function append(id: string, source: ReturnType<typeof turn>) {
    const row = records.get(id)!;
    for (const item of source) {
      const event = {...item, seq: row.events.length, time: 1000 + row.events.length} as SessionEvent;
      row.events.push(event);
      for (const listener of listeners) listener(live.get(id) ?? session(id), event);
    }
  }
  add('root');
  for (let i = 0; i < children; i++) add(`child-${i}`, [...turn(1), ...turn(2)], 5, 'root');
  const ctx = {
    on(_name: string, listener: typeof listeners[number]) {listeners.push(listener);},
    subagents: {async listDescendants() {lists++; return [...records.keys()].filter(id => id !== 'root').map(id => ({id, kind: 'child'}));}},
    sessions: {
      get: (id: string) => live.get(id),
      async flush(value: any) {
        const ok = flush ? await flush() : true;
        if (ok) records.get(value.id)!.persisted = [...records.get(value.id)!.events];
        return ok;
      },
    },
    sessionQuery: {async observeSession(id: string) {
      observations++;
      const row = records.get(id)!;
      const events = [...(live.has(id) ? row.events : row.persisted)];
      const source = live.has(id) ? 'live' : 'prepared';
      observed?.();
      return {source, cursor: events.length - 1, inheritedEventCount: row.inherited,
        get events() {observedEvents += events.length; return events;}, [Symbol.dispose]() {}};
    }},
  } as unknown as Context;
  return {ctx, add, append, activate, records, live, counts: () => ({observations, lists, observedEvents}),
    onFlush(fn?: typeof flush) {flush = fn;}, onObserve(fn?: typeof observed) {observed = fn;}};
}

it('rebuilds 400 cold children once, excludes inherited turns, then reads only new usage', async () => {
  const f = fixture(400);
  const cold = await readUsage(f.ctx, 'root');
  expect(cold.reports).toHaveLength(401);
  expect(cold.reports.reduce((sum, r) => sum + r.usage.total_tokens, 0)).toBe(6015);
  const before = f.counts();
  const repeated = await readUsage(f.ctx, 'root', cold.cursor);
  expect(repeated.reports).toEqual([]);
  expect(f.counts()).toEqual(before);
  f.activate('child-210');
  f.append('child-210', turn(3));
  const changed = await readUsage(f.ctx, 'root', repeated.cursor);
  expect(changed.reports).toMatchObject([{sessionId: 'child-210', turn: 3, usage: {total_tokens: 15}}]);
  expect(f.counts()).toEqual(before);
  // A lost response retries the same cursor without consuming its facts.
  expect(await readUsage(f.ctx, 'root', repeated.cursor)).toEqual(changed);
});

it('keeps initialization and flush-time events, including concurrently finishing roots and children', async () => {
  const f = fixture(1);
  f.activate('root'); f.activate('child-0');
  let injected = false;
  f.onObserve(() => {if (!injected) {injected = true; f.append('root', turn(2)); f.append('child-0', turn(3));}});
  const first = await readUsage(f.ctx, 'root');
  f.onObserve();
  const second = await readUsage(f.ctx, 'root', first.cursor);
  expect([...first.reports, ...second.reports].map(r => `${r.sessionId}:${r.turn}`).sort())
    .toEqual(['child-0:2', 'child-0:3', 'root:1', 'root:2']);
  f.append('root', turn(3));
  let duringFlush = false;
  f.onFlush(async () => {if (!duringFlush) {duringFlush = true; f.append('child-0', turn(4));} return true;});
  const a = await readUsage(f.ctx, 'root', second.cursor);
  const b = await readUsage(f.ctx, 'root', a.cursor);
  expect([...a.reports, ...b.reports].map(r => `${r.sessionId}:${r.turn}`).sort()).toEqual(['child-0:4', 'root:3']);
});

it('discovers newly created descendants without rescanning cold siblings', async () => {
  const f = fixture(400);
  const first = await readUsage(f.ctx, 'root');
  f.activate('root');
  f.add('new-child', [...turn(1), ...turn(2)], 5, 'root');
  f.activate('new-child');
  f.append('root', [{type: 'subagent/catalog', data: {childId: 'new-child', version: 0, mode: 'one-shot'}}] as any);
  f.append('new-child', turn(3));
  const before = f.counts();
  const next = await readUsage(f.ctx, 'root', first.cursor);
  expect(next.reports.map(r => `${r.sessionId}:${r.turn}`)).toEqual(['new-child:2', 'new-child:3']);
  expect(f.counts().lists).toBe(before.lists);
  expect(f.counts().observations - before.observations).toBe(1);
});

it('requires persistence before publishing and recovers an initialized child that has unloaded', async () => {
  const f = fixture(1);
  f.activate('child-0');
  const first = await readUsage(f.ctx, 'root');
  f.append('child-0', turn(3));
  f.onFlush(async () => false);
  await expect(readUsage(f.ctx, 'root', first.cursor)).rejects.toThrow(/persistence/i);
  f.onFlush();
  f.records.get('child-0')!.persisted = [...f.records.get('child-0')!.events];
  f.live.delete('child-0');
  const next = await readUsage(f.ctx, 'root', first.cursor);
  expect(next.reports).toMatchObject([{sessionId: 'child-0', turn: 3}]);
  f.activate('child-0'); f.append('child-0', turn(4));
  f.live.delete('child-0'); // Simulate best-effort final flush failure.
  await expect(readUsage(f.ctx, 'root', next.cursor)).rejects.toThrow(/persist/i);
  f.records.get('child-0')!.persisted = [...f.records.get('child-0')!.events];
  expect((await readUsage(f.ctx, 'root', next.cursor)).reports).toMatchObject([{sessionId: 'child-0', turn: 4}]);
});

it('invalidates runtime cursors on restart and replays stable run identities', async () => {
  const first = await readUsage(fixture(2).ctx, 'root');
  const restarted = await readUsage(fixture(2).ctx, 'root', first.cursor);
  expect(restarted.cursor).not.toBe(first.cursor);
  expect(restarted.reports).toEqual(first.reports);
});

it('retries unavailable catalog branches without rebuilding already recovered history', async () => {
  const f = fixture(1);
  const list = f.ctx.subagents.listDescendants.bind(f.ctx.subagents);
  let unavailable = true;
  f.ctx.subagents.listDescendants = async (...args) => unavailable
    ? [{kind:'diagnostic',id:'child-0',parentId:'root',depth:1,reason:'unavailable'}] as any
    : list(...args);
  const partial = await readUsage(f.ctx, 'root');
  expect(partial.reports.map(r=>r.sessionId)).toEqual(['root']);
  unavailable = false;
  const recovered = await readUsage(f.ctx, 'root', partial.cursor);
  expect(recovered.reports.map(r=>r.sessionId)).toEqual(['child-0']);
  const before = f.counts();
  expect((await readUsage(f.ctx, 'root', recovered.cursor)).reports).toEqual([]);
  expect(f.counts()).toEqual(before);
});
