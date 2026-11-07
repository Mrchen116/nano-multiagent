import { access, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { BrowserControl } from '../src/browser/control.js';
import { browserError, type BrowserError } from '../src/browser/errors.js';
import { BrowserFixtureDriver, event, fakeAgent, humanMessage } from './helpers/browser-fakes.js';
import { liveTurnSession } from '../src/policy/turn.js';
import { ApprovalSources } from '../src/policy/sources.js';

const NOW = 1_000_000;
const workspaces: string[] = [];

afterEach(async () => {
  await Promise.all(workspaces.splice(0).map(path => rm(path, { recursive: true, force: true })));
});

async function workspace(): Promise<string> {
  const path = await mkdtemp(join(tmpdir(), 'nano-browser-control-'));
  workspaces.push(path);
  return path;
}

function openAgent(id: string) {
  return fakeAgent(id, [
    event(1, NOW - 1_000, 'turn/start', { turn: 1 }),
    humanMessage(2, NOW - 500),
  ]);
}

function controlFor(driver: BrowserFixtureDriver, now = () => NOW, maxInstances?: number) {
  return new BrowserControl({ driver, lookup: () => undefined, now, ...(maxInstances ? { maxInstances } : {}) });
}

async function failure(promise: Promise<unknown>): Promise<BrowserError> {
  try {
    await promise;
  } catch (error) {
    return error as BrowserError;
  }
  throw new Error('expected the operation to fail');
}

function png(width: number, height: number): string {
  const buffer = Buffer.alloc(24);
  buffer.write('PNG', 1, 'ascii');
  buffer.write('IHDR', 12, 'ascii');
  buffer.writeUInt32BE(width, 16);
  buffer.writeUInt32BE(height, 20);
  return buffer.toString('base64');
}

it('registers an about:blank instance and never leaks driver identity', async () => {
  const driver = new BrowserFixtureDriver();
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const result = await control.read(agent, undefined, {});

  expect(result.read_id).toBe('r1');
  expect(result.tab).toEqual({ url: 'about:blank', title: 'about:blank', active: true, window_id: '10' });
  expect(result.text).toBe('Hello page');
  expect(result.refs).toEqual([{ ref: 'p1:0', role: 'button', name: 'Increment', actions: ['click', 'pointer'] }]);
  expect(JSON.stringify(result)).not.toContain('tab-');
  expect(JSON.stringify(result)).not.toContain('bt-');
  expect(driver.count('browser_prepare')).toBe(1);
});

it('resolves a subagent launch through the live parent turn and denies a broken lineage', async () => {
  const driver = new BrowserFixtureDriver();
  const parent = openAgent('parent');
  const child = fakeAgent('child', [event(1, NOW - 500, 'turn/start', { turn: 1 })], { origin: 'subagent', parentSession: 'parent' });
  const control = new BrowserControl({
    driver,
    lookup: id => id === 'parent' ? liveTurnSession(parent) : undefined,
    now: () => NOW,
  });

  await expect(control.read(child, undefined, {})).resolves.toMatchObject({ read_id: 'r1' });

  const orphan = fakeAgent('orphan', [event(1, NOW - 500, 'turn/start', { turn: 1 })], { origin: 'subagent', parentSession: 'gone' });
  const error = await failure(control.read(orphan, undefined, {}));
  expect(error.browserCode).toBe('browser_launch_requires_user_turn');
  expect(driver.count('browser_prepare')).toBe(1);
});

it.each([
  ['native', false], ['native', true], ['ptc', false], ['ptc', true],
] as const)('connects live %s Inbox presence to a browser launch (child=%s) without treating a wake as human', async (transport, child) => {
  const events = [
    event(1, NOW - 1_000, 'turn/start', { turn: 1 }),
    event(2, NOW - 500, 'user/message', { source: { kind: 'nano-system', channel: 'inbox' } }),
  ];
  const parent = fakeAgent('parent', events);
  const request = child
    ? fakeAgent('child', [event(1, NOW - 500, 'turn/start', { turn: 1 })], { origin: 'subagent', parentSession: 'parent' })
    : parent;
  const sources = new ApprovalSources();
  const driver = new BrowserFixtureDriver();
  const control = new BrowserControl({
    driver, now: () => NOW,
    lookup: id => id === parent.id ? liveTurnSession(parent) : undefined,
    liveHumanTimes: (id, seq) => id === parent.id ? sources.liveHumanTimes(parent, seq) : [],
  });
  expect((await failure(control.read(request, undefined, {}))).browserCode).toBe('browser_launch_requires_user_turn');
  expect(driver.count('browser_prepare')).toBe(0);
  const content = [{ type: 'text', text: JSON.stringify({ delivery: 'participant', messages: [{
    sender: { type: 'user' }, created_at: new Date(NOW - 500).toISOString(),
  }] }) }];
  sources.recordInbox(parent.id, 'inbox-call');
  events.push(transport === 'native'
    ? event(3, NOW, 'tool/result', { message: { toolCallId: 'inbox-call', content } })
    : event(3, NOW, 'tool/ptc-dispatch', { name: 'inbox', subCallId: 'inbox-call', content }));
  await expect(control.read(request, undefined, {})).resolves.toMatchObject({ read_id: 'r1' });
  expect(driver.count('browser_prepare')).toBe(1);
});

it('rejects a read_id after a newer read and keeps the driver action unexecuted', async () => {
  const driver = new BrowserFixtureDriver();
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const first = await control.read(agent, undefined, {});
  const second = await control.read(agent, undefined, {});
  expect(second.read_id).toBe('r2');
  const clicks = driver.count('browser_click');

  const error = await failure(control.act(agent, undefined, { action: 'click', read_id: first.read_id, ref: 'p1:0' }));
  expect(error.browserCode).toBe('browser_snapshot_stale');
  expect(driver.count('browser_click')).toBe(clicks);
});

it('rejects an action when the bound page URL drifted since the read', async () => {
  const driver = new BrowserFixtureDriver();
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const read = await control.read(agent, undefined, {});
  driver.state.binds.set('10', { url: 'https://drifted.example', title: 'Drifted', active: true, http: true });

  const error = await failure(control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' }));
  expect(error.browserCode).toBe('browser_snapshot_stale');
  expect(driver.count('browser_click')).toBe(0);
});

it('refuses a tab matcher that matches more than one tab', async () => {
  const driver = new BrowserFixtureDriver({ tabs: [
    { url: 'https://dup.example', title: 'Same', active: true },
    { url: 'https://dup.example', title: 'Same', active: false },
  ] });
  const control = controlFor(driver);

  const error = await failure(control.read(openAgent('agent-a'), undefined, { tab: { url: 'https://dup.example' } }));
  expect(error.browserCode).toBe('browser_tab_ambiguous');
  expect(driver.count('get_browser_state')).toBeGreaterThan(0);
});

it('fails loudly when more than one window binds exactly', async () => {
  const driver = new BrowserFixtureDriver({ windows: [
    { window_id: '10', title: 'about:blank', width: 1200, height: 800 },
    { window_id: '11', title: 'about:blank', width: 1200, height: 800 },
  ] });
  const control = controlFor(driver);

  const error = await failure(control.read(openAgent('agent-a'), undefined, {}));
  expect(error.browserCode).toBe('browser_window_ambiguous');
  expect(driver.count('end_session')).toBe(1);
});

it('reports a lost session when no window binds exactly and ends the instance', async () => {
  const driver = new BrowserFixtureDriver({ bindingQuality: 'approximate' });
  const control = controlFor(driver);

  const error = await failure(control.read(openAgent('agent-a'), undefined, {}));
  expect(error.browserCode).toBe('browser_session_lost');
  expect(driver.count('end_session')).toBe(1);
});

it('dispatches click through the latest bind and reports a changed effect without returning read_id', async () => {
  const driver = new BrowserFixtureDriver({ url: 'https://example.com', title: 'Example', textOnClick: 'After click' });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const read = await control.read(agent, undefined, {});
  const result = await control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' });

  expect(result).toMatchObject({ action: 'click', dispatched: true, effect: 'changed', text_after: 'After click', observed: { url: 'https://example.com', title: 'Example', active: true } });
  expect('read_id' in result).toBe(false);
  const click = driver.calls.find(call => call.tool === 'browser_click');
  expect(click?.args).toMatchObject({ ref: 'p1:0', delivery_mode: 'background' });
  expect(String(click?.args.target_id)).toMatch(/^bt-10-/);
  expect(JSON.stringify(result)).not.toContain('bt-');
});

it('opens an http(s) page and binds again for the readback URL', async () => {
  const driver = new BrowserFixtureDriver();
  const control = controlFor(driver);

  const result = await control.act(openAgent('agent-a'), undefined, { action: 'open', url: 'https://opened.example' });
  expect(result).toMatchObject({ action: 'open', dispatched: true, effect: 'changed', observed: { url: 'https://opened.example', active: true } });
  expect(driver.count('browser_navigate')).toBe(1);
});

it('reports unchanged when the readback matches the read text', async () => {
  const driver = new BrowserFixtureDriver({ url: 'https://example.com', title: 'Example' });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const read = await control.read(agent, undefined, {});
  const result = await control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' });
  expect(result.effect).toBe('unchanged');
});

it('requests a screenshot for scroll by default and saves it in the Agent workspace', async () => {
  const driver = new BrowserFixtureDriver({ url: 'https://example.com', title: 'Example', screenshot: png(2400, 1464) });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');
  const root = await workspace();

  const read = await control.read(agent, root, {});
  const result = await control.act(agent, root, { action: 'scroll', read_id: read.read_id, ref: 'p1:0', delta_y: -300 });

  expect(result.screenshot).toEqual({ path: expect.stringMatching(/^\.nanoassistant\/browser\/agent-a\/screen-.+\.png$/), width: 2400, height: 1464 });
  expect(driver.calls.some(call => call.tool === 'get_browser_state' && call.args.include_screenshot === true)).toBe(true);
  await expect(access(join(root, result.screenshot!.path))).resolves.toBeUndefined();
  expect(driver.calls.find(call => call.tool === 'browser_pointer')?.args).toMatchObject({ action: 'scroll', ref: 'p1:0', delta_y: -300 });
});

it('maps a driver action_unavailable refusal to guidance that names refs[].actions', async () => {
  const driver = new BrowserFixtureDriver({ url: 'https://example.com', title: 'Example' });
  driver.state.actionError = browserError('browser_driver_refused', 'refused', { refusalCode: 'browser_action_unavailable' });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const read = await control.read(agent, undefined, {});
  const error = await failure(control.act(agent, undefined, { action: 'scroll', read_id: read.read_id, ref: 'p1:0', delta_y: 100 }));
  expect(error.browserCode).toBe('browser_driver_refused');
  expect(error.message).toContain('换一个声明了 pointer 的 ref');
});

it('releases a real new window and reports the event', async () => {
  const driver = new BrowserFixtureDriver({
    url: 'https://example.com', title: 'Example',
    popup: { windowId: '20', url: 'https://popup.example', title: 'Popup' }, popupKind: 'real',
  });
  const control = controlFor(driver);
  const events = [event(1, NOW - 1_000, 'turn/start', { turn: 1 }), humanMessage(2, NOW - 500)];
  const agent = fakeAgent('agent-a', events);

  const read = await control.read(agent, undefined, {});
  const result = await control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' });

  expect(result.foreground_released).toBe(true);
  expect(result.events).toEqual([{ kind: 'window', window_id: '20', title: 'Popup', width: 520, height: 426, url: 'https://popup.example' }]);
  expect(driver.count('end_session')).toBe(1);

  const sameTurn = await failure(control.read(agent, undefined, {}));
  expect(sameTurn.browserCode).toBe('browser_launch_requires_user_turn');
  expect(driver.count('browser_prepare')).toBe(1);

  driver.state.windows = driver.state.windows.filter(window => window.window_id === '10');
  events.push(event(3, NOW, 'turn/end', { turn: 1, reason: 'completed' }), event(4, NOW, 'turn/start', { turn: 2 }), humanMessage(5, NOW));
  await expect(control.read(agent, undefined, {})).resolves.toMatchObject({ read_id: 'r1' });
  expect(driver.count('browser_prepare')).toBe(2);
});

it('ignores a Chrome noise window without releasing the instance', async () => {
  const driver = new BrowserFixtureDriver({
    url: 'https://example.com', title: 'Example',
    popup: { windowId: '20', url: '', title: '翻译此页？' }, popupKind: 'noise',
  });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const read = await control.read(agent, undefined, {});
  const result = await control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' });

  expect(result.ignored).toEqual([{ width: 284, height: 87, title: '翻译此页？' }]);
  expect(result.foreground_released).toBeUndefined();
  expect(driver.count('end_session')).toBe(0);
  await expect(control.read(agent, undefined, {})).resolves.toMatchObject({ read_id: 'r2' });
  expect(driver.count('browser_prepare')).toBe(1);
});

it('fails with browser_unexpected_event on a window it cannot classify', async () => {
  const driver = new BrowserFixtureDriver({
    url: 'https://example.com', title: 'Example',
    popup: { windowId: '20', url: 'about:blank', title: '' }, popupKind: 'unclassified',
  });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const read = await control.read(agent, undefined, {});
  const error = await failure(control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' }));
  expect(error.browserCode).toBe('browser_unexpected_event');
  expect(driver.count('end_session')).toBe(0);
});




it.each(['https://popup.example', 'about:blank'])('never adopts a surviving %s popup after primary bind loss', async url => {
  const driver = new BrowserFixtureDriver();
  const control = controlFor(driver);
  const agent = openAgent('agent-a');
  const read = await control.read(agent, undefined, {});
  driver.state.windows = [{ window_id: '20', title: 'Popup', width: 520, height: 426 }];
  driver.state.binds.set('20', { url, title: 'Popup', active: true, http: url.startsWith('https:') });
  const original = driver.call.bind(driver);
  vi.spyOn(driver, 'call').mockImplementation((tool, args, options) => {
    if (tool === 'get_browser_state' && args.window_id === '10') return Promise.reject(browserError('browser_driver_refused', 'primary lost'));
    return original(tool, args, options);
  });
  const error = await failure(control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' }));
  expect(error.browserCode).toBe('browser_session_lost');
  expect(driver.count('browser_click')).toBe(0);
  expect(driver.count('end_session')).toBe(1);
});

it('does not swallow a failed window listing as an event-free success', async () => {
  const driver = new BrowserFixtureDriver();
  const control = controlFor(driver);
  const agent = openAgent('agent-a');
  await control.read(agent, undefined, {});
  const original = driver.call.bind(driver);
  vi.spyOn(driver, 'call').mockImplementation((tool, args, options) => tool === 'list_windows'
    ? Promise.reject(browserError('browser_driver_timeout', 'listing failed')) : original(tool, args, options));
  expect((await failure(control.read(agent, undefined, {}))).browserCode).toBe('browser_driver_timeout');
});


it('releases proven real windows before returning mixed unclassified evidence', async () => {
  const driver = new BrowserFixtureDriver({ popup: { windowId: '20', url: 'https://popup.example', title: 'Popup' }, popupKind: 'real' });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');
  const read = await control.read(agent, undefined, {});
  const original = driver.call.bind(driver);
  vi.spyOn(driver, 'call').mockImplementation(async (tool, args, options) => {
    const result = await original(tool, args, options);
    if (tool === 'browser_click') {
      driver.state.windows.push({ window_id: '30', title: 'Unknown', width: 700, height: 700 });
      driver.state.binds.set('30', { url: 'about:blank', title: 'Unknown', active: true, http: false });
    }
    return result;
  });
  const error = await failure(control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' }));
  expect(error.browserCode).toBe('browser_unexpected_event');
  expect(error.details).toMatchObject({ foreground_released: true, events: [expect.objectContaining({ window_id: '20' })] });
  // Native toolErrorResult transports the message, not arbitrary Error fields.
  expect(error.message).toContain('"foreground_released":true');
  expect(error.message).toContain('"window_id":"30"');
  expect(driver.count('end_session')).toBe(1);
});


it('uses the configured product Agent screenshot group rather than the native session id', async () => {
  const driver = new BrowserFixtureDriver({ screenshot: png(800, 600) });
  const control = controlFor(driver);
  const root = await workspace();
  const read = await control.read(openAgent('native-session'), root, { screenshot: true }, 'product-agent');
  expect(read.screenshot?.path).toMatch(/^\.nanoassistant\/browser\/product-agent\//);
  await expect(access(join(root, read.screenshot!.path))).resolves.toBeUndefined();
  expect(read.notice).toContain('首次接入可能短暂占前台');
});

it('ends the driver session on dispose but keeps screenshots readable', async () => {
  const driver = new BrowserFixtureDriver({ screenshot: png(800, 600) });
  const control = controlFor(driver);
  const agent = openAgent('agent-a');
  const root = await workspace();

  const read = await control.read(agent, root, { screenshot: true });
  await expect(access(join(root, read.screenshot!.path))).resolves.toBeUndefined();
  await control.dispose(agent.id);

  expect(driver.count('end_session')).toBe(1);
  await expect(access(join(root, read.screenshot!.path))).resolves.toBeUndefined();
});
