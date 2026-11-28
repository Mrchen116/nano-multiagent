import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { existsSync } from 'node:fs';
import { chmod, mkdir, mkdtemp, readFile, rename, rm, access } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import lockfile from 'proper-lockfile';
import {
  CURRENT_DESKTOP_SHELL_PROTOCOL,
  classifyOriginSecurity,
  normalizeReleaseBaseUrl,
  parseReleaseManifest,
  nodeUpdateTerminal,
  type DesktopPlatform,
  type NodeRelease,
  type NodeUpdateReport,
  type ParseReleaseManifestOptions,
  type ReleaseManifest,
} from '@nano/product-contracts';
import { NodeConfiguration } from './configuration.js';
import { applyGatewayEnvironment, atomicPrivate, defaultGatewayStartupSeconds, gatewayState, processBirth, type GatewayState } from './lifecycle.js';
import { readUpdateFile, reportUpdate, updatePath, validLease, type UpdateLease, type UpdateHandoff } from './node-updater.js';
import { loadNodeRelease, loadTrustedReleaseOptions, verifyReleaseMetadata } from './release.js';

const exec = promisify(execFile);
const CURL_BIN = process.platform === 'win32' && existsSync('C:\\Windows\\System32\\curl.exe')
  ? 'C:\\Windows\\System32\\curl.exe'
  : 'curl';
const TAR_BIN = process.platform === 'win32' && existsSync('C:\\Windows\\System32\\tar.exe')
  ? 'C:\\Windows\\System32\\tar.exe'
  : 'tar';
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const matches = (actual: NodeRelease | undefined | null, expected: NodeRelease | ReleaseManifest) =>
  !!actual && actual.platform === expected.platform && actual.version === expected.version
  && actual.sha256 === expected.sha256 && actual.source_commit === (expected.source_commit ?? expected.version)
  && (expected.shell_protocol === undefined || actual.shell_protocol === expected.shell_protocol);

function isDesktopPlatform(platform: string | undefined): platform is DesktopPlatform {
  return platform === 'desktop-darwin-arm64' || platform === 'desktop-win32-x64';
}

const GITHUB_RELEASE_PREFIX = 'https://github.com/Mrchen116/nano-multiagent/releases/download/';

function resolveDownloadUrl(url: string): string {
  const override = process.env.NANO_LOOPBACK_RELEASE_ORIGIN?.trim();
  if (override && url.startsWith(GITHUB_RELEASE_PREFIX)) {
    const parsed = new URL(override);
    if (parsed.protocol === 'http:' && (parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost')) {
      return `${parsed.origin}/${url.slice(GITHUB_RELEASE_PREFIX.length)}`;
    }
  }
  return url;
}

function curlProtoArgs(url: string, trustedOptions?: ParseReleaseManifestOptions): string[] {
  if (process.env.NANO_ALLOW_LOOPBACK_UPDATE_HTTP === '1' || process.env.NANO_LOOPBACK_RELEASE_ORIGIN) {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' && (parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost')) {
      return ['--proto', '=http,https', '--proto-redir', '=http,https'];
    }
  }
  const allowPrivateHttp = Boolean(trustedOptions?.allowPrivateHttpReleaseBase);
  for (const rawBase of trustedOptions?.trustedReleaseBaseUrls ?? []) {
    const normalizedBase = normalizeReleaseBaseUrl(rawBase, allowPrivateHttp);
    if (!normalizedBase || !url.startsWith(normalizedBase)) continue;
    const security = classifyOriginSecurity(normalizedBase);
    if (security.kind === 'loopback_http' || (allowPrivateHttp && security.kind === 'private_http')) {
      // Cleartext loopback/private self-hosted release feeds forbid cross-host/protocol redirects.
      return ['--proto', '=http,https', '--max-redirs', '0'];
    }
  }
  return ['--proto', '=https', '--proto-redir', '=https'];
}

