import { expect, it, vi } from 'vitest';
import { BrowserControl } from '../src/browser/control.js';
import type { BrowserError } from '../src/browser/errors.js';
import { liveTurnSession } from '../src/policy/turn.js';
import { BrowserFixtureDriver, event, fakeAgent, humanMessage } from './helpers/browser-fakes.js';

const NOW = 1_000_000;

function holdProbe(driver: BrowserFixtureDriver) {
  const entered = Promise.withResolvers<void>();
  const resumed = Promise.withResolvers<{ version: string }>();
  vi.spyOn(driver, 'probe').mockImplementationOnce(() => {
    entered.resolve();
    return resumed.promise;
  });
  return { entered: entered.promise, resume: () => resumed.resolve({ version: driver.version }) };
}

it.each(['expired', 'closed', 'replaced'] as const)('rejects a launch whose ancestor turn becomes %s while probing', async change => {
  let now = NOW;
  const driver = new BrowserFixtureDriver();
  const events = [event(1, NOW - 1_000, 'turn/start', { turn: 1 }), humanMessage(2, NOW - 500)];
  const root = fakeAgent('root', events);
  const child = fakeAgent('child', [], { origin: 'subagent', parentSession: 'root' });
  const control = new BrowserControl({ driver, lookup: id => id === root.id ? liveTurnSession(root) : undefined, now: () => now, maxInstances: 1 });
  const probe = holdProbe(driver);
  const outcome = control.read(child, undefined, {}).then(value => ({ value }), error => ({ error }));
  await probe.entered;
  if (change === 'expired') now += 301_000;
  else events.push(event(3, NOW, 'turn/end', { turn: 1 }));
  if (change === 'replaced') events.push(event(4, NOW, 'turn/start', { turn: 2 }), humanMessage(5, NOW));
  probe.resume();

  expect(await outcome).toMatchObject({ error: { browserCode: 'browser_launch_requires_user_turn' } });
  expect(driver.calls).toEqual([]);
  // A denied late launch releases its slot without ending an unprepared label.
  const fresh = fakeAgent('fresh', [event(1, now, 'turn/start', { turn: 1 }), humanMessage(2, now)]);
  await expect(control.read(fresh, undefined, {})).resolves.toMatchObject({ read_id: 'r1' });
  expect(driver.count('browser_prepare')).toBe(1);
});

