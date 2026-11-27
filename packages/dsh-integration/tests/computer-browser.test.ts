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
    const server = createServer((req, res) => {
      if (req.url === '/redirect') {
        res.writeHead(302, { Location: redirectTarget });
        res.end();
        return;
      }
      res.end(
        `<html><title>Local fixture</title><button>Test button</button><input aria-label="Name"><a href="${redirectTarget}" target="_blank">Open Cross Origin Popup</a></html>`,
      );
    });
    const redirectedServer = createServer((_req, res) =>
      res.end('<html><title>Redirected origin</title><p>Landed on second origin</p></html>'),
    );
    let redirectTarget = '';
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
      redirectedServer.listen(0, '127.0.0.1');
      await Promise.all([once(server, 'listening'), once(redirectedServer, 'listening')]);
      const url = 'http://127.0.0.1:' + (server.address() as { port: number }).port + '/';
      redirectTarget = 'http://127.0.0.1:' + (redirectedServer.address() as { port: number }).port + '/landed';
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
      const shotParts = await (await other.prepare('screenshot', {}, signal)).run(signal);
      expect(shotParts.some((p) => p.type === 'image')).toBe(true);
      expect(shotParts.find((p) => p.type === 'text')?.text).toContain('Screenshot saved to ');

      // Cross-origin 302 redirect keeps the tab owned, readable, and closable
      const navResult = await (await other.prepare('navigate', { url: url + 'redirect' }, signal)).run(signal);
      expect(navResult[0]?.type === 'text' ? navResult[0].text : '').toContain(redirectTarget);
      const redirectedSnap = await (await other.prepare('snapshot', {}, signal)).run(signal);
      expect(JSON.stringify(redirectedSnap)).toContain('Landed on second origin');
      const otherTabsAfterRedirect = JSON.parse(
        ((await (await other.prepare('tabs', {}, signal)).run(signal))[0] as { text: string }).text,
      );
      expect(otherTabsAfterRedirect).toHaveLength(1);

      // Approved target="_blank" click adopts the spawned cross-origin popup tab
      await (await other.prepare('navigate', { url }, signal)).run(signal);
      const popupPageSnap = ((await (await other.prepare('snapshot', {}, signal)).run(signal))[0] as { text: string })
        .text;
      const popupLinkRef = /link "Open Cross Origin Popup" \[ref=(\w+)\]/.exec(popupPageSnap)![1]!;
      await (await other.prepare('click', { ref: popupLinkRef }, signal)).run(signal);
      const popupTabs = JSON.parse(
        ((await (await other.prepare('tabs', {}, signal)).run(signal))[0] as { text: string }).text,
      );
      expect(popupTabs).toHaveLength(2);
    } finally {
      await Promise.all([seat.close(), other.close()]);
      server.close();
      redirectedServer.close();
      await rm(cwd, { recursive: true, force: true });
    }
  },
  55000,
);
