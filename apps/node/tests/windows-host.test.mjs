// Run on the native build runner immediately after compiling GatewayHost.exe.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile, spawn } from 'node:child_process';
import { mkdtemp, mkdir, copyFile, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
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

test('Windows host confines its actual Gateway tree and checks birth before stop', {skip: process.platform !== 'win32', timeout: 90_000}, async () => {
  const temp = await mkdtemp(join(tmpdir(), 'Crewden 主机 '));
  const sha = 'a'.repeat(64);
  const root = join(temp, 'versions', sha);
  const cli = join(root, 'apps', 'node', 'lib', 'cli.js');
  const host = join(dirname(cli), 'GatewayHost.exe');
  const config = join(temp, 'config.yaml');
  const run = async (...args) => (await exec(host, args, {windowsHide: true, timeout: 15_000})).stdout.trim();
  let controller;
  try {
    await mkdir(dirname(cli), {recursive: true});
    await mkdir(join(root, 'runtime'));
    await copyFile(process.execPath, join(root, 'runtime', 'node.exe'));
    await copyFile(resolve('dist/windows-build/GatewayHost.exe'), host);
    await writeFile(cli, fixture);
    await writeFile(config, '{}');
    const boot = await run('boot');
    assert.match(boot, /^\d+$/);
    assert.equal(await run('boot'), boot);
    for (const mode of ['drain', 'force', 'crash']) {
      await writeFile(join(temp, 'mode'), mode);
      await rm(join(temp, 'pids.json'), {force: true});
      controller = spawn(host, ['serve', config, '250'], {stdio: 'ignore', windowsHide: true});
      const exit = new Promise((done, reject) => { controller.once('error', reject); controller.once('exit', done); });
      let pids;
      for (let i = 0; i < 80 && !pids; i++) {
        try { pids = JSON.parse(await readFile(join(temp, 'pids.json'), 'utf8')); }
        catch { await delay(100); }
      }
      assert.ok(pids, 'Gateway should have started with its DSH child');
      const [gateway, dsh] = pids.map(String);
      const birth = await run('birth', gateway);
      assert.match(birth, /^\d+$/);
      assert.match(await run('birth', dsh), /^\d+$/);
      if (mode === 'crash') {
        process.kill(pids[0]);
        assert.equal(await exit, 1);
      } else {
        await assert.rejects(run('stop', config, gateway, 'wrong-birth'), /identity changed/);
        assert.equal(await run('birth', gateway), birth);
        await run('stop', config, gateway, birth);
        assert.equal(await exit, 0);
        if (mode === 'drain') assert.equal(await readFile(join(temp, 'drained'), 'utf8'), 'yes');
      }
      assert.equal(await run('birth', gateway), '');
      for (let i = 0; i < 40 && await run('birth', dsh); i++) await delay(50);
      assert.equal(await run('birth', dsh), '');
    }
  } finally {
    if (controller && controller.exitCode === null) controller.kill();
    await rm(temp, {force: true, recursive: true, maxRetries: 10, retryDelay: 100});
  }
});
