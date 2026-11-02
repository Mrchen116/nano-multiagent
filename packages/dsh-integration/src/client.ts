/** Product-facing lifecycle for one owner node's official DSH process. */
import { randomUUID } from 'node:crypto';
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { mkdir, symlink, writeFile, readlink, unlink, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { RuntimeStopHistory } from '@nano/product-contracts';
import { RpcPeer } from './rpc.js';
import {load as loadYaml} from 'js-yaml';
import {ConfigurationInspector, type ConfigurationInspection} from './configuration-inspector.js';
export {ConfigurationInspector, InspectionError, type ConfigurationInspection} from './configuration-inspector.js';

const require = createRequire(import.meta.url);
const integrationRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/** Prepare a standard profile whose bundle resolution uses this locked install. */
export async function prepareProfile(home: string, providerPatch: unknown[] = []): Promise<void> {
  const profile = join(home, 'profiles', 'nano');
  await mkdir(join(profile, 'node_modules', '@nano'), { recursive: true });
  await link(integrationRoot, join(profile, 'node_modules', '@nano', 'dsh-integration'));
  await mkdir(join(profile, 'node_modules', '@deepseek-ai'), { recursive: true });
  await link(dirname(require.resolve('@deepseek-ai/dsh-base/package.json')), join(profile, 'node_modules', '@deepseek-ai', 'dsh-base'));
  await writeFile(join(profile, 'package.json'), JSON.stringify({
    name: 'nano-dsh-profile', private: true, type: 'module',
    dsh: { profile: { bundles: ['@deepseek-ai/dsh-base', '@nano/dsh-integration'] } },
  }, null, 2));
  // JSON is a YAML subset, so runtime configuration needs no custom serializer.
  await writeFile(join(profile, 'cordis.patch.yml'), JSON.stringify([{id: 'subagent', config: {maxDepth: 2}}, {id: 'web', config: {searchProvider: process.env.DSH_WEB_SEARCH_PROVIDER ?? (process.env.SEARXNG_URL ? 'searxng' : 'duckduckgo')}}, ...providerPatch], null, 2));
}

async function link(target: string, path: string) {
  try { await symlink(target, path, 'dir'); return; }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error; }
  // DSH_HOME survives deployments; its bundles must use this locked install.
  // readlink rejects ordinary files/directories without deleting owner content.
  const existing = await readlink(path);
  if (resolve(dirname(path), existing) === resolve(target)) return;
  await unlink(path);
  await symlink(target, path, 'dir');
}

/** Process exit is requested only after the runtime has drained durable owners. */
export class RuntimeClient {
  readonly processInstanceId = randomUUID();
  readonly process: ChildProcessWithoutNullStreams;
  readonly rpc: RpcPeer;
  readonly exited: Promise<{ code: number | null; signal: NodeJS.Signals | null }>;

  private readonly inspector?: ConfigurationInspector;
  private readonly ownsInspector: boolean;
  constructor(options: { home: string; cwd: string; env?: NodeJS.ProcessEnv; onLog?: (text: string) => void;
    inspector?: ConfigurationInspector; inspectionWorker?: {id:string;deadlineAt:number;requestId?:string} }) {
    this.ownsInspector = !options.inspector && !options.inspectionWorker;
    this.inspector = options.inspectionWorker ? undefined : options.inspector ?? new ConfigurationInspector({root:join(options.home,'.configuration-inspections'),env:options.env,onLog:options.onLog});
    const cli = require.resolve('@deepseek-ai/dsh/package.json');
    this.process = spawn(process.execPath, [join(dirname(cli), 'lib/bin.js'), '--profile', 'nano', ...(options.inspectionWorker ? [`--nano-inspection-id=${options.inspectionWorker.id}`] : [])], {
      cwd: options.cwd, stdio: ['pipe', 'pipe', 'pipe'], detached: process.platform !== 'win32',
      env: { ...process.env, ...options.env, DSH_HOME: options.home, DSH_TELEMETRY_DISABLED: '1', ...(options.inspectionWorker ? {NANO_CONFIGURATION_INSPECTION_ID:options.inspectionWorker.id, NANO_CONFIGURATION_INSPECTION_DEADLINE:String(options.inspectionWorker.deadlineAt), NANO_CONFIGURATION_INSPECTION_REQUEST:options.inspectionWorker.requestId} : {}) },
    });
    this.rpc = new RpcPeer(this.process.stdout, this.process.stdin);
    if (this.inspector) {
      this.rpc.handle('configuration.inspect', async value => {
        const input = value as ConfigurationInspection;
        // DSH settings can rewrite this trusted profile as YAML after initialization.
        const profilePatch = loadYaml(await readFile(join(options.home,'profiles','nano','cordis.patch.yml'),'utf8')) as unknown[];
        return this.inspector!.inspect({...input,profilePatch});
      });
      this.rpc.onNotification(method => {if (this.ownsInspector && method === 'configuration.catalog.changed') this.inspector!.invalidate();});
    }
    this.process.stderr.setEncoding('utf8');
    this.process.stderr.on('data', chunk => options.onLog?.(String(chunk)));
    this.exited = new Promise((resolveExit, reject) => {
      this.process.once('error', reject);
      this.process.once('exit', (code, signal) => { this.rpc.close(); if (this.ownsInspector) void this.inspector?.close(); resolveExit({ code, signal }); });
    });
  }

  /** Drain the runtime before asking the official launcher to dispose its root. */
  async shutdown(): Promise<void> {
    if (this.ownsInspector) await this.inspector?.close();
    await this.rpc.request('shutdown', {});
    this.process.kill('SIGTERM');
    await this.exited;
  }
}

