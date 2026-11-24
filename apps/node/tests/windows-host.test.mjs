// Run on the native build runner immediately after compiling GatewayHost.exe.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { execFile, spawn } from 'node:child_process';
import { mkdtemp, mkdir, copyFile, writeFile, readFile, rm, symlink, readlink, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, resolve, toNamespacedPath } from 'node:path';
import { promisify } from 'node:util';
import { setTimeout as delay } from 'node:timers/promises';
const exec = promisify(execFile);
const fixture = `
  const { spawn } = require('node:child_process');
  const { writeFileSync, readFileSync } = require('node:fs');
  const { join, dirname } = require('node:path');
  const root = dirname(process.argv[process.argv.indexOf('--config') + 1]);
  const dsh = spawn(process.execPath, ['-e', 'setInterval(() => {}, 5000)'], {stdio: 'ignore'});
  writeFileSync(join(root, 'pids.json'), JSON.stringify([process.pid, dsh.pid]));
  require('node:readline').createInterface({input: process.stdin}).on('line', line => {
    if (line === 'stop' && readFileSync(join(root, 'mode'), 'utf8') === 'drain') {
      writeFileSync(join(root, 'drained'), 'yes');
      process.exit();
    }
  });
`;

async function waitJson(path, attempts = 150) {
  for (let i = 0; i < attempts; i++) {
    try { return JSON.parse(await readFile(path, 'utf8')); }
    catch (error) {
      if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
      await delay(100);
    }
  }
  throw new Error(`Timed out waiting for ${path}`);
}

function serve(host, config) {
  const process = spawn(host, ['serve', config, '250'], {stdio: 'ignore', windowsHide: true});
  const exit = new Promise((done, reject) => { process.once('error', reject); process.once('exit', done); });
  return {process, exit};
}

