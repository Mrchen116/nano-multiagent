import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, readFile, rename, rm, access } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import lockfile from 'proper-lockfile';
import { parseReleaseManifest, nodeUpdateTerminal, type NodeRelease, type NodeUpdateReport, type ReleaseManifest } from '@nano/product-contracts';
import { NodeConfiguration } from './configuration.js';
import { atomicPrivate, gatewayState, processBirth, type GatewayState } from './lifecycle.js';
import { readUpdateFile, reportUpdate, updatePath, validLease, type UpdateLease, type UpdateHandoff } from './node-updater.js';
import { verifyReleaseMetadata } from './release.js';
const exec = promisify(execFile);
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const matches = (actual: NodeRelease | undefined | null, expected: NodeRelease | ReleaseManifest) =>
  !!actual && actual.version === expected.version && actual.sha256 === expected.sha256 && actual.source_commit === (expected.source_commit ?? expected.version);

/** Download and install a validated immutable package without touching the running installation. */
export async function installRelease(target: ReleaseManifest, root: string, onInstalling: () => Promise<void>, signal?: AbortSignal): Promise<string> {
  if (!parseReleaseManifest(target) || target.updater_protocol !== 1 || target.data_epoch !== 1) throw new Error('Incompatible release');
  await mkdir(join(root, 'releases'), {recursive: true});
  const release = join(root, 'releases', target.sha256);
  try { await access(join(release, '.installed')); await verifyReleaseMetadata(release, target); await onInstalling(); return release; }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  const stage = await mkdtemp(join(root, 'releases', '.update-'));
  try {
    const archive = join(stage, 'package.tgz');
    await exec('curl', ['--disable', '--fail', '--location', '--silent', '--show-error', '--retry', '2', '--proto', '=https', '--proto-redir', '=https', target.download_url, '-o', archive], {signal, timeout: 300000});
    if (createHash('sha256').update(await readFile(archive)).digest('hex') !== target.sha256) throw new Error('Package checksum mismatch');
    const payload = join(stage, 'payload'); await mkdir(payload);
    await exec('tar', ['-xzf', archive, '-C', payload], {signal});
    await verifyReleaseMetadata(payload, target);
    await onInstalling();
    const pnpm = join(root, 'tooling/node_modules/pnpm/bin/pnpm.cjs');
    await exec(process.execPath, [pnpm, 'install', '--prod', '--frozen-lockfile'], {cwd: payload, signal, timeout: 600000, maxBuffer: 10 * 1024 * 1024});
    await atomicPrivate(join(payload, '.release-manifest.json'), target);
    await atomicPrivate(join(payload, '.installed'), '');
    try { await rename(payload, release); }
    catch (error) {
      // Another config may have installed the identical content-addressed release.
      if (!['ENOTEMPTY', 'EEXIST'].includes((error as NodeJS.ErrnoException).code ?? '')) throw error;
      await verifyReleaseMetadata(release, target); await access(join(release, '.installed'));
    }
    return release;
  } finally { await rm(stage, {recursive: true, force: true}); }
}