interface SupervisorOptions {
  home: string;
  cwd: string;
  env?: NodeJS.ProcessEnv;
  onLog?: (text: string) => void;
  initialize: (rpc: RpcPeer) => Promise<void>;
  onReady: () => Promise<void>;
  onUnavailable?: () => Promise<void>;
  onError: (error: unknown) => void;
  stopTimeoutMs?: number;
  inspector?: ConfigurationInspector;


}

/** Restarts the execution process while the node retains inbound and delivery facts. */
export class RuntimeSupervisor {
  private client?: RuntimeClient;
  private ready = false;
  private stopping = false;
  private restarts = 0;
  private starting?: Promise<void>;
  private recovery?: Promise<void>;
  private timer?: ReturnType<typeof setTimeout>;
  private wakeTimer?: () => void;
  private readonly handlers = new Map<string, (params: unknown) => unknown | Promise<unknown>>();
  private readonly listeners = new Set<(method: string, params: unknown) => void>();
  constructor(private readonly options: SupervisorOptions) {}
  get process() { return this.client?.process; }
  get available() { return this.ready; }
  get processInstanceId() { return this.client?.processInstanceId; }

  /** Calls are never replayed: product owners reconcile stable operation identities. */
  request(method: string, params: unknown): Promise<unknown> {
    if (!this.ready || !this.client) return Promise.reject(new Error('DSH runtime unavailable'));
    return this.client.rpc.request(method, params);
  }
  onNotification(listener: (method: string, params: unknown) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }
  handle(method: string, handler: (params: unknown) => unknown | Promise<unknown>): void {
    this.handlers.set(method, handler);
    if (this.client) this.installHandler(this.client, method, handler);
  }
  private installHandler(client: RuntimeClient, method: string, handler: (params: unknown) => unknown | Promise<unknown>): void {
    client.rpc.handle(method, params => {
      if (this.stopping || this.client !== client) throw new Error('Agent is disabled or runtime instance is stale');
      return handler(params);
    });
  }
  async start(): Promise<void> {
    if (this.stopping) throw new Error('Agent is disabled');
    if (this.ready) return;
    if (!this.starting) {
      const starting = this.launch().finally(() => { if (this.starting === starting) this.starting = undefined; });
      this.starting = starting;
    }
    await this.starting;
  }
  private async launch(): Promise<void> {
    if (this.stopping) throw new Error('Agent is disabled');
    const client = new RuntimeClient(this.options);
    this.client = client;
    for (const [method, handler] of this.handlers) this.installHandler(client, method, handler);
    client.rpc.onNotification((method, params) => { if (this.client !== client || this.stopping) return; for (const listener of this.listeners) listener(method, params); });
    try {
      await this.options.initialize(client.rpc);
      if (this.stopping || this.client !== client) return;
      this.ready = true;
      await this.options.onReady();
    } catch (error) {
      if (this.stopping || this.client !== client) return;
      this.ready = false;
      await this.options.onUnavailable?.();
      client.process.kill('SIGTERM');
      await client.exited;
      throw error;
    }
    void client.exited.then(async () => {
      if (this.stopping || this.client !== client) return;
      this.ready = false;
      await this.options.onUnavailable?.();
      if (this.stopping || this.client !== client) return;
      this.options.onError(new Error('DSH runtime exited; recovering persisted sessions'));
      this.recovery = this.recover();
    }).catch(this.options.onError);
  }
  private async recover(): Promise<void> {
    // Three automatic attempts per node lifetime; repeated crashes remain visibly unavailable.
    while (!this.stopping && this.restarts < 3) {
      const delay = [250, 1000, 4000][this.restarts++]!;
      await new Promise<void>(resolve => { this.wakeTimer = resolve; this.timer = setTimeout(resolve, delay); });
      this.timer = undefined;
      this.wakeTimer = undefined;
      if (this.stopping) return;
      try { await this.launch(); return; } catch (error) { this.options.onError(error); }
    }
    if (!this.stopping) this.options.onError(new Error('DSH restart limit reached; node requires restart'));
  }
  /** Stop one Agent through DSH without changing the shared host lifecycle. */
  async disableAgent(agentId: string, revision: number, cursors: Record<string, number> = {}): Promise<{confirmed: boolean; processInstanceId?: string; errorDetail?: string; history?: RuntimeStopHistory[]}> {
    const processInstanceId = this.processInstanceId;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([
        this.request('agent.disable', {agentId, revision, cursors}).then(result => ({...result as {confirmed: boolean; history?: RuntimeStopHistory[]}, processInstanceId})),
        new Promise<{confirmed: false; processInstanceId?: string; errorDetail: string}>(resolve => {
          timer = setTimeout(() => resolve({confirmed: false, processInstanceId, errorDetail: 'Managed cleanup did not finish within the stop deadline.'}), this.options.stopTimeoutMs ?? 5000);
        }),
      ]);
    } catch (error) {
      this.options.onError(error);
      return {confirmed: false, processInstanceId, errorDetail: `Managed cleanup failed: ${String(error instanceof Error ? error.message : error).split('\n')[0]!.slice(0,500)}`};
    } finally { if (timer) clearTimeout(timer); }
  }
  async shutdown(): Promise<void> {
    this.stopping = true;
    this.ready = false;
    await this.options.onUnavailable?.();
    if (this.timer) clearTimeout(this.timer);
    this.wakeTimer?.();
    await this.recovery;
    if (this.client && this.client.process.exitCode === null && this.client.process.signalCode === null) await this.client.shutdown();
  }
}