it('does not prepare after a sibling consumes the ancestor turn while probing', async () => {
  const driver = new BrowserFixtureDriver({ popup: { windowId: '20', url: 'https://popup.example', title: 'Popup' }, popupKind: 'real' });
  const root = openAgent('root');
  const child = fakeAgent('child', [], { origin: 'subagent', parentSession: 'root' });
  const sibling = fakeAgent('sibling', [], { origin: 'subagent', parentSession: 'root' });
  const control = new BrowserControl({ driver, lookup: id => id === root.id ? liveTurnSession(root) : undefined, now: () => NOW });
  const read = await control.read(child, undefined, {});
  const probe = holdProbe(driver);
  const outcome = control.read(sibling, undefined, {}).then(value => ({ value }), error => ({ error }));
  await probe.entered;
  await control.act(child, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' });
  const callsAfterRelease = driver.calls.length;
  probe.resume();

  expect(await outcome).toMatchObject({ error: { browserCode: 'browser_launch_requires_user_turn' } });
  expect(driver.calls).toHaveLength(callsAfterRelease);
  expect(driver.count('browser_prepare')).toBe(1);
});

function openAgent(id: string) {
  return fakeAgent(id, [event(1, NOW - 1_000, 'turn/start', { turn: 1 }), humanMessage(2, NOW - 500)]);
}

function controlFor(driver: BrowserFixtureDriver, now = () => NOW, maxInstances?: number) {
  return new BrowserControl({ driver, lookup: () => undefined, now, ...(maxInstances ? { maxInstances } : {}) });
}

async function failure(promise: Promise<unknown>): Promise<BrowserError> {
  try { await promise; } catch (error) { return error as BrowserError; }
  throw new Error('expected the operation to fail');
}

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

it.each(['registration', 'prepare-timeout', 'prepare-malformed'] as const)('retains failed %s cleanup in the cap and blocks retries until lazy expiry', async stage => {
  let now = NOW;
  const driver = new BrowserFixtureDriver();
  const original = driver.call.bind(driver);
  vi.spyOn(driver, 'call').mockImplementation(async (tool, args, options) => {
    if (tool === 'browser_prepare' && stage === 'prepare-malformed') {
      driver.calls.push({ tool, args, options });
      return {};
    }
    if (tool === 'list_windows' || tool === 'end_session' || tool === 'browser_prepare' && stage === 'prepare-timeout') {
      driver.calls.push({ tool, args, options });
      throw new Error(`${tool} timed out`);
    }
    return original(tool, args, options);
  });
  const control = controlFor(driver, () => now, 2);
  const agent = openAgent('agent-a');
  const failed = await failure(control.read(agent, undefined, {}));
  expect(failed.browserCode).toBe('browser_foreground_release_failed');
  expect(failed.message).toContain('手动关闭');
  expect(driver.count('end_session')).toBe(2);
  expect(new Set(driver.calls.map(call => call.args.session).filter(Boolean)).size).toBe(1);
  const calls = driver.calls.length;
  expect(control.precheck(agent, 'browser_read', {})?.browserCode).toBe('browser_foreground_release_failed');
  expect((await failure(control.read(agent, undefined, {}))).browserCode).toBe('browser_foreground_release_failed');
  expect(driver.calls).toHaveLength(calls);

  await failure(control.read(openAgent('agent-b'), undefined, {}));
  expect((await failure(control.read(openAgent('agent-c'), undefined, {}))).browserCode).toBe('browser_busy');
  expect(driver.count('browser_prepare')).toBe(2);
  await control.dispose(agent.id);
  expect((await failure(control.read(openAgent('agent-d'), undefined, {}))).browserCode).toBe('browser_busy');
  expect(driver.count('browser_prepare')).toBe(2);

  now += 301_000;
  // The driver idle-expiry fallback, not a process liveness probe, bounds the
  // retained reservation. A fresh eligible turn may use the slot after expiry.
  await failure(control.read(fakeAgent('fresh', [event(1, now, 'turn/start', { turn: 1 }), humanMessage(2, now)]), undefined, {}));
  expect(driver.count('browser_prepare')).toBe(3);
});

it('preserves registration errors only when cleanup succeeds within one retry', async () => {
  const driver = new BrowserFixtureDriver();
  const original = driver.call.bind(driver);
  let cleanupAttempts = 0;
  vi.spyOn(driver, 'call').mockImplementation(async (tool, args, options) => {
    if (tool === 'list_windows' || tool === 'end_session' && cleanupAttempts++ === 0) {
      driver.calls.push({ tool, args, options });
      throw new Error(`${tool} timed out`);
    }
    return original(tool, args, options);
  });
  const control = controlFor(driver, () => NOW, 1);
  await expect(control.read(openAgent('agent-a'), undefined, {})).rejects.toThrow('list_windows timed out');
  expect(driver.count('end_session')).toBe(2);
  await expect(control.read(openAgent('agent-b'), undefined, {})).rejects.toThrow('list_windows timed out');
  expect(driver.count('browser_prepare')).toBe(2);
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

it('consumes the captured ancestor turn across root and sibling after asynchronous release', async () => {
  let now = NOW;
  const driver = new BrowserFixtureDriver({ popup: { windowId: '20', url: 'https://popup.example', title: 'Popup' }, popupKind: 'real' });
  const events = [event(1, NOW - 1_000, 'turn/start', { turn: 1 }), humanMessage(2, NOW - 500)];
  const root = fakeAgent('root', events);
  const child = fakeAgent('child', [], { origin: 'subagent', parentSession: 'root' });
  const sibling = fakeAgent('sibling', [], { origin: 'subagent', parentSession: 'root' });
  const control = new BrowserControl({ driver, lookup: id => id === 'root' ? liveTurnSession(root) : undefined, now: () => now });
  const read = await control.read(child, undefined, {});
  const original = driver.call.bind(driver);
  vi.spyOn(driver, 'call').mockImplementation(async (tool, args, options) => {
    if (tool === 'end_session') now += 301_000;
    return original(tool, args, options);
  });
  await control.act(child, undefined, { action: 'click', read_id: read.read_id, ref: 'p1:0' });
  events.push(humanMessage(3, now));
  for (const agent of [root, child, sibling]) {
    expect(control.precheck(agent, 'browser_read', {})?.browserCode).toBe('browser_launch_requires_user_turn');
    expect((await failure(control.read(agent, undefined, {}))).browserCode).toBe('browser_launch_requires_user_turn');
  }
  expect(driver.count('browser_prepare')).toBe(1);
});

it('waits for an in-flight prepare when disposing and leaves no instance', async () => {
  const driver = new BrowserFixtureDriver();
  driver.delayMs = 3;
  const control = controlFor(driver);
  const agent = openAgent('agent-a');
  const reading = control.read(agent, undefined, {});
  await Promise.resolve();
  await control.dispose(agent.id);
  await reading;
  expect(driver.count('end_session')).toBe(1);
  await control.read(agent, undefined, {});
  expect(driver.count('browser_prepare')).toBe(2);
});

it('retains a failed disposal reservation without retrying cleanup during its cooldown', async () => {
  const driver = new BrowserFixtureDriver({ endSessionError: new Error('cannot close') });
  const control = controlFor(driver, () => NOW, 1);
  const agent = openAgent('agent-a');
  await control.read(agent, undefined, {});
  await control.dispose(agent.id);
  expect(driver.count('end_session')).toBe(2);
  await control.dispose(agent.id);
  expect(driver.count('end_session')).toBe(2);
  expect((await failure(control.read(openAgent('agent-b'), undefined, {}))).browserCode).toBe('browser_busy');
  expect(driver.count('browser_prepare')).toBe(1);
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
  events.push(event(3, now, 'turn/end', { turn: 1 }), event(4, now, 'turn/start', { turn: 2 }), humanMessage(5, now));
  driver.state.windows = driver.state.windows.filter(window => window.window_id === '10');
  const recovered = await control.act(agent, undefined, { action: 'open', url: 'https://example.com' });
  expect(recovered.action).toBe('open');
  expect(driver.count('browser_prepare')).toBe(2);
});
