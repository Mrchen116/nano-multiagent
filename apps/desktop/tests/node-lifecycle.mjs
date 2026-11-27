// Run against the native Desktop host and its built Node bundle (or a source checkout).
import assert from 'node:assert/strict';
import { execFile, spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { once } from 'node:events';
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { promisify } from 'node:util';

const exec = promisify(execFile);
const [host, bundle] = process.argv.slice(2).map(arg => resolve(arg));
const root = await realpath(await mkdtemp(join(tmpdir(), 'desktop-lifecycle-')));
const upstream = createServer((req, res) => {
  if (req.url === '/im/v1/auth/me') {
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ id: 'owner' }));
  } else { res.writeHead(503).end(); }
});
upstream.listen(0, '127.0.0.1');
await once(upstream, 'listening');
const origin = 'http://127.0.0.1:' + upstream.address().port;
const dir = join(root, 'nano', 'connections', createHash('sha256').update(origin).digest('hex').slice(0, 16));
const config = join(dir, 'config.yaml');
const desktop = join(root, 'desktop');
const auto = join(root, 'autostart');
const marker = join(auto, 'desktop-login-autostart.json');
const trace = join(root, 'trace');
const hook = join(root, 'trace.cjs');
const env = { ...process.env, NANO_INSTALL_ROOT: join(root, 'nano'), NANO_TEST_AUTOSTART_DIR: auto,
  NANO_OWNER_CONFIG_ROOT: join(root, 'nano'), CREWDEN_DESKTOP_MANAGED: '1', CREWDEN_NODE_BIN: process.execPath,
  NODE_OPTIONS: '--require=' + JSON.stringify(hook), CREWDEN_SUPPRESS_OS_OPEN: '1' };
const save = (path, value) => writeFile(path, JSON.stringify(value));
const load = async path => JSON.parse(await readFile(path, 'utf8'));
const gateway = () => load(join(dir, '.gateway-state.json'));
let child, exited, base, cookie;
async function waitFor(label, check) {
  const until = Date.now() + 150_000;
  while (Date.now() < until) {
    try { const result = await check(); if (result) return result; }
    catch (err) { if (err.code !== 'ENOENT') throw err; }
    await delay(200);
  }
  throw new Error('Timed out waiting for ' + label);
}
async function openHost(...args) {
  child = spawn(host, ['--isolated-root', root, '--im-origin', origin, '--headless-host', '--dev-repo-root', bundle, ...args], { env });
  child.stderr.pipe(process.stderr);
  exited = once(child, 'exit');
  const state = await waitFor('new host', async () => {
    const s = await load(join(desktop, 'host-state.json'));
    return s.pid === child.pid && s;
  });
  base = 'http://127.0.0.1:' + state.port;
  const res = await fetch(base + '/desktop/bootstrap?nonce=' + state.boot_nonce, { redirect: 'manual' });
  cookie = res.headers.get('set-cookie').split(';')[0];
}
async function closeHost() {
  if (child) { child.kill(); await exited; child = undefined; }
}
async function setting(action, enabled) {
  const res = await fetch(base + '/desktop/v1/local-node/' + (action ? 'lifecycle' : 'inspect'), {
    method: action ? 'POST' : 'GET', headers: { cookie, authorization: 'Bearer fixture', 'content-type': 'application/json' },
    body: action ? JSON.stringify({ action, enabled }) : undefined,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? JSON.stringify(data));
  return data;
}
async function stopFixture() {
  const child = spawn(process.execPath, [join(bundle, 'apps/node/lib/cli.js'), 'local-admin', 'lifecycle',
    '--origin', origin, '--owner-id', 'owner'], { env, stdio: ['pipe', 'inherit', 'inherit'] });
  child.stdin.end(JSON.stringify({ action: 'stop' }));
  const [code] = await once(child, 'exit');
  assert.equal(code, 0);
}

try {
  for (const directory of [dir, desktop, auto]) await mkdir(directory, { recursive: true });
  await writeFile(trace, '');
  await writeFile(hook, `
    if (process.argv.includes('local-admin')) {
      const fs = require('node:fs'), fsp = require('node:fs/promises'), trace = ${JSON.stringify(trace)};
      fs.appendFileSync(trace, process.argv[3] + ' ' + process.pid + '\\n');
      const read = fsp.readFile;
      fsp.readFile = function(path, ...args) {
        if (String(path).endsWith('gateway.log')) fs.appendFileSync(trace, 'gateway.log\\n');
        return read.call(this, path, ...args);
      };
      require('node:module').syncBuiltinESMExports();
    }
  `);
  await save(join(desktop, 'sessions.json'), { by_origin: { [origin]: {
    id: 'owner', user_id: 'owner', owner_id: 'owner', username: 'Test', refresh_token: 'fixture', updated_at: 1,
  } } });
  await save(config, { node: { node_id: 'fixture', user_id: 'owner' }, im_service: { url: origin, token: 'fixture' },
    agents: [], gateway: { autostart: true, environment: { NANO_OWNER_CONFIG_ROOT: join(root, 'nano') } },
    llm: { default_model: 'm', providers: [{ name: 'test', base_url: origin, models: [{ name: 'm' }] }] } });
  await save(join(dir, '.desktop-active.json'), { managed_by: 'crewden-desktop', version_root: bundle, version: 'source' });
  await save(marker, { enabled: true });
  await openHost();
  await waitFor('bound gateway readiness', async () => (await gateway()).ready);
  const online = await setting();
  assert.equal(online.ownership, 'managed_online');
  await writeFile(trace, '');
  await delay(10_000);
  assert.equal(await readFile(trace, 'utf8'), '', 'healthy ticks spawned local-admin or reread gateway.log');
  console.log('10s healthy: zero local-admin processes and zero gateway.log rereads');
  process.kill(online.pid, 'SIGKILL');
  await waitFor('gateway crash recovery', async () => { const s = await gateway(); return s.ready && s.pid !== online.pid; });
  assert.equal((await setting('autostart', false)).autostart, false);
  await mkdir(marker); // A directory at the login item path forces both OS operations to fail.
  await assert.rejects(setting('autostart', true), /系统登录自启设置失败/);
  await assert.rejects(setting('autostart', false), /系统登录自启设置失败/);
  assert.equal((await setting()).autostart, false);
  await rm(marker, { recursive: true });
  assert.equal((await setting('stop')).ownership, 'managed_stopped');
  await closeHost();
  await openHost('--background');
  await delay(4000);
  assert.equal((await setting()).ownership, 'managed_stopped');
  assert.equal((await setting('autostart', true)).autostart, true);
  await closeHost();
  await openHost();
  await delay(4000);
  assert.equal((await setting()).ownership, 'managed_stopped');
  await closeHost();
  await openHost('--background');
  await waitFor('enabled login after manual stop', async () => (await gateway()).ready);
  assert.equal((await setting()).ownership, 'managed_online');
  console.log('Recovered after crash, stayed stopped on disabled login and ordinary reopen, resumed on enabled login');
} finally {
  await closeHost();
  upstream.closeAllConnections();
  upstream.close();
  try { await stopFixture(); } finally {
    if (process.platform === 'win32') {
      const { stdout } = await exec('whoami', ['/user', '/fo', 'csv', '/nh']);
      const sid = stdout.match(/S-1-[\d-]+/i)[0];
      const id = createHash('sha256').update(sid + '|' + config.toUpperCase()).digest('hex').slice(0, 24).toUpperCase();
      await exec('schtasks', ['/Delete', '/TN', 'CrewdenDesktop-' + id, '/F']).catch(() => {});
    }
    await rm(root, { recursive: true, force: true });
  }
}
