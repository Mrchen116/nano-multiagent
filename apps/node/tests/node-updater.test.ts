import { createServer } from 'node:http';
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chmod, mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { installedPackageManager, loadNodeRelease } from '../src/release.js';
import { installRelease } from '../src/update-worker.js';
import { NodeUpdater, updatePath, type UpdateLease } from '../src/node-updater.js';
import { atomicPrivate, processBirth } from '../src/lifecycle.js';
import type { NodeConfiguration } from '../src/configuration.js';
import type { ReleaseManifest } from '@nano/product-contracts';
const manifest = (): ReleaseManifest => ({version: '1.2.3', source_commit: 'a'.repeat(40), sha256: 'b'.repeat(64),
  download_url: 'https://github.com/Mrchen116/nano-multiagent/releases/download/v1.2.3/nano-node.tgz',
  package: 'nano-node.tgz', node_major: 24, pnpm_version: '11.7.0', updater_protocol: 1, data_epoch: 1});

it('distinguishes source installs and refuses mismatched managed package identity', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-release-'));
  try {
    expect(await loadNodeRelease(root)).toEqual({kind: 'source', version: 'source'});
    expect(installedPackageManager(await loadNodeRelease(root), root)).toBeUndefined();
    await writeFile(join(root, '.release-manifest.json'), JSON.stringify(manifest()));
    await writeFile(join(root, '.nano-release.json'), JSON.stringify({source_commit: 'c'.repeat(40), updater_protocol: 1, data_epoch: 1}));
    await expect(loadNodeRelease(root)).rejects.toThrow('metadata');
    await writeFile(join(root, '.nano-release.json'), JSON.stringify({source_commit: 'a'.repeat(40), updater_protocol: 1, data_epoch: 1}));
    expect(await loadNodeRelease(root)).toMatchObject({kind: 'managed', version: '1.2.3', sha256: 'b'.repeat(64)});
  } finally { await rm(root, {recursive: true, force: true}); }
});

it('verifies fixed HTTPS download and build metadata before dependency installation', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-download-'));
  const previousPath = process.env.PATH;
  try {
    const payload = join(root, 'payload'), bin = join(root, 'bin');
    await mkdir(payload); await mkdir(bin); await mkdir(join(root, 'tooling/node_modules/pnpm/bin'), {recursive: true});
    await writeFile(join(payload, '.nano-release.json'), JSON.stringify({source_commit: 'a'.repeat(40), updater_protocol: 1, data_epoch: 1}));
    await writeFile(join(payload, 'package.json'), '{}');
    const archive = join(root, 'fixture.tgz'); execFileSync('tar', ['-czf', archive, '-C', payload, '.']);
    const target = {...manifest(), sha256: createHash('sha256').update(await readFile(archive)).digest('hex')};
    await writeFile(join(root, 'tooling/node_modules/pnpm/bin/pnpm.cjs'), 'require("fs").writeFileSync("dependency-installed", "yes")');
    await writeFile(join(bin, 'curl'), `#!${process.execPath}\nconst fs=require('fs');const a=process.argv.slice(2);if(!a.includes('${target.download_url}')||a[a.indexOf('--proto')+1]!=='=https'||a[a.indexOf('--proto-redir')+1]!=='=https')process.exit(8);fs.copyFileSync(${JSON.stringify(archive)},a[a.indexOf('-o')+1]);`);
    await chmod(join(bin, 'curl'), 0o700); process.env.PATH = `${bin}:${previousPath}`;
    const installed = await installRelease(target, root, async () => {});
    expect(await readFile(join(installed, 'dependency-installed'), 'utf8')).toBe('yes');
    const release = await loadNodeRelease(installed);
    expect(release).toMatchObject({sha256: target.sha256});
    const manager = installedPackageManager(release, installed)!;
    await rm(join(installed, 'dependency-installed'));
    execFileSync(manager.command, [...manager.args, '--version'], {cwd: installed, env: {PATH: '', ...manager.env}});
    expect(await readFile(join(installed, 'dependency-installed'), 'utf8')).toBe('yes');
    await expect(installRelease({...target, sha256: 'c'.repeat(64)}, root, async () => {})).rejects.toThrow('checksum');
    await expect(installRelease({...target, download_url: 'https://attacker.example/package'}, root, async () => {})).rejects.toThrow('Incompatible');
  } finally { process.env.PATH = previousPath; await rm(root, {recursive: true, force: true}); }
});

it('releases a prepared barrier after real worker death without launching replacement work', async () => {
  const root = await mkdtemp(join(tmpdir(), 'nano-update-lease-'));
  const worker = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], {stdio: 'ignore'});
  await new Promise(resolve => worker.once('spawn', resolve));
  let prepare = 0, resume = 0;
  const reports: Record<string, unknown>[] = [];
  const server = createServer((req, res) => { let text = ''; req.on('data', b => text += b); req.on('end', () => {
    reports.push(JSON.parse(text)); res.setHeader('Content-Type', 'application/json'); res.end('{}');
  }); });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = (server.address() as {port: number}).port;
  const config = {path: join(root, 'config.yaml'), value: {node: {node_id: 'test'}, im_service: {url: `http://127.0.0.1:${port}`, token: 'test'}}} as NodeConfiguration;
  const updater = new NodeUpdater(config, {prepare: async () => {prepare++; return true;}, resume: async () => {resume++;}});
  try {
    const lease: UpdateLease = {operation_id: 'op', worker_pid: worker.pid!, worker_birth: (await processBirth(worker.pid!))!, heartbeat: Date.now(), state: 'waiting', command: 'prepare', sequence: 1};
    await atomicPrivate(updatePath(config.path), lease);
    await updater.start();
    expect(prepare).toBe(1);
    expect(JSON.parse(await readFile(updatePath(config.path, '.node-update-handoff.json'), 'utf8')).ready).toBe(true);
    worker.kill('SIGKILL');
    await expect.poll(() => reports.length, {timeout: 4000}).toBe(1);
    expect(resume).toBe(1);
    expect(reports[0]).toMatchObject({action: 'terminal', state: 'interrupted', resumed: true});
    await expect(readFile(updatePath(config.path, '.node-update-handoff.json'))).rejects.toThrow();
    expect(prepare).toBe(1);
  } finally { await updater.close(); worker.kill(); server.close(); await rm(root, {recursive: true, force: true}); }
});