async function downloadVerifiedAsset(
  rawUrl: string,
  dest: string,
  expectedSha256: string,
  signal?: AbortSignal,
  trustedOptions?: ParseReleaseManifestOptions,
): Promise<boolean> {
  const url = resolveDownloadUrl(rawUrl);
  if (existsSync(dest)) {
    const cachedDigest = createHash('sha256').update(await readFile(dest)).digest('hex');
    if (cachedDigest === expectedSha256) return true;
    await rm(dest, { force: true });
  }
  const tmp = `${dest}.part-${process.pid}-${Date.now()}`;
  try {
    await exec(
      CURL_BIN,
      ['--disable', '--fail', '--location', '--silent', '--show-error', '--retry', '2', ...curlProtoArgs(url, trustedOptions), url, '-o', tmp],
      { signal, timeout: 300000, windowsHide: true },
    );
    const actualDigest = createHash('sha256').update(await readFile(tmp)).digest('hex');
    if (actualDigest !== expectedSha256) {
      throw new Error(`Archive checksum mismatch for ${url}`);
    }
    await rename(tmp, dest);
    return false;
  } finally {
    await rm(tmp, { force: true }).catch(() => {});
  }
}

interface DesktopArchiveEntry {
  name: string;
  size: number;
  sha256: string;
  download_url: string;
}

interface DesktopDescriptor {
  version: string;
  source_commit: string;
  updater_protocol: 1;
  data_epoch: 1;
  shell_protocol: number;
  runtime: DesktopArchiveEntry;
  app: DesktopArchiveEntry;
}

/** Download and install a validated immutable Unix package without touching the running installation. */
export async function installRelease(
  target: ReleaseManifest,
  root: string,
  onInstalling: () => Promise<void>,
  signal?: AbortSignal,
  trustedOptions?: ParseReleaseManifestOptions,
): Promise<string> {
  const opts = trustedOptions ?? await loadTrustedReleaseOptions(root);
  if (target.package !== 'nano-node.tgz' || !parseReleaseManifest(target, opts) || target.updater_protocol !== 1 || target.data_epoch !== 1) throw new Error('Incompatible release');
  await mkdir(join(root, 'releases'), {recursive: true});
  const release = join(root, 'releases', target.sha256);
  try { await access(join(release, '.installed')); await verifyReleaseMetadata(release, target); await onInstalling(); return release; }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error; }
  const stage = await mkdtemp(join(root, 'releases', '.update-'));
  try {
    const archive = join(stage, 'package.tgz');
    await exec('curl', ['--disable', '--fail', '--location', '--silent', '--show-error', '--retry', '2', ...curlProtoArgs(target.download_url, opts), target.download_url, '-o', archive], {signal, timeout: 300000});
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
      if (!['ENOTEMPTY', 'EEXIST'].includes((error as NodeJS.ErrnoException).code ?? '')) throw error;
      await verifyReleaseMetadata(release, target); await access(join(release, '.installed'));
    }
    return release;
  } finally { await rm(stage, {recursive: true, force: true}); }
}

/** Prepare the operation's pinned version with the current Windows lightweight bootstrap. */
async function prepareWindowsUpdate(target: ReleaseManifest, oldEntry: string, origin: string, signal: AbortSignal) {
  const oldRoot = resolve(dirname(oldEntry), '../../..');
  const versionRoot = resolve(oldRoot, '..', target.sha256);
  await exec(join(oldRoot, 'Crewden.exe'), ['prepare', new URL(origin).origin, target.sha256], {
    signal, timeout: 600000, windowsHide: true,
  });
  const installed = await loadNodeRelease(versionRoot);
  if (installed.platform !== 'win32-x64' || !matches(installed, target))
    throw new Error('The prepared Windows installation does not match the selected target');
  return versionRoot;
}

