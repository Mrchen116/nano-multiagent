import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it, vi } from 'vitest';
import { createServer } from '../src/server.js';

const version = '0.2.0';
const manifest = { version, source_commit: 'a'.repeat(40), sha256: 'b'.repeat(64), package: 'nano-node.tgz', node_major: 24, pnpm_version: '11.7.0', download_url: `https://github.com/Mrchen116/nano-multiagent/releases/download/v${version}/nano-node.tgz` };

const closers: (() => Promise<void>)[] = [];
afterEach(async () => { for (const close of closers.splice(0)) await close(); });
async function fixture(published = true) {
  const dir = mkdtempSync(join(tmpdir(), 'nano-onboarding-'));
  if (published) {
    writeFileSync(join(dir, 'manifest.json'), JSON.stringify(manifest));
  }
  const app = await createServer({ dbPath: join(dir, 'im.sqlite3'), publicUrl: 'https://nano.example', nodeReleaseDir: dir });
  closers.push(async () => { await app.close(); rmSync(dir, { recursive: true, force: true }); });
  const pair = await app.im.identity.register('alice', 'password1', 'Alice');
  app.im.identity.initializeCompany(pair.user.id);
  const headers = { authorization: 'Bearer ' + pair.access_token };
  return { app, headers, dir, owner: pair.user.owner_id };
}
it('offers only the current account resources and server-origin installation materials', async () => {
  const { app, headers, owner } = await fixture();
  app.im.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('mine',?,'My laptop','online','',0,''),('other','other','Secret computer','online','',0,'')").run(owner);
  const response = await app.inject({ url: '/im/v1/onboarding', headers: { ...headers, host: 'attacker.example' } });
  expect(response.statusCode).toBe(200);
  expect(response.json().nodes.map((n: any) => n.node_id)).toEqual(['mine']);
  expect(response.json().install.command).toContain('https://nano.example/install.sh');
  expect(response.body).not.toContain('attacker');
  expect(response.body).not.toContain('Secret computer');
  const script = await app.inject({ url: '/install.sh', headers: { host: 'attacker.example' } });
  expect(script.statusCode).toBe(200);
  expect(script.body).toContain("NANO_ORIGIN='https://nano.example'");
  expect(script.body).not.toContain('attacker');
});
it('refuses setup on another owner node and rechecks transfer after an in-flight response', async () => {
  const { app, headers, owner } = await fixture();
  app.im.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('mine',?,'Laptop','online','',0,''),('other','other','Other','online','',0,'')").run(owner);
  const rpc = vi.spyOn(app.im.gateway, 'request').mockResolvedValue({ models: [], api_key: 'never-return', operation: { state: 'testing', api_key: 'never-return' } });
  expect((await app.inject({ method: 'POST', url: '/im/v1/nodes/other/setup', headers, payload: { action: 'status' } })).statusCode).toBe(404);
  expect(rpc).not.toHaveBeenCalled();
  const response = await app.inject({ method: 'POST', url: '/im/v1/nodes/mine/setup', headers, payload: { action: 'status' } });
  expect(response.statusCode).toBe(200);
  expect(response.body).not.toContain('never-return');
  rpc.mockImplementationOnce(async () => {
    app.im.db.prepare("UPDATE nodes SET owner_id='other' WHERE node_id='mine'").run();
    return { models: [{ provider: 'secret', model: 'secret' }] };
  });
  const moved = await app.inject({ method: 'POST', url: '/im/v1/nodes/mine/setup', headers, payload: { action: 'status' } });
  expect(moved.statusCode).toBe(404);
  expect(moved.body).not.toContain('secret');
});
it('does not present an unpublished installer as downloadable', async () => {
  const { app, headers } = await fixture(false);
  expect((await app.inject({ url: '/im/v1/onboarding', headers })).json().install.available).toBe(false);
  expect((await app.inject('/install.sh')).statusCode).toBe(503);
});

