import { createServer } from 'node:http';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { chromeExecutable } from '../src/computer/browser-connection.js';
import { BrowserBackend } from '../src/computer/browser.js';

const installed = await chromeExecutable().then(
  () => true,
  () => false,
);
it.skipIf(!installed)(
  'observes only the assigned browser and revalidates a reviewed target',
  async () => {
    const cwd = await mkdtemp(join(tmpdir(), 'nano-browser-test-'));
    const server = createServer((_req, res) =>
      res.end('<html><title>Local fixture</title><button>Test button</button><input aria-label="Name"></html>'),
    );
    const seat = new BrowserBackend(cwd);
    const other = new BrowserBackend(cwd);
    const signal = AbortSignal.timeout(45000);
    async function call(action: string, input: Record<string, unknown> = {}) {
      const prepared = await seat.prepare(action, input, signal);
      return (await prepared.run(signal))
        .filter((p) => p.type === 'text')
        .map((p) => p.text)
        .join(' ');
    }
    try {
      server.listen(0, '127.0.0.1');
      await once(server, 'listening');
      const url = 'http://127.0.0.1:' + (server.address() as { port: number }).port + '/';
      const opening = await seat.prepare('open', { mode: 'isolated', url }, signal);
      expect(opening.access).toBe('review');
      await expect(other.prepare('snapshot', {}, signal)).rejects.toThrow();
      await opening.run(signal);
      const snapshot = await call('snapshot');
      expect(snapshot).toContain('Test button');
      await expect(seat.prepare('snapshot', { filename: 'out' }, signal)).rejects.toThrow();
      const ref = /button "Test button" \[ref=(\w+)\]/.exec(snapshot)![1]!;
      await call('copy', { text: 'Test button' });
      await call('paste', { ref: /textbox "Name" \[ref=(\w+)\]/.exec(snapshot)![1]! });
      const pasted = await call('snapshot');
      expect(pasted).toMatch(/textbox "Name"[^\n]*Test button/);
      const otherOpening = await other.prepare('open', { url, mode: 'isolated' }, signal);
      await otherOpening.run(signal);
      const otherSnapshot = (await (await other.prepare('snapshot', {}, signal)).run(signal)).find(
        (block) => block.type === 'text',
      );
      const otherRef = /textbox "Name" \[ref=(\w+)\]/.exec(otherSnapshot!.text)![1]!;
      await expect(other.prepare('paste', { ref: otherRef }, signal)).rejects.toThrow('clipboard is empty');
      const originalTab = JSON.parse(await call('tabs'))[0].tab;
      await call('new_tab', { url: url + 'other' });
      const allTabs = JSON.parse(await call('tabs'));
      expect(allTabs).toHaveLength(2);
      await call('select_tab', { tab: originalTab });
      const secondSnapshot = await call('snapshot');
      expect(secondSnapshot).toContain('Test button');
      const click = await seat.prepare('click', { ref }, signal);
      expect(click.access).toBe('review');
      expect(click.evidence).toContain('Test button');
      await call('navigate', { url: url + 'other' });
      await expect(click.run(signal)).rejects.toThrow();
      await (await other.prepare('close_tab', {}, signal)).run(signal);
      await (await other.prepare('open', { url, mode: 'isolated' }, signal)).run(signal);
      expect(JSON.stringify(await (await other.prepare('snapshot', {}, signal)).run(signal))).toContain('Test button');
    } finally {
      await Promise.all([seat.close(), other.close()]);
      server.close();
      await rm(cwd, { recursive: true, force: true });
    }
  },
  55000,
);
