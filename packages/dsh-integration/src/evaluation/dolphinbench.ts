import { typedRuntimeRequest } from '@nano/product-contracts/runtime-rpc';
import { appendFileSync, existsSync } from 'node:fs';
import { randomUUID, createHash } from 'node:crypto';
import { Socket } from 'node:net';
import { mkdir, mkdtemp, readFile, writeFile, cp, lstat, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, isAbsolute, join, relative } from 'node:path';
import type { EvaluationLimits, EvaluationQuestion, RuntimePort, AgentConfiguration as ProductConfiguration } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from '../client.js';
import { RpcPeer } from '../rpc.js';
import type { AgentConfiguration, SessionBinding } from '../index.js';
import type { NanoEvaluationProduct } from '../evaluation.js';
import type { AppServerSpec } from './dolphinbench-runtime.js';

export type DolphinBenchArm = 'product' | 'search-only' | 'memory-only';

export interface DolphinBenchIdentity {
  nodeId: string;
  agentId: string;
  ownerId: string;
  bindingId: string;
  conversationId: string;
  rootSessionId: string;
}

export interface DolphinBenchHostOptions {
  provider: string;
  model: string;
  reasoningEffort?: string;
  providerPatch: unknown[];
  builtinSkillsRoot: string;
  timeZone: string;
  mcpToolNames?: string[];
  saveRawRequests?: boolean;
  dreamMinIntervalDays?: number;
  knowledge?: AgentConfiguration['knowledge'];
  environment?: NodeJS.ProcessEnv;
  createProduct(options: {
    configuration: ProductConfiguration;
    binding: SessionBinding;
    runtime: RuntimePort;
    directory: string;
    nodeId: string;
    startTime: number;
    chatSnapshot?: string;
    deliver(text: string): Promise<void>;
  }): NanoEvaluationProduct;
}

interface ActiveRuntime {
  client: RuntimeClient;
  peer: RpcPeer;
  socket: Socket;
  socketDir: string;
  dir: string;
  workspace: string;
  identity: DolphinBenchIdentity;
  product: NanoEvaluationProduct;
  deliveries: string[];
  stopping?: Promise<void>;
}

interface SealedCheckpoint {
  version: 1;
  persona: string;
  workspace: string;
  chatSnapshot: string;
  identity: DolphinBenchIdentity;
  memoryDigest: string;
}

async function copyMemoryTree(sourceWorkspace: string, targetWorkspace: string) {
  const source = join(sourceWorkspace, '.nanoassistant/memory');
  const check = async (path: string): Promise<void> => {
    const info = await lstat(path);
    if (info.isSymbolicLink()) throw new Error('Prepared memory contains a symlink');
    if (info.isDirectory()) {
      for (const entry of await readdir(path)) if (entry !== '.git') await check(join(path, entry));
    }
  };
  await check(source);
  await mkdir(join(targetWorkspace, '.nanoassistant/maintenance'), { recursive: true });
  await cp(source, join(targetWorkspace, '.nanoassistant/memory'), { recursive: true, filter: p => !p.split('/').includes('.git') });
  const docsMeta = join(sourceWorkspace, '.nanoassistant/maintenance/documents.json');
  if (existsSync(docsMeta)) {
    await cp(docsMeta, join(targetWorkspace, '.nanoassistant/maintenance/documents.json'));
  }
}

async function hashDirectory(root: string): Promise<string> {
  const rows: Array<[string, string]> = [];
  const walk = async (dir: string, prefix: string) => {
    for (const item of (await readdir(dir, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name))) {
      if (item.name === '.git') continue;
      const rel = prefix + item.name;
      const full = join(dir, item.name);
      if (item.isDirectory()) await walk(full, rel + '/');
      else if (item.isFile()) rows.push([rel, createHash('sha256').update(await readFile(full)).digest('hex')]);
    }
  };
  if (existsSync(root)) await walk(root, '');
  return createHash('sha256').update(JSON.stringify(rows)).digest('hex');
}

/** Persistent ingestion & isolated cold-test driver for DolphinBench on Nano PA. */
export class NanoDolphinBenchController {
  private ingestion?: ActiveRuntime;

  constructor(private readonly options: DolphinBenchHostOptions) {}

