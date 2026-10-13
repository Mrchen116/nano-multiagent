// @vitest-environment jsdom
// Opt-in feasibility probe: published artifacts and public registration API only.
import * as React from 'react';
import * as Jsx from 'react/jsx-runtime';
import * as Dom from 'react-dom';
import * as DomClient from 'react-dom/client';
import * as Cordis from '@deepseek-ai/cordis';
import * as Store from '@deepseek-ai/dsh-client-store';
import * as Slots from '@deepseek-ai/dsh-client-ui-slots';
import * as Primitives from '@deepseek-ai/dsh-client-ui-primitives';
import * as Dockkit from '@deepseek-ai/dsh-client-ui-dockkit';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { expect, it, vi } from 'vitest';

it('probes native trajectory public plugin extension points', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  HTMLElement.prototype.scrollTo = function() {};
  HTMLElement.prototype.scrollIntoView = function() {};
  const modules: Record<string, any> = {
    react: React, 'react/jsx-runtime': Jsx, 'react-dom': Dom, 'react-dom/client': DomClient,
    '@deepseek-ai/cordis': Cordis, '@deepseek-ai/dsh-client-store': Store,
    '@deepseek-ai/dsh-client-ui-slots': Slots, '@deepseek-ai/dsh-client-ui-primitives': Primitives,
    '@deepseek-ai/dsh-client-ui-dockkit': Dockkit,
  };
  const registrations: Record<string, any> = {};
  (window as any).__ModuleLoader__ = { load: (value: any) => { registrations[value.id] = value; } };
  const dist = resolve('packages/dsh-trajectory-viewer/dist');
  const manifest = JSON.parse(readFileSync(resolve(dist, 'manifest.json'), 'utf8'));
  for (const { id } of manifest.modules) new Function(readFileSync(resolve(dist, 'plugins', id, 'client.js'), 'utf8'))();
  const load = (id: string): any => {
    if (modules[id]) return modules[id];
    const key = id.replace(/\/client$/, '');
    if (!registrations[key]) throw new Error(`Missing module ${id}`);
    return modules[id] = registrations[key].factory(load);
  };
  const renderer = load('@deepseek-ai/dsh-client-ui-renderer/client');
  const conversation = load('@deepseek-ai/dsh-client-ui-conversation/client');
  const fork = process.env.NANO_TRAJECTORY_FORK === '1';
  if (fork) new Function(readFileSync(resolve('packages/trajectory-ui/lib/client.js'), 'utf8'))();
  else new Function(readFileSync(createRequire(import.meta.url).resolve('@deepseek-ai/dsh-client-ui-trajectory/client'), 'utf8'))();
  const trajectory = load(fork ? '@nano/trajectory-ui/client' : '@deepseek-ai/dsh-client-ui-trajectory/client');
  const ctx: any = new Cordis.Context();
  const slots = new renderer.SlotRegistry(ctx);
  slots.register({ name: 'root', children: { 'conversation.view': { kind: 'list', scope: 'session' } } }, () => null);
  ctx.provide('uiSession', { provide: () => () => {} });
  const sessions = { binding: () => undefined };
  ctx.provide('sessions', sessions);
  new conversation.UiConversation(ctx, sessions);
  const dictionaries: Record<string, any> = {};
  ctx.provide('locale', { register: (key: string, value: any) => { dictionaries[key] = value.en; return () => {}; }, bind: (key: string) => (name: string) => dictionaries[key]?.[name] ?? name });
  trajectory.apply(ctx);
  await Promise.resolve();
  const entries = slots.entries('conversation.view');
  expect(entries.map((entry: any) => entry.options.id)).toEqual(['trajectory']);
  const entry = entries[0];
  expect(Object.keys(entry.children ?? {})).toEqual(['conversation.trajectory.images']);
  const ImageExtension = () => null;
  slots.register({ name: 'conversation.trajectory.images' }, ImageExtension);
  expect(slots.entries('conversation.trajectory.images')).toHaveLength(1);
  let rowError = '';
  try { slots.register({ name: 'conversation.trajectory.row-actions', id: 'probe' }, () => null); } catch (e: any) { rowError = e.message; }
  expect(rowError).toMatch(/declar/i);

  // The public registry ledger supplies the original shipped component to this
  // test fixture. It is not wrapped/replaced or proposed as a production import.
  const NativeView = entry.component ?? entry.Component;
  expect(NativeView).toBeTypeOf('function');
  const snapshot = { eventNodes: [
    { kind: 'user', seq: 1, time: 1000, content: [{ type: 'text', text: 'Before range' }], source: null },
    { kind: 'tool-result', seq: 2, time: 2000, callId: 'probe-call', call: null, callTime: 1500, name: 'subagent', args: { type: 'complete', value: {} }, content: [{ type: 'text', text: 'Child execution result' }], isError: false, subCalls: [] },
    { kind: 'user', seq: 3, time: 3000, content: [{ type: 'text', text: 'After range' }], source: null },
  ], requests: [], eventLocations: new Map(), callSchemas: new Map(), partial: null, runningCalls: [] };
  const completeViewRequest = vi.fn();
  const props = { useSession: (s: any) => s({ openState: 'open', loadingOlder: false, hasMore: false }),
    useTrajectory: (s: any) => s(snapshot), useDuration: (s: any) => s(false),
    loadOlder: async () => false, loadImage: async () => '', setActualDuration: () => {},
    viewRequest: null, completeViewRequest, renderSlot: () => null,
    t: (key: string) => dictionaries.trajectory?.[key] ?? key };
  const container = document.createElement('div'); document.body.append(container);
  const root = DomClient.createRoot(container);
  const render = async (extra: any) => { await React.act(async () => { root.render(React.createElement(NativeView, { ...props, ...extra })); }); };
  try {
    await render({});
    const rows = () => [...container.querySelectorAll('[data-trajectory-row-key]')].map(row => row.getAttribute('data-trajectory-row-key'));
    const initialRows = rows();
    expect(initialRows.length).toBeGreaterThan(0);
    await render({ range: { start: 1500, end: 2500 }, timelineRange: { start: 1500, end: 2500 }, viewRequest: { view: 'trajectory', focus: 'range:1500:2500' } });
    expect(rows()).toEqual(initialRows);
    expect(completeViewRequest).not.toHaveBeenCalled();
    expect(container.querySelector('[data-timeline-focus]')).toBeNull();
    expect(container.querySelector('[style*="--trajectory-selection-left"]')).toBeNull();
    await render({ viewRequest: { view: 'trajectory', focus: 'probe-call' } });
    expect(completeViewRequest).toHaveBeenCalled();
    const focusSelected = container.querySelector('[data-selected]')?.getAttribute('data-trajectory-row-key');
    const plot = container.querySelector('[aria-label="Timeline overview; drag horizontally to focus events"]') as HTMLElement;
    expect(plot).toBeTruthy();
    plot.getBoundingClientRect = () => ({ x: 0, y: 0, left: 0, top: 0, right: 100, bottom: 72, width: 100, height: 72, toJSON() {} });
    for (const [type, clientX] of [['pointerdown', 55], ['pointermove', 95], ['pointerup', 95]] as const) {
      await React.act(async () => { plot.dispatchEvent(new MouseEvent(type, { bubbles: true, button: 0, clientX })); });
    }
    const manualFocus = [...container.querySelectorAll('[data-timeline-focus]')].map(row => ({ key: row.getAttribute('data-trajectory-row-key'), focus: row.getAttribute('data-timeline-focus') }));
    expect(manualFocus.length).toBeGreaterThan(0);
    expect(container.querySelector('[style*="--trajectory-selection-left"]')).not.toBeNull();
    writeFileSync(fork ? '/tmp/feat589-fork-probe-results.json' : '/tmp/feat589-native-plugin-probe-results.json', JSON.stringify({ version: manifest.rev, exports: Object.keys(trajectory), childSlots: Object.keys(entry.children ?? {}), registrationKeys: Object.keys(entry.options), rowRegistrationError: rowError, imageRegistrationAccepted: true, initialRows, requestedRange: { start: 1500, end: 2500 }, externalRangeProducedSelection: false, callFocusAcknowledgements: completeViewRequest.mock.calls.length, focusSelected, manualRangeFocus: manualFocus, evidenceScope: 'Published bundle mounted in React/JSDOM; not full browser product acceptance' }, null, 2));
    if (fork) {
      vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(800);
      vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(1000);
      const oldRun = {runId:'old-memory',sessionId:'child',parentSessionId:'parent',provider:'fork',kind:'memory',delegation:'background',state:'completed',startSeq:11,endSeq:20,launchSeq:10,startedAt:1000};
      const fullSnapshot = {...snapshot,eventNodes:Array.from({length:100},(_,index)=>({kind:'user',seq:index+1,time:(index+1)*1000,content:[{type:'text',text:`Input ${index+1}`}],source:null}))};
      await render({key:'history-window',sessionId:'parent',useTrajectory:(select:any)=>select(fullSnapshot),navigation:{isActive:()=>true,readRuns:async()=>[oldRun],firstSeq:()=>1,hasMore:()=>false,lastSeq:()=>100,loadThrough:async()=>{},navigate:()=>{}}});
      const launch = () => container.querySelector('[data-trajectory-row-key="run%3Aold-memory"]');
      expect(container.textContent).not.toContain('记忆整理');
      expect(launch()).toBeNull();
      expect(container.textContent).toContain('Input 51');
      const earlier = container.querySelector('[aria-label="Load earlier history"]') as HTMLButtonElement;
      expect(earlier).toBeTruthy();
      await React.act(async()=>earlier.click());
      await React.act(async()=>{const scroll=container.querySelector('[data-trajectory-scroll]') as HTMLElement;scroll.scrollTop=0;scroll.dispatchEvent(new Event('scroll'));});
      expect(launch()).not.toBeNull();
      expect(container.textContent).toContain('Input 10');
      const targetRun = {...oldRun,runId:'fork-range',sessionId:'parent',parentSessionId:'grandparent',startSeq:40,endSeq:60};
      await render({key:'full-fork',sessionId:'parent',useTrajectory:(select:any)=>select(fullSnapshot),navigation:{initialRunId:targetRun.runId,parentSessionId:'grandparent',isActive:()=>true,readRuns:async()=>[targetRun],firstSeq:()=>1,hasMore:()=>false,lastSeq:()=>100,loadThrough:async()=>{},navigate:()=>{}}});
      expect(container.textContent).toContain('Input 1');
      expect(container.querySelector('[data-timeline-focus="outside"]')?.textContent).toContain('Input 1');
      expect(container.querySelector('[style*="--trajectory-selection-left"]')).not.toBeNull();
      expect(container.textContent).not.toContain('查看会话历史');

    }
  } finally {
    await React.act(async () => root.unmount()); container.remove(); await ctx.fiber.dispose(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  }
});