/** Prepare a Desktop split-archive (`runtime` + `app` + `ui/`) release while reusing cached `runtime` bytes. */
export async function prepareDesktopUpdate(
  target: ReleaseManifest,
  oldEntry: string,
  onInstalling: () => Promise<void>,
  signal?: AbortSignal,
  trustedOptions?: ParseReleaseManifestOptions,
): Promise<{ versionRoot: string; runtimeReused: boolean }> {
  if (!isDesktopPlatform(target.platform) || target.shell_protocol !== CURRENT_DESKTOP_SHELL_PROTOCOL || target.updater_protocol !== 1 || target.data_epoch !== 1) {
    throw new Error('Incompatible desktop release');
  }
  const oldVersionRoot = resolve(dirname(oldEntry), '../../..');
  const opts = trustedOptions ?? await loadTrustedReleaseOptions(oldVersionRoot);
  const desktopHome = resolve(process.env.CREWDEN_DESKTOP_HOME ?? resolve(oldVersionRoot, '../..'));
  const cacheDir = join(desktopHome, 'cache');
  const runtimesDir = join(desktopHome, 'runtimes');
  const versionsDir = join(desktopHome, 'versions');
  await mkdir(cacheDir, { recursive: true });
  await mkdir(runtimesDir, { recursive: true });
  await mkdir(versionsDir, { recursive: true });

  const finalVersionRoot = join(versionsDir, target.sha256);
  if (existsSync(join(finalVersionRoot, '.ready'))) {
    const installed = await loadNodeRelease(finalVersionRoot);
    if (matches(installed, target)) {
      await onInstalling();
      return { versionRoot: finalVersionRoot, runtimeReused: true };
    }
  }

  const descriptorPath = join(cacheDir, `descriptor-${target.sha256}.json`);
  await downloadVerifiedAsset(target.download_url, descriptorPath, target.sha256, signal, opts);
  const desc = JSON.parse(await readFile(descriptorPath, 'utf8')) as DesktopDescriptor;
  const base = target.download_url.slice(0, target.download_url.lastIndexOf('/') + 1);
  if (
    desc.version !== target.version ||
    desc.source_commit !== (target.source_commit ?? target.version) ||
    desc.updater_protocol !== 1 ||
    desc.data_epoch !== 1 ||
    desc.shell_protocol !== CURRENT_DESKTOP_SHELL_PROTOCOL ||
    !/^[a-f0-9]{64}$/.test(desc.runtime?.sha256 ?? '') ||
    !/^[a-f0-9]{64}$/.test(desc.app?.sha256 ?? '') ||
    desc.runtime.download_url !== base + desc.runtime.name ||
    desc.app.download_url !== base + desc.app.name
  ) {
    throw new Error('Invalid desktop release descriptor');
  }

  const finalRuntimeRoot = join(runtimesDir, desc.runtime.sha256);
  let runtimeReused = existsSync(join(finalRuntimeRoot, '.ready'));
  if (!runtimeReused) {
    const runtimeArchive = join(cacheDir, `${desc.runtime.sha256}-${desc.runtime.name}`);
    runtimeReused = await downloadVerifiedAsset(desc.runtime.download_url, runtimeArchive, desc.runtime.sha256, signal, opts);
    const runtimeStage = await mkdtemp(join(runtimesDir, '.runtime-stage-'));
    try {
      await exec(TAR_BIN, ['-xzf', runtimeArchive, '-C', runtimeStage], { signal, windowsHide: true });
      const nodeBin = join(runtimeStage, process.platform === 'win32' ? 'node.exe' : 'bin/node');
      if (process.platform !== 'win32' && existsSync(nodeBin)) {
        await chmod(nodeBin, 0o755);
      }
      if (existsSync(join(runtimeStage, 'layout.mjs'))) {
        await exec(existsSync(nodeBin) ? nodeBin : process.execPath, [join(runtimeStage, 'layout.mjs'), 'runtime', runtimeStage, finalRuntimeRoot], { signal, windowsHide: true });
      }
      await atomicPrivate(join(runtimeStage, '.ready'), '');
      try {
        await rename(runtimeStage, finalRuntimeRoot);
      } catch (error) {
        if (!['ENOTEMPTY', 'EEXIST'].includes((error as NodeJS.ErrnoException).code ?? '')) throw error;
      }
    } finally {
      await rm(runtimeStage, { recursive: true, force: true }).catch(() => {});
    }
  }

  const appArchive = join(cacheDir, `${desc.app.sha256}-${desc.app.name}`);
  await downloadVerifiedAsset(desc.app.download_url, appArchive, desc.app.sha256, signal, opts);
  await onInstalling();

  const versionStage = await mkdtemp(join(versionsDir, '.version-stage-'));
  const appExtract = await mkdtemp(join(versionsDir, '.app-extract-'));
  try {
    await exec(TAR_BIN, ['-xzf', appArchive, '-C', appExtract], { signal, windowsHide: true });
    const nodeBin = join(finalRuntimeRoot, process.platform === 'win32' ? 'node.exe' : 'bin/node');
    const execNode = existsSync(nodeBin) ? nodeBin : process.execPath;
    const layoutScript = join(finalRuntimeRoot, 'layout.mjs');
    if (existsSync(layoutScript)) {
      await exec(execNode, [layoutScript, 'version', versionStage, finalVersionRoot, finalRuntimeRoot, appExtract], { signal, windowsHide: true });
    } else {
      await rename(appExtract, versionStage);
    }
    await atomicPrivate(join(versionStage, '.release-manifest.json'), target);
    await verifyReleaseMetadata(versionStage, target);
    try {
      await rename(versionStage, finalVersionRoot);
    } catch (error) {
      if (!['ENOTEMPTY', 'EEXIST'].includes((error as NodeJS.ErrnoException).code ?? '')) throw error;
    }
    if (!existsSync(join(finalVersionRoot, '.ready'))) {
      try {
        if (existsSync(layoutScript) && existsSync(join(finalVersionRoot, 'workspaces.json'))) {
          await exec(execNode, [layoutScript, 'verify', finalVersionRoot], { signal, timeout: 60000, windowsHide: true });
        }
        await atomicPrivate(join(finalVersionRoot, '.ready'), `${target.sha256}\n`);
      } catch (verifyError) {
        await rm(finalVersionRoot, { recursive: true, force: true }).catch(() => {});
        throw verifyError;
      }
    }
    return { versionRoot: finalVersionRoot, runtimeReused };
  } finally {
    await rm(versionStage, { recursive: true, force: true }).catch(() => {});
    await rm(appExtract, { recursive: true, force: true }).catch(() => {});
  }
}