it('serves independently verified Windows materials for the configured origin and rejects a misplaced manifest', async () => {
  const { app, headers, dir } = await fixture(false);
  const base = manifest.download_url.slice(0, manifest.download_url.lastIndexOf('/') + 1);
  const windows = { ...manifest, platform: 'win32-x64', package: 'windows-x64.json', download_url: base + 'windows-x64.json',
    size: 8192, updater_protocol: 1, data_epoch: 1, installer: { download_url: base + 'Crewden-Setup-x64.exe', size: 4096, sha256: 'c'.repeat(64) } };
  const windowsPath = join(dir, 'manifest.win32-x64.json');
  const route = '/install/manifest.win32-x64.json';
  expect((await app.inject(route)).statusCode).toBe(503);
  writeFileSync(windowsPath, JSON.stringify(windows));
  const state = await app.inject({ url: '/im/v1/onboarding', headers: {...headers, host: 'other.example'} });
  expect(state.json().install).toMatchObject({ available: false, windows_x64: {
    download_url: windows.installer.download_url, connect_url: 'crewden://connect?origin=https%3A%2F%2Fnano.example',
  } });
  const result = await app.inject(route);
  expect(result.json()).toEqual(windows);
  expect(result.headers['cache-control']).toBe('no-store');
  writeFileSync(windowsPath, JSON.stringify(manifest));
  writeFileSync(join(dir, 'manifest.json'), JSON.stringify(windows));
  expect((await app.inject(route)).statusCode).toBe(503);
  expect((await app.inject('/install/nano-node.tgz')).statusCode).toBe(503);
  expect((await app.inject({ url: '/im/v1/onboarding', headers })).json().install.windows_x64).toBeNull();
});

it('serves Desktop macOS arm64 and Windows x64 materials side-by-side with lightweight installers', async () => {
  const { app, headers, dir } = await fixture(true);
  const base = manifest.download_url.slice(0, manifest.download_url.lastIndexOf('/') + 1);
  const macDesktop = {
    ...manifest,
    platform: 'desktop-darwin-arm64',
    package: 'desktop-darwin-arm64.json',
    download_url: base + 'desktop-darwin-arm64.json',
    size: 1024,
    updater_protocol: 1,
    data_epoch: 1,
    shell_protocol: 1,
    installer: { download_url: base + 'Crewden-Desktop-arm64.dmg', size: 16384, sha256: 'd'.repeat(64) },
  };
  const winDesktop = {
    ...manifest,
    platform: 'desktop-win32-x64',
    package: 'desktop-win32-x64.json',
    download_url: base + 'desktop-win32-x64.json',
    size: 1024,
    updater_protocol: 1,
    data_epoch: 1,
    shell_protocol: 1,
    installer: { download_url: base + 'Crewden-Desktop-Setup-x64.exe', size: 24576, sha256: 'e'.repeat(64) },
  };
  expect((await app.inject('/install/manifest.desktop-darwin-arm64.json')).statusCode).toBe(503);
  expect((await app.inject('/install/manifest.desktop-win32-x64.json')).statusCode).toBe(503);

  writeFileSync(join(dir, 'manifest.desktop-darwin-arm64.json'), JSON.stringify(macDesktop));
  writeFileSync(join(dir, 'manifest.desktop-win32-x64.json'), JSON.stringify(winDesktop));

  const state = await app.inject({ url: '/im/v1/onboarding', headers: { ...headers, host: 'attacker.example' } });
  expect(state.json().install).toMatchObject({
    available: true,
    desktop_darwin_arm64: {
      download_url: macDesktop.installer.download_url,
      connect_url: 'crewden-desktop://connect?origin=https%3A%2F%2Fnano.example',
      version: macDesktop.version,
    },
    desktop_win32_x64: {
      download_url: winDesktop.installer.download_url,
      connect_url: 'crewden-desktop://connect?origin=https%3A%2F%2Fnano.example',
      version: winDesktop.version,
    },
  });
  expect((await app.inject('/install/manifest.desktop-darwin-arm64.json')).json()).toEqual(macDesktop);
  expect((await app.inject('/install/manifest.desktop-win32-x64.json')).json()).toEqual(winDesktop);

  const publicInstall = await app.inject({ url: '/im/v1/public/install', headers: { host: 'attacker.example' } });
  expect(publicInstall.statusCode).toBe(200);
  expect(publicInstall.headers['cache-control']).toBe('no-store');
  expect(publicInstall.body).not.toContain('attacker');
  expect(publicInstall.json()).toMatchObject({
    available: true,
    origin: 'https://nano.example',
    desktop_darwin_arm64: { download_url: macDesktop.installer.download_url, version: macDesktop.version },
    desktop_win32_x64: { download_url: winDesktop.installer.download_url, version: winDesktop.version },
    ios: null,
  });

  const iosApp = await createServer({
    dbPath: join(dir, 'im-ios.sqlite3'),
    publicUrl: 'https://nano.example',
    nodeReleaseDir: dir,
    iosDownloadUrl: 'https://testflight.apple.com/join/crewden',
  });
  closers.push(async () => { await iosApp.close(); });
  expect((await iosApp.inject('/im/v1/public/install')).json().ios).toEqual({
    download_url: 'https://testflight.apple.com/join/crewden',
  });

  const insecureIosApp = await createServer({
    dbPath: join(dir, 'im-ios-http.sqlite3'),
    publicUrl: 'https://nano.example',
    nodeReleaseDir: dir,
    iosDownloadUrl: 'http://insecure.example/app',
  });
  closers.push(async () => { await insecureIosApp.close(); });
  expect((await insecureIosApp.inject('/im/v1/public/install')).json().ios).toBeNull();
});

