import { chmod, mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import {
  PLAYWRIGHT_EXTENSION_ID,
  PLAYWRIGHT_EXTENSION_LEGACY_TOKEN_URL,
  PLAYWRIGHT_EXTENSION_STORE_URL,
  PLAYWRIGHT_EXTENSION_TOKEN_URL,
  browserCommand,
  inspectDailyBrowserStatus,
  normalizeExtensionToken,
  openDailyBrowserGuide,
} from '../src/browser-pairing.js';
import { inspectLocalNode, manageLocalNodeBrowser } from '../src/local-admin.js';
import { browserPairingFile } from '../src/lifecycle.js';

const SAMPLE_TOKEN = 'pw_ext_token_1234567890abcdefXYZ';

it('normalizes raw tokens and full PLAYWRIGHT_MCP_EXTENSION_TOKEN assignment lines without leaking invalid input', () => {
  expect(normalizeExtensionToken(SAMPLE_TOKEN)).toBe(SAMPLE_TOKEN);
  expect(normalizeExtensionToken(`  PLAYWRIGHT_MCP_EXTENSION_TOKEN=${SAMPLE_TOKEN}\n`)).toBe(SAMPLE_TOKEN);
  expect(normalizeExtensionToken(`export PLAYWRIGHT_MCP_EXTENSION_TOKEN="${SAMPLE_TOKEN}"`)).toBe(SAMPLE_TOKEN);
  expect(normalizeExtensionToken(`PLAYWRIGHT_MCP_EXTENSION_TOKEN='${SAMPLE_TOKEN}'`)).toBe(SAMPLE_TOKEN);
  expect(normalizeExtensionToken('short')).toBeNull();
  expect(normalizeExtensionToken('PLAYWRIGHT_MCP_EXTENSION_TOKEN=has spaces inside')).toBeNull();
});

it('auto-opens Chrome Web Store, transitions to token page once extension lands on disk, and writes 0600 pairing', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-browser-pair-'));
  try {
    const fakeChrome = join(root, 'Google Chrome');
    const userDataDir = join(root, 'ChromeUserData');
    const pairingPath = join(root, 'private', 'browser-pairing.json');
    await writeFile(fakeChrome, '#!/bin/sh\nexit 0\n');
    await chmod(fakeChrome, 0o755);
    await mkdir(join(userDataDir, 'Default'), { recursive: true });

    const openedUrls: { profile: string; url: string }[] = [];
    const stderrLogs: string[] = [];

    let resolvePrompt!: (val: string) => void;
    const promptPromise = new Promise<string>(resolve => {
      resolvePrompt = resolve;
    });

    const pairPromise = browserCommand('pair', pairingPath, 'Default', {
      platform: 'darwin',
      chromeExecutable: fakeChrome,
      userDataDir,
      chromeRunning: { running: true, versionOk: true },
      pollIntervalMs: 25,
      openChromeUrl: async (_exe, profile, url) => {
        openedUrls.push({ profile, url });
        if (url === PLAYWRIGHT_EXTENSION_STORE_URL) {
          // Simulate user clicking "Add to Chrome -> Add extension" so manifest + manage.html (0.6.0+) land on disk.
          const extVersionDir = join(userDataDir, 'Default', 'Extensions', PLAYWRIGHT_EXTENSION_ID, '0.6.0_0');
          await mkdir(extVersionDir, { recursive: true });
          await writeFile(join(extVersionDir, 'manifest.json'), JSON.stringify({ version: '0.6.0' }));
          await writeFile(join(extVersionDir, 'manage.html'), '<!doctype html>');
        } else if (url === PLAYWRIGHT_EXTENSION_TOKEN_URL) {
          resolvePrompt(`PLAYWRIGHT_MCP_EXTENSION_TOKEN=${SAMPLE_TOKEN}`);
        }
      },
      interactivePrompt: () => promptPromise,
      stderrWrite: chunk => stderrLogs.push(chunk),
    });

    const result = await pairPromise;
    expect(result).toEqual({ state: 'paired', profile: 'Default' });
    expect(openedUrls).toEqual([
      { profile: 'Default', url: PLAYWRIGHT_EXTENSION_STORE_URL },
      { profile: 'Default', url: PLAYWRIGHT_EXTENSION_TOKEN_URL },
    ]);
    expect(stderrLogs.join('')).toContain('Detected Playwright Extension');

    const fileStat = await stat(pairingPath);
    if (process.platform !== 'win32') {
      expect(fileStat.mode & 0o777).toBe(0o600);
    }
    const stored = JSON.parse(await readFile(pairingPath, 'utf8')) as { profile: string; token: string };
    expect(stored.profile).toBe('Default');
    expect(stored.token).toBe(SAMPLE_TOKEN);

    // Inspect never leaks token and marks reconnect if extension is uninstalled later.
    const statusOk = await inspectDailyBrowserStatus(pairingPath, undefined, {
      platform: 'darwin',
      chromeExecutable: fakeChrome,
      userDataDir,
      chromeRunning: { running: true, versionOk: true },
    });
    expect(statusOk.state).toBe('paired');
    expect(statusOk.extension_installed).toBe(true);
    expect(JSON.stringify(statusOk)).not.toContain(SAMPLE_TOKEN);

    const directTokenGuide = await openDailyBrowserGuide(pairingPath, 'Default', 'auto', {
      platform: 'darwin',
      chromeExecutable: fakeChrome,
      userDataDir,
      openChromeUrl: (_exe, profile, url) => {
        openedUrls.push({ profile, url });
      },
    });
    expect(directTokenGuide.opened).toBe('token');

    await rm(join(userDataDir, 'Default', 'Extensions'), { recursive: true, force: true });
    const statusMissingExt = await inspectDailyBrowserStatus(pairingPath, undefined, {
      platform: 'darwin',
      chromeExecutable: fakeChrome,
      userDataDir,
      chromeRunning: { running: true, versionOk: true },
    });
    expect(statusMissingExt.state).toBe('reconnect');
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

it('enforces owner_id isolation and extension prerequisite in local-admin manageLocalNodeBrowser', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-browser-admin-'));
  try {
    const fakeChrome = join(root, 'Google Chrome');
    const userDataDir = join(root, 'ChromeUserData');
    await writeFile(fakeChrome, '#!/bin/sh\nexit 0\n');
    await chmod(fakeChrome, 0o755);
    await mkdir(join(userDataDir, 'Default'), { recursive: true });
    await mkdir(join(userDataDir, 'Profile 1', 'Extensions', PLAYWRIGHT_EXTENSION_ID, '0.5.0_0'), {
      recursive: true,
    });
    await writeFile(
      join(userDataDir, 'Profile 1', 'Extensions', PLAYWRIGHT_EXTENSION_ID, '0.5.0_0', 'manifest.json'),
      JSON.stringify({ version: '0.5.0' }),
    );

    const configPath = join(root, 'config.yaml');
    const nodeConfig = {
      node: { node_id: 'node-1', node_name: 'MacBook', user_id: 'owner-alice' },
      im_service: { url: 'https://im.example.com', token: 'tok' },
      agents: [],
      llm: { default_model: '', providers: [] },
    };
    await writeFile(configPath, JSON.stringify(nodeConfig));

    const deps = {
      platform: 'darwin' as const,
      chromeExecutable: fakeChrome,
      userDataDir,
      chromeRunning: { running: true, versionOk: true },
      openChromeUrl: () => {},
    };

    // Foreign owner blocked with 403
    await expect(
      manageLocalNodeBrowser({
        origin: 'https://im.example.com',
        ownerId: 'owner-mallory',
        configPath,
        actionInput: { action: 'status' },
        deps,
      }),
    ).rejects.toMatchObject({ status: 403, errorCode: 'foreign_owner' });

    // Saving token on Default (no extension installed) fails cleanly with 422 browser_extension_missing
    await expect(
      manageLocalNodeBrowser({
        origin: 'https://im.example.com',
        ownerId: 'owner-alice',
        configPath,
        actionInput: { action: 'pair', profile: 'Default', token: SAMPLE_TOKEN },
        deps,
      }),
    ).rejects.toMatchObject({ status: 422, errorCode: 'browser_extension_missing' });

    // Saving full line on Profile 1 (extension installed) succeeds and shows in inspectLocalNode
    const paired = await manageLocalNodeBrowser({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      configPath,
      actionInput: {
        action: 'pair',
        profile: 'Profile 1',
        token: `PLAYWRIGHT_MCP_EXTENSION_TOKEN=${SAMPLE_TOKEN}`,
      },
      deps,
    });
    expect(paired.browser.state).toBe('paired');
    expect(paired.browser.paired_profile).toBe('Profile 1');

    const inspected = await inspectLocalNode({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      configPath,
      browserDeps: deps,
    });
    expect(inspected.browser?.state).toBe('paired');
    expect(inspected.browser?.paired_profile).toBe('Profile 1');
    expect(JSON.stringify(inspected)).not.toContain(SAMPLE_TOKEN);

    const pairingPath = browserPairingFile(configPath, nodeConfig.node);
    const disconnected = await manageLocalNodeBrowser({
      origin: 'https://im.example.com',
      ownerId: 'owner-alice',
      configPath,
      actionInput: { action: 'disconnect' },
      deps,
    });
    expect(disconnected.browser.state).toBe('not_paired');
    await expect(stat(pairingPath)).rejects.toThrow();

    // Legacy 0.5.x bundle with status.html falls back cleanly to status.html, while newer 0.6.0+ prefers manage.html.
    const legacyDir = join(userDataDir, 'Profile 1', 'Extensions', PLAYWRIGHT_EXTENSION_ID, '0.5.0_0');
    await writeFile(join(legacyDir, 'status.html'), '<!doctype html>');
    const legacyOpened: string[] = [];
    await openDailyBrowserGuide(pairingPath, 'Profile 1', 'token', {
      platform: 'darwin',
      chromeExecutable: fakeChrome,
      userDataDir,
      openChromeUrl: (_exe, _profile, url) => {
        legacyOpened.push(url);
      },
    });
    expect(legacyOpened).toEqual([PLAYWRIGHT_EXTENSION_LEGACY_TOKEN_URL]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