  /** Open or resume a persistent persona ingestion workspace. */
  async openIngestion(stateDir: string, startTimeMs: number, limits: EvaluationLimits): Promise<DolphinBenchIdentity> {
    if (this.ingestion) return this.ingestion.identity;
    await mkdir(stateDir, { recursive: true });
    const idPath = join(stateDir, 'identity.json');
    let identity: DolphinBenchIdentity;
    if (existsSync(idPath)) {
      identity = JSON.parse(await readFile(idPath, 'utf8')) as DolphinBenchIdentity;
    } else {
      const bindingId = randomUUID();
      identity = {
        nodeId: randomUUID(),
        agentId: `pa_${bindingId.replaceAll('-', '').slice(0, 12)}`,
        ownerId: randomUUID(),
        bindingId,
        conversationId: `c_${randomUUID().replaceAll('-', '').slice(0, 12)}`,
        rootSessionId: randomUUID(),
      };
      await writeFile(idPath, JSON.stringify(identity, null, 2));
    }
    const savedChat = join(stateDir, 'chat-checkpoint.sqlite');
    const run = await this.launch({
      dir: stateDir,
      stage: 'ingestion',
      allowConversationSearch: true,
      identity,
      startTimeMs,
      limits,
      chatSnapshot: existsSync(savedChat) ? savedChat : undefined,
      reuseDirs: true,
    });
    await run.peer.request('initRoot', { timestamp: startTimeMs });
    await run.client.rpc.request('knowledge.sources.sync', {
      agentId: identity.agentId,
      snapshot: { revision: '1', allowed: [identity.conversationId], excluded: [] },
    });
    this.ingestion = run;
    return identity;
  }

  /** Process one chronological DolphinBench user message inside the persistent ingestion runtime. */
  async ingestSession(input: {
    sessionId: string;
    windowIndex: number;
    date: string;
    timestampMs: number;
    datedMessage: string;
    apps: AppServerSpec;
    limits: EvaluationLimits;
  }) {
    const run = this.ingestion;
    if (!run) throw new Error('Ingestion runtime is not open');
    const started = Date.now();
    const clockRes = await run.peer.request('advanceClock', { toMs: input.timestampMs }) as {
      runs: unknown[]; backlog: unknown;
    };
    let rolloverRes: unknown = { rolledOver: false };
    if (input.windowIndex > 0) {
      rolloverRes = await run.peer.request('rolloverWindow', {
        windowIndex: input.windowIndex,
        timestamp: input.timestampMs,
      });
    }
    const mounted = await run.peer.request('mountApps', input.apps) as { tools: string[] };
    run.deliveries.length = 0;
    try {
      await run.peer.request('beginTurn', { maxModelCalls: input.limits.maxModelCalls, timestamp: input.timestampMs });
      const wakeInputId = await run.product.submit({
        id: input.sessionId,
        text: input.datedMessage,
        date: input.date,
      } satisfies EvaluationQuestion);
      const idleRes = await run.peer.request('idle', {}) as {
        status: string;
        budgetExhausted: boolean;
        turnUsage: { modelCalls: number; inputTokens: number; outputTokens: number; cachedTokens: number; deniedTools: number };
        dreamUsage: { modelCalls: number; inputTokens: number; outputTokens: number; cachedTokens: number };
      };
      const terminal = await run.client.rpc.request('session.lookup', {
        sessionId: run.identity.rootSessionId,
        inputId: wakeInputId,
      }) as { terminal?: { kind: string } };
      // Persist crash-safe chat checkpoint after every completed session.
      const tmpChat = join(run.dir, 'chat-checkpoint.sqlite.tmp');
      await rm(tmpChat, { force: true });
      await run.product.snapshot(tmpChat);
      await cp(tmpChat, join(run.dir, 'chat-checkpoint.sqlite'), { force: true });
      await rm(tmpChat, { force: true });
      return {
        status: terminal.terminal?.kind === 'completed' ? 'completed' : 'failed',
        terminalKind: terminal.terminal?.kind ?? 'unknown',
        reply: run.deliveries.join('\n\n'),
        deliveries: [...run.deliveries],
        mountedTools: mounted.tools.length,
        dreamingRunsBeforeSession: clockRes.runs,
        rollover: rolloverRes,
        turnUsage: idleRes.turnUsage,
        cumulativeDreamUsage: idleRes.dreamUsage,
        elapsedMs: Date.now() - started,
      };
    } finally {
      await run.peer.request('unmountApps', {}).catch(() => {});
    }
  }