test('Windows host confines its actual Gateway tree and checks birth before stop', {skip: process.platform !== 'win32', timeout: 90_000}, async () => {
  const temp = await mkdtemp(join(tmpdir(), 'Crewden 主机 '));
  const sha = 'a'.repeat(64);
  const root = join(temp, 'versions', sha);
  const cli = join(root, 'apps', 'node', 'lib', 'cli.js');
  const host = join(dirname(cli), 'GatewayHost.exe');
  const config = join(temp, 'config.yaml');
  const run = async (...args) => (await exec(host, args, {windowsHide: true, timeout: 15_000})).stdout.trim();
  let controller, other;
  try {
    await mkdir(dirname(cli), {recursive: true});
    await mkdir(join(root, 'runtime'));
    await writeFile(join(root, '.ready'), sha);
    await copyFile(process.execPath, join(root, 'runtime', 'node.exe'));
    await copyFile(resolve('dist/windows-build/GatewayHost.exe'), host);
    await writeFile(cli, fixture);
    await writeFile(join(dirname(cli), 'update-worker.js'), `
      const fs = require('node:fs'), path = require('node:path');
      const home = path.dirname(process.argv[2]);
      fs.writeFileSync(path.join(home, 'worker-started'), JSON.stringify(process.pid));
      setInterval(() => {
        if (fs.existsSync(path.join(home, 'allow-finish'))) {
          fs.writeFileSync(path.join(home, 'worker-result'), JSON.stringify(process.argv[3]));
          process.exit();
        }
      }, 100);
      setTimeout(() => process.exit(1), 30000);
    `);
    await writeFile(config, '{}');
    const boot = await run('boot');
    assert.match(boot, /^\d+$/);
    assert.equal(await run('boot'), boot);
    const second = join(temp, '另一个 IM');
    const otherConfig = join(second, 'config.yaml');
    await mkdir(second);
    await writeFile(otherConfig, '{}');
    await writeFile(join(second, 'mode'), 'drain');
    other = serve(host, otherConfig);
    const [otherPid] = await waitJson(join(second, 'pids.json'));
    const otherBirth = await run('birth', String(otherPid));
    for (const mode of ['drain', 'force', 'crash']) {
      await writeFile(join(temp, 'mode'), mode);
      await rm(join(temp, 'pids.json'), {force: true});
      controller = serve(host, config);
      const pids = await waitJson(join(temp, 'pids.json'));
      const [gateway, dsh] = pids.map(String);
      const birth = await run('birth', gateway);
      assert.match(birth, /^\d+$/);
      assert.match(await run('birth', dsh), /^\d+$/);
      const operation = randomUUID();
      let workerPid, workerBirth;
      if (mode === 'drain') {
        await run('launch-worker', config, operation, gateway, birth);
        workerPid = String(await waitJson(join(temp, 'worker-started')));
        workerBirth = await run('birth', workerPid);
        assert.match(workerBirth, /^\d+$/);
      }
      if (mode === 'crash') {
        process.kill(pids[0]);
        assert.equal(await controller.exit, 1);
      } else {
        await assert.rejects(run('stop', config, gateway, 'wrong-birth'), /identity changed/);
        assert.equal(await run('birth', gateway), birth);
        await run('stop', config, gateway, birth);
        assert.equal(await controller.exit, 0);
        if (mode === 'drain') {
          assert.equal(await readFile(join(temp, 'drained'), 'utf8'), 'yes');
          assert.equal(await run('birth', workerPid), workerBirth);
          await writeFile(join(temp, 'allow-finish'), '');
          assert.equal(await waitJson(join(temp, 'worker-result')), operation);
        }
      }
      assert.equal(await run('birth', String(otherPid)), otherBirth);
      assert.equal(await run('birth', gateway), '');
      for (let i = 0; i < 40 && await run('birth', dsh); i++) await delay(50);
      assert.equal(await run('birth', dsh), '');
    }
    // Exercise a registered on-demand task, since the scheduler can leave it
    // Ready after an unexpected child exit even with RestartOnFailure set.
    try {
      await writeFile(join(temp, 'mode'), 'drain');
      await rm(join(temp, 'pids.json'), {force:true});
      await run('start', config, '250', 'true');
      const [first] = await waitJson(join(temp, 'pids.json'));
      await rm(join(temp, 'pids.json'));
      process.kill(first);
      const [second] = await waitJson(join(temp, 'pids.json'), 400);
      assert.notEqual(first, second);
      await run('stop', config, String(second), await run('birth', String(second)));
    } finally {
      await exec('powershell.exe', ['-NoProfile', '-Command',
        'Get-ScheduledTask | Where-Object {$_.Actions.Execute -eq $env:CREWDEN_TEST_HOST} | Unregister-ScheduledTask -Confirm:$false'],
        {env:{...process.env, CREWDEN_TEST_HOST:host}});
    }
    await run('stop', otherConfig, String(otherPid), otherBirth);
    assert.equal(await other.exit, 0);
  } finally {
    for (const child of [controller, other]) if (child && child.process.exitCode === null) child.process.kill();
    await rm(temp, {force: true, recursive: true, maxRetries: 10, retryDelay: 100});
  }
});

test('retained Windows profiles replace only the recorded junction target', {skip: process.platform !== 'win32'}, async () => {
  const {prepareProfile} = await import('../../../packages/dsh-integration/lib/client.js');
  const home = await mkdtemp(join(tmpdir(), 'Crewden 配置 '));
  const entry = join(home, 'profiles', 'nano', 'node_modules', '@nano', 'dsh-integration');
  const previous = join(home, 'old install');
  try {
    await prepareProfile(home);
    const expected = await readlink(entry);
    await mkdir(previous);
    await unlink(entry);
    await symlink(previous, entry, 'junction');
    await assert.rejects(prepareProfile(home), /Unrecognized DSH profile junction/);
    assert.equal(toNamespacedPath(await readlink(entry)).toLowerCase(), toNamespacedPath(previous).toLowerCase());
    await writeFile(entry + '.crewden-target', toNamespacedPath(previous).toLowerCase());
    await prepareProfile(home);
    assert.equal(await readlink(entry), expected);
  } finally { await rm(home, {recursive: true, force: true}); }
});
