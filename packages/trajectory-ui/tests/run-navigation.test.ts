// @vitest-environment jsdom
import * as React from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { useRunNavigation } from '../src/client/use-run-navigation';

const disposals: (() => void)[] = [];
afterEach(() => { for (const dispose of disposals.splice(0)) dispose(); vi.unstubAllGlobals(); });

async function viewFixture(softFailure = false) {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  function View(props: any) {
    const state = useRunNavigation(props, props.sessionId, true);
    return React.createElement('div', {},
      state.loadError && React.createElement('div', {role:'alert'}, state.loadError, React.createElement('button', {'data-retry-range':'', onClick:state.retry}, 'retry')),
      state.blocked ? 'Loading' : props.useTrajectory((s:any)=>s.eventNodes[0]?.content[0]?.text));
  }
  const run = { runId: 'older-epoch', sessionId: 'child', parentSessionId: 'parent', provider: 'fork', kind: 'tool', delegation: 'foreground', state: 'completed', startSeq: 40, endSeq: 60, startedAt: 4000, endedAt: 6000 };
  const empty = { eventNodes: [], requests: [], runningCalls: [], partial: null, eventLocations: new Map(), callSchemas: new Map() };
  const oldWindow = { ...empty, eventNodes: [{ kind: 'user', seq: 40, time: 4000, content: [{ type: 'text', text: 'Older execution input' }] }] };
  let first = 20, snapshot = empty;
  let hasMore = true;
  const container = document.createElement('div'); document.body.append(container);
  const root = createRoot(container);
  disposals.push(() => { React.act(() => root.unmount()); container.remove(); });
  let render: () => void;
  const loadThrough = vi.fn(async () => { if (softFailure) return; first = 1; hasMore = false; snapshot = oldWindow; render(); });
  const props = { sessionId: 'child', initialRunId: run.runId, parentSessionId: 'parent',
    useTrajectory: (select: Function) => select(snapshot),
    useSession: (select: Function) => select({ hasMore: true, openState: 'open', loadingOlder: false }),
    readRuns: async () => [run], firstSeq: () => first, hasMore: () => hasMore, loadThrough,
    loadOlder: vi.fn(), isActive: () => true, loadImage: vi.fn(), navigate: vi.fn(), openNative: vi.fn(), publishPosition: vi.fn(),
  };
  render = () => root.render(React.createElement(View!, props));
  await React.act(async () => { render(); });
  return { container, loadThrough, resync: async () => {
    first = 20; hasMore = true; snapshot = empty;
    await React.act(async () => { render(); });
  }, recover: async () => { softFailure = false; await React.act(async () => { (container.querySelector('[data-retry-range]') as HTMLButtonElement)?.click(); }); } };
}

it('reloads an older execution after the official same-session window is replaced', async () => {
  const f = await viewFixture();
  expect(f.loadThrough).toHaveBeenCalledWith(0);
  expect(f.loadThrough).toHaveBeenCalledTimes(1);
  expect(f.container.textContent).toContain('Older execution input');
  await f.resync();
  expect(f.loadThrough).toHaveBeenCalledTimes(2);
  expect(f.container.textContent).toContain('Older execution input');
});

it('makes a soft paging failure explicit and lets the reader retry the original range', async () => {
  const f = await viewFixture(true);
  expect(f.container.querySelector('[role=alert]')?.textContent).toContain('尚未完整加载会话历史');
  expect(f.loadThrough).toHaveBeenCalledTimes(1);
  await f.recover();
  expect(f.loadThrough).toHaveBeenCalledTimes(2);
  expect(f.container.textContent).toContain('Older execution input');
  expect(f.container.querySelector('[data-retry-range]')).toBeNull();
});
