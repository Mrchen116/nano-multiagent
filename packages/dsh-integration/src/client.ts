/** Product-facing lifecycle for one owner node's official DSH process. */
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { mkdir, symlink, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { RpcPeer } from './rpc.js';

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
  await writeFile(join(profile, 'cordis.patch.yml'), JSON.stringify(providerPatch, null, 2));
}

async function link(target: string, path: string) {
  try { await symlink(target, path, 'dir'); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error; }
}

/** Process exit is requested only after the runtime has drained durable owners. */
export class RuntimeClient {
  readonly process: ChildProcessWithoutNullStreams;
  readonly rpc: RpcPeer;
  readonly exited: Promise<{ code: number | null; signal: NodeJS.Signals | null }>;

  constructor(options: { home: string; cwd: string; env?: NodeJS.ProcessEnv; onLog?: (text: string) => void }) {
    const cli = require.resolve('@deepseek-ai/dsh/package.json');
    this.process = spawn(process.execPath, [join(dirname(cli), 'lib/bin.js'), '--profile', 'nano'], {
      cwd: options.cwd, stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, ...options.env, DSH_HOME: options.home, DSH_TELEMETRY_DISABLED: '1' },
    });
    this.rpc = new RpcPeer(this.process.stdout, this.process.stdin);
    this.process.stderr.setEncoding('utf8');
    this.process.stderr.on('data', chunk => options.onLog?.(String(chunk)));
    this.exited = new Promise((resolveExit, reject) => {
      this.process.once('error', reject);
      this.process.once('exit', (code, signal) => { this.rpc.close(); resolveExit({ code, signal }); });
    });
  }

  /** Drain the runtime before asking the official launcher to dispose its root. */
  async shutdown(): Promise<void> {
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
  onError: (error: unknown) => void;
}

/** Restarts the execution process while the node retains inbound and delivery facts. */
export class RuntimeSupervisor {
  private client?: RuntimeClient;
  private ready = false;
  private stopping = false;
  private restarts = 0;
  private recovery?: Promise<void>;
  private timer?: ReturnType<typeof setTimeout>;
  private wakeTimer?: () => void;
  private readonly listeners = new Set<(method: string, params: unknown) => void>();
  constructor(private readonly options: SupervisorOptions) {}
  get process() { return this.client?.process; }
  get available() { return this.ready; }

  /** Calls are never replayed: product owners reconcile stable operation identities. */
  request(method: string, params: unknown): Promise<unknown> {
    if (!this.ready || !this.client) return Promise.reject(new Error('DSH runtime unavailable'));
    return this.client.rpc.request(method, params);
  }
  onNotification(listener: (method: string, params: unknown) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }
  async start(): Promise<void> { await this.launch(); }
  private async launch(): Promise<void> {
    const client = new RuntimeClient(this.options);
    this.client = client;
    client.rpc.onNotification((method, params) => { for (const listener of this.listeners) listener(method, params); });
    try {
      await this.options.initialize(client.rpc);
      if (this.stopping) return;
      this.ready = true;
      await this.options.onReady();
    } catch (error) {
      this.ready = false;
      client.process.kill('SIGTERM');
      await client.exited;
      throw error;
    }
    void client.exited.then(() => {
      if (this.stopping || this.client !== client) return;
      this.ready = false;
      this.options.onError(new Error('DSH runtime exited; recovering persisted sessions'));
      this.recovery = this.recover();
    });
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
  async shutdown(): Promise<void> {
    this.stopping = true;
    this.ready = false;
    if (this.timer) clearTimeout(this.timer);
    this.wakeTimer?.();
    await this.recovery;
    if (this.client && this.client.process.exitCode === null && this.client.process.signalCode === null) await this.client.shutdown();
  }
}
