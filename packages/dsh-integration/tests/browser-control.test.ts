import { access, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it } from 'vitest';
import { BrowserControl } from '../src/browser/control.js';
import { browserError, type BrowserError } from '../src/browser/errors.js';
import { BrowserFixtureDriver, event, fakeAgent, humanMessage } from './helpers/browser-fakes.js';
import { liveTurnSession } from '../src/policy/turn.js';

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

it('blocks every call during the release cooldown and recovers after it expires lazily', async () => {
  let now = NOW;
  const driver = new BrowserFixtureDriver({
    url: 'https://example.com', title: 'Example',
    popup: { windowId: '20', url: 'https://popup.example', title: 'Popup' }, popupKind: 'real',
    endSessionError: new Error('cannot close'),
  });
  const control = controlFor(driver, () => now);
  const events = [event(1, NOW - 1_000, 'turn/start', { turn: 1 }), humanMessage(2, NOW - 500)];
  const agent = fakeAgent('agent-a', events);

  const read = await control.read(agent, undefined, {});
  const release = await failure(control.act(agent, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' }));
  expect(release.browserCode).toBe('browser_foreground_release_failed');
  expect(driver.count('end_session')).toBe(2);

  const calls = driver.calls.length;
  now += 299_000;
  const cooling = await failure(control.act(agent, undefined, { action: 'open', url: 'https://example.com' }));
  expect(cooling.browserCode).toBe('browser_foreground_release_failed');
  expect(driver.calls.length).toBe(calls);

  now += 2_000;
  // The cooldown and the presence window are both 300s. A fresh user message is
  // what makes the post-cooldown retry eligible again. The real popup was
  // closed by hand in the meantime, leaving only the original window.
  events.push(humanMessage(3, now));
  driver.state.windows = driver.state.windows.filter(window => window.window_id === '10');
  const recovered = await control.act(agent, undefined, { action: 'open', url: 'https://example.com' });
  expect(recovered.action).toBe('open');
  expect(driver.count('browser_prepare')).toBe(2);
});

it('caps the process at two instances and reports browser_busy for a third Agent', async () => {
  const driver = new BrowserFixtureDriver();
  driver.delayMs = 2;
  const control = controlFor(driver, () => NOW, 2);

  const results = await Promise.allSettled([
    control.read(openAgent('agent-a'), undefined, {}),
    control.read(openAgent('agent-b'), undefined, {}),
    control.read(openAgent('agent-c'), undefined, {}),
  ]);

  expect(results.filter(result => result.status === 'fulfilled')).toHaveLength(2);
  const rejected = results.find(result => result.status === 'rejected');
  expect(rejected).toMatchObject({ status: 'rejected', reason: { browserCode: 'browser_busy' } });
  expect(driver.probeCalls).toBe(2);
});

it('serializes concurrent calls for one Agent to a single in-flight driver call', async () => {
  const driver = new BrowserFixtureDriver();
  driver.delayMs = 3;
  const control = controlFor(driver);
  const agent = openAgent('agent-a');

  const [first, second] = await Promise.all([
    control.read(agent, undefined, {}),
    control.read(agent, undefined, {}),
  ]);

  expect(first.read_id).toBe('r1');
  expect(second.read_id).toBe('r2');
  expect(driver.maxInFlight).toBe(1);
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
