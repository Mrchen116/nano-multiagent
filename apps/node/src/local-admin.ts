import { access, constants, lstat, readFile, realpath } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { homedir, hostname } from 'node:os';
import { delimiter, dirname, isAbsolute, join, resolve, sep } from 'node:path';
import {
  extractDesktopProxySettings,
  isBlockedDesktopOpenPath,
  mergeDesktopEnvironment,
  type DesktopBrowserActionInput,
  type DesktopBrowserActionResponse,
  type DesktopLocalConfigInput,
  type DesktopLocalInspectResponse,
  type DesktopWorkerProbeItem,
} from '@nano/product-contracts';
import { findWindowsWorker } from '@nano/dsh-integration/client';
import { bootstrapNode } from './bootstrap.js';
import {
  BrowserPairingRequestError,
  handleNodeBrowserRequest,
  inspectDailyBrowserStatus,
  type BrowserPairingDeps,
} from './browser-pairing.js';
import { NodeConfiguration, type NodeConfigurationFile } from './configuration.js';
import { bindDevice } from './device-binding.js';
import { applyGatewayEnvironment, atomicPrivate, browserPairingFile, gatewayState, manageGateway, processBirth } from './lifecycle.js';
import { localNodeBridgeEndpoint } from './local-bridge.js';
import { isPathWithinRoot } from './platform-io.js';
import { windowsHost } from './windows-platform.js';
import net from 'node:net';

export class LocalAdminHttpError extends Error {
  constructor(
    readonly status: number,
    readonly errorCode: string,
    message: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
  }
}

/** Resolve the connection `config.yaml` path for one IM origin without creating files on disk. */
export function connectionConfigPathForOrigin(origin: string, explicitConfigPath?: string): string {
  if (explicitConfigPath) return resolve(explicitConfigPath);
  const url = new URL(origin);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
    throw new LocalAdminHttpError(400, 'invalid_origin', 'Use the HTTP(S) address of your Nano IM service');
  }
  const root = resolve(process.env.NANO_INSTALL_ROOT ?? join(homedir(), '.nanoassistant'));
  const connection = createHash('sha256').update(url.origin).digest('hex').slice(0, 16);
  return resolve(join(root, 'connections', connection, 'config.yaml'));
}

export const desktopActiveFilePath = (configPath: string) => join(dirname(configPath), '.desktop-active.json');

const DEFAULT_SERVICE_PATH = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin';

/** Probe local CLI worker runtimes using the configured worker search path. */
export async function probeDesktopWorkers(candidatePath?: string): Promise<DesktopWorkerProbeItem[]> {
  const mergedSegments = [
    ...(candidatePath ? candidatePath.split(delimiter) : []),
    ...DEFAULT_SERVICE_PATH.split(delimiter),
    ...(process.env.PATH ? process.env.PATH.split(delimiter) : []),
  ]
    .map(segment => segment.trim())
    .filter(Boolean);
  const uniqueDirs = [...new Set(mergedSegments)];

  const findBinary = async (binary: string): Promise<string | null> => {
    if (process.platform === 'win32') return findWindowsWorker(binary, candidatePath ?? process.env.PATH ?? '');
    for (const dir of uniqueDirs) {
      const full = join(dir, binary);
      try {
        await access(full, constants.X_OK);
        const stat = await lstat(full);
        if (stat.isFile() || stat.isSymbolicLink()) return full;
      } catch {
        // Try next directory.
      }
    }
    return null;
  };

  const [codexPath, claudePath, agyPath] = await Promise.all([
    findBinary('codex'),
    findBinary('claude'),
    findBinary('agy'),
  ]);
  return [
    {
      runtime: 'dsh',
      available: true,
      resolved_path: process.execPath,
      detail: '内置受管 DSH 运行时已就绪',
    },
    {
      runtime: 'codex',
      available: codexPath !== null,
      resolved_path: codexPath,
      detail: codexPath ? `已检测到 · ${codexPath}` : '未在当前 PATH 中找到 codex',
    },
    {
      runtime: 'claude',
      available: claudePath !== null,
      resolved_path: claudePath,
      detail: claudePath ? `已检测到 · ${claudePath}` : '未在当前 PATH 中找到 claude',
    },
    {
      runtime: 'antigravity',
      available: agyPath !== null,
      resolved_path: agyPath,
      detail: agyPath ? `已检测到 · ${agyPath}` : '未在当前 PATH 中找到 agy',
    },
  ];
}

