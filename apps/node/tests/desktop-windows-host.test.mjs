// Native Windows test for DesktopGatewayHost.exe isolation, birth verification,
// crash recovery, and clean takeover of feat-781 Crewden-Gateway-* tasks.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { execFile, spawn } from 'node:child_process';
import { mkdtemp, mkdir, copyFile, writeFile, readFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
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
  writeFileSync(join(root, 'pids.json'), JSON.stringify([process.pid, dsh.pid, process.env.CREWDEN_DESKTOP_MANAGED || '']));
  require('node:readline').createInterface({input: process.stdin}).on('line', line => {
    if (line === 'stop' && readFileSync(join(root, 'mode'), 'utf8') === 'drain') {
      writeFileSync(join(root, 'drained'), 'yes');
      process.exit();
    }
  });
`;

async function waitJson(path, attempts = 150) {
  for (let i = 0; i < attempts; i++) {
    try {
      return JSON.parse(await readFile(path, 'utf8'));
    } catch (error) {
      if (error.code !== 'ENOENT' && !(error instanceof SyntaxError)) throw error;
      await delay(100);
    }
  }
  throw new Error(`Timed out waiting for ${path}`);
}

function serve(host, config) {
  const proc = spawn(host, ['serve', config, '250'], { stdio: 'ignore', windowsHide: true });
  const exit = new Promise((done, reject) => {
    proc.once('error', reject);
    proc.once('exit', done);
  });
  return { process: proc, exit };
}

test(
  'DesktopGatewayHost isolates CrewdenDesktop tasks/pipes and cleanly retires standalone feat-781 tasks on takeover',
  { skip: process.platform !== 'win32', timeout: 120_000 },
  async () => {
    const temp = await mkdtemp(join(tmpdir(), 'CrewdenDesktopHost '));
    const sha = 'b'.repeat(64);
    const desktopRoot = join(temp, 'desktop', 'versions', sha);
    const cli = join(desktopRoot, 'apps', 'node', 'lib', 'cli.js');
    const desktopHost = join(dirname(cli), 'DesktopGatewayHost.exe');

    const standaloneSha = 'c'.repeat(64);
    const standaloneRoot = join(temp, 'standalone', 'versions', standaloneSha);
    const standaloneCli = join(standaloneRoot, 'apps', 'node', 'lib', 'cli.js');
    const standaloneHost = join(dirname(standaloneCli), 'GatewayHost.exe');

    const connDir = join(temp, 'conn');
    const config = join(connDir, 'config.yaml');
    const runDesktop = async (...args) =>
      (await exec(desktopHost, args, { windowsHide: true, timeout: 15_000 })).stdout.trim();
    const runStandalone = async (...args) =>
      (await exec(standaloneHost, args, { windowsHide: true, timeout: 15_000 })).stdout.trim();

    let controller;
    try {
      await mkdir(dirname(cli), { recursive: true });
      await mkdir(join(desktopRoot, 'runtime'), { recursive: true });
      await mkdir(connDir, { recursive: true });
      await writeFile(join(desktopRoot, '.ready'), sha);
      await copyFile(process.execPath, join(desktopRoot, 'runtime', 'node.exe'));
      await copyFile(resolve('dist/desktop-windows-build/DesktopGatewayHost.exe'), desktopHost);
      await writeFile(cli, fixture);
      await writeFile(
        join(dirname(cli), 'update-worker.js'),
        `
        const fs = require('node:fs'), path = require('node:path');
        const home = path.dirname(process.argv[2]);
        fs.writeFileSync(path.join(home, 'worker-result'), JSON.stringify({
          op: process.argv[3],
          desktopManaged: process.env.CREWDEN_DESKTOP_MANAGED
        }));
        process.exit(0);
      `,
      );
      await writeFile(config, '{}');
      await writeFile(join(connDir, 'mode'), 'drain');

      // 1. Verify standalone feat-781 coexistence & clean takeover without deleting .windows-active.json
      if (existsSync(resolve('dist/windows-build/GatewayHost.exe'))) {
        await mkdir(dirname(standaloneCli), { recursive: true });
        await mkdir(join(standaloneRoot, 'runtime'), { recursive: true });
        await writeFile(join(standaloneRoot, '.ready'), standaloneSha);
        await copyFile(process.execPath, join(standaloneRoot, 'runtime', 'node.exe'));
        await copyFile(resolve('dist/windows-build/GatewayHost.exe'), standaloneHost);
        await writeFile(standaloneCli, fixture);
        await writeFile(join(connDir, '.windows-active.json'), JSON.stringify({ sha256: standaloneSha }));

        await runStandalone('start', config, '250', 'true');
        const [legacyPid, legacyDsh] = await waitJson(join(connDir, 'pids.json'));
        assert.match(await runDesktop('birth', String(legacyPid)), /^\d+$/);

        assert.equal(await runDesktop('retire-standalone', config, String(legacyPid), ''), 'retired');
        for (let i = 0; i < 40 && (await runDesktop('birth', String(legacyPid))); i++) await delay(50);
        assert.equal(await runDesktop('birth', String(legacyPid)), '');
        for (let i = 0; i < 40 && (await runDesktop('birth', String(legacyDsh))); i++) await delay(50);
        assert.equal(await runDesktop('birth', String(legacyDsh)), '');
        // .windows-active.json must remain intact for Crewden.lnk coexistence
        assert.equal(
          JSON.parse(await readFile(join(connDir, '.windows-active.json'), 'utf8')).sha256,
          standaloneSha,
        );
        await rm(join(connDir, 'pids.json'), { force: true });
        await rm(join(connDir, 'drained'), { force: true });
      }

      // 2. Verify DesktopGatewayHost serve, birth check, worker launch, and graceful drain
      await writeFile(
        join(connDir, '.desktop-active.json'),
        JSON.stringify({ managed_by: 'crewden-desktop', sha256: sha, version_root: desktopRoot }),
      );
      controller = serve(desktopHost, config);
      const [gwPid, dshPid, managedFlag] = await waitJson(join(connDir, 'pids.json'));
      assert.equal(managedFlag, '1');
      const birth = await runDesktop('birth', String(gwPid));
      assert.match(birth, /^\d+$/);

      const op = randomUUID();
      await runDesktop('launch-worker', config, op, String(gwPid), birth);
      const workerResult = await waitJson(join(connDir, 'worker-result'));
      assert.equal(workerResult.op, op);
      assert.equal(workerResult.desktopManaged, '1');

      await assert.rejects(runDesktop('stop', config, String(gwPid), 'wrong-birth'), /identity changed/);
      await runDesktop('stop', config, String(gwPid), birth);
      assert.equal(await controller.exit, 0);
      assert.equal(await readFile(join(connDir, 'drained'), 'utf8'), 'yes');
      for (let i = 0; i < 40 && (await runDesktop('birth', String(dshPid))); i++) await delay(50);
      assert.equal(await runDesktop('birth', String(dshPid)), '');

      // 3. Verify Task Scheduler start + crash auto-recovery + autostart-off without stopping live job
      await rm(join(connDir, 'pids.json'), { force: true });
      assert.equal(await runDesktop('start', config, '250', 'true'), 'enabled');
      const [firstPid] = await waitJson(join(connDir, 'pids.json'));
      await rm(join(connDir, 'pids.json'), { force: true });
      process.kill(firstPid);
      const [recoveredPid] = await waitJson(join(connDir, 'pids.json'), 250);
      assert.notEqual(firstPid, recoveredPid);
      const recoveredBirth = await runDesktop('birth', String(recoveredPid));
      assert.equal(await runDesktop('autostart-off', config, '250', 'false'), 'disabled');
      // Turning off login autostart must not kill the currently running job
      assert.equal(await runDesktop('birth', String(recoveredPid)), recoveredBirth);
      await runDesktop('stop', config, String(recoveredPid), recoveredBirth);
    } finally {
      if (controller && controller.process.exitCode === null) controller.process.kill();
      await exec(
        'powershell.exe',
        [
          '-NoProfile',
          '-Command',
          'Get-ScheduledTask | Where-Object {$_.Actions.Execute -eq $env:TEST_DESKTOP_HOST -or $_.Actions.Execute -eq $env:TEST_STANDALONE_HOST} | Unregister-ScheduledTask -Confirm:$false',
        ],
        { env: { ...process.env, TEST_DESKTOP_HOST: desktopHost, TEST_STANDALONE_HOST: standaloneHost } },
      ).catch(() => {});
      await rm(temp, { force: true, recursive: true, maxRetries: 10, retryDelay: 100 });
    }
  },
);