it('serves a pinned manifest without the package and redirects old scripts without a body', async () => {
  const { app, dir } = await fixture();
  const response = await app.inject('/install/manifest.json');
  expect(response.statusCode).toBe(200);
  expect(response.json()).toEqual(manifest);
  expect(response.headers['cache-control']).toBe('no-store');
  const redirect = await app.inject('/install/nano-node.tgz');
  expect(redirect.statusCode).toBe(302);
  expect(redirect.headers.location).toBe(manifest.download_url);
  expect(redirect.headers['cache-control']).toBe('no-store');
  expect(redirect.body).toBe('');
  const previous = { ...manifest, version: 'c'.repeat(40), download_url: manifest.download_url.replace(`v${version}`, 'node-' + 'c'.repeat(40)) };
  writeFileSync(join(dir, 'manifest.json'), JSON.stringify(previous));
  expect((await app.inject('/install/manifest.json')).json()).toEqual(previous);
  expect((await app.inject('/install/nano-node.tgz')).headers.location).toBe(previous.download_url);
});
it.each([
  '{broken', JSON.stringify({ sha256: 'b'.repeat(64) }),
  JSON.stringify({ ...manifest, source_commit: 'not-a-commit' }),
  JSON.stringify({ ...manifest, source_commit: undefined }),
  JSON.stringify({ ...manifest, version: '01.2.3', download_url: manifest.download_url.replace('v0.2.0', 'v01.2.3') }),
  JSON.stringify({ ...manifest, download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/latest/download/nano-node.tgz' }),
  JSON.stringify({ ...manifest, download_url: manifest.download_url.replace('Mrchen116', 'attacker') }),
  JSON.stringify({ ...manifest, version: 'd'.repeat(40) }),
])('does not publish invalid or mismatched release metadata: %s', async (content) => {
  const { app, headers, dir } = await fixture();
  writeFileSync(join(dir, 'manifest.json'), content);
  expect((await app.inject({ url: '/im/v1/onboarding', headers })).json().install.available).toBe(false);
  for (const url of ['/install.sh', '/install/manifest.json', '/install/nano-node.tgz']) {
    expect((await app.inject(url)).statusCode).toBe(503);
  }
});


it('projects nested model metadata and dependency errors without returning credentials, and relays only editable fields', async () => {
  const {app, headers, owner} = await fixture();
  app.im.db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('mine',?,'Laptop','online','',0,'')").run(owner);
  const rpc = vi.spyOn(app.im.gateway, 'request').mockResolvedValue({revision: 'new', services: [{provider: 'p', display_name: 'API', api_key: 'never-return', models: [{name: 'p/m', id: 'm', api_key: 'never-return'}]}], catalog: [{provider: 'builtin', models: [{id: 'm', key: 'never-return'}]}], error: {code: 'in_use', message: 'Change helper first', credential: 'never-return', dependencies: [{agent_id: 'a', display_name: 'Helper', api_key: 'never-return'}]}});
  const response = await app.inject({method: 'POST', url: '/im/v1/nodes/mine/setup', headers, payload: {action: 'save', revision: 'old', source: 'custom', api_key: 'write-only', arbitrary_patch: {}, models: [{id: 'm', display_name: 'Model', context_window: 1000, input: ['text'], api_key: 'discard-nested-key'}]}});
  expect(response.statusCode).toBe(200);
  expect(response.body).not.toContain('never-return');
  expect(response.json().services[0].models).toEqual([{name: 'p/m', id: 'm'}]);
  expect(response.json().error.dependencies).toEqual([{agent_id: 'a', display_name: 'Helper'}]);
  expect(rpc.mock.calls[0]?.[2]).toEqual({action: 'save', revision: 'old', source: 'custom', api_key: 'write-only', models: [{id: 'm', display_name: 'Model', context_window: 1000, input: ['text']}]});
  expect((await app.inject({method: 'POST', url: '/im/v1/nodes/mine/setup', headers, payload: {action: 'save', models: [{id: 'm', context_window: -1}]}})).statusCode).toBe(422);
});

it('transiently bridges Web Daily Chrome pairing only to owned nodes with Cache-Control no-store and strips unexpected fields', async () => {
  const { app, headers, owner } = await fixture();
  app.im.db
    .prepare(
      "INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES('mine',?,'Mac-Studio','online','',0,''),('other','other','Foreign','online','',0,'')",
    )
    .run(owner);
  const rpc = vi.spyOn(app.im.gateway, 'request').mockResolvedValue({
    browser: {
      supported: true,
      state: 'paired',
      chrome_installed: true,
      chrome_running: true,
      chrome_version_ok: true,
      paired_profile: 'Default',
      selected_profile: 'Default',
      extension_installed: true,
      token: 'never-leak-token',
      profiles: [{ profile: 'Default', extension_installed: true, token: 'never-leak-token' }],
    },
    opened: 'token',
  } as any);

  expect(
    (await app.inject({ method: 'POST', url: '/im/v1/nodes/other/browser', headers, payload: { action: 'status' } }))
      .statusCode,
  ).toBe(404);
  expect(rpc).not.toHaveBeenCalled();

  const paired = await app.inject({
    method: 'POST',
    url: '/im/v1/nodes/mine/browser',
    headers,
    payload: {
      action: 'pair',
      profile: 'Default',
      token: 'PLAYWRIGHT_MCP_EXTENSION_TOKEN=pw_secret_1234567890abcdef',
      unexpected: 'dropped',
    },
  });
  expect(paired.statusCode).toBe(200);
  expect(paired.headers['cache-control']).toBe('no-store');
  expect(paired.body).not.toContain('never-leak-token');
  expect(paired.body).not.toContain('pw_secret_1234567890abcdef');
  expect(rpc).toHaveBeenCalledWith('mine', 'node.browser.request', {
    action: 'pair',
    profile: 'Default',
    token: 'PLAYWRIGHT_MCP_EXTENSION_TOKEN=pw_secret_1234567890abcdef',
  });

  rpc.mockResolvedValueOnce({
    error: { code: 'browser_extension_missing', message: 'Install Playwright Extension first' },
  } as any);
  const missingExt = await app.inject({
    method: 'POST',
    url: '/im/v1/nodes/mine/browser',
    headers,
    payload: { action: 'pair', profile: 'Default', token: 'pw_secret_1234567890abcdef' },
  });
  expect(missingExt.statusCode).toBe(422);
  expect(missingExt.json()).toEqual({
    detail: { code: 'browser_extension_missing', message: 'Install Playwright Extension first' },
  });
});