async function pingBridgeActiveTasks(configPath: string): Promise<number> {
  const endpoint = localNodeBridgeEndpoint(configPath);
  return new Promise<number>(resolvePromise => {
    const socket = net.connect(endpoint);
    const timer = setTimeout(() => {
      socket.destroy();
      resolvePromise(0);
    }, 600);
    let buf = '';
    socket.once('connect', () => {
      socket.write(JSON.stringify({ id: 'ping', method: 'local.ping' }) + '\n');
    });
    socket.on('data', chunk => {
      buf += chunk.toString('utf8');
      const nl = buf.indexOf('\n');
      if (nl !== -1) {
        clearTimeout(timer);
        try {
          const parsed = JSON.parse(buf.slice(0, nl));
          resolvePromise(Number(parsed?.result?.active_tasks ?? 0));
        } catch {
          resolvePromise(0);
        }
        socket.end();
      }
    });
    socket.on('error', () => {
      clearTimeout(timer);
      resolvePromise(0);
    });
  });
}

async function readLogTail(configPath: string, query?: string, maxLines = 200): Promise<string[]> {
  const logPath = join(dirname(configPath), 'gateway.log');
  let raw = '';
  try {
    raw = await readFile(logPath, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
    throw error;
  }
  let lines = raw.split(/\r?\n/).filter(Boolean);
  if (query && query.trim()) {
    const needle = query.trim().toLowerCase();
    lines = lines.filter(line => line.toLowerCase().includes(needle));
  }
  return lines.slice(-maxLines);
}

async function disableStandaloneWindowsTaskIfPresent(configPath: string): Promise<void> {
  if (process.platform !== 'win32' || process.env.NANO_TEST_AUTOSTART_DIR) return;
  try {
    await windowsHost('retire-standalone', configPath, '0', '');
  } catch {
    // Best-effort cleanup when taking over a feat-781 lightweight node.
  }
}

/** Inspect local node status, configuration, workers, and logs with strict `owner_id` isolation. */
export async function inspectLocalNode(input: {
  origin: string;
  ownerId?: string;
  configPath?: string;
  logQuery?: string;
  browserDeps?: BrowserPairingDeps;
}): Promise<DesktopLocalInspectResponse> {
  const configPath = connectionConfigPathForOrigin(input.origin, input.configPath);
  if (!existsSync(configPath)) {
    return { ownership: 'unbound', node_name: hostname() };
  }
  const config = await NodeConfiguration.read(configPath);
  const value = config.value;
  const environment = value.gateway?.environment;
  const workerPath = process.platform === 'win32'
    ? Object.entries(environment ?? {}).findLast(([key]) => key.toUpperCase() === 'PATH')?.[1]
    : environment?.PATH;
  const nodeName = value.node.node_name ?? value.node.node_id ?? hostname();
  if (!value.node.user_id || !value.im_service.token) {
    const workers = await probeDesktopWorkers(workerPath);
    return {
      ownership: 'unbound',
      node_id: value.node.node_id,
      node_name: nodeName,
      workers,
    };
  }
  if (!input.ownerId || value.node.user_id !== input.ownerId) {
    return {
      ownership: 'foreign_owner',
      node_name: nodeName,
    };
  }

  const desktopManaged = existsSync(desktopActiveFilePath(configPath));
  const rawState = await gatewayState(configPath);
  const live = Boolean(rawState && (await processBirth(rawState.pid)) === rawState.process_start);
  const activeTasks = live ? await pingBridgeActiveTasks(configPath) : 0;
  const { proxy, userEnvironment } = extractDesktopProxySettings(value.gateway?.environment);
  const [workers, browser, logs] = await Promise.all([
    probeDesktopWorkers(workerPath),
    inspectDailyBrowserStatus(browserPairingFile(configPath, value.node), undefined, input.browserDeps),
    readLogTail(configPath, input.logQuery),
  ]);
  const ownership = !desktopManaged
    ? 'takeover_available'
    : live
      ? 'managed_online'
      : 'managed_stopped';

  return {
    ownership,
    node_id: value.node.node_id,
    node_name: nodeName,
    owner_id: value.node.user_id,
    desktop_managed: desktopManaged,
    running: live,
    ready: live ? Boolean(rawState?.ready) : false,
    connected: live ? Boolean(rawState?.connected) : false,
    active_tasks: activeTasks,
    ...(live && rawState ? { pid: rawState.pid, ...(rawState.runtime_pid ? { runtime_pid: rawState.runtime_pid } : {}) } : {}),
    version: rawState?.release?.version ?? 'source',
    autostart: value.gateway?.autostart !== false,
    worker_runtime: value.gateway?.worker_runtime ?? 'dsh',
    workers,
    browser,
    proxy,
    tool_approval_model: value.llm.tool_approval_model ?? null,
    registered_models: value.llm.providers.flatMap(provider =>
      provider.models.map(model => ({
        name: model.name,
        display_name: model.display_name ?? model.id ?? model.name,
      })),
    ),
    environment: userEnvironment,
    agents: value.agents.map(agent => ({
      agent_id: agent.agent_id,
      display_name: String(agent.title ?? agent.display_name ?? agent.agent_id),
      workspace_root: agent.workspace_root,
    })),
    logs,
  };
}

/** Bind a fresh computer, smoothly take over a same-owner node, or guard cross-owner device transfer. */
export async function connectLocalNode(input: {
  origin: string;
  ownerId: string;
  accessToken: string;
  confirmTransfer?: boolean;
  configPath?: string;
  activeMetadata?: { sha256?: string; version?: string; version_root?: string; ui_root?: string };
}): Promise<{ ok: true; node_id: string; node_name: string; ready: boolean; autostart: boolean; pid?: number }> {
  if (!input.ownerId || !input.accessToken) {
    throw new LocalAdminHttpError(401, 'unauthorized', 'Sign in before connecting this computer');
  }
  const targetPath = connectionConfigPathForOrigin(input.origin, input.configPath);
  const config = await bootstrapNode(input.origin, targetPath);
  const value = config.value;
  const sameOwnerBound = value.node.user_id === input.ownerId && Boolean(value.im_service.token);

  if (!sameOwnerBound && value.node.user_id && value.node.user_id !== input.ownerId && !input.confirmTransfer) {
    throw new LocalAdminHttpError(
      409,
      'transfer_confirmation_required',
      'This computer is already bound to another account. Explicit device transfer confirmation is required.',
      { node_name: value.node.node_name ?? value.node.node_id },
    );
  }

  // Stop any existing running instance under the shared lifecycle lock before takeover or re-binding.
  await manageGateway(config.path, value, 'stop');
  await disableStandaloneWindowsTaskIfPresent(config.path);

  if (!sameOwnerBound) {
    try {
      await bindDevice(config, {
        inAppAccessToken: input.accessToken,
        confirmTransfer: Boolean(input.confirmTransfer),
        signal: AbortSignal.timeout(45_000),
        confirm: async () => Boolean(input.confirmTransfer),
        open: () => {},
        report: () => {},
      });
    } catch (error) {
      if ((error as { code?: string }).code === 'transfer_confirmation_required') {
        throw new LocalAdminHttpError(
          409,
          'transfer_confirmation_required',
          'Explicit device transfer confirmation is required',
          { node_name: value.node.node_name ?? value.node.node_id },
        );
      }
      throw error;
    }
  }

  const refreshed = await NodeConfiguration.read(config.path);
  await atomicPrivate(desktopActiveFilePath(config.path), {
    managed_by: 'crewden-desktop',
    sha256: input.activeMetadata?.sha256 ?? null,
    version: input.activeMetadata?.version ?? 'source',
    version_root: input.activeMetadata?.version_root ?? null,
    ui_root: input.activeMetadata?.ui_root ?? null,
    updated_at: new Date().toISOString(),
  });
  applyGatewayEnvironment(refreshed.value, refreshed.path);
  const started = await manageGateway(refreshed.path, refreshed.value, 'start');
  return {
    ok: true,
    node_id: refreshed.value.node.node_id,
    node_name: refreshed.value.node.node_name ?? refreshed.value.node.node_id,
    ready: Boolean(started.state?.ready),
    autostart: refreshed.value.gateway?.autostart !== false,
    ...(started.state?.pid ? { pid: started.state.pid } : {}),
  };
}

/** Control local node lifecycle (`start`, `stop`, `restart`, `autostart-on`, `autostart-off`) for its owner. */
export async function controlLocalNodeLifecycle(input: {
  origin: string;
  ownerId: string;
  action: 'start' | 'stop' | 'restart' | 'autostart-on' | 'autostart-off';
  preserveUserStopped?: boolean;
  configPath?: string;
}): Promise<{ ok: true; autostart: boolean; running: boolean; active_tasks: number }> {
  const configPath = connectionConfigPathForOrigin(input.origin, input.configPath);
  if (!existsSync(configPath)) {
    throw new LocalAdminHttpError(404, 'not_bound', 'This computer is not connected yet');
  }
  const config = await NodeConfiguration.read(configPath);
  if (!input.ownerId || config.value.node.user_id !== input.ownerId) {
    throw new LocalAdminHttpError(403, 'foreign_owner', 'This computer belongs to another account');
  }

  if (input.action === 'autostart-on' || input.action === 'autostart-off') {
    const enabled = input.action === 'autostart-on';
    const next: NodeConfigurationFile = {
      ...config.value,
      gateway: { ...(config.value.gateway ?? {}), autostart: enabled },
    };
    await config.persistNodeSettings(next);
    await manageGateway(config.path, next, input.action);
    const rawState = await gatewayState(config.path);
    const running = Boolean(rawState && (await processBirth(rawState.pid)) === rawState.process_start);
    const activeTasks = running ? await pingBridgeActiveTasks(config.path) : 0;
    return { ok: true, autostart: enabled, running, active_tasks: activeTasks };
  }

  const activeFile = desktopActiveFilePath(config.path);
  if (existsSync(activeFile) && !(input.action === 'stop' && input.preserveUserStopped)) {
    try {
      const prevActive = JSON.parse(await readFile(activeFile, 'utf8')) as Record<string, unknown>;
      await atomicPrivate(activeFile, {
        ...prevActive,
        user_stopped: input.action === 'stop',
        updated_at: new Date().toISOString(),
      });
    } catch {
      // Best-effort desired-state update.
    }
  }

  if (input.action !== 'stop') {
    config.validateNodeSettings();
    for (const agent of config.value.agents) config.runtime(agent);
  }
  applyGatewayEnvironment(config.value);
  await manageGateway(config.path, config.value, input.action);
  const rawState = await gatewayState(config.path);
  const running = Boolean(rawState && (await processBirth(rawState.pid)) === rawState.process_start);
  const activeTasks = running ? await pingBridgeActiveTasks(config.path) : 0;
  return {
    ok: true,
    autostart: config.value.gateway?.autostart !== false,
    running,
    active_tasks: activeTasks,
  };
}

function classifyConfigValidationCode(message: string): string {
  if (message.includes('socks://')) return 'invalid_proxy_scheme';
  if (message.includes('Proxy URL')) return 'invalid_proxy_url';
  if (message.includes('tool_approval_model')) return 'unregistered_approval_model';
  if (message.includes('worker_runtime')) return 'invalid_worker_runtime';
  if (message.includes('environment variable') || message.includes('NO_PROXY') || message.includes('managed automatically')) {
    return 'invalid_env_var';
  }
  return 'invalid_config';
}

/** Atomically validate, persist, and apply local node configuration with automatic rollback on failed restart. */
export async function updateLocalNodeConfig(input: {
  origin: string;
  ownerId: string;
  update: DesktopLocalConfigInput;
  configPath?: string;
}): Promise<{ ok: true; restarted: boolean; running: boolean }> {
  const configPath = connectionConfigPathForOrigin(input.origin, input.configPath);
  if (!existsSync(configPath)) {
    throw new LocalAdminHttpError(404, 'not_bound', 'This computer is not connected yet');
  }
  const originalRaw = await readFile(configPath, 'utf8');
  const config = await NodeConfiguration.read(configPath);
  if (!input.ownerId || config.value.node.user_id !== input.ownerId) {
    throw new LocalAdminHttpError(403, 'foreign_owner', 'This computer belongs to another account');
  }

  let mergedEnvironment: Record<string, string>;
  try {
    mergedEnvironment = mergeDesktopEnvironment(
      config.value.gateway?.environment,
      input.update.proxy,
      input.update.environment,
    );
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    throw new LocalAdminHttpError(422, classifyConfigValidationCode(msg), msg);
  }

  const nextLlm = { ...config.value.llm };
  if (input.update.tool_approval_model) {
    nextLlm.tool_approval_model = input.update.tool_approval_model;
  } else {
    delete nextLlm.tool_approval_model;
  }

  const nextValue: NodeConfigurationFile = {
    ...config.value,
    llm: nextLlm,
    gateway: {
      ...(config.value.gateway ?? {}),
      worker_runtime: input.update.worker_runtime,
      environment: mergedEnvironment,
    },
  };

  try {
    config.validateNodeSettings(nextValue);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    throw new LocalAdminHttpError(422, classifyConfigValidationCode(msg), msg);
  }

  const beforeState = await gatewayState(config.path);
  const wasRunning = Boolean(beforeState && (await processBirth(beforeState.pid)) === beforeState.process_start);
  if (wasRunning && !input.update.confirm_restart) {
    const activeTasks = await pingBridgeActiveTasks(config.path);
    if (activeTasks > 0) {
      throw new LocalAdminHttpError(
        409,
        'active_tasks_running',
        `There are ${activeTasks} active task(s) running on this computer; confirm restart before applying`,
        { active_tasks: activeTasks },
      );
    }
  }

  try {
    await config.persistNodeSettings(nextValue);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    throw new LocalAdminHttpError(422, classifyConfigValidationCode(msg), msg);
  }

  if (!wasRunning) {
    return { ok: true, restarted: false, running: false };
  }

  try {
    applyGatewayEnvironment(nextValue);
    await manageGateway(config.path, nextValue, 'restart');
    return { ok: true, restarted: true, running: true };
  } catch (restartError) {
    // Atomically restore the previous working configuration and recover the prior running state.
    await atomicPrivate(config.path, originalRaw);
    try {
      const restored = await NodeConfiguration.read(config.path);
      applyGatewayEnvironment(restored.value);
      await manageGateway(restored.path, restored.value, 'start').catch(() =>
        manageGateway(restored.path, restored.value, 'restart'),
      );
    } catch {
      // Preserve rollback error surface below.
    }
    throw new LocalAdminHttpError(
      422,
      'restart_rolled_back',
      `Restart failed and configuration was rolled back: ${restartError instanceof Error ? restartError.message : String(restartError)}`,
      { rolled_back: true },
    );
  }
}

function isWithinWorkspace(target: string, root: string): boolean {
  return isPathWithinRoot(target, root);
}

/** Validate and canonicalize a local Agent workspace file/directory target for Finder/Explorer reveal or open. */
export async function resolveLocalWorkspaceTarget(input: {
  origin: string;
  ownerId: string;
  agentId: string;
  targetPath: string;
  mode: 'open' | 'reveal';
  configPath?: string;
}): Promise<{ ok: true; resolved_path: string; is_directory: boolean }> {
  const configPath = connectionConfigPathForOrigin(input.origin, input.configPath);
  if (!existsSync(configPath)) {
    throw new LocalAdminHttpError(404, 'not_bound', 'This computer is not connected yet');
  }
  const config = await NodeConfiguration.read(configPath);
  if (!input.ownerId || config.value.node.user_id !== input.ownerId) {
    throw new LocalAdminHttpError(403, 'foreign_owner', 'This computer belongs to another account');
  }
  const agent = config.value.agents.find(item => item.agent_id === input.agentId);
  if (!agent) {
    throw new LocalAdminHttpError(404, 'agent_not_local', 'Agent does not belong to this computer');
  }
  const rawTarget = input.targetPath.startsWith('file://')
    ? decodeURIComponent(new URL(input.targetPath).pathname).replace(/^\/([A-Za-z]:[\\/])/, '$1')
    : input.targetPath;
  const workspaceRoot = await realpath(agent.workspace_root).catch(() => null);
  if (!workspaceRoot) {
    throw new LocalAdminHttpError(404, 'workspace_missing', 'Local workspace directory does not exist');
  }
  const candidate = isAbsolute(rawTarget) ? resolve(rawTarget) : resolve(workspaceRoot, rawTarget);
  if (!isWithinWorkspace(candidate, workspaceRoot)) {
    throw new LocalAdminHttpError(403, 'outside_workspace', 'Target path is outside the Agent workspace');
  }
  const resolvedTarget = await realpath(candidate).catch(() => null);
  if (!resolvedTarget) {
    throw new LocalAdminHttpError(404, 'path_not_found', 'Target file no longer exists on this computer');
  }
  if (!isWithinWorkspace(resolvedTarget, workspaceRoot)) {
    throw new LocalAdminHttpError(403, 'outside_workspace', 'Target path is outside the Agent workspace');
  }
  const stat = await lstat(resolvedTarget);
  const isDirectory = stat.isDirectory();
  if (input.mode === 'open' && !isDirectory && isBlockedDesktopOpenPath(resolvedTarget)) {
    throw new LocalAdminHttpError(
      403,
      'executable_open_blocked',
      'Executable scripts and application bundles can only be revealed in Finder/Explorer, not executed directly',
    );
  }
  return { ok: true, resolved_path: resolvedTarget, is_directory: isDirectory };
}

/** Inspect, open guided setup pages, pair, or disconnect the owner's local daily Chrome extension. */
export async function manageLocalNodeBrowser(input: {
  origin: string;
  ownerId: string;
  actionInput: DesktopBrowserActionInput;
  configPath?: string;
  deps?: BrowserPairingDeps;
}): Promise<DesktopBrowserActionResponse> {
  const configPath = connectionConfigPathForOrigin(input.origin, input.configPath);
  if (!existsSync(configPath)) {
    throw new LocalAdminHttpError(404, 'not_bound', 'This computer is not connected yet');
  }
  const config = await NodeConfiguration.read(configPath);
  if (!input.ownerId || config.value.node.user_id !== input.ownerId) {
    throw new LocalAdminHttpError(403, 'foreign_owner', 'This computer belongs to another account');
  }
  const pairingFile = browserPairingFile(config.path, config.value.node);
  try {
    return await handleNodeBrowserRequest(pairingFile, input.actionInput, input.deps);
  } catch (err) {
    if (err instanceof BrowserPairingRequestError) {
      throw new LocalAdminHttpError(err.status, err.code, err.message);
    }
    throw err;
  }
}