  /** Advance through the final nightly consolidation (if requested) and seal an immutable snapshot.
   *
   * Args:
   *   persona: DolphinBench persona slug (`morgan`, `alex`, or `riley`).
   *   sealedDir: Output directory receiving `prepared.json`, `prepared-chat.sqlite`, and `workspace/`.
   *   finalNightMs: Optional post-history `03:05` local timestamp to flush remaining unconsolidated turns.
   * Returns:
   *   Sealed checkpoint path, metadata with SHA-256 memory digest, and final Dreaming run records.
   */
  async freezeIngestion(persona: string, sealedDir: string, finalNightMs?: number): Promise<{ checkpointPath: string; checkpoint: SealedCheckpoint; finalDreamRuns: unknown[] }> {
    const run = this.ingestion;
    if (!run) throw new Error('Ingestion runtime is not open');
    let finalDreamRuns: unknown[] = [];
    if (finalNightMs !== undefined) {
      const clockRes = await run.peer.request('advanceClock', { toMs: finalNightMs, force: true }) as { runs: unknown[] };
      finalDreamRuns = clockRes.runs;
    }
    await mkdir(sealedDir, { recursive: true });
    const chatSnapshot = join(sealedDir, 'prepared-chat.sqlite');
    await rm(chatSnapshot, { force: true });
    await run.product.snapshot(chatSnapshot);
    const sealedWorkspace = join(sealedDir, 'workspace');
    await rm(sealedWorkspace, { recursive: true, force: true });
    await mkdir(sealedWorkspace, { recursive: true });
    await copyMemoryTree(run.workspace, sealedWorkspace);
    const memoryDigest = await hashDirectory(join(sealedWorkspace, '.nanoassistant/memory'));
    const checkpoint: SealedCheckpoint = {
      version: 1,
      persona,
      workspace: relative(sealedDir, sealedWorkspace) || 'workspace',
      chatSnapshot: relative(sealedDir, chatSnapshot) || 'prepared-chat.sqlite',
      identity: run.identity,
      memoryDigest,
    };
    const checkpointPath = join(sealedDir, 'prepared.json');
    await writeFile(checkpointPath, JSON.stringify(checkpoint, null, 2));
    await this.closeIngestion();
    return { checkpointPath, checkpoint, finalDreamRuns };
  }

  async closeIngestion(): Promise<void> {
    if (!this.ingestion) return;
    const active = this.ingestion;
    this.ingestion = undefined;
    await this.stopRuntime(active);
  }

  /** Run a single DolphinBench evaluation task in a fresh cold runtime under the chosen ablation arm. */
  async runTest(input: {
    checkpointPath: string;
    testDir: string;
    testId: string;
    arm: DolphinBenchArm;
    date: string;
    timestampMs: number;
    datedMessage: string;
    apps: AppServerSpec;
    limits: EvaluationLimits;
    keepRuntimeFiles?: boolean;
  }) {
    const rawCheckpoint = JSON.parse(await readFile(input.checkpointPath, 'utf8')) as SealedCheckpoint;
    const baseSealedDir = dirname(input.checkpointPath);
    const checkpoint: SealedCheckpoint = {
      ...rawCheckpoint,
      workspace: isAbsolute(rawCheckpoint.workspace) && existsSync(rawCheckpoint.workspace)
        ? rawCheckpoint.workspace
        : join(baseSealedDir, 'workspace'),
      chatSnapshot: isAbsolute(rawCheckpoint.chatSnapshot) && existsSync(rawCheckpoint.chatSnapshot)
        ? rawCheckpoint.chatSnapshot
        : join(baseSealedDir, 'prepared-chat.sqlite'),
    };
    const currentDigest = await hashDirectory(join(checkpoint.workspace, '.nanoassistant/memory'));
    if (currentDigest !== checkpoint.memoryDigest) {
      throw new Error(`Sealed memory digest mismatch for ${checkpoint.persona}`);
    }
    const localWorkDir = await mkdtemp(join(tmpdir(), `ndb-test-${input.testId}-`));
    const useMemory = input.arm === 'product' || input.arm === 'memory-only';
    const useSearch = input.arm === 'product' || input.arm === 'search-only';
    const started = Date.now();
    let run: ActiveRuntime | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let timedOut = false;
    try {
      run = await this.launch({
        dir: localWorkDir,
        stage: 'test',
        allowConversationSearch: useSearch,
        identity: checkpoint.identity,
        startTimeMs: input.timestampMs,
        limits: input.limits,
        chatSnapshot: useSearch ? checkpoint.chatSnapshot : undefined,
        preparedWorkspace: useMemory ? checkpoint.workspace : undefined,
        reuseDirs: false,
      });
      timer = setTimeout(() => {
        timedOut = true;
        if (run) void this.stopRuntime(run);
      }, input.limits.timeoutMs);
      await run.peer.request('initRoot', { timestamp: input.timestampMs });
      await run.client.rpc.request('knowledge.sources.sync', {
        agentId: checkpoint.identity.agentId,
        snapshot: { revision: '1', allowed: [checkpoint.identity.conversationId], excluded: [] },
      });
      const mounted = await run.peer.request('mountApps', input.apps) as { tools: string[] };
      await run.peer.request('beginTurn', { maxModelCalls: input.limits.maxModelCalls, timestamp: input.timestampMs });
      const wakeInputId = await run.product.submit({
        id: input.testId,
        text: input.datedMessage,
        date: input.date,
      });
      const idleRes = await run.peer.request('idle', {}) as {
        status: string;
        budgetExhausted: boolean;
        turnUsage: { modelCalls: number; inputTokens: number; outputTokens: number; cachedTokens: number; deniedTools: number };
      };
      const terminal = await run.client.rpc.request('session.lookup', {
        sessionId: run.identity.rootSessionId,
        inputId: wakeInputId,
      }) as { terminal?: { kind: string } };
      await run.peer.request('unmountApps', {}).catch(() => {});
      return {
        status: terminal.terminal?.kind === 'completed' ? 'completed' : 'failed',
        terminalKind: terminal.terminal?.kind ?? 'unknown',
        reply: run.deliveries.join('\n\n'),
        deliveries: [...run.deliveries],
        mountedTools: mounted.tools.length,
        usage: idleRes.turnUsage,
        elapsedMs: Date.now() - started,
      };
    } catch (error) {
      if (timedOut) {
        return {
          status: 'incomplete',
          terminalKind: 'timeout',
          reply: run ? run.deliveries.join('\n\n') : '',
          deliveries: run ? [...run.deliveries] : [],
          mountedTools: 0,
          usage: { modelCalls: 0, inputTokens: 0, outputTokens: 0, cachedTokens: 0, deniedTools: 0 },
          elapsedMs: Date.now() - started,
        };
      }
      throw error;
    } finally {
      if (timer) clearTimeout(timer);
      if (run) await this.stopRuntime(run);
      await rm(localWorkDir, { recursive: true, force: true }).catch(() => {});
    }
  }