/** Execute an authorized update under one config-scoped lock, independently of the Node it replaces. */
export async function runUpdate(configPath: string, operationId: string): Promise<void> {
  const config = await NodeConfiguration.read(resolve(configPath));
  const unlock = await lockfile.lock(config.path, {realpath: false, lockfilePath: updatePath(config.path, '.node-update.lock'), stale: 15000, update: 1000});
  let heartbeat: NodeJS.Timeout | undefined;
  let poller: NodeJS.Timeout | undefined;
  let journalWrite = Promise.resolve();
  let switched = false;
  let gated = false;
  let old: GatewayState | undefined;
  let report: NodeUpdateReport;
  const abort = new AbortController();
  const birth = await processBirth(process.pid);
  const lease: UpdateLease = {operation_id: operationId, worker_pid: process.pid, worker_birth: birth!, heartbeat: Date.now(), state: 'requested', sequence: 0};
  const write = () => { lease.heartbeat = Date.now(); const snapshot = {...lease}; journalWrite = journalWrite.then(() => atomicPrivate(updatePath(config.path), snapshot)); return journalWrite; };
  const send = async (action: string, extra: Parameters<typeof reportUpdate>[3] = {}) => {
    report = await reportUpdate(config, operationId, action, extra); return report;
  };
  const phase = async (state: UpdateLease['state']) => { lease.state = state; await write(); await send('progress', {state}); };
  const command = async (value: 'prepare' | 'resume'): Promise<UpdateHandoff> => {
    lease.command = value; lease.sequence++; await write();
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      const h = await readUpdateFile<UpdateHandoff>(updatePath(config.path, '.node-update-handoff.json'));
      if (h?.operation_id === operationId && h.sequence === lease.sequence && h.worker_pid === process.pid && h.worker_birth === birth
          && await processBirth(h.node_pid) === h.node_birth) return h;
      await delay(100);
    }
    throw new Error('Node barrier response timed out');
  };
  const resume = async () => {
    await command('resume'); gated = false;
    // After claim_switch only an interrupted terminal ACK may reopen the IM gate.
    if (lease.state !== 'switching') await send('resume', {resumed: true});
  };
  const terminal = async (state: UpdateLease['state'], error_code?: string, resumed?: boolean) => {
    await send('terminal', {state, error_code, resumed}); lease.state = state; delete lease.command; await write();
  };
  const cli = async (state: Pick<GatewayState, 'entry' | 'node_exec'>, action: string) => {
    await exec(state.node_exec!, [state.entry!, action, '--config', config.path], {timeout: 120000, maxBuffer: 1024 * 1024});
  };
  const verify = async (expected: NodeRelease | ReleaseManifest, previousPid: number) => {
    const deadline = Date.now() + (config.value.gateway?.startup_timeout_seconds ?? 60) * 1000;
    while (Date.now() < deadline) {
      const state = await gatewayState(config.path);
      if (state && state.pid !== previousPid && state.config_path === config.path && state.ready && state.connected && state.runtime_pid
          && await processBirth(state.pid) === state.process_start && await processBirth(state.runtime_pid) && matches(state.release, expected)) {
        const r = await send('poll');
        if (r.registered.online && matches(r.registered.release, expected)) return;
      }
      await delay(500);
    }
    throw new Error('Updated process did not become ready and register the expected release');
  };
  try {
    if (!birth) throw new Error('Cannot establish updater process identity');
    report = await send('poll');
    if (nodeUpdateTerminal(report.operation.state)) return;
    if (!['requested', 'downloading', 'installing', 'waiting'].includes(report.operation.state)) throw new Error('Interrupted switch requires recovery');
    old = await gatewayState(config.path);
    if (!old?.entry || !old.node_exec || old.release?.kind !== 'managed' || old.release.updater_protocol !== 1
        || await processBirth(old.pid) !== old.process_start) throw new Error('Running Node does not support safe updates');
    const target = parseReleaseManifest(report.operation.target);
    if (!target || target.data_epoch !== old.release.data_epoch || target.updater_protocol !== 1) throw new Error('Incompatible target');
    await write();
    heartbeat = setInterval(() => { void write().catch(() => abort.abort()); }, 1000);
    let polling = false;
    poller = setInterval(() => {
      if (polling) return; polling = true;
      void send('poll').then(r => { if (r.operation.cancel_requested && !switched) abort.abort(); }).catch(() => {}).finally(() => {polling = false;});
    }, 3000);
    if (report.operation.cancel_requested) { await terminal('cancelled', undefined, true); return; }
    await phase('downloading');
    const installRoot = resolve(dirname(old.entry), '../../../../..');
    const targetRoot = await installRelease(target, installRoot, () => phase('installing'), abort.signal);
    await phase('waiting');
    for (;;) {
      const r = await send('poll');
      if (r.operation.cancel_requested) { await terminal('cancelled', undefined, true); return; }
      await send('prepare'); gated = true;
      const h = await command('prepare');
      if (!h.ready) { await resume(); await delay(1000); continue; }
      const validHandoff = async () => {
        const current = await readUpdateFile<UpdateHandoff>(updatePath(config.path, '.node-update-handoff.json'));
        const currentLease = await readUpdateFile<UpdateLease>(updatePath(config.path));
        return currentLease?.operation_id === operationId && currentLease.worker_pid === process.pid
          && currentLease.worker_birth === birth && await validLease(currentLease) && current?.ready && current.operation_id === operationId && current.sequence === h.sequence
          && current.node_pid === old!.pid && current.node_birth === old!.process_start
          && await processBirth(old!.pid) === old!.process_start;
      };
      if (!await validHandoff()) throw new Error('Update barrier expired');
      try { await send('claim_switch'); }
      catch (error) {
        const latest = await send('poll');
        if (latest.operation.state !== 'switching') { await resume(); if (latest.operation.cancel_requested) { await terminal('cancelled', undefined, true); return; } throw error; }
      }
      lease.state = 'switching'; await write();
      if (!await validHandoff()) throw new Error('Update barrier expired before stop');
      delete lease.command; await write();
      switched = true;
      const targetProcess = {entry: join(targetRoot, 'apps/node/lib/cli.js'), node_exec: process.execPath};
      try {
        await cli(old, 'stop');
        await cli(targetProcess, 'start');
        await phase('verifying');
        await verify(target, old.pid);
        // A lost completion ACK must not undo a verified switch that IM may already have accepted.
        await terminal('succeeded').catch(async () => {
          await terminal('succeeded').catch(error => console.error(error));
        });
      } catch (error) {
        console.error(error);
        await phase('rolling_back').catch(error => console.error(error));
        try {
          const failed = await gatewayState(config.path);
          await cli(targetProcess, 'stop');
          await cli(old, 'start');
          await verify(old.release!, failed?.pid ?? old.pid);
          await terminal('rolled_back', 'start_failed');
        } catch (rollbackError) { console.error(rollbackError); await terminal('recovery_required', 'rollback_failed'); }
      }
      return;
    }
  } catch (error) {
    console.error(error);
    if (!switched) {
      let resumed = !gated;
      if (gated) { try { await resume(); resumed = true; } catch {} }
      const cancelled = (await send('poll').catch(() => undefined))?.operation.cancel_requested;
      await terminal(resumed ? cancelled ? 'cancelled' : lease.state === 'switching' ? 'interrupted' : 'failed' : 'interrupted', cancelled ? undefined : 'update_failed', resumed).catch(() => {});
    }
  } finally {
    clearInterval(heartbeat); clearInterval(poller);
    await journalWrite;
    await unlock();
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runUpdate(process.argv[2]!, process.argv[3]!).catch(error => { console.error(error); process.exitCode = 1; });
}