async function notifyDesktopHostReload(desktopHome: string, imUrl: string): Promise<void> {
  try {
    const stateRaw = await readFile(join(desktopHome, 'host-state.json'), 'utf8');
    const hostState = JSON.parse(stateRaw) as { port?: number; reload_token?: string };
    if (hostState.port && hostState.reload_token) {
      await fetch(`http://127.0.0.1:${hostState.port}/desktop/internal/reload-assets`, {
        method: 'POST',
        headers: { 'x-crewden-reload-token': hostState.reload_token, 'x-crewden-im-origin': new URL(imUrl).origin },
        signal: AbortSignal.timeout(3000),
      }).catch(() => {});
    }
  } catch {
    // Host also watches .desktop-active.json directly or may not be running in headless tests.
  }
}

/** Execute an authorized update under one config-scoped lock, independently of the Node it replaces. */
export async function runUpdate(configPath: string, operationId: string): Promise<void> {
  const config = await NodeConfiguration.read(resolve(configPath));
  if (process.platform === 'win32') applyGatewayEnvironment(config.value);
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
    if (lease.state !== 'switching') await send('resume', {resumed: true});
  };
  const terminal = async (state: UpdateLease['state'], error_code?: string, resumed?: boolean) => {
    await send('terminal', {state, error_code, resumed}); lease.state = state; delete lease.command; await write();
  };
  const startupSeconds = config.value.gateway?.startup_timeout_seconds ?? defaultGatewayStartupSeconds;
  const cli = async (state: Pick<GatewayState, 'entry' | 'node_exec'>, action: string) => {
    const timeout = process.platform === 'win32' && action === 'start' ? Math.max(120, startupSeconds + 30) * 1000 : 120000;
    await exec(state.node_exec!, [state.entry!, action, '--config', config.path], {timeout, maxBuffer: 1024 * 1024, windowsHide: true});
  };
  const verify = async (expected: NodeRelease | ReleaseManifest, previousPid: number) => {
    const deadline = Date.now() + startupSeconds * 1000;
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
    const trustedOptions = await loadTrustedReleaseOptions(resolve(dirname(old.entry), '../../..'));
    const target = parseReleaseManifest(report.operation.target, trustedOptions);
    const desktop = isDesktopPlatform(target?.platform);
    const windows = target?.platform === 'win32-x64';
    const expectedWinHost = windows || target?.platform === 'desktop-win32-x64';
    if (!target || target.platform !== old.release.platform || expectedWinHost !== (process.platform === 'win32')
        || (target.platform === 'desktop-darwin-arm64' && process.platform !== 'darwin')
        || target.data_epoch !== old.release.data_epoch || target.updater_protocol !== 1
        || (desktop && (target.shell_protocol !== CURRENT_DESKTOP_SHELL_PROTOCOL || old.release.shell_protocol !== target.shell_protocol))) {
      throw new Error('Incompatible target');
    }
    await write();
    heartbeat = setInterval(() => { void write().catch(() => abort.abort()); }, 1000);
    let polling = false;
    poller = setInterval(() => {
      if (polling) return; polling = true;
      void send('poll').then(r => { if (r.operation.cancel_requested && !switched) abort.abort(); }).catch(() => {}).finally(() => {polling = false;});
    }, 3000);
    if (report.operation.cancel_requested) { await terminal('cancelled', undefined, true); return; }
    await phase('downloading');
    let targetRoot: string;
    let runtimeReused = false;
    if (desktop) {
      const prepared = await prepareDesktopUpdate(target, old.entry, () => phase('installing'), abort.signal, trustedOptions);
      targetRoot = prepared.versionRoot;
      runtimeReused = prepared.runtimeReused;
    } else if (windows) {
      targetRoot = await prepareWindowsUpdate(target, old.entry, config.value.im_service.url, abort.signal);
      await phase('installing');
    } else {
      targetRoot = await installRelease(target, resolve(dirname(old.entry), '../../../../..'), () => phase('installing'), abort.signal, trustedOptions);
    }
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

      const oldVersionRoot = resolve(dirname(old.entry), '../../..');
      const desktopHome = resolve(process.env.CREWDEN_DESKTOP_HOME ?? resolve(oldVersionRoot, '../..'));
      const switchPath = updatePath(config.path, desktop ? '.desktop-switch.json' : '.windows-switch.json');
      const activePath = updatePath(config.path, desktop ? '.desktop-active.json' : '.windows-active.json');
      if (windows || desktop) await atomicPrivate(switchPath, {
        operation_id: operationId, worker_pid: process.pid, worker_birth: birth,
        previous_sha256: old.release.sha256, target_sha256: target.sha256,
      });
      switched = true;
      const desktopNodeExec = join(targetRoot, process.platform === 'win32' ? 'runtime/node.exe' : 'runtime/bin/node');
      const targetProcess = {
        entry: join(targetRoot, 'apps/node/lib/cli.js'),
        node_exec: desktop
          ? (existsSync(desktopNodeExec) ? desktopNodeExec : old.node_exec)
          : windows
            ? join(targetRoot, 'runtime', 'node.exe')
            : process.execPath,
      };
      try {
        await cli(old, 'stop');
        if (desktop) {
          await atomicPrivate(activePath, {
            managed_by: 'crewden-desktop',
            sha256: target.sha256,
            version: target.version,
            version_root: targetRoot,
            ui_root: join(targetRoot, 'ui'),
            runtime_reused: runtimeReused,
            updated_at: new Date().toISOString(),
          });
        }
        await cli(targetProcess, 'start');
        await phase('verifying');
        await verify(target, old.pid);
        if (windows) {
          await atomicPrivate(activePath, {sha256: target.sha256});
          await rm(switchPath, {force: true});
        } else if (desktop) {
          await rm(switchPath, {force: true});
          await notifyDesktopHostReload(desktopHome, config.value.im_service.url);
        }
        await terminal('succeeded').catch(async () => {
          await terminal('succeeded').catch(error => console.error(error));
        });
      } catch (error) {
        console.error(error);
        await phase('rolling_back').catch(error => console.error(error));
        try {
          const failed = await gatewayState(config.path);
          await cli(targetProcess, 'stop').catch(() => {});
          if (windows) {
            await atomicPrivate(activePath, {sha256: old.release.sha256});
          } else if (desktop) {
            await atomicPrivate(activePath, {
              managed_by: 'crewden-desktop',
              sha256: old.release.sha256,
              version: old.release.version,
              version_root: oldVersionRoot,
              ui_root: join(oldVersionRoot, 'ui'),
              updated_at: new Date().toISOString(),
            });
            await notifyDesktopHostReload(desktopHome, config.value.im_service.url);
          }
          await cli(old, 'start');
          await verify(old.release!, failed?.pid ?? old.pid);
          if (windows || desktop) await rm(switchPath, {force: true});
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
