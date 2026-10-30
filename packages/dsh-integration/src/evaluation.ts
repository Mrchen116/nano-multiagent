import { appendFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { Socket } from 'node:net';
import { mkdir, mkdtemp, readFile, writeFile, cp, lstat, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import type { EvaluationHistory, EvaluationQuestion, EvaluationLimits, EvaluationUsage, MemoryCandidate, PreparationResult, EvaluationAnswer, RuntimePort, AgentConfiguration as ProductConfiguration } from '@nano/product-contracts';
import { prepareProfile, RuntimeClient } from './client.js';
import { RpcPeer } from './rpc.js';
import { contextTools } from './agent-context.js';
import { hash } from './evaluation/history.js';
import type { AgentConfiguration, SessionBinding } from './index.js';

export interface NanoEvaluationOptions {
  id: string;
  root: string;
  provider: string;
  model: string;
  /** Explicit provider profile, never discovered from production configuration. */
  providerPatch: unknown[];
  /** Packaged product guidance supplied by the composition root, never private owner skills. */
  builtinSkillsRoot: string;
  /** Product composition supplied by the runner, keeping PA dependencies outside the runtime package. */
  createProduct(options: { configuration: ProductConfiguration; binding: SessionBinding; runtime: RuntimePort; directory: string;
    deliver(text: string): Promise<void> }): NanoEvaluationProduct;
  knowledge?: AgentConfiguration['knowledge'];
  reasoningEffort?: string;
  allowModelCalls: boolean;
  /** Used by deterministic integration tests, not a CLI injection point. */
  environment?: NodeJS.ProcessEnv;
}
export interface NanoEvaluationProduct {
  /** Admit a question through the product and return its actual wake input ID. */
  submit(question: EvaluationQuestion): Promise<string>;
  call(value: unknown): Promise<unknown>;
  close(): Promise<void>;
}
interface Identity { agentId: string; ownerId: string; bindingId: string; conversationId: string; rootSessionId: string }
interface Audit { requests: string; deniedTools: number; importedSessions: number; importedMessages: number; usage: EvaluationUsage }
interface Running { client: RuntimeClient; peer: RpcPeer; socket: Socket; socketDir: string; dir: string; workspace: string; rootSessionId: string; binding: SessionBinding; product?: NanoEvaluationProduct; audit?: Audit; stopping?: Promise<void> }
interface Prepared { workspace: string; identity: Identity }

/** Exercise Nano's native memory services while keeping benchmark control data outside them. */
export class NanoMemoryCandidate implements MemoryCandidate {
  readonly id: string;
  private active?: Running;
  private stopped = false;
  private work?: Promise<unknown>;
  constructor(private readonly options: NanoEvaluationOptions) {
    this.id = options.id;
    if (!options.allowModelCalls) throw new Error('Nano evaluation requires explicit model-call permission');
    if (options.knowledge?.memoryMode === 'legacy') throw new Error('This candidate adapter supports document memory only');
  }

  /** Prepare full history and seal the current candidate's persistent representation. */
  prepare(history: EvaluationHistory, limits: EvaluationLimits): Promise<PreparationResult> {
    return this.track(() => this.prepareHistory(history, limits));
  }

  private async prepareHistory(history: EvaluationHistory, limits: EvaluationLimits): Promise<PreparationResult> {
    this.stopped = false;
    const started = Date.now();
    let run: Running | undefined;
    const bindingId = randomUUID();
    const identity: Identity = { agentId: `pa_${bindingId.replaceAll('-', '').slice(0, 12)}`, ownerId: randomUUID(), bindingId,
      conversationId: `c_${randomUUID().replaceAll('-', '').slice(0, 12)}`, rootSessionId: randomUUID() };
    const sources = [identity.conversationId];
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      timer = setTimeout(() => { this.stopped = true; this.kill(); }, limits.timeoutMs);
      run = await this.launch('prepare', identity, limits, history);
      await run.peer.request('initializeHistory', history);
      await run.client.rpc.request('knowledge.sources.sync', { agentId: identity.agentId, snapshot: { revision: '1', allowed: sources, excluded: [] } });
      const result = await run.peer.request('prepare', history) as { status: 'ready' | 'incomplete' | 'failed'; reason?: string; details: unknown };
      const audit = await run.peer.request('audit', {}) as Audit;
      const evidenceRef = join(run.dir, 'receipt.json');
      const receipt = { candidateId: this.id, historyDigest: hash(history), importedSessions: audit.importedSessions,
        importedMessages: audit.importedMessages, evidenceRef,
        usage: { ...audit.usage, elapsedMs: Date.now() - started } };
      await writeFile(evidenceRef, JSON.stringify({ ...receipt, ...audit, result }, null, 2));
      await this.stop(run);
      if (result.status !== 'ready') return { status: result.status, receipt, reason: result.reason ?? 'Memory preparation incomplete' };
      const workspace = join(run.dir, 'prepared');
      await copyMemory(run.workspace, workspace);
      const preparedRef = join(run.dir, 'prepared.json');
      await writeFile(preparedRef, JSON.stringify({ workspace, identity } satisfies Prepared));
      return { status: 'ready', preparedRef, receipt };
    } catch (error) {
      if (!run) return { status: this.stopped ? 'incomplete' : 'failed', reason: String(error) };
      const audit = await this.failedAudit(run, error);
      return { status: this.stopped ? 'incomplete' : 'failed', reason: String(error), receipt: { candidateId: this.id,
        historyDigest: hash(history), importedSessions: audit.importedSessions, importedMessages: audit.importedMessages, evidenceRef: audit.evidenceRef, usage: audit.usage } };
    } finally { if (timer) clearTimeout(timer); if (run) await this.stop(run); }
  }

  /** Restore the same PA relationship in an empty runtime, without its original active history. */
  answer(preparedRef: string, question: EvaluationQuestion, limits: EvaluationLimits): Promise<EvaluationAnswer> {
    return this.track(() => this.answerQuestion(preparedRef, question, limits));
  }

  private async answerQuestion(preparedRef: string, question: EvaluationQuestion, limits: EvaluationLimits): Promise<EvaluationAnswer> {
    this.stopped = false;
    let run: Running | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const prepared = JSON.parse(await readFile(preparedRef, 'utf8')) as Prepared;
      timer = setTimeout(() => { this.stopped = true; this.kill(); }, limits.timeoutMs);
      run = await this.launch('answer', prepared.identity, limits, undefined, prepared.workspace);
      // The cold process has no source-authority cache. Establish the connected chat before the root assembles its first context.
      await run.client.rpc.request('knowledge.sources.sync', { agentId: prepared.identity.agentId,
        snapshot: { revision: '1', allowed: [prepared.identity.conversationId], excluded: [] } });
      const inputId = await run.product!.submit(question);
      await run.peer.request('idle', {});
      const audit = await run.peer.request('audit', {}) as Audit;
      const evidenceRef = join(run.dir, 'answer.json');
      const deliveries = JSON.parse(await readFile(join(run.dir, 'deliveries.json'), 'utf8')) as string[];
      const terminal = await run.client.rpc.request('session.lookup', { sessionId: run.rootSessionId, inputId }) as { terminal?: { kind: string } };
      await writeFile(evidenceRef, JSON.stringify({ ...audit, terminal, deliveries, questionDate: question.date }, null, 2));
      if (terminal.terminal?.kind !== 'completed') return { status: 'failed', reason: 'Answer turn did not complete', evidenceRef, usage: audit.usage };
      if (!deliveries.length) return { status: 'failed', reason: 'Agent delivered no public answer', evidenceRef, usage: audit.usage };
      // Keep all delivered prose in order; never choose the best message using gold.
      return { status: 'completed', text: deliveries.join('\n\n'), evidenceRef, usage: audit.usage };
    } catch (error) {
      return { status: 'failed', reason: String(error), ...(run ? await this.failedAudit(run, error) : {}) };
    }
    finally { if (timer) clearTimeout(timer); if (run) await this.stop(run); }
  }

  /** Cancel owned work, retaining its audit directory. */
  async close(): Promise<void> {
    this.stopped = true; this.kill();
    await this.work;
    if (this.active) await this.stop(this.active);
  }

  private track<T>(operation: () => Promise<T>): Promise<T> {
    if (this.work) return Promise.reject(new Error('Evaluation candidate already has an active operation'));
    const work = operation().finally(() => { if (this.work === work) this.work = undefined; });
    this.work = work; return work;
  }

  private async failedAudit(run: Running, error: unknown) {
    const evidenceRef = join(run.dir, 'failure.json');
    let audit: Partial<Audit> = {};
    try { audit = JSON.parse(await readFile(join(run.dir, 'usage.json'), 'utf8')) as Audit; } catch { /* Startup can fail before the recorder mounts. */ }
    const usage = audit.usage ?? { modelCalls: 0, inputTokens: null, outputTokens: null, costUsd: null, elapsedMs: 0 };
    await writeFile(evidenceRef, JSON.stringify({ ...audit, reason: String(error) }, null, 2));
    return { evidenceRef, usage, importedSessions: audit.importedSessions ?? 0, importedMessages: audit.importedMessages ?? 0 };
  }

  private kill() {
    const child = this.active?.client.process;
    if (!child?.pid || child.exitCode !== null || child.signalCode !== null) return;
    try { process.kill(process.platform === 'win32' ? child.pid : -child.pid, 'SIGKILL'); }
    catch (error) { if ((error as NodeJS.ErrnoException).code !== 'ESRCH') throw error; }
  }
  private stop(run: Running): Promise<void> {
    return run.stopping ??= this.stopRuntime(run);
  }

  private async stopRuntime(run: Running) {
    await run.product?.close();
    if (run.client.process.exitCode === null && run.client.process.signalCode === null) {
      const watchdog = setTimeout(() => this.kill(), 5000);
      try { await run.client.shutdown(); } catch { this.kill(); await run.client.exited; }
      finally { clearTimeout(watchdog); }
    }
    run.peer.close(); run.socket.destroy(); await rm(run.socketDir, { recursive: true, force: true });
    if (this.active === run) this.active = undefined;
  }

  private async launch(stage: 'prepare' | 'answer', identity: Identity, limits: EvaluationLimits,
    history?: EvaluationHistory, prepared?: string): Promise<Running> {
    const { agentId, ownerId, bindingId, conversationId, rootSessionId } = identity;
    await mkdir(this.options.root, { recursive: true });
    const dir = await mkdtemp(join(resolve(this.options.root), `${stage}-`));
    const home = join(dir, 'runtime'), workspace = join(dir, 'workspace');
    await mkdir(home); await mkdir(workspace);
    if (prepared) await copyMemory(prepared, workspace);
    const socketDir = await mkdtemp(join(tmpdir(), 'nme-')), socketPath = join(socketDir, 'control');
    await prepareProfile(home, [...this.options.providerPatch, { insert: [{ id: 'nano-memory-evaluation',
      name: '@nano/dsh-integration/evaluation/runtime', config: { socket: socketPath, workspace, agentId, ownerId, rootSessionId, conversationId, stage, audit: dir, limits,
        builtinSkillsRoot: this.options.builtinSkillsRoot,
        startTime: history?.sessions[0]?.timestamp ?? 0 } }] }]);
    if (this.stopped) { await rm(socketDir, { recursive: true, force: true }); throw new Error('Evaluation cancelled before runtime start'); }
    const client = new RuntimeClient({ home, cwd: workspace, env: this.options.environment,
      onLog: text => appendFileSync(join(dir, 'runtime.log'), text) });
    const socket = new Socket();
    // Install ownership before any awaited runtime initialization, so deadlines can kill it.
    const binding = { sessionId: rootSessionId, agentId, ownerId, cwd: workspace, revision: '1' };
    const run: Running = { client, socket, peer: new RpcPeer(socket, socket), dir, socketDir, workspace, rootSessionId, binding };
    this.active = run;
    const deliveries: string[] = [];
    await writeFile(join(dir, 'deliveries.json'), '[]');
    client.rpc.handle('product.call', async value => {
      if (run.product) return run.product.call(value);
      const call = value as { method: string; args: Record<string, unknown> };
      if (call.method === 'memory.sources.refresh') {
        await client.rpc.request('knowledge.sources.sync', { agentId, snapshot: { revision: '1', allowed: [conversationId], excluded: [] } });
        return { refreshed: true };
      }
      throw new Error(`Evaluation product operation unavailable: ${call.method}`);
    });
    try {
      if (this.stopped) throw new Error('Evaluation cancelled');
      const configuration: ProductConfiguration = { agentId, workspace, revision: '1', mode: 'global', provider: this.options.provider,
        model: this.options.model, reasoningEffort: this.options.reasoningEffort, maxTokens: limits.maxOutputTokens,
        personal: { bindingId, ownerId, conversationId, epoch: 1 },
        features: { dreaming: stage === 'prepare', skill_creation: false, task_graph: false, heartbeat: false, cron_scheduling: false },
        skillRoots: [{ path: this.options.builtinSkillsRoot, source: 'builtin' }],
        skillSelection: { mode: 'explicit_allowlist', names: ['nano-memory', 'nano-interactive-ui'] },
        toolAllowlist: stage === 'prepare' ? ['read', 'write', 'edit', 'memory_maintenance', ...contextTools] : ['read', 'glob', 'grep', 'skill', 'inbox', 'send_message'],
        knowledge: { ...this.options.knowledge, memoryMode: 'document' } };
      if (stage === 'answer') run.product = this.options.createProduct({ configuration, binding, runtime: client.rpc, directory: dir,
        deliver: async text => { deliveries.push(text); await writeFile(join(dir, 'deliveries.json'), JSON.stringify(deliveries)); } });
      await client.rpc.request('initialize', { protocol: 1, agents: [configuration],
        bindings: [binding] });
      await new Promise<void>((resolveConnect, reject) => {
        socket.once('error', reject); socket.connect(socketPath, () => { socket.off('error', reject); resolveConnect(); });
      });
      return run;
    } catch (error) { await this.failedAudit(run, error); await this.stop(run); throw new Error(`${String(error)} (audit: ${dir})`); }
  }
}

async function copyMemory(sourceWorkspace: string, targetWorkspace: string) {
  const source = join(sourceWorkspace, '.nanoassistant/memory');
  // The answer file tools never receive symlinks back into the source runtime.
  const check = async (path: string): Promise<void> => {
    const info = await lstat(path); if (info.isSymbolicLink()) throw new Error('Prepared memory contains a symlink');
    if (info.isDirectory()) for (const name of await readdir(path)) if (name !== '.git') await check(join(path, name));
  };
  await check(source);
  await mkdir(join(targetWorkspace, '.nanoassistant/maintenance'), { recursive: true });
  await cp(source, join(targetWorkspace, '.nanoassistant/memory'), { recursive: true, filter: path => !path.split('/').includes('.git') });
  await cp(join(sourceWorkspace, '.nanoassistant/maintenance/documents.json'), join(targetWorkspace, '.nanoassistant/maintenance/documents.json'));
}