  private async launch(params: {
    dir: string;
    stage: 'ingestion' | 'test';
    allowConversationSearch: boolean;
    identity: DolphinBenchIdentity;
    startTimeMs: number;
    limits: EvaluationLimits;
    chatSnapshot?: string;
    preparedWorkspace?: string;
    reuseDirs: boolean;
  }): Promise<ActiveRuntime> {
    const { dir, identity } = params;
    const home = join(dir, 'runtime');
    const workspace = join(dir, 'workspace');
    await mkdir(home, { recursive: true });
    await mkdir(workspace, { recursive: true });
    await mkdir(join(workspace, '.nanoassistant/memory'), { recursive: true });
    if (params.preparedWorkspace) {
      await copyMemoryTree(params.preparedWorkspace, workspace);
    }
    // Always recreate fresh runtime.json profile configuration pointing to the new control socket.
    await rm(join(home, 'runtime.json'), { force: true });
    const socketDir = await mkdtemp(join(tmpdir(), 'ndb-'));
    const socketPath = join(socketDir, 'control');
    await prepareProfile(home, [
      ...this.options.providerPatch,
      {
        insert: [{
          id: 'nano-dolphinbench-evaluation',
          name: '@nano/dsh-integration/evaluation/dolphinbench-runtime',
          config: {
            socket: socketPath,
            workspace,
            agentId: identity.agentId,
            ownerId: identity.ownerId,
            rootSessionId: identity.rootSessionId,
            conversationId: identity.conversationId,
            stage: params.stage,
            allowConversationSearch: params.allowConversationSearch,
            saveRawRequests: Boolean(this.options.saveRawRequests),
            dreamMinIntervalDays: this.options.dreamMinIntervalDays,
            audit: dir,
            limits: params.limits,
            startTime: params.startTimeMs,
            builtinSkillsRoot: this.options.builtinSkillsRoot,
          },
        }],
      },
    ]);
    const env: NodeJS.ProcessEnv = {
      ...process.env,
      ...this.options.environment,
      TZ: this.options.timeZone,
    };
    const client = new RuntimeClient({
      home,
      cwd: workspace,
      env,
      onLog: text => appendFileSync(join(dir, 'runtime.log'), text),
    });
    const binding: SessionBinding = {
      sessionId: identity.rootSessionId,
      agentId: identity.agentId,
      ownerId: identity.ownerId,
      cwd: workspace,
      revision: '1',
    };
    const deliveries: string[] = [];
    const configuration: ProductConfiguration = {
      agentId: identity.agentId,
      workspace,
      revision: '1',
      mode: 'global',
      workerRuntime: 'dsh',
      provider: this.options.provider,
      model: this.options.model,
      reasoningEffort: this.options.reasoningEffort,
      maxTokens: params.limits.maxOutputTokens,
      personal: {
        bindingId: identity.bindingId,
        ownerId: identity.ownerId,
        conversationId: identity.conversationId,
        epoch: 1,
      },
      features: {
        dreaming: params.stage === 'ingestion',
        skill_creation: false,
        task_graph: false,
        heartbeat: false,
        cron_scheduling: false,
      },
      skillRoots: [{ path: this.options.builtinSkillsRoot, source: 'builtin' }],
      skillSelection: { mode: 'explicit_allowlist', names: ['nano-memory'] },
      toolAllowlist: [
        'read', 'glob', 'grep', 'skill', 'inbox', 'send_message',
        ...(params.stage === 'ingestion' ? ['memory_maintenance'] : []),
        ...(this.options.mcpToolNames ?? []),
      ],
      knowledge: { ...this.options.knowledge, memoryMode: 'document' },
    };
    for (const suffix of ['', '-wal', '-shm']) {
      await rm(join(dir, `chat.sqlite${suffix}`), { force: true });
    }
    const product = this.options.createProduct({
      configuration,
      binding,
      runtime: {
        request: typedRuntimeRequest(client.rpc.request.bind(client.rpc)),
        onNotification: client.rpc.onNotification.bind(client.rpc),
      },
      directory: dir,
      nodeId: identity.nodeId,
      startTime: params.startTimeMs,
      chatSnapshot: params.chatSnapshot,
      deliver: async text => {
        deliveries.push(text);
        await writeFile(join(dir, 'deliveries.json'), JSON.stringify(deliveries));
      },
    });
    client.rpc.handle('product.call', value => product.call(value));
    client.rpc.handle('product.task_context.prepare', value => product.taskContext.prepare(value));
    client.rpc.handle('product.task_context.commit', value => product.taskContext.commit(value));
    let connectedSocket: Socket | undefined;
    let peer: RpcPeer | undefined;
    try {
      await client.rpc.request('initialize', { protocol: 1, agents: [configuration], bindings: [binding] });
      const deadline = Date.now() + 5000;
      for (;;) {
        try {
          connectedSocket = await new Promise<Socket>((resolveConnect, reject) => {
            const candidate = new Socket();
            candidate.once('error', err => { candidate.destroy(); reject(err); });
            candidate.connect(socketPath, () => { candidate.removeAllListeners('error'); resolveConnect(candidate); });
          });
          break;
        } catch (err) {
          if ((err as NodeJS.ErrnoException).code !== 'ENOENT' || Date.now() >= deadline) throw err;
          await new Promise(resolveWait => setTimeout(resolveWait, 25));
        }
      }
      peer = new RpcPeer(connectedSocket, connectedSocket);
      return { client, peer, socket: connectedSocket, socketDir, dir, workspace, identity, product, deliveries };
    } catch (error) {
      if (peer) { try { peer.close(); } catch { /* ignore */ } }
      if (connectedSocket) { try { connectedSocket.destroy(); } catch { /* ignore */ } }
      try { await product.close(); } catch { /* ignore */ }
      try { await client.shutdown(); } catch { /* ignore */ }
      await rm(socketDir, { recursive: true, force: true }).catch(() => {});
      throw error;
    }
  }

  private killProcess(run: ActiveRuntime) {
    const child = run.client.process;
    if (!child?.pid || child.exitCode !== null || child.signalCode !== null) return;
    try { process.kill(process.platform === 'win32' ? child.pid : -child.pid, 'SIGKILL'); }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error; }
  }

  private async stopRuntime(run: ActiveRuntime): Promise<void> {
    if (run.stopping) return run.stopping;
    run.stopping = (async () => {
      try { await run.product.close(); } catch { /* ignore */ }
      if (run.client.process.exitCode === null && run.client.process.signalCode === null) {
        const watchdog = setTimeout(() => this.killProcess(run), 5000);
        try { await run.client.shutdown(); }
        catch { this.killProcess(run); await run.client.exited.catch(() => {}); }
        finally { clearTimeout(watchdog); }
      }
      try { run.peer.close(); } catch { /* ignore */ }
      try { run.socket.destroy(); } catch { /* ignore */ }
      await rm(run.socketDir, { recursive: true, force: true }).catch(() => {});
    })();
    return run.stopping;
  }
}
