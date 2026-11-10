import { expect, it, vi } from 'vitest';
import { BrowserControl } from '../src/browser/control.js';
import { BrowserFixtureDriver, event, fakeAgent, humanMessage } from './helpers/browser-fakes.js';

it('checks for a delayed URL commit without dispatching navigation twice', async () => {
  const now = 1_000_000;
  const driver = new BrowserFixtureDriver();
  const call = driver.call.bind(driver);
  let navigation: Record<string, unknown> | undefined;
  const spy = vi.spyOn(driver, 'call').mockImplementation(async (name, args, options) => {
    if (name === 'browser_navigate') {
      navigation = args;
      return { effect: 'unverifiable' };
    }
    const value = await call(name, args, options);
    if (name === 'get_browser_state' && navigation) {
      const pending = navigation;
      navigation = undefined;
      await call('browser_navigate', pending);
    }
    return value;
  });
  const agent = fakeAgent('browser-navigation', [event(1, now - 1000, 'turn/start', { turn: 1 }), humanMessage(2, now - 500)]);
  const control = new BrowserControl({ driver, lookup: () => undefined, now: () => now });
  await expect(control.act(agent, undefined, { action: 'open', url: 'https://committed.example' }))
    .resolves.toMatchObject({ dispatched: true, effect: 'changed', observed: { url: 'https://committed.example' } });
  expect(spy.mock.calls.filter(([tool]) => tool === 'browser_navigate')).toHaveLength(1);
});
